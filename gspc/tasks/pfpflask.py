import logging
import asyncio
import typing
from .sample import *

_LOGGER = logging.getLogger(__name__)


INITIAL_FLOW = 3
SAMPLE_FLOW = 7.2
UPPER_SAMPLE_FLOW = 1.3
LOWER_SAMPLE_FLOW = 0.5
LOW_FLOW_THRESHOLD = 0.2


class PFPData(Data):
    def __init__(self):
        Data.__init__(self)

        self.pfp_index: typing.Optional[int] = 0

        self.pfp_open: typing.Optional[str] = None
        self.pfp_close: typing.Optional[str] = None

        self.pfp_pressure1: typing.Optional[float] = None
        self.pfp_pressure2: typing.Optional[float] = None
        self.pfp_pressure3: typing.Optional[float] = None

    def record_pfp_pressure1(self, pressure: float):
        self.pfp_pressure1 = pressure

    def record_pfp_pressure2(self, pressure: float):
        self.pfp_pressure2 = pressure

    def record_pfp_pressure3(self, pressure: float):
        self.pfp_pressure3 = pressure

    def record_pfp_open(self, message: str):
        self.pfp_open = message

    def record_pfp_close(self, message: str):
        self.pfp_close = message

    def record_fields(self) -> typing.List[str]:
        return Data.record_fields(self) + [
            self.pfp_index is not None and f"{self.pfp_index}" or "NONE",
            self.pfp_open is not None and self.pfp_open or "NONE",
            self.pfp_close is not None and self.pfp_close or "NONE",
            self.pfp_pressure1 is not None and f"{self.pfp_pressure1:.2f}" or "NONE",
            self.pfp_pressure2 is not None and f"{self.pfp_pressure2:.2f}" or "NONE",
            self.pfp_pressure3 is not None and f"{self.pfp_pressure3:.2f}" or "NONE",
        ]


