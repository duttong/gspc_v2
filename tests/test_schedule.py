import pytest
import asyncio
import math
import gspc.schedule


class BasicRunnable(gspc.schedule.Runnable):
    def __init__(self, context: gspc.schedule.Execute.Context, origin: float, target, key, events: dict=dict()):
        gspc.schedule.Runnable.__init__(self, context, origin)
        self._target = target
        self._key = key
        for event, sc in events.items():
            if sc:
                self.set_events.add(event)
            else:
                self.clear_events.add(event)

    async def execute(self):
        self._target[self._key] = True


class BasicTask(gspc.schedule.Task):
    def __init__(self, target, key, origin_advance: float = 0.01, events=dict(), origin_offset: float = 0):
        gspc.schedule.Task.__init__(self, origin_advance)
        self._target = target
        self._key = key
        self._events = events
        self._origin_offset = origin_offset

    def schedule(self, context: gspc.schedule.Execute.Context):
        return [BasicRunnable(context, context.origin + self._origin_offset, self._target, self._key, self._events)]


def test_schedule_basic():
    ran = dict()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    exe = gspc.schedule.Execute([
        BasicTask(ran, 1),
        BasicTask(ran, 2),
        BasicTask(ran, 3),
        BasicTask(ran, 4),
    ])

    result = loop.run_until_complete(exe.execute(None))

    assert result == True
    assert len(ran) == 4
    assert ran[1] == True
    assert ran[2] == True
    assert ran[3] == True
    assert ran[4] == True


class GateRunnable(gspc.schedule.Runnable):
    def __init__(self, context: gspc.schedule.Execute.Context, origin: float, target, key, gate):
        gspc.schedule.Runnable.__init__(self, context, origin)
        self._target = target
        self._key = key
        self._gate = gate

    async def execute(self):
        self._target[self._key] = self._key
        self._gate()


class GateTask(gspc.schedule.Task):
    def __init__(self, target, origin_advance: float = 0):
        gspc.schedule.Task.__init__(self, origin_advance)
        self._target = target

    def schedule(self, context: gspc.schedule.Execute.Context):
        gate = gspc.schedule.Gate(context, context.origin+0.01)
        return [
            GateRunnable(context, context.origin, self._target, 1, gate.add_gate()),
            GateRunnable(context, context.origin, self._target, 2, gate.add_gate()),
            GateRunnable(context, context.origin, self._target, 3, gate.add_gate()),
            gate,
            BasicRunnable(context, context.origin+0.02, self._target, 3),
            BasicRunnable(context, context.origin+0.02, self._target, 4),
        ]


def test_schedule_gate():
    ran = dict()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    exe = gspc.schedule.Execute([
        GateTask(ran),
    ])

    result = loop.run_until_complete(exe.execute(None))

    assert result == True
    assert len(ran) == 4
    assert ran[1] == 1
    assert ran[2] == 2
    assert ran[3] == True
    assert ran[4] == True


class EventRunnable(gspc.schedule.Runnable):
    def __init__(self, context: gspc.schedule.Execute.Context, origin: float, event: str, occurred: bool):
        gspc.schedule.Runnable.__init__(self, context, origin)
        self._event = event
        self._occurred = occurred

    async def execute(self):
        if self._occurred is None:
            assert self._event not in self.context.schedule.events
        else:
            assert self.context.schedule.events[self._event].occurred == self._occurred


class EventTask(gspc.schedule.Task):
    def __init__(self, event: str, occurred: bool):
        gspc.schedule.Task.__init__(self)
        self._event = event
        self._occurred = occurred

    def schedule(self, context: gspc.schedule.Execute.Context):
        return [EventRunnable(context, context.origin, self._event, self._occurred)]


def test_schedule_events():
    ran = dict()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    exe = gspc.schedule.Execute([
        BasicTask(ran, 1, events={'e1': True}),
        EventTask('e1', True),
        EventTask('e2', False),
        BasicTask(ran, 2, events={'e2': True}),
        EventTask('e1', True),
        EventTask('e2', True),
        BasicTask(ran, 3, events={'e2': False}),
        EventTask('e1', True),
        EventTask('e2', None),
        BasicTask(ran, 4),
    ])

    result = loop.run_until_complete(exe.execute(None))

    assert result == True
    assert len(ran) == 4
    assert ran[1] == True
    assert ran[2] == True
    assert ran[3] == True
    assert ran[4] == True


class AbortRunnable(BasicRunnable):
    def __init__(self, context: gspc.schedule.Execute.Context,
                 origin: float, target, key, abort: gspc.schedule.AbortPoint, message):
        BasicRunnable.__init__(self, context, origin, target, key)
        self._abort = abort
        self._message = message

    async def execute(self):
        await BasicRunnable.execute(self)
        await self._abort.abort(self._message)


