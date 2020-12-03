import asyncio
import typing
import types


class Interface:
    """The abstract interface to the hardware control"""

    def __init__(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

        self.sample_flow_zero_offset: float = 0.0

    async def get_pressure(self) -> float:
        """Read the current pressure"""
        pass

    async def get_oven_temperature(self) -> float:
        """Read the current oven temperature"""
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

    async def set_gc_solenoid(self, enable: bool):
        """Set the GC solenoid"""
        pass

    async def set_gc_heater(self, enable: bool):
        """Set the GC heater"""
        pass

    async def set_overflow(self, enable: bool):
        """Set the overflow valve"""
        pass

    async def set_load(self, enable: bool):
        """Set the load valve"""
        pass

    async def precolumn_in(self):
        """Put the pre-column in line"""
        pass

    async def precolumn_out(self):
        """Put the pre-column out of line"""
        pass

    async def get_flow_control_output(self) -> float:
        """Get the current flow control value"""
        pass

    async def get_flow(self) -> float:
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

    async def select_source(self, index: int, manual: bool = False):
        """Change the selection valve"""
        pass

    async def set_high_pressure_valve(self, enable: bool):
        """Set the high pressure valve for the currently selected source"""
        pass

    async def ready_gc(self):
        """Prepare for GC trigger"""
        pass

    async def trigger_gc(self):
        """Trigger a GC sample"""
        pass

    async def shutdown(self):
        """Perform a shutdown, putting the hardware into a safe mode"""
        pass
