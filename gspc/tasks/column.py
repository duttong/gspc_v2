import logging
import asyncio
from gspc.schedule import Runnable

_LOGGER = logging.getLogger(__name__)


class PreColumnIn(Runnable):
    async def execute(self):
        await self.schedule.start_background(self.interface.precolumn_in())
        _LOGGER.info("Pre column in line")


class PreColumnOut(Runnable):
    async def execute(self):
        await self.schedule.start_background(self.interface.precolumn_out())
        _LOGGER.info("Pre column out of line")
