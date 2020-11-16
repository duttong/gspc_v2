import logging
from gspc.hw.interface import Interface
from gspc.schedule import Runnable, Execute

_LOGGER = logging.getLogger(__name__)


class GCReady(Runnable):
    async def execute(self):
        await self.interface.ready_gc()


class GCSample(Runnable):
    def __init__(self, interface: Interface, schedule: Execute, origin: float):
        Runnable.__init__(self, interface, schedule, origin)
        self.set_events.add("gc_trigger")

    async def execute(self):
        await self.interface.trigger_gc()
        _LOGGER.info("GC started")


class GCSolenoidOn(Runnable):
    async def execute(self):
        _LOGGER.debug("GC solenoid ON")
        await self.interface.set_gc_solenoid(True)


class GCSolenoidOff(Runnable):
    async def execute(self):
        _LOGGER.debug("GC solenoid OFF")
        await self.interface.set_gc_solenoid(False)


class GCHeaterOn(Runnable):
    async def execute(self):
        _LOGGER.debug("GC heater ON")
        await self.interface.set_gc_heater(True)


class GCHeaterOff(Runnable):
    async def execute(self):
        _LOGGER.debug("GC heater OFF")
        await self.interface.set_gc_heater(False)
