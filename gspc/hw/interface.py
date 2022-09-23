import asyncio
import typing


class Interface:
    """The abstract interface to the hardware control"""

    def __init__(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

        self.sample_flow_zero_offset: float = 0.0

    async def get_pressure(self) -> float:
        """Read the current pressure"""
        pass

    async def get_oven_temperature_signal(self) -> float:
        """Read the current oven temperature signal"""
        pass

    async def set_cryogen(self, enable: bool):
        """Set the cryogen control state"""
        pass

    async def set_gc_cryogen(self, enable: bool):
        """Set the GC cryogen control state"""
        pass

    async def set_vacuum(self, enable: bool):
        """Set the evac vacuum"""
        pass

    async def set_sample(self, enable: bool):
        """Set the sample valve"""
        pass

    async def set_cryo_heater(self, enable: bool):
        """Set the GC heater"""
        pass

    async def set_overflow(self, enable: bool):
        """Set the overflow valve"""
        pass

    async def valve_load(self):
        """Set valve to load position"""
        pass

    async def valve_inject(self):
        """Set valve to inject position"""
        pass

    async def precolumn_in(self):
        """Set valve to load pre-column in position"""
        pass

    async def precolumn_out(self):
        """Set valve to load pre-column out position"""
        pass

    async def get_flow_control_output(self) -> float:
        """Get the current flow control value"""
        pass

    async def get_flow_signal(self) -> float:
        """Read the current flow"""
        pass

    async def set_flow(self, flow: float):
        """Set the flow target directly"""
        pass

    async def adjust_flow(self, flow: float):
        """Perform a flow adjustment iteration"""
        pass

    async def increment_flow(self, flow: float, multiplier: float):
        """Perform a flow increment in the direction of the multiplier"""
        pass

    async def set_ssv(self, index: int, manual: bool = False):
        """Change the selection valve"""
        pass

    async def set_high_pressure_valve(self, enable: bool):
        """Set the high pressure valve for the currently selected source"""
        pass

    async def ready_gcms(self):
        """Prepare for GC trigger"""
        pass

    async def trigger_gcms(self):
        """Trigger a GC sample"""
        pass

    async def shutdown(self):
        """Perform a shutdown, putting the hardware into a safe mode"""
        pass
