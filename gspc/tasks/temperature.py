import logging
import time
import typing
import asyncio
from gspc.hw.interface import Interface
from gspc.schedule import Runnable, Execute, AbortPoint

_LOGGER = logging.getLogger(__name__)


class WaitForOvenCool(Runnable):
    REQUIRED_TEMPERATURE_SIGNAL = 2.5

    def __init__(self, interface: Interface, schedule: Execute, origin: float,
                 cooling_failed: typing.Optional[typing.Callable[[], None]] = None,
                 abort_point: typing.Optional[AbortPoint] = None):
        Runnable.__init__(self, interface, schedule, origin)
        self._cooling_failed = cooling_failed
        self._abort_point = abort_point

    async def execute(self):
        for i in range(4):
            sig = await self.interface.get_oven_temperature_signal()
            if sig is not None and sig <= self.REQUIRED_TEMPERATURE_SIGNAL:
                _LOGGER.info("Oven cooled")
                if i == 0:
                    return False
                return True
            if self._cooling_failed:
                self._cooling_failed()
            _LOGGER.info(f"Oven temperature too high ({sig:.3f} > {self.REQUIRED_TEMPERATURE_SIGNAL}), waiting for 15 seconds")
            await asyncio.sleep(15)

        _LOGGER.info(f"Oven failed to reach {self.REQUIRED_TEMPERATURE_SIGNAL}, cycle will abort")
        if self._abort_point:
            await self._abort_point.abort("Oven failed to cool")
        else:
            await self.schedule.abort("Oven failed to cool")
        return True


class CheckSampleTemperature(Runnable):
    REQUIRED_TEMPERATURE_SIGNAL = 2.5

    async def execute(self):
        sig = await self.interface.get_oven_temperature_signal()
        if sig is not None and sig > self.REQUIRED_TEMPERATURE_SIGNAL:
            return
        _LOGGER.info(f"GC temperature too low (f{sig:.3f} < {self.REQUIRED_TEMPERATURE_SIGNAL}), aborting")
        await self.schedule.abort("Oven failed to heat")
