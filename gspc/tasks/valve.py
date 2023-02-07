import logging
import asyncio
import typing
from gspc.hw.interface import Interface
from gspc.schedule import Runnable, Execute

_LOGGER = logging.getLogger(__name__)


class OverflowOn(Runnable):
    async def execute(self):
        await self.context.interface.set_overflow(True)
        _LOGGER.debug("Overflow valve ON")


class OverflowOff(Runnable):
    async def execute(self):
        await self.context.interface.set_overflow(False)
        _LOGGER.debug("Overflow valve OFF")


class HighPressureOn(Runnable):
    async def execute(self):
        await self.context.interface.set_high_pressure_valve(True)
        _LOGGER.debug("High pressure valve ON")


class HighPressureOff(Runnable):
    async def execute(self):
        await self.context.interface.set_high_pressure_valve(False)
        _LOGGER.debug("High pressure valve OFF")


class EvacuateOn(Runnable):
    async def execute(self):
        await self.context.interface.set_evacuation_valve(True)
        _LOGGER.debug("Evacuation valve ON")


class EvacuateOff(Runnable):
    async def execute(self):
        await self.context.interface.set_evacuation_valve(False)
        _LOGGER.debug("Evacuation valve OFF")


class LoadSwitch(Runnable):
    async def execute(self):
        await self.context.schedule.start_background(self.context.interface.valve_load())
        _LOGGER.info("Valve set to LOAD")


class InjectSwitch(Runnable):
    async def execute(self):
        await self.context.schedule.start_background(self.context.interface.valve_inject())
        _LOGGER.info("Valve set to INJECT")


class PreColumnIn(Runnable):
    async def execute(self):
        await self.context.schedule.start_background(self.context.interface.precolumn_in())
        _LOGGER.info("Precolumn IN line")


class PreColumnOut(Runnable):
    async def execute(self):
        await self.context.schedule.start_background(self.context.interface.precolumn_out())
        _LOGGER.info("Precolumn OUT of line")


class SetSSV(Runnable):
    def __init__(self, context: Execute.Context, origin: float, source: int):
        Runnable.__init__(self, context, origin)
        self._source = source

    async def execute(self):
        await self.context.interface.set_ssv(self._source)
        _LOGGER.debug(f"SSV set to {self._source}")


class PFPValveOpen(Runnable):
    def __init__(self, context: Execute.Context, origin: float, ssv: int, pfp_index: int,
                 record: typing.Optional[typing.Callable[[str], None]] = None):
        Runnable.__init__(self, context, origin)
        self._ssv = ssv
        self._pfp_index = pfp_index
        self._record = record

    async def _manipulate_valve(self):
        response = await self.context.interface.set_pfp_valve(self._ssv, self._pfp_index, True)
        _LOGGER.info(f"PFP{self._ssv} valve {self._pfp_index} OPEN: {response}")
        if self._record:
            self._record(response)

    async def execute(self):
        await self.context.schedule.start_background(self._manipulate_valve())
        _LOGGER.debug(f"Setting PFP{self._ssv} valve {self._pfp_index} OPEN")


class PFPValveClose(Runnable):
    def __init__(self, context: Execute.Context, origin: float, ssv: int, pfp_index: int,
                 record: typing.Optional[typing.Callable[[str], None]] = None):
        Runnable.__init__(self, context, origin)
        self._ssv = ssv
        self._pfp_index = pfp_index
        self._record = record

    async def _manipulate_valve(self):
        response = await self.context.interface.set_pfp_valve(self._ssv, self._pfp_index, False)
        _LOGGER.info(f"PFP{self._ssv} valve {self._pfp_index} CLOSED: {response}")
        if self._record:
            self._record(response)

    async def execute(self):
        await self.context.schedule.start_background(self._manipulate_valve())
        _LOGGER.debug(f"Setting PFP{self._ssv} valve {self._pfp_index} CLOSED")
