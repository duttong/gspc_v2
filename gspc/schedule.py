import logging
import asyncio
import typing
from gspc.hw.interface import Interface

_LOGGER = logging.getLogger(__name__)


class Runnable:
    """A component of the sequence that is able to be run"""

    def __init__(self, interface: Interface, schedule: 'Execute'):
        """Create the runnable component."""
        self.interface = interface
        self.schedule = schedule

    async def execute(self):
        """Execute the task."""
        pass

    async def predicted_run_time(self) -> float:
        """Get the time the component is predicted to run for"""
        return 0.0

    async def active_description(self) -> str:
        """Get the description of the component to be displayed while it is running"""
        return ""


class RunInParallel(Runnable):
    """Run multiple parts of a sequence in parallel and wait for them all to finish."""
    def __init__(self, interface: Interface, schedule: 'Execute', *run: Runnable):
        Runnable.__init__(self, interface, schedule)
        self._run = run

    async def execute(self):
        await asyncio.gather(*[asyncio.ensure_future(r.execute()) for r in self._run])

    async def predicted_run_time(self) -> float:
        longest_run_time = 0.0
        for r in self._run:
            longest_run_time = max(longest_run_time, await r.predicted_run_time())
        return longest_run_time


class Task:
    """The base for tasks that can be executed on a schedule."""

    def schedule(self, interface: Interface, schedule: 'Execute') -> typing.Sequence[Runnable]:
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
        self._aborted = False
        self._paused = None
        self.abort_message = None

    async def update_predicted_run_time(self, seconds_remaining: float):
        """Called at every component advance with the predicted remaining time"""
        pass

    async def before_run(self, running: Runnable):
        """Called before the current runnable is executed"""
        pass

    async def execute(self, interface: Interface):
        """Execute the scheduled tasks."""
        run = list()
        for task in self._tasks:
            run.extend(task.schedule(interface, self))

        self._aborted = False
        self.abort_message = None
        for i in range(len(run)):
            seconds_remaining = 0
            for j in range(i, len(run)):
                seconds_remaining += await run[j].predicted_run_time()
            await self.update_predicted_run_time(seconds_remaining)
            await self.before_run(run[i])
            if self._aborted:
                _LOGGER.debug("Schedule abort completed")
                return False
            await run[i].execute()
            if self._aborted:
                _LOGGER.debug("Schedule abort completed")
                return False
            if self._paused is not None:
                _LOGGER.debug("Schedule processing paused")
                await self._paused
                self._paused = None
                _LOGGER.debug("Schedule processing resumed")

        _LOGGER.debug("Schedule processing completed")
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
