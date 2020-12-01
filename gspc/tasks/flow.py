import logging
import asyncio
import time
import math
import typing
import types
from gspc.hw.interface import Interface
from gspc.schedule import Runnable, Execute

_LOGGER = logging.getLogger(__name__)


class ZeroFlow(Runnable):
    def __init__(self, interface: Interface, schedule: Execute, origin: float, duration: float = 20.0):
        Runnable.__init__(self, interface, schedule, origin)
        self._duration = duration

    async def _zero_flow(self):
        self.interface.sample_flow_zero_offset = 0
        end_time = time.time() + self._duration
        flow_sum = 0.0
        flow_count = 0
        while time.time() <= end_time:
            flow = await self.interface.get_flow()
            if flow is not None:
                flow_sum += flow
                flow_count += 1
            await asyncio.sleep(1)
        if flow_sum <= 0:
            return
        zero_flow = flow_sum / flow_count
        self.interface.sample_flow_zero_offset = -zero_flow
        _LOGGER.info(f"Measured zero flow as {zero_flow:.1f}")

    async def execute(self):
        await self.schedule.start_background(self._zero_flow())


class FullFlow(Runnable):
    def __init__(self, interface: Interface, schedule: Execute, origin: float):
        Runnable.__init__(self, interface, schedule, origin)

    async def execute(self):
        await self.interface.set_flow(math.inf)
        _LOGGER.info(f"Set flow to fully open")


class StaticFlow(Runnable):
    def __init__(self, interface: Interface, schedule: Execute, origin: float, flow: float):
        Runnable.__init__(self, interface, schedule, origin)
        self._flow = flow

    async def execute(self):
        await self.interface.set_flow(self._flow)
        _LOGGER.info(f"Set flow to {self._flow:.1f}")


class FeedbackFlow(Runnable):
    DEADBAND = 0.15
    SETTLING_TIME = 0.3

    def __init__(self, interface: Interface, schedule: Execute, origin: float, flow: float):
        Runnable.__init__(self, interface, schedule, origin)
        self._flow = flow

    async def _feedback_loop(self):
        for iteration in range(15):
            if abs(await self.interface.get_flow() - self._flow) <= self.DEADBAND:
                return
            await self.interface.adjust_flow(self._flow)
            await asyncio.sleep(self.SETTLING_TIME)
        _LOGGER.warning(f"Flow control feedback failed")

    async def execute(self):
        await self.interface.set_flow(self._flow)
        await self.schedule.start_background(self._feedback_loop())
        _LOGGER.info(f"Setting flow to {self._flow:.1f} with feedback")


class MaintainFlow(Runnable):
    def __init__(self, interface: Interface, schedule: Execute, origin: float, end: float, flow: float,
                 lower: typing.Optional[float] = None, upper: typing.Optional[float] = None):
        Runnable.__init__(self, interface, schedule, origin)
        self._duration = end - origin
        self._flow = flow
        self._lower = lower
        self._upper = upper
        self._stopped = False

    async def _monitor_flow(self):
        end_time = time.time() + self._duration
        while time.time() <= end_time and not self._stopped:
            measured_flow = await self.interface.get_flow()
            if self._lower is not None and measured_flow < self._lower:
                await self.interface.increment_flow(self._flow, 1.0)
                _LOGGER.info(f"Increased flow")
            elif self._upper is not None and measured_flow > self._upper:
                await self.interface.increment_flow(self._flow, -1.0)
                _LOGGER.info(f"Decreased flow")
            await asyncio.sleep(1)

    async def execute(self):
        await self.schedule.start_background(self._monitor_flow())

    async def stop(self):
        self._stopped = True


class DetectLowFlow(Runnable):
    TRIGGER_SECONDS = 2

    def __init__(self, interface: Interface, schedule: Execute, origin: float, end: float,
                 flow: float, threshold: float,
                 increment: typing.Optional[float] = None,
                 cancel: typing.Optional[typing.Callable[[], typing.Awaitable[None]]] = None):
        Runnable.__init__(self, interface, schedule, origin)
        self._duration = end - origin
        self._flow = flow
        self._threshold = threshold
        self._increment = increment
        self._cancel = cancel

    async def _monitor_flow(self):
        end_time = time.time() + self._duration
        low_begin_time = None
        while time.time() <= end_time:
            measured_flow = await self.interface.get_flow()
            if measured_flow < self._threshold:
                if low_begin_time is None:
                    low_begin_time = time.time()
                    if self._increment is not None:
                        await self.interface.increment_flow(self._flow, self._increment)
                    _LOGGER.info(f"Low flow detected")
                elif time.time() - low_begin_time >= self.TRIGGER_SECONDS:
                    if self._cancel is not None:
                        await self._cancel()
                    _LOGGER.info(f"Extended low flow detected")
                    return
            else:
                low_begin_time = None
            await asyncio.sleep(1)

    async def execute(self):
        await self.schedule.start_background(self._monitor_flow())


class RecordFlow(Runnable):
    def __init__(self, interface: Interface, schedule: Execute, origin: float):
        Runnable.__init__(self, interface, schedule, origin)

    async def execute(self):
        flow = await self.interface.get_flow()
        # Warning NYI
