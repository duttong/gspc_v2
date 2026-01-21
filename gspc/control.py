import typing
import asyncio
import time
import logging
import enum
import threading
from gspc.ui.window import Main
from gspc.schedule import Execute, Task, known_tasks
from gspc.hw.interface import Interface
from gspc.util import call_on_ui, LogHandler, background_task
from gspc.output import set_output_name
from PyQt5 import QtCore, QtGui, QtWidgets

if typing.TYPE_CHECKING:
    import gspc.ui.simulator


_LOGGER = logging.getLogger(__name__)


class Window(Main):
    """The main control window"""

    _schedule_complete = QtCore.pyqtSignal()

    def __init__(self, loop: asyncio.AbstractEventLoop, interface: Interface, enable_pfp: bool = True):
        Main.__init__(self, enable_pfp=enable_pfp)
        self._loop = loop
        self._interface = interface
        self._active_schedule: typing.Optional["_Schedule"] = None

        for name, task in known_tasks.items():
            self.add_manual_task(name, lambda task=task, name=name: self._run_manual_task(task, name))
            self.loadable_tasks[name] = task

        def update_ssv(ssv_position: int) -> None:
            """ method for reading initial SSV position and updating ui (GSD)"""
            self.selected_ssv.setValue(ssv_position)
            self.selected_ssv_in.setText(f"   {ssv_position}")

        self._loop.call_soon_threadsafe(lambda: background_task(self._call_ui_with_result(
            self._interface.get_ssv_cp, update_ssv
        )))

        def update_sample_flow_signal(value: float) -> None:
            self.sample_flow.setText(f"{value:8.3f}")
            self.output_flow_feedback.setText(f"{value:.3f}")

        self._loop.call_soon_threadsafe(lambda: background_task(self._repeat_ui_with_result(
            self._interface.get_flow_signal, update_sample_flow_signal
        )))

        self._loop.call_soon_threadsafe(lambda: background_task(self._repeat_ui_with_result(
            self._interface.get_pressure, lambda value: self.sample_pressure.setText(f"{value:8.3f}")
        )))
        self._loop.call_soon_threadsafe(lambda: background_task(self._repeat_ui_with_result(
            self._interface.get_thermocouple_temperature_0,
            lambda value: self.thermocouple_0.setText(f"{value:8.3f}")
        )))
        self._loop.call_soon_threadsafe(lambda: background_task(self._repeat_ui_with_result(
            self._interface.get_oven_temperature_signal,
            lambda value: self.oven_temperature.setText(f"{value:8.3f}")
        )))
        # calling get_pfp_pressure too often interfears with other pfp comms. GSD
        if self.pfp_pressure is not None:
            self._loop.call_soon_threadsafe(lambda: background_task(self._repeat_ui_with_result(
                self._interface.get_display_pfp_pressure,
                lambda value: self.pfp_pressure.setText(f"{value:8.3f}")
            )))

        self._log_handler = LogHandler(self._log_message)
        log_format = logging.Formatter('%(message)s')
        self._log_handler.setFormatter(log_format)
        self._log_handler.setLevel(logging.INFO)
        root_logger = logging.getLogger()
        root_logger.addHandler(self._log_handler)

        self._hook_interface('set_overflow', self._interface_set_overflow)
        self.overflow_toggle.clicked.connect(self._ui_overflow_toggle)

        self._hook_interface('set_vacuum', self._interface_set_vacuum)
        self.vacuum_toggle.clicked.connect(self._ui_vacuum_toggle)

        self._hook_interface('set_evacuation_valve', self._interface_set_evacuation_valve)
        self.evacuate_toggle.clicked.connect(self._ui_evacuate_toggle)

        #self.trigger_gc.clicked.connect(self._ui_trigger_gc)

        self._hook_interface('set_ssv', self._interface_set_ssv)
        self.apply_ssv.clicked.connect(self._ui_apply_ssv)

        self._hook_interface('set_flow', self._interface_set_flow)
        self.apply_flow.clicked.connect(self._ui_apply_flow)

        if self.selected_pfp_in is not None:
            self._hook_interface('set_pfp_valve', self._interface_set_pfp_valve)

        if self.pfp_open is not None:
            self.pfp_open.clicked.connect(self._ui_open_pfp)
        if self.pfp_close is not None:
            self.pfp_close.clicked.connect(self._ui_close_pfp)

        self.restore_open_files()
        self.restore_output_target()

    def _hook_interface(self, method: str, hook: typing.Callable):
        original = getattr(self._interface, method)

        def _hooked(*args, **kwargs):
            hook(*args, **kwargs)
            return original(*args, **kwargs)

        setattr(self._interface, method, _hooked)

    @staticmethod
    async def _call_ui_with_result(reader: typing.Callable[[], typing.Awaitable[typing.Any]],
                                   ui_update: typing.Callable[[typing.Any], None]) -> None:
        value = await reader()
        if value is None:
            return

        def call_gui():
            ui_update(value)

        call_on_ui(call_gui)

    @staticmethod
    async def _repeat_ui_with_result(reader: typing.Callable[[], typing.Awaitable[typing.Any]],
                                     ui_update: typing.Callable[[typing.Any], None],
                                     interval: float = 1.0) -> None:
        while True:
            await Window._call_ui_with_result(reader, ui_update)
            await asyncio.sleep(interval)

    async def _execute_schedule(self):
        abort_message = None
        if not await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(
                self._active_schedule.execute(self._interface), self._loop)):
            abort_message = self._active_schedule.abort_message

        def message_gui():
            self.set_stopped()
            self._active_schedule = None
            self.log_event("Tasks completed")
            self._schedule_complete.emit()
            if abort_message is not None:
                QtWidgets.QMessageBox.warning(self, "Schedule Aborted", f"Task execution aborted: {abort_message}")

        call_on_ui(message_gui)
        await self._interface.shutdown()    # put instrument in idle state

    def _run_manual_task(self, task: Task, name: str):
        if self._active_schedule is not None:
            return
        self._active_schedule = _Schedule([task], self, task_names=[name])
        self.set_running(time.time())
        self.current_task.setText(name)
        self._loop.call_soon_threadsafe(lambda: background_task(self._execute_schedule()))

    def start_schedule(self, tasks: typing.Sequence[Task],
                       task_names: typing.Optional[typing.Sequence[str]] = None):
        if self._active_schedule is not None:
            return

        self._active_schedule = _Schedule(tasks, self, task_names=task_names)
        self.set_running(time.time())
        self._loop.call_soon_threadsafe(lambda: background_task(self._execute_schedule()))

    def stop_schedule(self):
        async def loop_call():
            if self._active_schedule is None:
                return
            await self._active_schedule.abort()

        self._loop.call_soon_threadsafe(lambda: background_task(loop_call()))

    def pause_execution(self):
        async def loop_call():
            if self._active_schedule is None:
                return
            await self._active_schedule.pause()

        self._loop.call_soon_threadsafe(lambda: background_task(loop_call()))

    def resume_execution(self):
        async def loop_call():
            if self._active_schedule is None:
                return
            await self._active_schedule.resume()

        self._loop.call_soon_threadsafe(lambda: background_task(loop_call()))

    def modify_active_list(self, modified_index: int) -> bool:
        if self._active_schedule is None:
            return True
        task_list = self.current_task_list
        if task_list is None:
            return True

        _LOGGER.debug(f"Attempting reschedule after {modified_index}")

        completed = threading.Event()
        result: typing.Optional[_Schedule.RescheduleFailure] = None

        append_tasks = list()
        for i in range(modified_index, task_list.count()):
            task_item: QtWidgets.QListWidgetItem = task_list.item(i)
            append_tasks.append(task_item.data(QtCore.Qt.UserRole).task)

        async def loop_call():
            nonlocal result
            if self._active_schedule is None:
                completed.set()
                return
            try:
                await self._active_schedule.reschedule(remove=modified_index, append=append_tasks)
            except _Schedule.RescheduleFailure as e:
                result = e
            completed.set()

        self._loop.call_soon_threadsafe(lambda: background_task(loop_call()))

        while True:
            if self._active_schedule is None:
                break
            if completed.wait(0.0):
                break

            QtGui.QGuiApplication.processEvents(QtCore.QEventLoop.AllEvents, 50)

        if result is not None:
            QtWidgets.QMessageBox.warning(self, "Reschedule Failed", f"Task reschedule failed: {result.message}")
            return False

        return True

    def _log_message(self, msg: str, record: logging.LogRecord):
        self.log_event(msg)

    @staticmethod
    def _get_settings():
        return QtCore.QSettings("NOAA_GML", "GSPC")

    def save_open_files(self):
        settings = self._get_settings()
        open_files = self.get_open_files()
        settings.beginWriteArray("taskFiles", len(open_files))
        for i in range(len(open_files)):
            settings.setArrayIndex(i)
            settings.setValue("path", open_files[i])
        settings.sync()

    def restore_open_files(self):
        settings = self._get_settings()
        for i in range(settings.beginReadArray("taskFiles")):
            settings.setArrayIndex(i)
            file_path = settings.value("path", "", str)
            if len(file_path) <= 0:
                continue
            self.add_open_file(file_path)
        settings.endArray()

    def change_output(self, name: typing.Optional[str]):
        Main.change_output(self, name)
        set_output_name(name)
        settings = self._get_settings()
        if name is not None and len(name) > 0:
            settings.setValue("outputName", name)
        else:
            settings.setValue("outputName", "")

    def restore_output_target(self):
        settings = self._get_settings()
        output_name = settings.value("outputName", None, str)
        Main.change_output(self, output_name)
        if output_name and len(output_name) > 0:
            set_output_name(output_name)

    def closeEvent(self, event):
        if self._active_schedule is None:
            self.save_open_files()
            event.accept()
            return

        close = QtWidgets.QMessageBox.question(self,
                                               "Confirm Exit",
                                               "Task execution is still in progress.  Are you sure you want to quit and abort it?",
                                               QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if close != QtWidgets.QMessageBox.Yes:
            event.ignore()
            return

        wait_dialog = QtWidgets.QProgressDialog("Waiting for task completion...", str(), 0, 0, self)
        wait_dialog.setCancelButton(None)
        wait_dialog.setModal(True)
        self._schedule_complete.connect(wait_dialog.close, type=QtCore.Qt.QueuedConnection)

        self.stop_schedule()
        self.save_open_files()

        wait_dialog.exec()

        event.accept()

    def _interface_set_overflow(self, enable: bool):
        call_on_ui(lambda: self.overflow_toggle.setChecked(enable))

    def _ui_overflow_toggle(self, checked: bool):
        self._loop.call_soon_threadsafe(lambda: background_task(self._interface.set_overflow(checked)))

    def _interface_set_vacuum(self, enable: bool):
        call_on_ui(lambda: self.vacuum_toggle.setChecked(enable))

    def _ui_vacuum_toggle(self, checked: bool):
        self._loop.call_soon_threadsafe(lambda: background_task(self._interface.set_vacuum(checked)))

    def _interface_set_evacuation_valve(self, enable: bool):
        call_on_ui(lambda: self.evacuate_toggle.setChecked(enable))

    def _ui_evacuate_toggle(self, checked: bool):
        self._loop.call_soon_threadsafe(lambda: background_task(self._interface.set_evacuation_valve(checked)))

    def _ui_trigger_gc(self, checked: bool):
        async def _trigger():
            await self._interface.ready_gcms()
            await asyncio.sleep(1)
            await self._interface.trigger_gcms()

        self._loop.call_soon_threadsafe(lambda: background_task(_trigger()))

    def _interface_set_ssv(self, index: int, manual: bool = False):
        call_on_ui(lambda: self.selected_ssv.setValue(index))
        call_on_ui(lambda: self.selected_ssv_in.setText(f"   {index}"))

    def _interface_set_flow(self, flow: float):
        call_on_ui(lambda: self.output_flow.setValue(flow))

    def _interface_set_pfp_valve(self, ssv_index: typing.Optional[int], pfp_valve: int, set_open: bool):
        if self.select_pfp is not None:
            call_on_ui(lambda: self.select_pfp.setValue(pfp_valve))
        if self.selected_pfp_in is not None:
            if set_open:
                call_on_ui(lambda: self.selected_pfp_in.setText(f"   {pfp_valve}"))
            else:
                call_on_ui(lambda: self.selected_pfp_in.setText("   -"))

    def _ui_apply_ssv(self, checked: bool):
        index = self.selected_ssv.value()
        self._loop.call_soon_threadsafe(lambda: background_task(self._interface.set_ssv(index, True)))

    def _ui_apply_flow(self, checked: bool):
        flow = self.output_flow.value()
        self._loop.call_soon_threadsafe(lambda: background_task(self._interface.set_flow(flow)))

    def _ui_open_pfp(self, checked: bool):
        index = self.select_pfp.value()
        self._loop.call_soon_threadsafe(lambda: background_task(self._interface.set_pfp_valve(None, index, True)))

    def _ui_close_pfp(self, checked: bool):
        index = self.select_pfp.value()
        self._loop.call_soon_threadsafe(lambda: background_task(self._interface.set_pfp_valve(None, index, False)))


class _Schedule(Execute):
    """The schedule execution class for the main control window."""

    def __init__(self, task_sequence: typing.Sequence[Task], window: Window,
                 task_names: typing.Optional[typing.Sequence[str]] = None):
        Execute.__init__(self, task_sequence, task_names=task_names)
        self._window = window

    async def state_update(self):
        is_paused = await self.is_paused()
        events = dict()
        for key, event in self.events.items():
            events[key] = event

        class State(enum.Enum):
            COMPLETE = enum.auto()
            ACTIVE = enum.auto()
            PREPARING = enum.auto()

        task_state = dict()
        current_task = None
        for context in self.contexts:
            if context.task_completed:
                task_state[context.task_index] = State.COMPLETE
            elif context.task_started:
                task_state[context.task_index] = State.ACTIVE
                current_task = context.task_index
            elif context.task_activated:
                task_state[context.task_index] = State.PREPARING

        def update():
            if not is_paused:
                self._window.update_events(events)

            task_list = self._window._schedule_control.currentWidget().findChild(QtWidgets.QListWidget, "FileTasks")
            if task_list:
                for i in range(task_list.count()):
                    state = task_state.get(i)
                    if state is None:
                        continue
                    task_item = task_list.item(i)
                    task_data = task_item.data(QtCore.Qt.UserRole)
                    if state == State.COMPLETE:
                        task_item.setText(f"{task_data.name} - COMPLETE")
                        task_item.setFlags(task_item.flags() & ~QtCore.Qt.ItemIsEnabled)
                        if task_item.flags() & QtCore.Qt.ItemIsSelectable:
                            task_item.setFlags(task_item.flags() & ~QtCore.Qt.ItemIsSelectable)
                            task_list.clearSelection()
                    elif state == State.ACTIVE:
                        task_item.setText(f"{task_data.name} - RUNNING")
                        task_item.setFlags(task_item.flags() & ~QtCore.Qt.ItemIsEnabled)
                        if task_item.flags() & QtCore.Qt.ItemIsSelectable:
                            task_item.setFlags(task_item.flags() & ~QtCore.Qt.ItemIsSelectable)
                            task_list.clearSelection()
                    elif state == State.PREPARING:
                        task_item.setText(f"{task_data.name} - PREPARE")
                        task_item.setFlags(task_item.flags() & ~QtCore.Qt.ItemIsEnabled)
                        if task_item.flags() & QtCore.Qt.ItemIsSelectable:
                            task_item.setFlags(task_item.flags() & ~QtCore.Qt.ItemIsSelectable)
                            task_list.clearSelection()

                if current_task is not None and current_task < task_list.count():
                    task_data = task_list.item(current_task).data(QtCore.Qt.UserRole)
                    self._window.current_task.setText(f"{task_data.name} (#{current_task+1})")
                else:
                    self._window.current_task.setText("NONE")

        call_on_ui(update)


class Simulator(Interface):
    """A display for the simulator"""

    def __init__(self, loop: asyncio.AbstractEventLoop, display: 'gspc.ui.simulator.Display'):
        Interface.__init__(self, loop)
        self._display = display

        self.sample_pressure = None
        self.sample_flow = None
        self.oven_temperature = None
        self.thermocouple_0 = 0.0
        self.thermocouple_1 = 0.0
        self.high_pressure_on = False
        self.ssv_position = 0
        self.pfp_pressure = None

        self._display.sample_flow.valueChanged.connect(self._sample_flow_changed)
        self._sample_flow_changed()

        self._display.sample_pressure.valueChanged.connect(self._sample_pressure_changed)
        self._sample_pressure_changed()

        self._display.oven_temperature.valueChanged.connect(self._oven_temperature_changed)
        self._oven_temperature_changed()

        self._display.pfp_pressure.valueChanged.connect(self._pfp_pressure_changed)
        self._pfp_pressure_changed()

    def _sample_flow_changed(self):
        value = self._display.sample_flow.value()

        def _update():
            self.sample_flow = value

        self._loop.call_soon_threadsafe(_update)

    def _sample_pressure_changed(self):
        value = self._display.sample_pressure.value()

        def _update():
            self.sample_pressure = value

        self._loop.call_soon_threadsafe(_update)

    def _pfp_pressure_changed(self):
        value = self._display.pfp_pressure.value()

        def _update():
            self.pfp_pressure = value

        self._loop.call_soon_threadsafe(_update)

    def _oven_temperature_changed(self):
        value = self._display.oven_temperature.value()

        def _update():
            self.oven_temperature = value

        self._loop.call_soon_threadsafe(_update)

    async def get_pressure(self) -> float:
        return self.sample_pressure

    async def get_oven_temperature_signal(self) -> float:
        return self.oven_temperature

    async def get_thermocouple_temperature_0(self) -> float:
        return self.thermocouple_0

    async def get_thermocouple_temperature_1(self) -> float:
        return self.thermocouple_1

    async def set_cryogen(self, enable: bool):
        call_on_ui(lambda: self._display.cryogen.setText("ON" if enable else "OFF"))
        if enable and self.oven_temperature < 4.0:
            call_on_ui(lambda: self._display.oven_temperature.setValue(4.0))

    async def set_gc_cryogen(self, enable: bool):
        call_on_ui(lambda: self._display.gc_cryogen.setText("ON" if enable else "OFF"))

    async def set_vacuum(self, enable: bool):
        call_on_ui(lambda: self._display.vacuum.setText("ON" if enable else "OFF"))

    async def set_sample(self, enable: bool):
        call_on_ui(lambda: self._display.sample_valve.setText("ON" if enable else "OFF"))

    async def set_cryo_heater(self, enable: bool):
        call_on_ui(lambda: self._display.cryro_heater.setText("ON" if enable else "OFF"))
        if enable and self.oven_temperature > 2.0:
            call_on_ui(lambda: self._display.oven_temperature.setValue(2.0))

    async def set_overflow(self, enable: bool):
        call_on_ui(lambda: self._display.overflow.setText("ON" if enable else "OFF"))

    async def valve_load(self):
        call_on_ui(lambda: self._display.load_inject.setText("LOAD"))

    async def valve_inject(self):
        call_on_ui(lambda: self._display.load_inject.setText("INJECT"))

    async def precolumn_in(self):
        call_on_ui(lambda: self._display.pre_column.setText("IN"))

    async def precolumn_out(self):
        call_on_ui(lambda: self._display.pre_column.setText("OUT"))

    async def get_flow_control_output(self) -> float:
        return self.sample_flow

    async def get_flow_signal(self) -> float:
        return self.sample_flow

    async def set_flow(self, flow: float):
        call_on_ui(lambda: self._display.sample_flow.setValue(flow))

    async def increment_flow(self, flow: float, multiplier: float):
        delta = 0.25 * multiplier

        def _update():
            value = self._display.sample_flow.value()
            value += delta
            self._display.sample_flow.setValue(value)

        call_on_ui(_update)

    async def set_ssv(self, index: int, manual: bool = False):
        display = f"{index}"
        if manual:
            self.high_pressure_on = True
        if self.high_pressure_on:
            display += " ON"
        self.ssv_position = index
        call_on_ui(lambda: self._display.ssv_position.setText(display))

    async def set_high_pressure_valve(self, enable: bool):
        self.high_pressure_on = enable

    async def trigger_gcms(self):
        call_on_ui(lambda: self._display.update_gcms_trigger())

    async def get_ssv_cp(self) -> int:
        return self.ssv_position

    async def set_evacuation_valve(self, enable: bool):
        call_on_ui(lambda: self._display.evacuation.setText("ON" if enable else "OFF"))
        if enable and self.pfp_pressure > 2.0:
            call_on_ui(lambda: self._display.pfp_pressure.setValue(2.0))

    async def set_pfp_valve(self, ssv_index: typing.Optional[int], pfp_valve: int, set_open: bool) -> str:
        display = f"{pfp_valve}"
        if set_open:
            display += " OPEN"
        else:
            display += " CLOSE"
        call_on_ui(lambda: self._display.ssv_position.setText(display))
        return "OK"

    async def get_pfp_pressure(self, ssv_index: typing.Optional[int] = None) -> float:
        return self.pfp_pressure

    async def get_display_pfp_pressure(self) -> float:
        return self.pfp_pressure

    async def get_pfp_reply(self, ssv_index: typing.Optional[int] = None) -> str:
        return "OK"

    async def ready_gcms(self):
        pass

    async def shutdown(self):
        pass

    async def adjust_flow(self, flow: float):
        pass
