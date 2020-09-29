import asyncio

class Interface:
    """The abstract interface to the hardware control"""

    def __init__(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

        self.trap_temperature = None
        self.sample_flow = None
        self.sample_temperature = None

    async def select_flask(self, select):
        """Select a flask for sampling."""
        pass

    async def unselect_flask(self):
        """Unselect sampling from any flask."""
        pass

    async def select_tank(self, select):
        """Select a tank for sampling."""
        pass

    async def unselect_tank(self):
        """Unselect sampling from any tank."""
        pass

    async def set_target_flow(self, flow: float):
        """Unselect sampling from any tank."""
        pass

    async def begin_flask_sample(self, select):
        """Tell the sampling instrument to collect a measurement."""
        pass

    async def begin_tank_sample(self, select):
        """Tell the sampling instrument to collect a measurement."""
        pass

    async def shutdown(self):
        """Perform a shutdown, putting the hardware into a safe mode"""
        pass
