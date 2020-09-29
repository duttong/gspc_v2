import time
import logging
import asyncio
from gspc.hw.interface import Interface
from gspc.schedule import Runnable, Execute

_LOGGER = logging.getLogger(__name__)


class SwitchToFlask(Runnable):
    """Change to a flask."""

    def __init__(self, interface: Interface, schedule: Execute, select):
        Runnable.__init__(self, interface, schedule)
        self.select = select

    async def execute(self):
        _LOGGER.info(f"Changing to flask {self.select}")
        await self.interface.select_flask(self.select)

    async def active_description(self) -> str:
        return f"Operate valve"


class SwitchToTank(Runnable):
    """Change to a tank."""

    def __init__(self, interface: Interface, schedule: Execute, select):
        Runnable.__init__(self, interface, schedule)
        self.select = select

    async def execute(self):
        _LOGGER.info(f"Changing to tank {self.select}")
        await self.interface.select_tank(self.select)

    async def active_description(self) -> str:
        return f"Operate valve"


class WaitForFlow(Runnable):
    """Set and wait for flow to stabilize."""
    MAXIMUM_WAIT_TIME = 20
    ACCEPT_BAND = 0.1

    def __init__(self, interface: Interface, schedule: Execute, target_flow: float = 1.0):
        Runnable.__init__(self, interface, schedule)
        self.target_flow = target_flow

    async def execute(self):
        _LOGGER.debug(f"Setting flow rate to {self.target_flow}")
        await self.interface.set_target_flow(self.target_flow)

        begin = time.time()
        while time.time() - begin < self.MAXIMUM_WAIT_TIME:
            sample_flow = self.interface.sample_flow
            if sample_flow is not None and abs(sample_flow - self.target_flow) <= self.ACCEPT_BAND:
                return
            await asyncio.sleep(0.5)

        _LOGGER.warning(f"Trap failed to reach target flow after {self.MAXIMUM_WAIT_TIME} seconds")
        await self.schedule.abort(
            f"Sampling flow ({self.interface.sample_flow}) failed to reach target {self.target_flow}")

    async def active_description(self) -> str:
        return f"Flow stabilization"