class PFPFlask(Sample):
    def __init__(self, pfp_number, ssv_selection):
        Sample.__init__(self)
        self._pfp = pfp_number
        self._ssv = ssv_selection
        self._evac_ssv = ssv_selection - 1

    def schedule(self, interface: Interface, schedule: Execute, origin: float,
                 data: typing.Optional[Data] = None) -> typing.List[Runnable]:
        sample_origin = origin + SAMPLE_OPEN_AT
        sample_post_origin = origin + SAMPLE_OPEN_AT + SAMPLE_SECONDS
        prior_post_origin = origin - CYCLE_SECONDS + SAMPLE_OPEN_AT + SAMPLE_SECONDS

        if data is None:
            data = PFPData()
        data.sample_type = "flask"
        data.ssv_pos = self._ssv
        data.pfp_index = self._pfp
        data.sample_number = int(origin / CYCLE_SECONDS) + 1

        maintain_sample_flow = MaintainFlow(interface, schedule, sample_origin, sample_post_origin,
                                            SAMPLE_FLOW, LOWER_SAMPLE_FLOW, UPPER_SAMPLE_FLOW)

        async def low_flow_detected():
            await maintain_sample_flow.stop()
            await interface.set_overflow(False)
            data.low_flow = "Y"

        abort_after_cycle = AbortPoint(interface, schedule, origin + CYCLE_SECONDS)
        abort_flow_invalid = AbortPoint(interface, schedule, sample_post_origin + 160)
        result = [
            CycleBegin(interface, schedule, origin, data),

            EnableCryogen(interface, schedule, origin + 1),
            DisableCryogen(interface, schedule, sample_post_origin - 5),

            SampleOpen(interface, schedule, origin + SAMPLE_OPEN_AT),
            SampleClose(interface, schedule, sample_post_origin),

            StaticFlow(interface, schedule, origin + 3, INITIAL_FLOW),

            OverflowOn(interface, schedule, origin + 5),
            CheckNegativeFlow(interface, schedule, origin + 6, abort_flow_invalid),
            FeedbackFlow(interface, schedule, origin + 6, INITIAL_FLOW),

            StaticFlow(interface, schedule, origin + 81, INITIAL_FLOW),
            CheckNegativeFlow(interface, schedule, origin + 83, abort_flow_invalid),
            FeedbackFlow(interface, schedule, origin + 83, SAMPLE_FLOW),
            CheckNegativeFlow(interface, schedule, origin + 126, abort_flow_invalid),
            FeedbackFlow(interface, schedule, origin + 126, SAMPLE_FLOW),
            StaticFlow(interface, schedule, sample_post_origin + 175, INITIAL_FLOW),  # Should this just be full flow?
            FullFlow(interface, schedule, sample_post_origin + 176),

            VacuumOn(interface, schedule, origin + 121),

            MeasurePressure(interface, schedule, origin + SAMPLE_OPEN_AT - 7, 7, data.record_pressure_start),

            MaintainFlow(interface, schedule, origin + 111, sample_origin,
                         SAMPLE_FLOW, LOWER_SAMPLE_FLOW),
            maintain_sample_flow,
            DetectLowFlow(interface, schedule, sample_origin + 1, sample_post_origin, SAMPLE_FLOW,
                          LOW_FLOW_THRESHOLD, 3.0, low_flow_detected),

            EnableGCCryogen(interface, schedule, sample_post_origin - 240),
            DisableGCCryogen(interface, schedule, sample_post_origin + 360),

            PreColumnIn(interface, schedule, sample_post_origin - 120),
            PreColumnOut(interface, schedule, sample_post_origin + 150),

            PFPValveClose(interface, schedule, sample_post_origin + 30, self._ssv, self._pfp, data.record_pfp_close),

            WaitForOvenCool(interface, schedule, sample_post_origin - 15,
                            data.cryo_extended, abort_after_cycle),
            RecordLastFlow(interface, schedule, sample_post_origin - 2, data.record_last_flow),

            GCReady(interface, schedule, sample_post_origin + 1),
            InjectSwitch(interface, schedule, sample_post_origin + 1),
            GCSample(interface, schedule, sample_post_origin + 2),
            CryogenTrapHeaterOn(interface, schedule, sample_post_origin + 2),
            OverflowOff(interface, schedule, sample_post_origin + 3),

            LoadSwitch(interface, schedule, sample_post_origin + 57),
            VacuumOff(interface, schedule, sample_post_origin + 59),

            MeasurePressure(interface, schedule, sample_post_origin + 4, 16, data.record_pressure_end),
            CheckSampleTemperature(interface, schedule, sample_post_origin + 69),

            MeasurePFPPressure(interface, schedule, sample_post_origin + 15, self._ssv, data.record_pfp_pressure3),

            abort_flow_invalid,
            abort_after_cycle,
            CycleEnd(interface, schedule, origin + CYCLE_SECONDS),
        ]
        if prior_post_origin > 0.0:
            result += [
                # Seems redundant (already closed at sample_post_origin+3)
                OverflowOff(interface, schedule, prior_post_origin + 182),

                SetSSV(interface, schedule, prior_post_origin + 182, self._evac_ssv),
                EvacuateOn(interface, schedule, prior_post_origin + 198),
            ]

        if origin > 0.0:
            result += [
                SetSSV(interface, schedule, origin - 30, self._ssv),

                EvacuateOff(interface, schedule, origin - 240),
                ZeroFlow(interface, schedule, origin - 230),

                CryogenTrapHeaterOff(interface, schedule, origin - 150),

                MeasurePFPPressure(interface, schedule, origin - 123, self._ssv, data.record_pfp_pressure1),
                MeasurePFPPressure(interface, schedule, origin - 108, self._ssv, data.record_pfp_pressure2),
                CheckPFPEvacuated(interface, schedule, origin - 120, self._ssv),

                PFPValveOpen(interface, schedule, origin - 115, self._ssv, self._pfp, data.record_pfp_open),
            ]
        else:
            result += [
                # Some failsafes to make sure the initial state on the first sample is sane
                SetSSV(interface, schedule, origin, self._ssv),
                EvacuateOff(interface, schedule, origin),
                # CheckPFPEvacuated(interface, schedule, origin, self._ssv),

                FeedbackFlow(interface, schedule, origin + 6, INITIAL_FLOW),
            ]
        return result
