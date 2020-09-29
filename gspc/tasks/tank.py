import logging
import asyncio
import typing
from gspc.hw.interface import Interface
from gspc.schedule import Task, Runnable, Execute
from .valve import SwitchToTank, WaitForFlow
from .trap import WaitForCooled

_LOGGER = logging.getLogger(__name__)


class SampleTank(Runnable):
    """Execute sampling of a tank, once the flow is ready."""
    SAMPLE_TIME = 30.0

    def __init__(self, interface: Interface, schedule: Execute, select):
        Runnable.__init__(self, interface, schedule)
        self.select = select

    async def execute(self):
        _LOGGER.info(f"Sampling tank {self.select}")
        await self.interface.begin_flask_sample(self.select)
        await asyncio.sleep(self.SAMPLE_TIME)
        _LOGGER.info(f"Sampling completed for tank {self.select}")
        await self.interface.unselect_flask()

    async def predicted_run_time(self) -> float:
        return self.SAMPLE_TIME

    async def active_description(self) -> str:
        return f"Tank {self.select}"


class Tank(Task):
    """A task that samples from a tank."""

    def __init__(self, select):
        self.select = select

    def schedule(self, interface: Interface, schedule: Execute) -> typing.Sequence[Runnable]:
        return [
            SwitchToTank(interface, schedule, self.select),
            WaitForFlow(interface, schedule),
            WaitForCooled(interface, schedule),
            SampleTank(interface, schedule, self.select)
        ]
