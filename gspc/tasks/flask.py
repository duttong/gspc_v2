import logging
import asyncio
import typing
from gspc.hw.interface import Interface
from gspc.schedule import Task, Runnable, Execute
from .valve import SwitchToFlask, WaitForFlow
from .trap import WaitForCooled

_LOGGER = logging.getLogger(__name__)


class SampleFlask(Runnable):
    """Execute sampling of a flask, once the flow is ready."""
    SAMPLE_TIME = 30.0

    def __init__(self, interface: Interface, schedule: Execute, select):
        Runnable.__init__(self, interface, schedule)
        self.select = select

    async def execute(self):
        _LOGGER.debug(f"Sampling flask {self.select}")
        await self.interface.begin_flask_sample(self.select)
        await asyncio.sleep(self.SAMPLE_TIME)
        _LOGGER.debug(f"Sampling completed for flask {self.select}")
        await self.interface.unselect_flask()

    async def predicted_run_time(self) -> float:
        return self.SAMPLE_TIME

    async def active_description(self) -> str:
        return f"Flask {self.select}"


class Flask(Task):
    """A task that samples from a flask."""

    def __init__(self, select):
        self.select = select

    def schedule(self, interface: Interface, schedule: Execute) -> typing.Sequence[Runnable]:
        return [
            SwitchToFlask(interface, schedule, self.select),
            WaitForFlow(interface, schedule),
            WaitForCooled(interface, schedule),
            SampleFlask(interface, schedule, self.select)
        ]
