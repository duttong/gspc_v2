import logging
import asyncio
from gspc.schedule import Runnable

_LOGGER = logging.getLogger(__name__)


class CycleVacuum(Runnable):
    async def _cycle_valve(self):
        await self.context.interface.set_vacuum(True)
        await asyncio.sleep(2)
        await self.context.interface.set_vacuum(False)
        _LOGGER.info("Cycled vacuum valve")

    async def execute(self):
        _LOGGER.debug("Cycling vacuum valve")
        await self.context.schedule.start_background(self._cycle_valve())


class VacuumOn(Runnable):
    async def execute(self):
        await self.context.interface.set_vacuum(True)
        _LOGGER.info("Vacuum valve ON")


class VacuumOff(Runnable):
    async def execute(self):
        await self.context.interface.set_vacuum(False)
        _LOGGER.debug("Vacuum valve OFF")
