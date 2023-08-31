import logging
import asyncio
import typing
from gspc.const import CYCLE_SECONDS, SAMPLE_OPEN_AT, SAMPLE_SECONDS
from gspc.hw.interface import Interface
from gspc.schedule import Task, Runnable, Execute

from .sample import *
from .flow import *
from .valve import *

LOW_FLOW_THRESHOLD = 0.2


class Tank(Sample):
    def __init__(self, selection):
        Sample.__init__(self)
        self._selection = selection

    def schedule(self, context: Execute.Context, data: typing.Optional[Data] = None) -> typing.List[Runnable]:
        sample_origin = context.origin + SAMPLE_OPEN_AT
        sample_post_origin = context.origin + SAMPLE_OPEN_AT + SAMPLE_SECONDS

        if data is None:
            data = Data()
        data.sample_type = "tank"
        data.ssv_pos = self._selection

        async def low_flow_detected():
            """ called if low flow is detected """
            data.low_flow_count += 1

        async def low_flow_mode():
            """ called after low flow is detected twice """
            await context.interface.set_overflow(False)
            data.low_flow = "Y"
            data.low_flow_count += 1

        result = Sample.schedule(self, context, data) + [
            FullFlow(context, context.origin + 69),

            DetectLowFlow(context, sample_origin + 1, sample_post_origin, math.inf,
                          LOW_FLOW_THRESHOLD, None, low_flow_detected, low_flow_mode),

            # Redundant? appears to always happen
            # OverflowOff(context, sample_post_origin + 4),
        ]
        if context.origin > 0.0:
            result += [
                SetSSV(context, context.origin - 814, self._selection),
                FullFlow(context, context.origin - 813),

                SetSSV(context, context.origin - 435, self._selection),
                FullFlow(context, context.origin - 425),

                FullFlow(context, context.origin - 185),
                OverflowOn(context, context.origin - 180),
                HighPressureOn(context, context.origin - 180),
            ]
        else:
            result += [
                SetSSV(context, context.origin, self._selection),
                OverflowOn(context, context.origin + 9),
                HighPressureOn(context, context.origin + 10),
            ]
        return result
