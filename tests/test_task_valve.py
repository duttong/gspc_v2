import pytest
import asyncio

import gspc.schedule
import gspc.hw.interface
import gspc.tasks.valve


class Interface(gspc.hw.interface.Interface):
    async def select_flask(self, select):
        self.flask = select

    async def select_tank(self, select):
        self.tank = select


class WaitTask(gspc.schedule.Task):
    def schedule(self, interface, schedule):
        return [gspc.tasks.valve.WaitForFlow(interface, schedule, target_flow=1.0)]


class SwitchToFlaskTask(gspc.schedule.Task):
    def schedule(self, interface, schedule):
        return [gspc.tasks.valve.SwitchToFlask(interface, schedule, 1)]


class SwitchToTankTask(gspc.schedule.Task):
    def schedule(self, interface, schedule):
        return [gspc.tasks.valve.SwitchToTank(interface, schedule, 2)]


class FailTask(gspc.schedule.Task):
    def schedule(self, interface, schedule):
        class Fail(gspc.tasks.valve.WaitForFlow):
            MAXIMUM_WAIT_TIME = 1.0

        return [Fail(interface, schedule)]


def test_immediately_ready():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    exe = gspc.schedule.Execute([
        WaitTask(),
        SwitchToFlaskTask(),
        SwitchToTankTask(),
    ])

    interface = Interface()
    interface.sample_flow = 1.0

    result = loop.run_until_complete(exe.execute(interface))

    assert result == True
    assert interface.flask == 1
    assert interface.tank == 2


def test_timed_out():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    exe = gspc.schedule.Execute([
        FailTask(),
    ])

    interface = Interface()
    interface.sample_flow = 100.0

    result = loop.run_until_complete(exe.execute(interface))

    assert result == False
    assert len(exe.abort_message) > 0
