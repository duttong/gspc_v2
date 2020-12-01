import asyncio
import time
import logging
from .interface import Interface
from .lj import LabJack
#from .omega import Flow

_LOGGER = logging.getLogger(__name__)


def _clamp(x, minimum, maximum):
    return max(minimum, min(x, maximum))


class Instrument(Interface):
    AIN_PRESSURE = 1
    AIN_OVEN_TEMPERATURE = 2
    AIN_FLOW = 3

    AOT_FLOW = 0

    DOT_CRYOGEN = 0
    DOT_GC_CRYOGEN = 1
    DOT_VACUUM = 2
    DOT_SAMPLE = 3
    DOT_GC_SOLENOID = 4
    DOT_GC_HEATER = 5
    DOT_OVERFLOW = 6
    DOT_LOAD = 7
    DOT_PRECOLUMN_IN = 8
    DOT_PRECOLUMN_OUT = 9
    DOT_STEP_SOURCE_SELECT = 10

    DIN_SELECTED_SOURCE = [11, 12, 13, 14]

    # Source index -> digital channel
    HIGH_PRESSURE_VALVES = {
        0: 16,
        2: 9,
        13: 13,
        14: 14,
        15: 15,
    }

    def __init__(self, loop: asyncio.AbstractEventLoop):
        Interface.__init__(self, loop)

        self._lj = LabJack()
        #self._flow = Flow()

        self._selected_source = None
        self._flow_control_voltage = None

    async def get_pressure(self) -> float:
        return (await self._lj.read_analog(self.AIN_PRESSURE)) * 100.0

    async def get_oven_temperature(self) -> float:
        return (await self._lj.read_analog(self.AIN_OVEN_TEMPERATURE)) * 100.0

    async def set_cryogen(self, enable: bool):
        await self._lj.write_digital(self.DOT_CRYOGEN, enable)

    async def set_gc_cryogen(self, enable: bool):
        await self._lj.write_digital(self.DOT_GC_CRYOGEN, enable)

    async def set_vacuum(self, enable: bool):
        await self._lj.write_digital(self.DOT_VACUUM, enable)

    async def set_sample(self, enable: bool):
        await self._lj.write_digital(self.DOT_SAMPLE, enable)

    async def set_gc_solenoid(self, enable: bool):
        await self._lj.write_digital(self.DOT_GC_SOLENOID, enable)

    async def set_gc_heater(self, enable: bool):
        await self._lj.write_digital(self.DOT_GC_HEATER, enable)

    async def set_overflow(self, enable: bool):
        await self._lj.write_digital(self.DOT_OVERFLOW, enable)

    async def set_load(self, enable: bool):
        await self._lj.write_digital(self.DOT_LOAD, enable)

    async def precolumn_in(self):
        await self._lj.write_digital(self.DOT_PRECOLUMN_IN, True)
        await asyncio.sleep(2)
        await self._lj.write_digital(self.DOT_PRECOLUMN_IN, False)

    async def precolumn_out(self):
        await self._lj.write_digital(self.DOT_PRECOLUMN_OUT, True)
        await asyncio.sleep(2)
        await self._lj.write_digital(self.DOT_PRECOLUMN_OUT, False)

    async def get_flow(self) -> float:
        return (await self._lj.read_analog(self.AIN_FLOW)) * 100.0 + self.sample_flow_zero_offset

    @staticmethod
    def _to_flow_control_voltage(flow: float):
        return _clamp((flow * .05) + 2.6, 0, 12)

    async def set_flow(self, flow: float):
        self._flow_control_voltage = self._to_flow_control_voltage(flow)
        await self._lj.write_analog(self.AOT_FLOW, self._flow_control_voltage)

    @staticmethod
    def _to_adjustment_increment(delta: float):
        return (abs(delta) * 2 + 1) * 0.01

    async def adjust_flow(self, flow: float):
        if self._flow_control_voltage is None:
            await self.set_flow(flow)

        deadband = 0.15

        measured_flow = None
        for i in range(15):
            measured_flow = await self.get_flow()
            delta = measured_flow - flow
            if abs(delta) < deadband:
                return

            if delta < 0:
                self._flow_control_voltage -= self._to_adjustment_increment(delta)
            else:
                self._flow_control_voltage += self._to_adjustment_increment(delta)
            self._flow_control_voltage = _clamp(self._flow_control_voltage, 0, 12)
            await self._lj.write_analog(self.AOT_FLOW, self._flow_control_voltage)
            await asyncio.sleep(1.0)

        _LOGGER.info(f"Failed to adjust flow {measured_flow:.2f} to target {flow:.2f}")

    async def increment_flow(self, flow: float, multiplier: float):
        if self._flow_control_voltage is None:
            await self.set_flow(flow)

        self._flow_control_voltage += multiplier * 0.02
        await self._lj.write_analog(self.AOT_FLOW, self._flow_control_voltage)

    async def _step_source_selector(self):
        await self._lj.write_digital(self.DOT_STEP_SOURCE_SELECT, False)
        await asyncio.sleep(0.3)
        await self._lj.write_digital(self.DOT_STEP_SOURCE_SELECT, True)

    async def _get_selected_source(self):
        result = 0
        for i in range(len(self.DIN_SELECTED_SOURCE)):
            bit = await self._lj.read_digital(self.DIN_SELECTED_SOURCE[i])
            if not bit:
                continue
            result |= (1 << i)
        return result

    async def _step_to_source(self, index: int):
        selected = await self._get_selected_source()
        if selected == index:
            return True

        # Open overflow if changing the source
        await self.set_overflow(True)

        timeout = time.time() + 30
        while timeout < time.time():
            await self._step_source_selector()
            await asyncio.sleep(0.3)
            selected = await self._get_selected_source()
            if selected == index:
                return True
        return False

    async def select_source(self, index: int, manual: bool = False):
        if manual:
            # Close all high pressure valves
            for _, channel in self.HIGH_PRESSURE_VALVES.items():
                await self._lj.write_digital(channel, False)

        if not await self._step_to_source(index):
            _LOGGER.warning(f"Failed to step to source {index}")

        self._selected_source = index

        # Open the valve if in manual mode
        if manual:
            await self.set_high_pressure_valve(True)

    async def set_high_pressure_valve(self, enable: bool):
        if self._selected_source is None:
            return
        channel = self.HIGH_PRESSURE_VALVES.get(self._selected_source)
        if channel is None:
            return
        await self._lj.write_digital(channel, enable)

    async def ready_gc(self):
        await self._lj.write_digital(11, True)

    async def trigger_gc(self):
        await self._lj.write_digital(11, False)

    async def shutdown(self):
        for _, channel in self.HIGH_PRESSURE_VALVES.items():
            await self._lj.write_digital(channel, False)
        await self.select_source(2)
        await self.set_overflow(True)
        await self.set_flow(3)
