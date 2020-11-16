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

    def schedule(self, interface: Interface, schedule: Execute, origin: float) -> typing.List[Runnable]:
        sample_origin = origin + SAMPLE_OPEN_AT
        sample_post_origin = origin + SAMPLE_OPEN_AT + SAMPLE_SECONDS

        async def low_flow_detected():
            await interface.set_vacuum(False)

        result = Sample.schedule(self, interface, schedule, origin) + [
            FullFlow(interface, schedule, origin + 69),

            DetectLowFlow(interface, schedule, sample_origin + 1, sample_post_origin, math.inf,
                          LOW_FLOW_THRESHOLD, None, low_flow_detected),

            # Redundant? appears to always happen
            # OverflowOff(interface, schedule, sample_post_origin + 4),
        ]
        if origin > 0.0:
            result += [
                SelectSource(interface, schedule, origin - 814, self._selection),
                FullFlow(interface, schedule, origin - 813),

                SelectSource(interface, schedule, origin - 435, self._selection),
                FullFlow(interface, schedule, origin - 425),

                FullFlow(interface, schedule, origin - 185),
                OverflowOn(interface, schedule, origin - 180),
                HighPressureOn(interface, schedule, origin - 180),
            ]
        else:
            result += [
                OverflowOn(interface, schedule, origin),
                SelectSource(interface, schedule, origin, self._selection),
                HighPressureOn(interface, schedule, origin),
            ]
        return result
