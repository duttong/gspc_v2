import logging
import asyncio
import typing
from gspc.const import CYCLE_SECONDS, SAMPLE_OPEN_AT, SAMPLE_SECONDS
from gspc.hw.interface import Interface
from gspc.schedule import Task, Runnable, Execute, AbortPoint
from gspc.output import CycleData, begin_cycle, complete_cycle, log_message

from .cryogen import *
from .vacuum import *
from .pressure import *
from .temperature import *
from .flow import *
from .gc import *
from .valve import *

_LOGGER = logging.getLogger(__name__)


class SampleOpen(Runnable):
    def __init__(self, context: Execute.Context, origin: float):
        Runnable.__init__(self, context, origin)
        self.set_events.add("sample_open")

    async def execute(self):
        await self.context.interface.set_sample(True)
        _LOGGER.info("Sample valve open")


class SampleClose(Runnable):
    def __init__(self, context: Execute.Context, origin: float):
        Runnable.__init__(self, context, origin)
        self.set_events.add("sample_close")

    async def execute(self):
        await self.context.interface.set_sample(False)
        _LOGGER.info("Sample valve closed")


class Data(CycleData):
    def __init__(self):
        CycleData.__init__(self)
        self.sample_number: typing.Optional[int] = None
        self.sample_type: typing.Optional[str] = None
        self.ssv_pos: typing.Optional[int] = None

        self.mean1: typing.Optional[float] = None
        self.stddev1: typing.Optional[float] = None
        self.data1: typing.Optional[typing.List[float]] = None

        self.mean2: typing.Optional[float] = None
        self.stddev2: typing.Optional[float] = None
        self.data2: typing.Optional[typing.List[float]] = None

        self.low_flow: typing.Optional[str] = None
        self.last_flow: typing.Optional[float] = None
        self.last_flow_control: typing.Optional[float] = None

        self.cryo_extra_count: typing.Optional[int] = 0

        # Not sure this is actually useful: it would only be non-zero if not in low flow mode and the low flow
        # condition occured 1-s before the end of the cycle (i.e. the last reading was low flow)
        self.low_flow_count: typing.Optional[int] = 0

    def _begin(self):
        self.header("\t".join([
            "Filename", "Date", "Time",
            "Sample#",
            "Net Pressure",
            "SampType",
            "SSVPos",
            "Last flow",
            "Low Flow?",
            "cryocount",
            "Mean1",
            "Mean2",
            "%Error1",
            "%Error2",
            "loflocount",
            "Last vflow",
            "pfpFlask",
            "pfpOPEN",
            "pfpCLOSE",
            "PRESS #1",
            "PRESS #2",
            "PRESS #3",
        ]))

    def record_fields(self) -> typing.List[str]:
        if self.mean1 and self.mean2:
            net_pressure = self.mean2 - self.mean1
            pct_error1 = ((self.stddev1 or 0.0) / self.mean1)
            pct_error2 = ((self.stddev2 or 0.0) / self.mean2)
        else:
            net_pressure = None
            pct_error1 = None
            pct_error2 = None
        return [
            net_pressure is not None and f"{net_pressure:.2f}" or "NONE",
            self.sample_type is not None and f"{self.sample_type}" or "NONE",
            self.ssv_pos is not None and f"{self.ssv_pos}" or "NONE",
            self.last_flow is not None and f"{self.last_flow:.2f}" or "NONE",
            self.low_flow is not None and f"{self.low_flow}" or "N",
            self.cryo_extra_count is not None and f"{self.cryo_extra_count}" or "0",
            self.mean1 is not None and f"{self.mean1:.2f}" or "NONE",
            self.mean2 is not None and f"{self.mean2:.2f}" or "NONE",
            pct_error1 is not None and f"{pct_error1:.2f}" or "NONE",
            pct_error2 is not None and f"{pct_error2:.2f}" or "NONE",
            self.low_flow_count is not None and f"{self.low_flow_count}" or "0",
            self.last_flow_control is not None and f"{self.last_flow_control:.2f}" or "NONE",
        ]

    @staticmethod
    def _log_fields(fields: typing.List[str]):
        log_message(",".join(fields))

    def finish(self):
        self._begin()

        now = time.localtime()
        fields = [
            self.current_file_name() or "NONE",
            time.strftime("%Y-%m-%d", now),
            time.strftime("%H-%M-%S", now),
            self.sample_number and f"{self.sample_number}" or "NONE",
        ]
        net_pressure = None
        fields += self.record_fields()
        self.write("\t".join(fields))

        log_message("-------------------------------------------------------------")
        self._log_fields(["date", "time", "filename", "sample#"])
        self._log_fields([self.current_file_name() or "NONE",
                          time.strftime("%Y-%m-%d", now),
                          time.strftime("%H-%M-%S", now),
                          self.sample_number and f"{self.sample_number}" or "NONE"
                          ])
        log_message("")

        self._log_fields(["data (torr)", "mean", "std dev", "net change"])
        if self.data1 is not None:
            self._log_fields([f"{value:.2f}" for value in self.data1])
        self._log_fields(["XXXXXXXXX",
                          self.mean1 and f"{self.mean1:.2f}" or "NONE",
                          self.stddev1 and f"{self.stddev1:.2f}" or "NONE"])

        if self.data2 is not None:
            self._log_fields([f"{value:.2f}" for value in self.data2])
        self._log_fields(["XXXXXXXXX",
                          self.mean2 and f"{self.mean2:.2f}" or "NONE",
                          self.stddev2 and f"{self.stddev2:.2f}" or "NONE",
                          net_pressure and f"{net_pressure:.2f}" or "NONE"])
        log_message("")

    def abort(self, message: typing.Optional[str] = None):
        self.finish()
        if message is not None:
            log_message("SAMPLING ABORTED: " + message)
        else:
            log_message("SAMPLING ABORTED")

    def record_pressure_start(self, mean: float, stddev: float, values: typing.List[float]):
        self.mean1 = mean
        self.stddev1 = stddev
        self.data1 = values

    def record_pressure_end(self, mean: float, stddev: float, values: typing.List[float]):
        self.mean2 = mean
        self.stddev2 = stddev
        self.data2 = values

    def record_last_flow(self, flow: float, control: float):
        self.last_flow = flow
        self.last_flow_control = control

    def cryo_extended(self):
        self.cryo_extra_count = (self.cryo_extra_count or 0) + 1


