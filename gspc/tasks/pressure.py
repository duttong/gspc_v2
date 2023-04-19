import logging
import time
import asyncio
import statistics
import typing
from gspc.hw.interface import Interface
from gspc.schedule import Runnable, Execute

_LOGGER = logging.getLogger(__name__)


class MeasurePressure(Runnable):
    def __init__(self, context: Execute.Context, origin: float, duration: float,
                 record: typing.Callable[[float, float, typing.List[float]], None]):
        Runnable.__init__(self, context, origin)
        self._duration = duration
        self._record = record

    async def execute(self):
        _LOGGER.info("Collecting pressure data")
        end_time = time.time() + self._duration
        pressure_readings = list()
        while time.time() <= end_time:
            pressure = await self.context.interface.get_pressure()
            if pressure is not None:
                pressure_readings.append(pressure)
            await asyncio.sleep(1)
        pressure_mean = statistics.mean(pressure_readings)
        pressure_stddev = statistics.stdev(pressure_readings)
        _LOGGER.info(f"Measured pressure {pressure_mean:.1f} with stddev {pressure_stddev:.2f}")
        self._record(pressure_mean, pressure_stddev, pressure_readings)


class MeasurePFPPressure(Runnable):
    def __init__(self, context: Execute.Context, origin: float,
                 ssv: int, record: typing.Callable[[float], None]):
        Runnable.__init__(self, context, origin)
        self._record = record
        self._ssv = ssv

    async def execute(self):
        pressure = await self.context.interface.get_pfp_pressure(self._ssv)
        _LOGGER.info(f"Measured PFP ssv={self._ssv} pressure {pressure:.1f}")
        if self._record:
            self._record(pressure)


class CheckPFPEvacuated(Runnable):
    REQUIRED_PRESSURE_SIGNAL = 2.5

    def __init__(self, context: Execute.Context, origin: float, ssv: int):
        Runnable.__init__(self, context, origin)
        self._ssv = ssv

    async def execute(self):
        sig = await self.context.interface.get_pfp_pressure(self._ssv)
        if sig is not None and sig < self.REQUIRED_PRESSURE_SIGNAL:
            _LOGGER.info(f"PFF inlet evacuated ok")
            return
        _LOGGER.info(f"PFP inlet pressure too high (f{sig:.3f} > {self.REQUIRED_PRESSURE_SIGNAL}), aborting")
        await self.context.schedule.abort("Inlet pressure too high")

