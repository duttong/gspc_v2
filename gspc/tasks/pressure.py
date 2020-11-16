import logging
import time
import asyncio
import statistics
from gspc.hw.interface import Interface
from gspc.schedule import Runnable, Execute

_LOGGER = logging.getLogger(__name__)


class MeasurePressure(Runnable):
    def __init__(self, interface: Interface, schedule: Execute, origin: float, duration: float):
        Runnable.__init__(self, interface, schedule, origin)
        self._duration = duration
        # Warning NYI store it somewhere

    async def _sample_pressure(self):
        end_time = time.time() + self._duration
        pressure_readings = list()
        while time.time() <= end_time:
            pressure = await self.interface.get_pressure()
            if pressure is not None:
                pressure_readings.append(pressure)
            await asyncio.sleep(1)
        pressure_mean = statistics.mean(pressure_readings)
        pressure_stddev = statistics.stdev(pressure_readings)
        _LOGGER.debug(f"Measured pressure {pressure_mean:.1f} with stddev {pressure_stddev:.2f}")

    async def execute(self):
        await self.schedule.start_background(self._sample_pressure())
        _LOGGER.info("Collecting pressure data")