class CycleBegin(Runnable):
    def __init__(self, context: Execute.Context, origin: float, data: Data):
        Runnable.__init__(self, context, origin)
        self.clear_events.add("sample_open")
        self.clear_events.add("sample_close")
        self.clear_events.add("gc_trigger")
        self.clear_events.add("cycle_end")
        self.data = data

    async def execute(self):
        self.context.task_started = True
        begin_cycle(self.data)


class CycleEnd(Runnable):
    def __init__(self, context: Execute.Context, origin: float):
        Runnable.__init__(self, context, origin)
        self.clear_events.add("sample_open")
        self.clear_events.add("sample_close")
        self.clear_events.add("gc_trigger")
        self.set_events.add("cycle_end")

    async def execute(self):
        self.context.task_completed = True
        complete_cycle()


class Sample(Task):
    def __init__(self):
        Task.__init__(self, CYCLE_SECONDS)

    def schedule(self, context: Execute.Context, data: typing.Optional[Data] = None) -> typing.List[Runnable]:
        # sample_post_origin is the start time of the injection
        sample_post_origin = context.origin + SAMPLE_OPEN_AT + SAMPLE_SECONDS

        if data is None:
            data = Data()

        data.sample_number = int(context.origin / CYCLE_SECONDS) + 1

        abort_after_cycle = AbortPoint(context, context.origin + CYCLE_SECONDS)
        result = [
            CycleBegin(context, context.origin, data),

            EnableCryogen(context, context.origin + 1),
            DisableCryogen(context, sample_post_origin - 5),

            CycleVacuum(context, context.origin + 36),
            VacuumOn(context, context.origin + 120),
            LoadSwitch(context, sample_post_origin + 57),
            VacuumOff(context, sample_post_origin + 59),

            SampleOpen(context, context.origin + SAMPLE_OPEN_AT),
            SampleClose(context, sample_post_origin),

            PreColumnIn(context, sample_post_origin - 120),
            PreColumnOut(context, sample_post_origin + 150),

            EnableGCCryogen(context, sample_post_origin - 240),
            DisableGCCryogen(context, sample_post_origin + 360),

            MeasurePressure(context, context.origin + SAMPLE_OPEN_AT - 7, 7, data.record_pressure_start),

            WaitForOvenCool(context, sample_post_origin - 15,
                            data.cryo_extended, abort_after_cycle),
            RecordLastFlow(context, sample_post_origin - 2, data.record_last_flow),

            GCReady(context, sample_post_origin + 1),
            InjectSwitch(context, sample_post_origin + 1),
            GCSample(context, sample_post_origin + 2),
            CryogenTrapHeaterOn(context, sample_post_origin + 2),
            HighPressureOff(context, sample_post_origin + 3),
            OverflowOff(context, sample_post_origin + 3),

            MeasurePressure(context, sample_post_origin + 4, 16, data.record_pressure_end),
            CheckSampleTemperature(context, sample_post_origin + 69),

            abort_after_cycle,
            CycleEnd(context, context.origin + CYCLE_SECONDS),
        ]
        if context.origin > 0.0:
            result += [
                CryogenTrapHeaterOff(context, context.origin - 300),
                OverflowOff(context, context.origin - 435),

                ZeroFlow(context, context.origin - 230),

                EnableCryogen(context, context.origin - 100),
                OverflowOn(context, context.origin - 50),
            ]
        return result
