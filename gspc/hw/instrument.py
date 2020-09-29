import asyncio
from .interface import Interface
from .lj import LabJack
from .omega import Flow


class Instrument(Interface):
    def __init__(self, loop: asyncio.AbstractEventLoop):
        Interface.__init__(self, loop)

        self._lj = LabJack()
        self._flow = Flow()

        loop.create_task(self._update_flow())
        loop.create_task(self._update_temperature())
        loop.create_task(self._update_pressure())

    async def _update_flow(self):
        while True:
            self.sample_flow = await self._flow.get_sp1()
            await asyncio.sleep(1)

    async def _update_temperature(self):
        while True:
            self.sample_flow = (await self._lj.read_analog(1)) * 100.0
            await asyncio.sleep(1)

    async def _update_pressure(self):
        while True:
            self.sample_temperature = (await self._lj.read_analog(1)) * 100.0
            await asyncio.sleep(1)

    async def select_flask(self, select):
        for i in range(1, 16):
            await self._lj.write_digital(i, i == select)

    async def unselect_flask(self):
        for i in range(1, 16):
            await self._lj.write_digital(i, False)

    async def select_tank(self, select):
        for i in range(1, 16):
            await self._lj.write_digital(i + 16, i == select)

    async def unselect_tank(self):
        for i in range(1, 16):
            await self._lj.write_digital(i + 16, False)

    async def set_target_flow(self, flow: float):
        await self._flow.set_sp1(flow)

    async def begin_flask_sample(self, select):
        await self._lj.write_digital(0, True)
        await asyncio.sleep(0.25)
        await self._lj.write_digital(0, False)

    async def begin_tank_sample(self, select):
        await self._lj.write_digital(0, True)
        await asyncio.sleep(0.25)
        await self._lj.write_digital(0, False)

    async def shutdown(self):
        for i in range(0, 32):
            await self._lj.write_digital(i, False)
        await self._flow.set_sp1(0)
