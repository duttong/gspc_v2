import logging
import asyncio
import typing
from gspc.const import CYCLE_SECONDS, SAMPLE_OPEN_AT, SAMPLE_SECONDS
from gspc.hw.interface import Interface
from gspc.schedule import Task, Runnable, Execute, AbortPoint

from .cyrogen import *
from .vacuum import *
from .pressure import *
from .column import *
from .temperature import *
from .flow import *
from .gc import *
from .valve import *

_LOGGER = logging.getLogger(__name__)


class SampleOpen(Runnable):
    def __init__(self, interface: Interface, schedule: Execute, origin: float):
        Runnable.__init__(self, interface, schedule, origin)
        self.set_events.add("sample_open")

    async def execute(self):
        await self.interface.set_sample(True)
        _LOGGER.info("Sample valve open")


class SampleClose(Runnable):
    def __init__(self, interface: Interface, schedule: Execute, origin: float):
        Runnable.__init__(self, interface, schedule, origin)
        self.set_events.add("sample_close")

    async def execute(self):
        await self.interface.set_sample(False)
        _LOGGER.info("Sample valve closed")


class CycleEnd(Runnable):
    def __init__(self, interface: Interface, schedule: Execute, origin: float):
        Runnable.__init__(self, interface, schedule, origin)
        self.clear_events.add("sample_open")
        self.clear_events.add("sample_close")
        self.clear_events.add("gc_trigger")


class Sample(Task):
    def __init__(self):
        Task.__init__(self, CYCLE_SECONDS)

    def schedule(self, interface: Interface, schedule: Execute, origin: float) -> typing.List[Runnable]:
        sample_post_origin = origin + SAMPLE_OPEN_AT + SAMPLE_SECONDS

        abort_after_cycle = AbortPoint(interface, schedule, origin + CYCLE_SECONDS)
        result = [
            EnableCryogen(interface, schedule, origin + 1),
            DisableCryogen(interface, schedule, sample_post_origin - 5),

            CycleVacuum(interface, schedule, origin + 36),
            VacuumOn(interface, schedule, origin + 120),
            LoadSwitch(interface, schedule, sample_post_origin + 57),
            VacuumOff(interface, schedule, sample_post_origin + 59),

            SampleOpen(interface, schedule, origin + SAMPLE_OPEN_AT),
            SampleClose(interface, schedule, sample_post_origin),

            PreColumnIn(interface, schedule, sample_post_origin - 120),
            PreColumnOut(interface, schedule, sample_post_origin + 150),

            EnableGCCryogen(interface, schedule, sample_post_origin - 240),
            DisableGCCryogen(interface, schedule, sample_post_origin + 360),

            MeasurePressure(interface, schedule, origin + SAMPLE_OPEN_AT - 7, 7),

            WaitForOvenCool(interface, schedule, sample_post_origin - 15, abort_after_cycle),
            RecordFlow(interface, schedule, sample_post_origin - 2),

            GCReady(interface, schedule, sample_post_origin + 1),
            GCSolenoidOn(interface, schedule, sample_post_origin + 1),
            GCSample(interface, schedule, sample_post_origin + 2),
            GCHeaterOn(interface, schedule, sample_post_origin + 2),
            GCSolenoidOff(interface, schedule, sample_post_origin + 3),
            HighPressureOff(interface, schedule, sample_post_origin + 3),
            OverflowOff(interface, schedule, sample_post_origin + 3),

            MeasurePressure(interface, schedule, sample_post_origin + 4, 16),
            CheckSampleTemperature(interface, schedule, sample_post_origin + 69),

            CycleEnd(interface, schedule, origin + CYCLE_SECONDS),
            abort_after_cycle
        ]
        if origin > 0.0:
            result += [
                OverflowOff(interface, schedule, origin - 435),

                # Does this make sense? (isn't the flow on here?)
                #ZeroFlow(interface, schedule, origin - 230),

                EnableCryogen(interface, schedule, origin - 100),
                OverflowOn(interface, schedule, origin - 50),
            ]
        return result
