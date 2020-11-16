import logging
import asyncio
from gspc.hw.interface import Interface
from gspc.schedule import Runnable, Execute

_LOGGER = logging.getLogger(__name__)


class OverflowOn(Runnable):
    async def execute(self):
        await self.interface.set_overflow(True)
        _LOGGER.debug("Overflow valve ON")


class OverflowOff(Runnable):
    async def execute(self):
        await self.interface.set_overflow(False)
        _LOGGER.debug("Overflow valve OFF")


class HighPressureOn(Runnable):
    async def execute(self):
        await self.interface.set_high_pressure_valve(True)
        _LOGGER.debug("High pressure valve ON")


class HighPressureOff(Runnable):
    async def execute(self):
        await self.interface.set_high_pressure_valve(False)
        _LOGGER.debug("High pressure valve OFF")


class LoadSwitch(Runnable):
    async def _cycle_valve(self):
        await self.interface.set_load(True)
        _LOGGER.info("Valve switched to load")
        await asyncio.sleep(1)
        await self.interface.set_load(False)

    async def execute(self):
        await self.schedule.start_background(self._cycle_valve())


class SelectSource(Runnable):
    def __init__(self, interface: Interface, schedule: Execute, origin: float, source: int):
        Runnable.__init__(self, interface, schedule, origin)
        self._source = source

    async def execute(self):
        await self.interface.select_source(self._source)
        _LOGGER.debug(f"Selected source {self._source}")
