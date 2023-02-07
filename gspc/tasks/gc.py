import logging
from gspc.hw.interface import Interface
from gspc.schedule import Runnable, Execute

_LOGGER = logging.getLogger(__name__)


class GCReady(Runnable):
    async def execute(self):
        await self.context.interface.ready_gcms()


class GCSample(Runnable):
    def __init__(self, context: Execute.Context, origin: float):
        Runnable.__init__(self, context, origin)
        self.set_events.add("gc_trigger")

    async def execute(self):
        await self.context.interface.trigger_gcms()
        _LOGGER.info("GC started")
