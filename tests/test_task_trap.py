import pytest
import asyncio

import gspc.schedule
import gspc.hw.interface
import gspc.tasks.trap


class Interface(gspc.hw.interface.Interface):
    pass


class WaitTask(gspc.schedule.Task):
    def schedule(self, interface, schedule):
        return [gspc.tasks.trap.WaitForCooled(interface, schedule)]


class FailTask(gspc.schedule.Task):
    def schedule(self, interface, schedule):
        class Fail(gspc.tasks.trap.WaitForCooled):
            MAXIMUM_WAIT_TIME = 1.0

        return [Fail(interface, schedule)]


def test_immediately_ready():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    exe = gspc.schedule.Execute([
        WaitTask(),
    ])

    interface = Interface()
    interface.trap_temperature = -273

    result = loop.run_until_complete(exe.execute(interface))

    assert result == True


def test_timed_out():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    exe = gspc.schedule.Execute([
        FailTask(),
    ])

    interface = Interface()
    interface.trap_temperature = 100

    result = loop.run_until_complete(exe.execute(interface))

    assert result == False
    assert len(exe.abort_message) > 0
