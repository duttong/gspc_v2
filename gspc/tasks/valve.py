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
    async def execute(self):
        await self.schedule.start_background(self.interface.valve_load())
        _LOGGER.info("Valve set to LOAD")


class InjectSwitch(Runnable):
    async def execute(self):
        await self.schedule.start_background(self.interface.valve_inject())
        _LOGGER.info("Valve set to INJECT")


class PreColumnIn(Runnable):
    async def execute(self):
        await self.schedule.start_background(self.interface.precolumn_in())
        _LOGGER.info("Precolumn IN line")


class PreColumnOut(Runnable):
    async def execute(self):
        await self.schedule.start_background(self.interface.precolumn_out())
        _LOGGER.info("Precolumn OUT of line")


class SetSSV(Runnable):
    def __init__(self, interface: Interface, schedule: Execute, origin: float, source: int):
        Runnable.__init__(self, interface, schedule, origin)
        self._source = source

    async def execute(self):
        await self.interface.set_ssv(self._source)
        _LOGGER.debug(f"SSV set to {self._source}")
