import logging
import time
import typing
import asyncio
from gspc.hw.interface import Interface
from gspc.schedule import Runnable, Execute, AbortPoint

_LOGGER = logging.getLogger(__name__)


class WaitForOvenCool(Runnable):
    REQUIRED_TEMPERATURE = -55

    def __init__(self, interface: Interface, schedule: Execute, origin: float,
                 cooling_failed: typing.Optional[typing.Callable[[], None]] = None,
                 abort_point: typing.Optional[AbortPoint] = None):
        Runnable.__init__(self, interface, schedule, origin)
        self._cooling_failed = cooling_failed
        self._abort_point = abort_point

    async def execute(self):
        for i in range(4):
            temperature = await self.interface.get_oven_temperature()
            if temperature is not None and temperature <= self.REQUIRED_TEMPERATURE:
                _LOGGER.info("GC oven cooled")
                if i == 0:
                    return False
                return True
            if self._cooling_failed:
                self._cooling_failed()
            _LOGGER.info(f"GC oven temperature too high ({temperature:.1f} > {self.REQUIRED_TEMPERATURE}), waiting for 15 seconds")
            await asyncio.sleep(15)

        _LOGGER.info(f"GC oven failed to reach {self.REQUIRED_TEMPERATURE}, cycle will abort")
        if self._abort_point:
            await self._abort_point.abort("GC oven failed to cool")
        else:
            await self.schedule.abort("GC oven failed to cool")
        return True


class CheckSampleTemperature(Runnable):
    REQUIRED_TEMPERATURE = -55

    async def execute(self):
        temperature = await self.interface.get_oven_temperature()
        if temperature is not None and temperature > self.REQUIRED_TEMPERATURE:
            return
        _LOGGER.info(f"GC temperature too low (f{temperature:.1f} < {self.REQUIRED_TEMPERATURE}), aborting")
        await self.schedule.abort("GC failed to heat")
