import asyncio
import typing
from abc import ABC, abstractmethod


class Interface(ABC):
    """The abstract interface to the hardware control"""

    def __init__(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

        self.sample_flow_zero_offset: float = -1.45

    @abstractmethod
    async def get_pressure(self) -> float:
        """Read the current pressure"""
        pass

    @abstractmethod
    async def get_pfp_pressure(self, ssv_index: typing.Optional[int] = None) -> float:
        """Read the current PFP pressure"""
        pass

    @abstractmethod
    async def get_display_pfp_pressure(self) -> float:
        """Read the current PFP pressure for display"""
        pass

    @abstractmethod
    async def get_oven_temperature_signal(self) -> float:
        """Read the current oven temperature signal"""
        pass

    @abstractmethod
    async def set_cryogen(self, enable: bool):
        """Set the cryogen control state"""
        pass

    @abstractmethod
    async def set_gc_cryogen(self, enable: bool):
        """Set the GC cryogen control state"""
        pass

    @abstractmethod
    async def set_vacuum(self, enable: bool):
        """Set the evac vacuum"""
        pass

    @abstractmethod
    async def set_sample(self, enable: bool):
        """Set the sample valve"""
        pass

    @abstractmethod
    async def set_cryo_heater(self, enable: bool):
        """Set the GC heater"""
        pass

    @abstractmethod
    async def set_overflow(self, enable: bool):
        """Set the overflow valve"""
        pass

    @abstractmethod
    async def valve_load(self):
        """Set valve to load position"""
        pass

    @abstractmethod
    async def valve_inject(self):
        """Set valve to inject position"""
        pass

    @abstractmethod
    async def precolumn_in(self):
        """Set valve to load pre-column in position"""
        pass

    @abstractmethod
    async def precolumn_out(self):
        """Set valve to load pre-column out position"""
        pass

    @abstractmethod
    async def get_flow_control_output(self) -> float:
        """Get the current flow control value"""
        pass

    @abstractmethod
    async def get_flow_signal(self) -> float:
        """Read the current flow"""
        pass

    @abstractmethod
    async def set_flow(self, flow: float):
        """Set the flow target directly"""
        pass

    @abstractmethod
    async def adjust_flow(self, flow: float):
        """Perform a flow adjustment iteration"""
        pass

    @abstractmethod
    async def increment_flow(self, flow: float, multiplier: float):
        """Perform a flow increment in the direction of the multiplier"""
        pass

    @abstractmethod
    async def get_ssv_cp(self) -> int:
        """ Read current SSV position """
        pass

    @abstractmethod
    async def set_ssv(self, index: int, manual: bool = False):
        """Change the selection valve"""
        pass

    @abstractmethod
    async def set_high_pressure_valve(self, enable: bool):
        """Set the high pressure valve for the currently selected source"""
        pass

    @abstractmethod
    async def set_evacuation_valve(self, enable: bool):
        """Set the evacuation valve for the currently selected source"""
        pass

    @abstractmethod
    async def ready_gcms(self):
        """Prepare for GC trigger"""
        pass

    @abstractmethod
    async def trigger_gcms(self):
        """Trigger a GC sample"""
        pass

    @abstractmethod
    async def set_pfp_valve(self, ssv_index:  typing.Optional[int], pfp_valve: int, set_open: bool) -> str:
        """Set the PFP valve (open or close)"""
        pass

    async def shutdown(self):
        """Perform a shutdown, putting the hardware into a safe mode"""
        pass
