import logging
import asyncio
import typing
from gspc.const import CYCLE_SECONDS, SAMPLE_OPEN_AT, SAMPLE_SECONDS
from gspc.hw.interface import Interface
from gspc.schedule import Task, Runnable, Execute

from .sample import *
from .flow import *
from .vacuum import *

_LOGGER = logging.getLogger(__name__)

INITIAL_FLOW = 3
#Changed sample_flow from 7.2 to 7.05 on 11/18/25 to help with high pressure flask flow control during sampling 
#Changed sample_flow from 7.05 to 7.1 on 02/26/26 to help with high pressure flask flow control during sampling 
SAMPLE_FLOW = 7.10
UPPER_SAMPLE_FLOW = 1.3
LOWER_SAMPLE_FLOW = 0.5
LOW_FLOW_THRESHOLD = 0.2


class Flask(Sample):
    def __init__(self, selection):
        Sample.__init__(self)
        self._selection = selection

    def schedule(self, context: Execute.Context,
                 data: typing.Optional[Data] = None) -> typing.List[Runnable]:
        sample_origin = context.origin + SAMPLE_OPEN_AT
        sample_post_origin = context.origin + SAMPLE_OPEN_AT + SAMPLE_SECONDS

        if data is None:
            data = Data()
        data.sample_type = "flask"
        data.ssv_pos = self._selection

        maintain_sample_flow = MaintainFlow(context, sample_origin + 2, sample_post_origin,
                                            SAMPLE_FLOW, LOWER_SAMPLE_FLOW, UPPER_SAMPLE_FLOW)

        async def low_flow_detected():
            """ called if low flow is detected """
            # Increament the flow by a factor of 5.0 = 0.1 volts (the normal step size is 0.02 volts)
            await context.interface.increment_flow(LOWER_SAMPLE_FLOW, 5.0)
            _LOGGER.info(f"Increase flow by increasing pneutroincs 0.1 volts")
            data.low_flow_count += 1

        async def low_flow_mode():
            """ called after low flow is detected twice """
            await maintain_sample_flow.stop()
            await context.interface.set_overflow(False)
            _LOGGER.info("Low flow. Overflow valve OFF")
            data.low_flow = "Y"
            data.low_flow_count += 1

        result = Sample.schedule(self, context, data) + [
            FeedbackFlow(context, context.origin + 71, SAMPLE_FLOW),
            FeedbackFlow(context, context.origin + 123, SAMPLE_FLOW),

            maintain_sample_flow,
            DetectLowFlow(context, sample_origin + 1, sample_post_origin, SAMPLE_FLOW,
                          LOW_FLOW_THRESHOLD, 3.0, low_flow_detected, low_flow_mode),
        ]
        if context.origin > 0.0:
            result += [
                SetSSV(context, context.origin - 814, self._selection),

                SetSSV(context, context.origin - 435, self._selection),
                StaticFlow(context, context.origin - 427, INITIAL_FLOW),     # added 230117
                OverflowOn(context, context.origin - 425),
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
