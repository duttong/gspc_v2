import pytest
import asyncio

import gspc.schedule


class Runnable(gspc.schedule.Runnable):
    def __init__(self, target, key):
        self._target = target
        self._key = key

    async def execute(self):
        self._target[self._key] = True


class Task(gspc.schedule.Task):
    def __init__(self, target, key):
        self._target = target
        self._key = key

    def schedule(self, interface, runner):
        return [Runnable(self._target, self._key)]


class Parallel(gspc.schedule.Task):
    def __init__(self, target, keys):
        self._target = target
        self._keys = keys

    def schedule(self, interface, runner):
        return [gspc.schedule.RunInParallel(interface, runner, *[Runnable(self._target, key) for key in self._keys])]


def test_schedule_basic():
    ran = dict()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    exe = gspc.schedule.Execute([
        Task(ran, 1),
        Task(ran, 2),
        Task(ran, 3),
        Task(ran, 4),
    ])

    result = loop.run_until_complete(exe.execute(None))

    assert result == True
    assert len(ran) == 4
    assert ran[1] == True
    assert ran[2] == True
    assert ran[3] == True
    assert ran[4] == True


def test_schedule_parallel():
    ran = dict()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    exe = gspc.schedule.Execute([Parallel(ran, [1, 2, 3, 4])])

    result = loop.run_until_complete(exe.execute(None))

    assert result == True
    assert len(ran) == 4
    assert ran[1] == True
    assert ran[2] == True
    assert ran[3] == True
    assert ran[4] == True


class AbortRunnable(gspc.schedule.Runnable):
    def __init__(self, target, key, runner):
        self._target = target
        self._key = key
        self._runner = runner

    async def execute(self):
        self._target[self._key] = True
        await self._runner.abort("message")


class AbortTask(gspc.schedule.Task):
    def __init__(self, target, key):
        self._target = target
        self._key = key

    def schedule(self, interface, runner):
        return [AbortRunnable(self._target, self._key, runner)]


def test_schedule_abort():
    ran = dict()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    exe = gspc.schedule.Execute([
        Task(ran, 1),
        AbortTask(ran, 2),
        Task(ran, 3),
    ])

    result = loop.run_until_complete(exe.execute(None))

    assert result == False
    assert len(ran) == 2
    assert ran[1] == True
    assert ran[2] == True
    assert 3 not in ran
    assert exe.abort_message == "message"
