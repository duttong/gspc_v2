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

    def schedule(self, context: Execute.Context, data: typing.Optional[Data] = None) -> typing.List[Runnable]:
        sample_origin = context.origin + SAMPLE_OPEN_AT
        sample_post_origin = context.origin + SAMPLE_OPEN_AT + SAMPLE_SECONDS
        prior_post_origin = context.origin - CYCLE_SECONDS + SAMPLE_OPEN_AT + SAMPLE_SECONDS

        if data is None:
            data = PFPData()
        data.sample_type = "flask"
        data.ssv_pos = self._ssv
        data.pfp_index = self._pfp
        data.sample_number = int(context.origin / CYCLE_SECONDS) + 1

        maintain_sample_flow = MaintainFlow(context, sample_origin + 2, sample_post_origin,
                                            SAMPLE_FLOW, LOWER_SAMPLE_FLOW, UPPER_SAMPLE_FLOW)

        async def low_flow_detected():
            """ called if low flow is detected """
            data.low_flow_count += 1

        async def low_flow_mode():
            """ called after low flow is detected twice """
            await maintain_sample_flow.stop()
            await context.interface.set_overflow(False)
            _LOGGER.info("Low flow. Overflow valve OFF")
            data.low_flow = "Y"
            data.low_flow_count += 1

        #abort_after_cycle = AbortPoint(context, context.origin + CYCLE_SECONDS)
        abort_after_injection = AbortPoint(context, sample_post_origin + 8)
        abort_flow_invalid = AbortPoint(context, sample_post_origin + 160)

        result = [
            CycleBegin(context, context.origin, data),

            # added GSD
            MeasurePFPPressure(context, context.origin + 3, self._ssv, None),
            MeasurePFPPressure(context, context.origin + 30, self._ssv, None),

            EnableCryogen(context, context.origin + 1),
            DisableCryogen(context, sample_post_origin - 5),

            SampleOpen(context, context.origin + SAMPLE_OPEN_AT),
            SampleClose(context, sample_post_origin),

            StaticFlow(context, context.origin + 3, INITIAL_FLOW),

            OverflowOn_pcheck(context, context.origin + 5, data.record_pfp_pressure2),
            CheckNegativeFlow(context, context.origin + 6, abort_flow_invalid),
            FeedbackFlow(context, context.origin + 6, INITIAL_FLOW),

            #StaticFlow(context, context.origin + 81, INITIAL_FLOW),
            CheckNegativeFlow(context, context.origin + 83, abort_flow_invalid),
            FeedbackFlow(context, context.origin + 83, SAMPLE_FLOW),
            CheckNegativeFlow(context, context.origin + 126, abort_flow_invalid),
            FeedbackFlow(context, context.origin + 126, SAMPLE_FLOW),
            #StaticFlow(context, sample_post_origin + 175, INITIAL_FLOW),  # Should this just be full flow?
            #FullFlow(context, sample_post_origin + 176),

            VacuumOn(context, context.origin + 121),

            MeasurePressure(context, context.origin + SAMPLE_OPEN_AT - 7, 7, data.record_pressure_start),

            # this is happing at the same time as FeedbackFlow
            #MaintainFlow(context, context.origin + 111, sample_origin,
            #             SAMPLE_FLOW, LOWER_SAMPLE_FLOW),
            maintain_sample_flow,
            DetectLowFlow(context, sample_origin + 1, sample_post_origin, SAMPLE_FLOW,
                          LOW_FLOW_THRESHOLD, 3.0, low_flow_detected, low_flow_mode),

            EnableGCCryogen(context, sample_post_origin - 240),
            DisableGCCryogen(context, sample_post_origin + 360),

            PreColumnIn(context, sample_post_origin - 120),
            PreColumnOut(context, sample_post_origin + 150),

            PFPValveClose(context, sample_post_origin + 30, self._ssv, self._pfp, data.record_pfp_close),

            WaitForOvenCool(context, sample_post_origin - 15,
                            data.cryo_extended, abort_after_injection),
            RecordLastFlow(context, sample_post_origin - 2, data.record_last_flow),

            GCReady(context, sample_post_origin + 1),
            InjectSwitch(context, sample_post_origin + 1),
            GCSample(context, sample_post_origin + 2),
            CryogenTrapHeaterOn(context, sample_post_origin + 2),
            OverflowOff(context, sample_post_origin + 3),

            LoadSwitch(context, sample_post_origin + 57),
            VacuumOff(context, sample_post_origin + 59),

            MeasurePressure(context, sample_post_origin + 4, 16, data.record_pressure_end),
            CheckSampleTemperature(context, sample_post_origin + 69),

            # extra pressure measurements added GSD
            MeasurePFPPressure(context, sample_post_origin + 6, self._ssv, None),
            MeasurePFPPressure(context, sample_post_origin + 10, self._ssv, None),
            MeasurePFPPressure(context, sample_post_origin + 15, self._ssv, data.record_pfp_pressure3),
            MeasurePFPPressure(context, sample_post_origin + 20, self._ssv, None),

            abort_flow_invalid,
            abort_after_injection,
            CycleEnd(context, context.origin + CYCLE_SECONDS),
        ]
        if prior_post_origin > 0.0:
            result += [
                # Seems redundant (already closed at sample_post_origin+3)
                OverflowOff(context, prior_post_origin + 182),

                SetSSV(context, prior_post_origin + 182, self._evac_ssv),
                EvacuateOn(context, prior_post_origin + 198),
            ]

        if context.origin > 0.0:
            result += [
                SetSSV(context, context.origin - 30, self._ssv),
                
                # added GSD
                MeasurePFPPressure(context, context.origin - 32, self._ssv, None),

                EvacuateOff(context, context.origin - 240),
                ZeroFlow(context, context.origin - 230),

                CryogenTrapHeaterOff(context, context.origin - 150),

                MeasurePFPPressure(context, context.origin - 123, self._ssv, data.record_pfp_pressure1),
                MeasurePFPPressure(context, context.origin - 103, self._ssv, data.record_pfp_pressure2),
                CheckPFPEvacuated(context, context.origin - 120, self._ssv),

                PFPValveOpen(context, context.origin - 115, self._ssv, self._pfp, data.record_pfp_open),
            ]
        else:
            result += [
                HighPressureOff(context, context.origin),
                # Some failsafes to make sure the initial state on the first sample is sane
                SetSSV(context, context.origin, self._ssv),
                EvacuateOff(context, context.origin),
                # CheckPFPEvacuated(context, context.origin, self._ssv),

                FeedbackFlow(context, context.origin + 6, INITIAL_FLOW),
            ]
        return result