class AbortTask(gspc.schedule.Task):
    def __init__(self, target, key, message):
        gspc.schedule.Task.__init__(self, 0.01)
        self._target = target
        self._key = key
        self._message = message

    def schedule(self, context: gspc.schedule.Execute.Context):
        abort = gspc.schedule.AbortPoint(context, context.origin+0.02)
        return [
            AbortRunnable(context, context.origin, self._target, self._key, abort, self._message),
            abort,
        ]


def test_schedule_abort():
    ran = dict()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    exe = gspc.schedule.Execute([
        BasicTask(ran, 1),
        AbortTask(ran, 2, "message"),
        BasicTask(ran, 3),
        BasicTask(ran, 4),
        AbortTask(ran, 5, "missed"),
    ])

    should_not_set = False

    async def abort_task():
        await asyncio.sleep(10)
        nonlocal should_not_set
        should_not_set = True

    abort_task = loop.create_task(exe.start_background(abort_task()))
    result = loop.run_until_complete(exe.execute(None))

    assert result == False
    assert should_not_set == False
    assert len(ran) == 3
    assert ran[1] == True
    assert ran[2] == True
    assert ran[3] == True
    assert 4 not in ran
    assert 5 not in ran
    assert exe.abort_message == "message"


class BreakTask(gspc.schedule.Task):
    def __init__(self):
        gspc.schedule.Task.__init__(self, 1.0)
        self.reached = asyncio.Future()
        self.resume = asyncio.Future()

    class _Reached(gspc.schedule.Runnable):
        def __init__(self, context: gspc.schedule.Execute.Context, origin: float, reached):
            gspc.schedule.Runnable.__init__(self, context, origin)
            self.reached = reached

        async def execute(self):
            self.reached.set_result(True)

    class _Resume(gspc.schedule.Runnable):
        def __init__(self, context: gspc.schedule.Execute.Context, origin: float, resume):
            gspc.schedule.Runnable.__init__(self, context, origin)
            self.resume = resume

        async def execute(self):
            await self.resume

    def schedule(self, context: gspc.schedule.Execute.Context):
        return [
            self._Reached(context, context.origin, self.reached),
            self._Resume(context, context.origin + 1.0, self.resume),
        ]


def test_reschedule():
    ran = dict()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    mid = BreakTask()
    exe = gspc.schedule.Execute([
        BasicTask(ran, 1),
        BasicTask(ran, 2),
        mid,
        BasicTask(ran, 3),
        BasicTask(ran, 98),
        BasicTask(ran, 99),
    ])

    async def reschedule_execute():
        await mid.reached
        await asyncio.wait_for(exe.reschedule(remove=4, append=[
            BasicTask(ran, 4),
            BasicTask(ran, 5),
            BasicTask(ran, 6),
        ]), timeout=2.0)
        mid.resume.set_result(True)

    op = loop.create_task(reschedule_execute())
    result = loop.run_until_complete(exe.execute(None))
    loop.run_until_complete(op)

    assert result == True
    assert len(ran) == 6
    assert ran[1] == True
    assert ran[2] == True
    assert ran[3] == True
    assert ran[4] == True
    assert ran[5] == True
    assert ran[6] == True
    assert ran.get(98) is None
    assert ran.get(99) is None


def test_reschedule_fail_modify_past():
    ran = dict()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    mid = BreakTask()
    exe = gspc.schedule.Execute([
        BasicTask(ran, 1),
        BasicTask(ran, 2),
        mid,
        BasicTask(ran, 3),
    ])

    reschedule_exception = False

    async def reschedule_execute():
        nonlocal reschedule_exception
        await mid.reached
        try:
            await asyncio.wait_for(exe.reschedule(remove=1), timeout=2.0)
        except gspc.schedule.Execute.RescheduleFailure:
            reschedule_exception = True
        mid.resume.set_result(True)

    op = loop.create_task(reschedule_execute())
    result = loop.run_until_complete(exe.execute(None))
    loop.run_until_complete(op)

    assert result == True
    assert len(ran) == 3
    assert ran[1] == True
    assert ran[2] == True
    assert ran[3] == True
    assert reschedule_exception


def test_reschedule_fail_add_passed():
    ran = dict()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    mid = BreakTask()
    exe = gspc.schedule.Execute([
        BasicTask(ran, 1),
        BasicTask(ran, 2),
        mid,
        BasicTask(ran, 3),
    ])

    reschedule_exception = False

    async def reschedule_execute():
        nonlocal reschedule_exception
        await mid.reached
        try:
            await asyncio.wait_for(exe.reschedule(append=[
                BasicTask(ran, 99, origin_offset=-10.0),
            ]), timeout=2.0)
        except gspc.schedule.Execute.RescheduleFailure:
            reschedule_exception = True
        mid.resume.set_result(True)

    op = loop.create_task(reschedule_execute())
    result = loop.run_until_complete(exe.execute(None))
    loop.run_until_complete(op)

    assert result == True
    assert len(ran) == 3
    assert ran[1] == True
    assert ran[2] == True
    assert ran[3] == True
    assert reschedule_exception