import logging
from gspc.hw.interface import Interface
from gspc.schedule import Runnable, Execute

_LOGGER = logging.getLogger(__name__)


class GCReady(Runnable):
    async def execute(self):
        await self.interface.ready_gcms()


class GCSample(Runnable):
    def __init__(self, interface: Interface, schedule: Execute, origin: float):
        Runnable.__init__(self, interface, schedule, origin)
        self.set_events.add("gc_trigger")

    async def execute(self):
        await self.interface.trigger_gcms()
        _LOGGER.info("GC started")
