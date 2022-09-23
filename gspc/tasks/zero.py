import logging
import asyncio
import typing
from gspc.const import CYCLE_SECONDS, SAMPLE_OPEN_AT, SAMPLE_SECONDS
from gspc.hw.interface import Interface
from gspc.schedule import Task, Runnable, Execute

from .sample import *
from .flow import *
from .vacuum import *

INITIAL_FLOW = 6.9
SAMPLE_FLOW = 7.2
UPPER_SAMPLE_FLOW = 1.3
LOWER_SAMPLE_FLOW = 0.5
LOW_FLOW_THRESHOLD = 0.2


class Zero(Sample):
    def schedule(self, interface: Interface, schedule: Execute, origin: float,
                 data: typing.Optional[Data] = None) -> typing.List[Runnable]:
        sample_origin = origin + SAMPLE_OPEN_AT
        sample_post_origin = origin + SAMPLE_OPEN_AT + SAMPLE_SECONDS

        if data is None:
            data = Data()
        data.sample_type = "zero"

        maintain_sample_flow = MaintainFlow(interface, schedule, sample_origin, sample_post_origin,
                                            SAMPLE_FLOW, LOWER_SAMPLE_FLOW, UPPER_SAMPLE_FLOW)

        async def low_flow_detected():
            await maintain_sample_flow.stop(),
            await interface.set_vacuum(False)
            data.low_flow = "Y"

        result = Sample.schedule(self, interface, schedule, origin, data) + [
            StaticFlow(interface, schedule, origin + 69, SAMPLE_FLOW),
            FeedbackFlow(interface, schedule, origin + 71, SAMPLE_FLOW),
            FeedbackFlow(interface, schedule, origin + 111, SAMPLE_FLOW),
            FeedbackFlow(interface, schedule, origin + 123, SAMPLE_FLOW),

            MaintainFlow(interface, schedule, origin + 111, sample_origin,
                         SAMPLE_FLOW, LOWER_SAMPLE_FLOW),
            maintain_sample_flow,
            DetectLowFlow(interface, schedule, sample_origin + 1, sample_post_origin, SAMPLE_FLOW,
                          LOW_FLOW_THRESHOLD, 3.0, low_flow_detected),

            # Redundant? appears to always happen
            # OverflowOff(interface, schedule, sample_post_origin + 4),
        ]
        if origin > 0.0:
            result += [
                SetSSV(interface, schedule, origin - 814, 9),
                FeedbackFlow(interface, schedule, origin - 813, INITIAL_FLOW),

                OverflowOn(interface, schedule, origin - 180),
                HighPressureOn(interface, schedule, origin - 180),

                FeedbackFlow(interface, schedule, origin + 6, SAMPLE_FLOW),
            ]
        else:
            result += [
                OverflowOn(interface, schedule, origin),
                SetSSV(interface, schedule, origin, 9),
                HighPressureOn(interface, schedule, origin),

                FeedbackFlow(interface, schedule, origin + 6, INITIAL_FLOW),
            ]
        return result
