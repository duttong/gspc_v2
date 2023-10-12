import logging
import asyncio
import typing
from gspc.const import CYCLE_SECONDS, SAMPLE_OPEN_AT, SAMPLE_SECONDS
from gspc.hw.interface import Interface
from gspc.schedule import Task, Runnable, Execute

from .sample import *
from .flow import *
from .vacuum import *

INITIAL_FLOW = 3
SAMPLE_FLOW = 7.2
UPPER_SAMPLE_FLOW = 1.3
LOWER_SAMPLE_FLOW = 0.5
LOW_FLOW_THRESHOLD = 0.2


class Flask(Sample):
    def __init__(self, selection):
        Sample.__init__(self)
        self._selection = selection

    def schedule(self, context: Execute.Context,
                 data: typing.Optional[Data] = None) -> typing.List[Runnable]:
        sample_origin = context.origin + SAMPLE_OPEN_AT + 2
        sample_post_origin = context.origin + SAMPLE_OPEN_AT + SAMPLE_SECONDS

        if data is None:
            data = Data()
        data.sample_type = "flask"
        data.ssv_pos = self._selection

        maintain_sample_flow = MaintainFlow(context, sample_origin, sample_post_origin,
                                            SAMPLE_FLOW, LOWER_SAMPLE_FLOW, UPPER_SAMPLE_FLOW)

        async def low_flow_detected():
            """ called if low flow is detected """
            data.low_flow_count += 1

        async def low_flow_mode():
            """ called after low flow is detected twice """
            await maintain_sample_flow.stop()
            await context.interface.set_overflow(False)
            data.low_flow = "Y"
            data.low_flow_count += 1

        result = Sample.schedule(self, context, data) + [
            StaticFlow(context, context.origin + 69, SAMPLE_FLOW),
            FeedbackFlow(context, context.origin + 71, SAMPLE_FLOW),
            FeedbackFlow(context, context.origin + 111, SAMPLE_FLOW),
            FeedbackFlow(context, context.origin + 123, SAMPLE_FLOW),

            # this is happing at the same time as FeedbackFlow + 123
            #MaintainFlow(context, context.origin + 111, sample_origin,
            #             SAMPLE_FLOW, LOWER_SAMPLE_FLOW),
            maintain_sample_flow,
            DetectLowFlow(context, sample_origin + 1, sample_post_origin, SAMPLE_FLOW,
                          LOW_FLOW_THRESHOLD, 3.0, low_flow_detected, low_flow_mode),

            # Redundant? appears to always happen
            # same call in sample.py at +3. Yes, it's redundant
            # OverflowOff(context, sample_post_origin + 4),
        ]
        if context.origin > 0.0:
            result += [
                SetSSV(context, context.origin - 814, self._selection),

                SetSSV(context, context.origin - 435, self._selection),
                OverflowOn(context, context.origin - 420),
                FeedbackFlow(context, context.origin - 420, INITIAL_FLOW),
                OverflowOff(context, context.origin - 350),

                OverflowOn(context, context.origin - 180),
                OverflowOff(context, context.origin - 130),

                FeedbackFlow(context, context.origin + 6, SAMPLE_FLOW),
            ]
        else:
            result += [
                HighPressureOff(context, context.origin),
                SetSSV(context, context.origin, self._selection),
                OverflowOn(context, context.origin + 9),

                FeedbackFlow(context, context.origin + 10, INITIAL_FLOW),
            ]
        return result
