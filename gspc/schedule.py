import logging
import asyncio
import typing
import math
import time
import types
from collections import namedtuple
from gspc.hw.interface import Interface

_LOGGER = logging.getLogger(__name__)


Event = namedtuple("Event", ["time", "occurred"])


class Runnable:
    """A component of the sequence that is able to be run"""

    def __init__(self, interface: Interface, schedule: 'Execute', origin: float = -math.inf):
        """Create the runnable component."""
        self.interface = interface
        self.schedule = schedule
        self.origin = origin
        self.set_events: typing.Set[str] = set()
        self.clear_events: typing.Set[str] = set()

    async def execute(self) -> typing.Optional[bool]:
        """Execute the task.  Return true if the task should shift subsequent ones by its execution time."""
        pass


class Gate(Runnable):
    """A runnable that can be used to gate the schedule advance, waiting until a set of conditions are ready"""

    def __init__(self, interface: Interface, schedule: 'Execute', origin: float,
                 required_ready: typing.Optional[int] = None):
        Runnable.__init__(self, interface, schedule, origin)
        self._required_ready = required_ready
        self._futures_waiting: typing.List[asyncio.Future] = list()
        self._total_completed = None

    class _Gate:
        def __init__(self):
            self.future = asyncio.get_running_loop().create_future()

        def __call__(self, *args, **kwargs):
            if self.future is None:
                return
            self.future.set_result(True)
            self.future = None

    def add_gate(self):
        if self._total_completed is not None:
            raise RuntimeError("Cannot add gate once started")
        gate = self._Gate()
        self._futures_waiting.append(gate.future)
        return gate

    async def execute(self) -> bool:
        self._total_completed = 0

        if self._required_ready is None:
            await asyncio.wait(self._futures_waiting, return_when=asyncio.ALL_COMPLETED)
            self._futures_waiting.clear()
            return True

        while self._required_ready < self._total_completed:
            done, futures = await asyncio.wait(self._futures_waiting,
                                               return_when=asyncio.FIRST_COMPLETED)
            self._futures_waiting = futures
            self._total_completed += len(done)

        return True


class AbortPoint(Runnable):
    """A runnable that serves as a future abort point to allow for a deferred sequence abort"""

    def __init__(self, interface: Interface, schedule: 'Execute', origin=-math.inf):
        Runnable.__init__(self, interface, schedule, origin)
        self._aborted = False
        self._abort_message = None

    async def abort(self, message: typing.Optional[str] = None):
        """Schedule the abort"""
        self._aborted = True
        if message is not None:
            self._abort_message = message

    async def execute(self):
        if not self._aborted:
            return
        await self.schedule.abort(self._abort_message)


class Task:
    """The base for tasks that can be executed on a schedule."""

    def __init__(self, origin_advance: float = 0):
        self.origin_advance = origin_advance

    def schedule(self, interface: Interface, schedule: 'Execute', origin: float) -> typing.Sequence[Runnable]:
        """Return a list of runnable tasks for execution"""
        return list()


known_tasks = dict()


def register_task(name: str, task: Task):
    """Register a task that can be scheduled from a sequence set."""
    known_tasks[name] = task


class Execute:
    """The execution handler for a list of tasks"""

    def __init__(self, task_sequence: typing.Sequence[Task]):
        self._tasks = task_sequence
        self._background_tasks : typing.Set[asyncio.Task] = set()
        self._aborted = False
        self._paused = None
        self.abort_message = None
        self.events: typing.Dict[str, Event] = dict()

    async def before_run(self, running: Runnable):
        """Called before the current runnable is executed"""
        pass

    async def _execute_run(self, running: Runnable, completed_origin: float) -> typing.Optional[bool]:
        if not math.isfinite(running.origin):
            return await running.execute()

        delay = running.origin - completed_origin
        assert math.isfinite(delay)
        if delay > 0.0:
            await asyncio.sleep(delay)

        if self._paused is not None:
            _LOGGER.debug("Schedule processing paused")
            await self._paused
            self._paused = None
            _LOGGER.debug("Schedule processing resumed")

        return await running.execute()

    async def _abort_processing(self):
        for task in self._background_tasks:
            if task.done():
                continue
            try:
                task.cancel()
            except:
                pass
            try:
                await task
            except:
                pass
        self._background_tasks.clear()

        _LOGGER.debug("Schedule abort completed")

    async def _complete_processing(self):
        for task in self._background_tasks:
            try:
                await task
            except:
                pass
        self._background_tasks.clear()

        _LOGGER.debug("Schedule processing completed")

    async def execute(self, interface: Interface):
        """Execute the scheduled tasks."""
        run = list()
        origin = 0.0
        for task in self._tasks:
            add = task.schedule(interface, self, origin)
            run.extend(add)
            origin += task.origin_advance

        run.sort(key=lambda runnable: runnable.origin)

        self._aborted = False
        self.abort_message = None
        self.events.clear()
        completed_time = time.time()
        completed_origin = -math.inf
        for i in range(len(run)):
            to_run = run[i]

            # Assign future events
            stop_events = set()
            for j in range(i, len(run)):
                next_run = run[j]

                # If we don't yet have an origin, set it to this one
                if not math.isfinite(completed_origin):
                    completed_origin = next_run.origin

                expected_time = next_run.origin - completed_origin
                expected_time += completed_time
                if not math.isfinite(expected_time):
                    continue

                for event in next_run.clear_events:
                    stop_events.add(event)
                for event in next_run.set_events:
                    if event in stop_events:
                        continue
                    if event in self.events:
                        continue

                    self.events[event] = Event(expected_time, False)

            # Call the before run so that displays are updated
            await self.before_run(to_run)
            if self._aborted:
                await self._abort_processing()
                return False

            # Run it
            use_real_time = await self._execute_run(to_run, completed_origin)
            if self._aborted:
                _LOGGER.debug("Schedule abort completed")
                return False

            # Change the origin based on the completion time
            if use_real_time or not math.isfinite(completed_origin):
                completed_origin = to_run.origin
                completed_time = time.time()
            else:
                completed_time += to_run.origin - completed_origin
                completed_origin = to_run.origin

            # Completed now, so record events that were processed
            for event in to_run.clear_events:
                self.events.pop(event, None)
            for event in to_run.set_events:
                self.events[event] = Event(completed_time, True)

            # Purge any completed background tasks
            if len(self._background_tasks) > 0:
                completed_tasks, _ = await asyncio.wait(self._background_tasks,
                                                        timeout=0,
                                                        return_when=asyncio.FIRST_COMPLETED)
                for task in completed_tasks:
                    try:
                        await task
                    except:
                        pass
                    self._background_tasks.discard(task)

        await self._complete_processing()
        return True

    async def abort(self, message: typing.Optional[str] = None):
        """Abort the running schedule."""
        self._aborted = True
        if message is not None:
            self.abort_message = message
        _LOGGER.debug("Schedule processing aborting")

    async def pause(self):
        """Pause the schedule execution"""
        if self._paused is not None:
            return
        _LOGGER.debug("Schedule processing pause requested")
        self._paused = asyncio.get_running_loop().create_future()

    async def resume(self):
        """Resume paused schedule execution"""
        if self._paused is None:
            return
        _LOGGER.debug("Schedule processing resume requested")
        self._paused.set_result(False)

    async def start_background(self, execute: types.coroutine) -> asyncio.Task:
        """Start a task in the background, which will be waited for and aborted with the schedule"""
        task = asyncio.create_task(execute)
        self._background_tasks.add(task)
        return task
