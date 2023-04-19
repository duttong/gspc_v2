import logging
import asyncio
import typing
import math
import time
from collections import namedtuple
from gspc.hw.interface import Interface
from gspc.output import abort_cycle

_LOGGER = logging.getLogger(__name__)


Event = namedtuple("Event", ["time", "occurred"])
_Reschedule = namedtuple("_Reschedule", ["remove", "append"])


class Runnable:
    """A component of the sequence that is able to be run"""

    def __init__(self, context: 'Execute.Context', origin: float = -math.inf):
        """Create the runnable component."""
        self.context = context
        self.origin = origin
        self.set_events: typing.Set[str] = set()
        self.clear_events: typing.Set[str] = set()

    async def execute(self) -> typing.Optional[bool]:
        """Execute the task.  Return true if the task should shift subsequent ones by its execution time."""
        pass


class Gate(Runnable):
    """A runnable that can be used to gate the schedule advance, waiting until a set of conditions are ready"""

    def __init__(self, context: 'Execute.Context', origin: float,
                 required_ready: typing.Optional[int] = None):
        Runnable.__init__(self, context, origin)
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

    def __init__(self, context: 'Execute.Context', origin=-math.inf):
        Runnable.__init__(self, context, origin)
        self._aborted = False
        self._abort_message = None

    async def abort(self, message: typing.Optional[str] = None) -> None:
        """Schedule the abort"""
        self._aborted = True
        if message is not None:
            self._abort_message = message

    async def execute(self):
        if not self._aborted:
            return
        await self.context.schedule.abort(self._abort_message)


class Task:
    """The base for tasks that can be executed on a schedule."""

    def __init__(self, origin_advance: float = 0):
        self.origin_advance = origin_advance

    def schedule(self, context: 'Execute.Context') -> typing.Sequence[Runnable]:
        """Return a list of runnable tasks for execution"""
        return list()


known_tasks = dict()


def register_task(name: str, task: Task):
    """Register a task that can be scheduled from a sequence set."""
    known_tasks[name] = task


