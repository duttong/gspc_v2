import time
import logging
import asyncio
from gspc.schedule import Runnable

_LOGGER = logging.getLogger(__name__)


class WaitForCooled(Runnable):
    """Wait for the trap to cool below a required temperature before proceeding."""
    MAXIMUM_WAIT_TIME = 300
    REQUIRED_TEMPERATURE = -30

    async def execute(self):
        _LOGGER.debug(f"Waiting for trap to cool to {self.REQUIRED_TEMPERATURE}")

        begin = time.time()
        while time.time() - begin < self.MAXIMUM_WAIT_TIME:
            trap_temperature = self.interface.trap_temperature
            if trap_temperature is not None and trap_temperature <= self.REQUIRED_TEMPERATURE:
                return
            await asyncio.sleep(0.5)

        _LOGGER.warning(f"Trap failed to reach target temperature after {self.MAXIMUM_WAIT_TIME} seconds")
        await self.schedule.abort(
            f"Trap temperature ({self.interface.trap_temperature}) failed to reach target {self.REQUIRED_TEMPERATURE}")

    async def active_description(self) -> str:
        return f"Cooling trap"
