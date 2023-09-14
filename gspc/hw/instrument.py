import asyncio
import time
import math
import logging
import typing

from .interface import Interface
from .lj import LabJack
#from .omega import Flow
from .pressure import Pressure
from .ssv import SSV
from .pfp import PFP

_LOGGER = logging.getLogger(__name__)


def _clamp(x, minimum, maximum):
    maximum = 5   # safty GSD 221208
    return max(minimum, min(x, maximum))


class Instrument(Interface):
    # AIN_PRESSURE = 10
    AIN_OVEN_TEMPERATURE = 11
    AIN_FLOW = 12

    AOT_FLOW = 1

    DOT_LN2_FLOW_TO_CRYO_TRAP = "CIO1"
    DOT_GC_CRYOGEN = "EIO3"
    DOT_CLOSE_OFF_VACUUM_PUMP = "CIO2"
    DOT_ENABLE_SAMPLE_INTO_VACUUM_CHAMBER = "EIO4"
    DOT_INJECT = "FIO2"
    DOT_HEAT_CRYO_TRAP = "FIO3"
    DOT_OVERFLOW = "CIO0"
    DOT_LOAD = "FIO1"
    DOT_PRECOLUMN_IN = "FIO6"
    DOT_PRECOLUMN_OUT = "FIO5"
    DOT_GCMS_START = "FIO0"
    DOT_EVAC_PORT_1 = "FIO7"  # PFP sampling
    DOT_EVAC_PORT_12 = "CIO3"  # PFP sampling

    DOT_ISOVALVE_SSV2 = "EIO5"

    # Source index -> digital channel
    HIGH_PRESSURE_VALVES = {
        2: DOT_ISOVALVE_SSV2,
        13: "EIO1",
        14: "EIO0",
        15: "EIO6",
        16: "EIO7",
    }

    # Source index -> digital channel
    # The evacuation is done at PFP position - 1, so these are 1 and 12
    EVACUATION_VALVES = {
        0: DOT_EVAC_PORT_1,
        11: DOT_EVAC_PORT_12,
    }

    def __init__(self, loop: asyncio.AbstractEventLoop):
        Interface.__init__(self, loop)

        self._lj = LabJack()
        #self._flow = Flow()
        self._pressure = Pressure("COM2")
        self._ssv = SSV("COM1")

        self._pfp: typing.Dict[typing.Optional[int], PFP] = dict()
        pfp1: typing.Optional[PFP] = PFP.detect_optional("COM11")
        if pfp1:
            self._pfp[1] = pfp1
            # Evacuation alias
            self._pfp[0] = pfp1
            # Default alias
            self._pfp[None] = pfp1
        pfp12: typing.Optional[PFP] = PFP.detect_optional("COM4")
        if pfp12:
            self._pfp[12] = pfp12
            # Evacuation alias
            self._pfp[11] = pfp12
            if not pfp1:
                # Default alias
                self._pfp[None] = pfp12

        self._selected_ssv = None
        self._flow_control_voltage = None
        self._pfp_pressure = 0.0

    @property
    def has_pfp(self) -> bool:
        return len(self._pfp) != 0

    async def get_pressure(self) -> float:
        # return (await self._lj.read_analog(self.AIN_PRESSURE)) * 100.0
        return await self._pressure.read()

    async def get_oven_temperature_signal(self) -> float:
        return await self._lj.read_analog(self.AIN_OVEN_TEMPERATURE)

    async def set_cryogen(self, enable: bool):
        await self._lj.write_digital(self.DOT_LN2_FLOW_TO_CRYO_TRAP, enable)

    async def set_gc_cryogen(self, enable: bool):
        await self._lj.write_digital(self.DOT_GC_CRYOGEN, enable)

    async def set_vacuum(self, enable: bool):
        await self._lj.write_digital(self.DOT_CLOSE_OFF_VACUUM_PUMP, enable)

    async def set_sample(self, enable: bool):
        await self._lj.write_digital(self.DOT_ENABLE_SAMPLE_INTO_VACUUM_CHAMBER, enable)

    async def set_cryo_heater(self, enable: bool):
        await self._lj.write_digital(self.DOT_HEAT_CRYO_TRAP, enable)

    async def set_overflow(self, enable: bool):
        await self._lj.write_digital(self.DOT_OVERFLOW, enable)

    async def valve_load(self):
        await self._lj.write_digital(self.DOT_LOAD, True)
        await asyncio.sleep(1)
        await self._lj.write_digital(self.DOT_LOAD, False)

    async def valve_inject(self):
        await self._lj.write_digital(self.DOT_INJECT, True)
        await asyncio.sleep(2)
        await self._lj.write_digital(self.DOT_INJECT, False)

    async def precolumn_in(self):
        await self._lj.write_digital(self.DOT_PRECOLUMN_IN, True)
        await asyncio.sleep(2)
        await self._lj.write_digital(self.DOT_PRECOLUMN_IN, False)

    async def precolumn_out(self):
        await self._lj.write_digital(self.DOT_PRECOLUMN_OUT, True)
        await asyncio.sleep(2)
        await self._lj.write_digital(self.DOT_PRECOLUMN_OUT, False)

    async def get_flow_control_output(self) -> float:
        return self._flow_control_voltage

    async def get_flow_signal(self) -> float:
        return (await self._lj.read_analog(self.AIN_FLOW)) + self.sample_flow_zero_offset

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
            measured_flow = await self.get_flow_signal()
            delta = measured_flow - flow
            _LOGGER.debug(f"Adjusting flow {measured_flow:.2f} to target {flow:.2f}, delta {delta:.2f}")
            if abs(delta) < deadband:
                return

            if delta < 0:
                self._flow_control_voltage += self._to_adjustment_increment(delta)
            else:
                self._flow_control_voltage -= self._to_adjustment_increment(delta)
            self._flow_control_voltage = _clamp(self._flow_control_voltage, 0, 12)
            await self._lj.write_analog(self.AOT_FLOW, self._flow_control_voltage)
            await asyncio.sleep(1.0)

        _LOGGER.info(f"Failed to adjust flow {measured_flow:.2f} to target {flow:.2f}")

    async def increment_flow(self, flow: float, multiplier: float):
        if self._flow_control_voltage is None:
            await self.set_flow(flow)

        self._flow_control_voltage += multiplier * 0.02
        self._flow_control_voltage = _clamp(self._flow_control_voltage, 0, 12)
        await self._lj.write_analog(self.AOT_FLOW, self._flow_control_voltage)

    async def get_ssv_cp(self) -> int:
        return await self._ssv.read()

    async def set_ssv(self, index: int, manual: bool = False):
        if manual:
            # Close all high pressure valves
            for _, channel in self.HIGH_PRESSURE_VALVES.items():
                await self._lj.write_digital(channel, False)
            await self.set_overflow(True)

        if (await self._ssv.read()) != index:
            # Open overflow if changing the position
            await self.set_overflow(True)

            await self._ssv.set(index)
            for i in range(30):
                if (await self._ssv.read()) == index:
                    break
                await asyncio.sleep(1)
            else:
                _LOGGER.warning(f"Failed to change SSV to {index}")

        self._selected_ssv = index
        _LOGGER.info(f"SSV position is {index}")

        # Open the valve if in manual mode
        if manual:
            await self.set_high_pressure_valve(True)
            # set full flow
            await self.set_flow(math.inf)

        # close overflow after moving SSV in automatic mode
        if not manual:
            await self.set_overflow(False)

    async def set_high_pressure_valve(self, enable: bool):
        if self._selected_ssv is None:
            return
        channel = self.HIGH_PRESSURE_VALVES.get(self._selected_ssv)
        if channel is None:
            return
        else:
            await self._lj.write_digital(channel, enable)
            _LOGGER.info(f"High Pressure Valve {enable}")

    async def set_evacuation_valve(self, enable: bool):
        if self._selected_ssv is None:
            return
        channel = self.EVACUATION_VALVES.get(self._selected_ssv)
        if channel is None:
            return
        else:
            await self._lj.write_digital(channel, enable)
            _LOGGER.info(f"Evacuation Valve {enable}")

    async def ready_gcms(self):
        await self._lj.write_digital(self.DOT_GCMS_START, True)

    async def trigger_gcms(self):
        await self._lj.write_digital(self.DOT_GCMS_START, False)

    async def set_pfp_valve(self, ssv_index: typing.Optional[int], pfp_valve: int, set_open: bool) -> str:
        if ssv_index is None:
            ssv_index = self._selected_ssv
        pfp = self._pfp.get(ssv_index)
        if pfp is None:
            return ""
        if set_open:
            return await pfp.open_valve(pfp_valve)
        else:
            return await pfp.close_valve(pfp_valve)

    async def get_pfp_pressure(self, ssv_index: typing.Optional[int] = None) -> float:
        """ method to read the pfp flask pressure.
            GSD modified the method to save the pfp flask pressure to self._pfp_pressure """
        if ssv_index is None:
            ssv_index = self._selected_ssv
        pfp = self._pfp.get(ssv_index)
        if pfp is None:
            return None
        self._pfp_pressure = await pfp.read_pressure()
        return self._pfp_pressure

    async def get_display_pfp_pressure(self) -> float:
        return self._pfp_pressure

    async def initialization(self):
        """ This method is called when gspc starts. Sets al of the digio lines
            to low (False). """
        await self.set_ssv(2)
        await self._lj.write_digital(f'CIO1', False)
        await self._lj.write_digital(f'CIO2', False)
        await self._lj.write_digital(f'CIO3', False)
        for n in range(0, 8):
            await self._lj.write_digital(f'EIO{n}', False)
            await self._lj.write_digital(f'FIO{n}', False)

    async def shutdown(self):
        await self.initialization()
        await self.set_high_pressure_valve(True)
        await self.set_flow(3)
        await self.set_overflow(True)
        self._flow_control_voltage = None
