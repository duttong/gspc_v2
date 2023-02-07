import logging
from gspc.hw.interface import Interface
from gspc.schedule import Runnable, Execute

_LOGGER = logging.getLogger(__name__)


class EnableCryogen(Runnable):
    def __init__(self, context: Execute.Context, origin: float):
        Runnable.__init__(self, context, origin)
        self.set_events.add("cyrogen")

    async def execute(self):
        await self.context.interface.set_cryogen(True)
        _LOGGER.info("Activated cyrogen")


class DisableCryogen(Runnable):
    def __init__(self, context: Execute.Context, origin: float):
        Runnable.__init__(self, context, origin)
        self.clear_events.add("cyrogen")

    async def execute(self):
        await self.context.interface.set_cryogen(False)
        _LOGGER.info("Deactivated cyrogen")


class EnableGCCryogen(Runnable):
    def __init__(self, context: Execute.Context, origin: float):
        Runnable.__init__(self, context, origin)
        self.set_events.add("gc_cyrogen")

    async def execute(self):
        await self.context.interface.set_gc_cryogen(True)
        _LOGGER.info("Activated GC cyrogen")


class DisableGCCryogen(Runnable):
    def __init__(self, context: Execute.Context, origin: float):
        Runnable.__init__(self, context, origin)
        self.clear_events.add("gc_cyrogen")

    async def execute(self):
        await self.context.interface.set_gc_cryogen(False)
        _LOGGER.info("Deactivated GC cyrogen")


class CryogenTrapHeaterOn(Runnable):
    async def execute(self):
        _LOGGER.debug("Cyrogen trap heater ON")
        await self.context.interface.set_cryo_heater(True)


class CryogenTrapHeaterOff(Runnable):
    async def execute(self):
        _LOGGER.debug("Cryogen heater OFF")
        await self.context.interface.set_cryo_heater(False)
