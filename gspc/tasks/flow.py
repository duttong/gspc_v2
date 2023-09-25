import logging
import asyncio
import time
import math
import typing
from gspc.hw.interface import Interface
from gspc.schedule import Runnable, Execute, AbortPoint

_LOGGER = logging.getLogger(__name__)


class ZeroFlow(Runnable):
    def __init__(self, context: Execute.Context, origin: float, duration: float = 20.0):
        Runnable.__init__(self, context, origin)
        self._duration = duration

    async def execute(self):
        self.context.interface.sample_flow_zero_offset = 0.0
        end_time = time.time() + self._duration
        flow_sum = 0.0
        flow_count = 0
        while time.time() <= end_time:
            flow = await self.context.interface.get_flow_signal()
            if flow is not None:
                flow_sum += flow
                flow_count += 1
            await asyncio.sleep(1)
        if flow_sum <= 0:
            return
        zero_flow = flow_sum / flow_count
        self.context.interface.sample_flow_zero_offset = -zero_flow
        _LOGGER.info(f"Measured zero flow as {zero_flow:.2f}")


class FullFlow(Runnable):
    def __init__(self, context: Execute.Context, origin: float):
        Runnable.__init__(self, context, origin)

    async def execute(self):
        await self.context.interface.set_flow(math.inf)
        _LOGGER.info(f"Set flow to fully open")


class StaticFlow(Runnable):
    def __init__(self, context: Execute.Context, origin: float, flow: float):
        Runnable.__init__(self, context, origin)
        self._flow = flow

    async def execute(self):
        await self.context.interface.set_flow(self._flow)
        _LOGGER.info(f"Set flow to {self._flow:.2f}")


class CheckNegativeFlow(Runnable):
    def __init__(self, context: Execute.Context, origin: float,
                 abort_point: typing.Optional[AbortPoint] = None):
        Runnable.__init__(self, context, origin)
        self._abort_point = abort_point

    async def execute(self):
        measured_flow = await self.context.interface.get_flow_signal()
        if measured_flow >= 0.0:
            return
        await self.context.interface.set_overflow(False)
        _LOGGER.info(f"Sample flow rate ({measured_flow}) less than zero, cycle will abort")
        if self._abort_point:
            await self._abort_point.abort("Negative sample flow")
        else:
            await self.context.schedule.abort("Negative sample flow")


class FeedbackFlow(Runnable):
    DEADBAND = 0.15
    SETTLING_TIME = 0.3

    def __init__(self, context: Execute.Context, origin: float, flow: float):
        Runnable.__init__(self, context, origin)
        self._flow = flow

    async def execute(self):
        await self.context.interface.set_flow(self._flow)

        for iteration in range(15):
            if abs(await self.context.interface.get_flow_signal() - self._flow) <= self.DEADBAND:
                return
            await self.context.interface.adjust_flow(self._flow)
            await asyncio.sleep(self.SETTLING_TIME)
        _LOGGER.warning(f"Flow control feedback failed")


class MaintainFlow(Runnable):
    def __init__(self, context: Execute.Context, origin: float, end: float, flow: float,
                 lower: typing.Optional[float] = None, upper: typing.Optional[float] = None):
        Runnable.__init__(self, context, origin)
        self._duration = end - origin
        self._flow = flow
        self._lower = lower
        self._upper = upper
        self._stopped = False

    async def execute(self):
        end_time = time.time() + self._duration
        while time.time() <= end_time and not self._stopped:
            measured_flow = await self.context.interface.get_flow_signal()
            if self._lower is not None and measured_flow < self._lower:
                await self.context.interface.increment_flow(self._flow, 1.0)
                _LOGGER.info(f"Increased flow")
            elif self._upper is not None and measured_flow > self._upper:
                await self.context.interface.increment_flow(self._flow, -1.0)
                _LOGGER.info(f"Decreased flow")
            await asyncio.sleep(1)

    async def stop(self):
        self._stopped = True


class DetectLowFlow(Runnable):
    TRIGGER_SECONDS = 2

    def __init__(self, context: Execute.Context, origin: float, end: float,
                 flow: float, threshold: float,
                 increment: typing.Optional[float] = None,
                 low_flow_detected: typing.Optional[typing.Callable[[], typing.Awaitable[None]]] = None,
                 low_flow_mode: typing.Optional[typing.Callable[[], typing.Awaitable[None]]] = None):
        Runnable.__init__(self, context, origin)
        self._duration = end - origin
        self._flow = flow
        self._threshold = threshold
        self._increment = increment
        self._low_flow_detected = low_flow_detected
        self._low_flow_mode = low_flow_mode

    async def execute(self):
        end_time = time.time() + self._duration
        low_begin_time = None
        while time.time() <= end_time:
            measured_flow = await self.context.interface.get_flow_signal()
            if measured_flow < self._threshold:
                # tries to adjust flow if that doesn't work runs the self._low_flow_mode method.
                if low_begin_time is None:
                    low_begin_time = time.time()
                    if self._increment is not None:
                        await self.context.interface.increment_flow(self._flow, self._increment)
                    if self._low_flow_detected is not None:
                        await self._low_flow_detected()
                    _LOGGER.info(f"Low flow detected")
                elif time.time() - low_begin_time >= self.TRIGGER_SECONDS:
                    if self._low_flow_mode is not None:
                        await self._low_flow_mode()
                    _LOGGER.info(f"Extended low flow detected")
                    return
            else:
                low_begin_time = None
            await asyncio.sleep(1)


class RecordLastFlow(Runnable):
    def __init__(self, context: Execute.Context, origin: float,
                 record: typing.Callable[[float, float], None]):
        Runnable.__init__(self, context, origin)
        self._record = record

    async def execute(self):
        self._record(await self.context.interface.get_flow_signal(),
                     await self.context.interface.get_flow_control_output())