class Execute:
    """The execution handler for a list of tasks"""

    class Context:
        """The context identifier for a task scheduled for execution"""
        def __init__(self, interface: Interface, schedule: 'Execute', origin: float, task_index: int):
            self.interface = interface
            self.schedule = schedule
            self.origin = origin
            self.task_index = task_index
            self.task_started: bool = False
            self.task_completed: bool = False
            self.task_activated: bool = False

    class RescheduleFailure(Exception):
        """An exception raised when rescheduling fails"""
        def __init__(self, message: str, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.message = message

    def __init__(self, task_sequence: typing.Sequence[Task]):
        self._tasks = task_sequence
        self._background_tasks: typing.Set[asyncio.Task] = set()
        self._break_event = None
        self._aborted = False
        self._paused = None
        self._reschedule_operation: typing.Optional[_Reschedule] = None
        self._reschedule_result: typing.Optional[asyncio.Future] = None
        self.contexts: typing.List["Execute.Context"] = list()
        self.abort_message = None
        self.events: typing.Dict[str, Event] = dict()

    async def state_update(self):
        """Called when part of the schedule state has changed"""
        pass

    async def _execute_run(self, running: Runnable, completed_origin: float) -> typing.Optional[bool]:
        if not math.isfinite(running.origin):
            running.context.task_activated = True
            await self.state_update()
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

        running.context.task_activated = True
        await self.state_update()
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
        abort_cycle(self.abort_message)

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
        if self._break_event is not None:
            raise RuntimeError
        self._break_event = asyncio.Event()

        run = list()
        origin = 0.0
        for i in range(len(self._tasks)):
            task = self._tasks[i]
            context = self.Context(interface, self, origin, i)
            self.contexts.append(context)
            add = task.schedule(context)
            run.extend(add)
            origin += task.origin_advance

        run.sort(key=lambda runnable: runnable.origin)

        self._aborted = False
        self.abort_message = None
        self.events.clear()
        zero_real_time = time.time()
        zero_monotonic_time = time.monotonic()

        async def wait_for_ready(running: Runnable) -> bool:
            if not math.isfinite(running.origin):
                need_break = self._break_event.is_set()
                self._break_event.clear()
                return not need_break

            target_time = running.origin + zero_monotonic_time
            delay = target_time - time.monotonic()
            if delay <= 0.0:
                need_break = self._break_event.is_set()
                self._break_event.clear()
                return not need_break

            try:
                await asyncio.wait_for(self._break_event.wait(), timeout=delay)
            except (TimeoutError, asyncio.TimeoutError):
                # Timeout means the delay has elapsed, so we're ready to execute
                return True

            self._break_event.clear()
            return False

        def update_future_events():
            nonlocal zero_real_time

            # Remove all future events so they can be regenerated
            self.events = {e: d for e, d in self.events.items() if d.occurred}
            stop_events = set()
            for future_run in run:
                expected_time = future_run.origin + zero_real_time
                if not math.isfinite(expected_time):
                    continue

                for event in future_run.clear_events:
                    stop_events.add(event)
                for event in future_run.set_events:
                    if event in stop_events:
                        continue
                    if event in self.events:
                        continue

                    self.events[event] = Event(expected_time, False)

        def apply_reschedule(remove: typing.Optional[int], append: typing.Optional[typing.Sequence]):
            nonlocal run

            modified_contexts = list(self.contexts)
            modified_tasks = list(self._tasks)

            if remove is not None and remove < len(modified_contexts):
                remove_contexts = set()
                for ctx in modified_contexts[remove:]:
                    if ctx.task_activated:
                        raise self.RescheduleFailure("task already active")
                    remove_contexts.add(ctx)

                del modified_tasks[remove:]
                del modified_contexts[remove:]

                modified_run = [next_run for next_run in run if next_run.context not in remove_contexts]
            else:
                modified_run = list(run)

            if append:
                index = len(modified_contexts)
                if index > 0:
                    origin = modified_contexts[-1].origin + modified_tasks[-1].origin_advance
                else:
                    origin = 0.0
                first_possible_origin = time.monotonic() - zero_monotonic_time

                for task in append:
                    context = self.Context(interface, self, origin, index)
                    add = task.schedule(context)

                    for check in add:
                        if check.origin < first_possible_origin:
                            raise self.RescheduleFailure("task requires action in the past")

                    modified_contexts.append(context)

                    modified_run.extend(add)
                    origin += task.origin_advance
                    index += 1

            self._tasks = modified_tasks
            self.contexts = modified_contexts
            run = modified_run
            run.sort(key=lambda runnable: runnable.origin)

        async def get_next_execute() -> typing.Optional[Runnable]:
            nonlocal run
            nonlocal zero_monotonic_time
            nonlocal zero_real_time
            while run:
                if self._paused is not None:
                    # So that unscheduled events are updated
                    await self.state_update()

                    _LOGGER.debug("Schedule processing paused")
                    pause_begin = time.monotonic()
                    await self._paused
                    pause_consumed = time.monotonic() - pause_begin
                    self._paused = None
                    _LOGGER.debug("Schedule processing resumed")

                    # Apply a delay so that the pause "doesn't happen" with respect to time scheduling
                    zero_monotonic_time += pause_consumed
                    zero_real_time += pause_consumed
                    continue

                if self._aborted:
                    return None

                if self._reschedule_operation is not None:
                    op = self._reschedule_operation
                    self._reschedule_operation = None
                    try:
                        apply_reschedule(op.remove, op.append)
                        if self._reschedule_result:
                            self._reschedule_result.set_result(True)
                    except Exception as e:
                        if self._reschedule_result:
                            self._reschedule_result.set_exception(e)
                        else:
                            _LOGGER.warning("Reschedule failure", exc_info=True)
                    continue

                update_future_events()

                # Call before the wait, so that event times are updated
                await self.state_update()

                to_run = run[0]

                # Wait for ready or something to do
                if not await wait_for_ready(to_run):
                    continue

                run = run[1:]
                return to_run

            return None

        async def execute_pending(running: Runnable):
            nonlocal zero_monotonic_time
            nonlocal zero_real_time
            # Mark as executing
            running.context.task_activated = True
            await self.state_update()

            delay_schedule = await running.execute()

            if delay_schedule and math.isfinite(running.origin):
                # Change the zero origin so that time spent delaying is removed and the current time "becomes"
                # the start of executing the delaying runnable
                zero_monotonic_time = time.monotonic() - running.origin
                zero_real_time = time.time() - running.origin

            # Completed now, so record events that were processed
            completed_time = time.time()
            for event in running.clear_events:
                self.events.pop(event, None)
            for event in running.set_events:
                self.events[event] = Event(completed_time, True)

        async def reap_background_tasks():
            if len(self._background_tasks) == 0:
                return

            completed_tasks, _ = await asyncio.wait(self._background_tasks,
                                                    timeout=0,
                                                    return_when=asyncio.FIRST_COMPLETED)
            for task in completed_tasks:
                try:
                    await task
                except:
                    _LOGGER.warning("Error in background task", exc_info=True)
                self._background_tasks.discard(task)

        while True:
            to_run = await get_next_execute()
            if to_run is None:
                break

            await execute_pending(to_run)
            await reap_background_tasks()

        if self._aborted:
            await self._abort_processing()
            self._break_event = None
            return False
        else:
            await self._complete_processing()
            self._break_event = None
            return True

    async def abort(self, message: typing.Optional[str] = None):
        """Abort the running schedule."""
        self._aborted = True
        if message is not None:
            self.abort_message = message
        if self._break_event:
            self._break_event.set()
        _LOGGER.debug("Schedule processing aborting")

    async def pause(self):
        """Pause the schedule execution"""
        if self._paused is not None:
            return
        _LOGGER.debug("Schedule processing pause requested")
        self._paused = asyncio.get_running_loop().create_future()
        if self._break_event:
            self._break_event.set()

    async def resume(self):
        """Resume paused schedule execution"""
        if self._paused is None:
            return
        _LOGGER.debug("Schedule processing resume requested")
        self._paused.set_result(False)

    async def is_paused(self) -> bool:
        """Test if the schedule has currently been paused"""
        return self._paused is not None

    async def reschedule(self, remove: typing.Optional[int] = None,
                         append: typing.Optional[typing.Sequence[Task]] = None):
        """Attempt to remove the specified task index and all tasks after it and append the new ones"""
        if self._reschedule_result is not None:
            raise self.RescheduleFailure("reschedule currently in progress")
        self._reschedule_result = asyncio.get_running_loop().create_future()
        assert self._reschedule_operation is None
        self._reschedule_operation = _Reschedule(remove, append)
        if self._break_event:
            self._break_event.set()
        await self._reschedule_result
        self._reschedule_result.result()
        self._reschedule_result = None

    async def start_background(self, execute: typing.Coroutine) -> asyncio.Task:
        """Start a task in the background, which will be waited for and aborted with the schedule"""
        task = asyncio.create_task(execute)
        self._background_tasks.add(task)
        return task
