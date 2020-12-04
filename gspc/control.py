import typing
import asyncio
import time
import logging
from gspc.ui.window import Main
from gspc.schedule import Execute, Task, Runnable, known_tasks
from gspc.hw.interface import Interface
from gspc.util import call_on_ui, LogHandler
from gspc.output import set_output_name
from PyQt5 import QtCore, QtGui, QtWidgets


class Window(Main):
    """The main control window"""

    _schedule_complete = QtCore.pyqtSignal()

    def __init__(self, loop: asyncio.AbstractEventLoop, interface: Interface):
        Main.__init__(self)
        self._loop = loop
        self._interface = interface
        self._active_schedule = None

        for name, task in known_tasks.items():
            self.add_manual_task(name, lambda task=task: self._run_manual_task(task))
            self.loadable_tasks[name] = task

        self._loop.call_soon_threadsafe(lambda: self._loop.create_task(self._update_inputs()))

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

        self.trigger_gc.clicked.connect(self._ui_trigger_gc)

        self._hook_interface('select_source', self._interface_select_source)
        self.apply_source.clicked.connect(self._ui_apply_source)

        self.restore_open_files()
        self.restore_output_target()

    def _hook_interface(self, method: str, hook: typing.Callable):
        original = getattr(self._interface, method)

        def _hooked(*args, **kwargs):
            hook(*args, **kwargs)
            return original(*args, **kwargs)

        setattr(self._interface, method, _hooked)

    async def _update_inputs(self):
        while True:
            sample_flow = await self._interface.get_flow()
            sample_pressure = await self._interface.get_pressure()
            oven_temperature = await self._interface.get_oven_temperature()

            def update_gui():
                if sample_flow is not None:
                    self.sample_flow.setText(f"{sample_flow:7.2f}")
                if sample_pressure is not None:
                    self.sample_pressure.setText(f"{sample_pressure:6.1f}")
                if oven_temperature is not None:
                    self.oven_temperature.setText(f"{oven_temperature: 6.1f}")

            call_on_ui(update_gui)
            await asyncio.sleep(1)

    async def _execute_schedule(self):
        abort_message = None
        if not await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(
                self._active_schedule.execute(self._interface), self._loop)):
            abort_message = self._active_schedule.abort_message

        def message_gui():
            if abort_message is not None:
                QtWidgets.QMessageBox.warning(self, "Schedule Aborted", f"Task execution aborted: {abort_message}")
            self.set_stopped()
            self._active_schedule = None
            self.log_event("Tasks completed")
            self._schedule_complete.emit()

        call_on_ui(message_gui)

    def _run_manual_task(self, task: 'gspc.schedule.Task'):
        if self._active_schedule is not None:
            return
        self._active_schedule = _Schedule([task], self)
        self.set_running(time.time())
        self._loop.call_soon_threadsafe(lambda: self._loop.create_task(self._execute_schedule()))

    def start_schedule(self, tasks: typing.Sequence['gspc.schedule.Task']):
        if self._active_schedule is not None:
            return
        self._active_schedule = _Schedule(tasks, self)
        self.set_running(time.time())
        self._loop.call_soon_threadsafe(lambda: self._loop.create_task(self._execute_schedule()))

    def stop_schedule(self):
        async def loop_call():
            if self._active_schedule is None:
                return
            await self._active_schedule.abort()

        self._loop.call_soon_threadsafe(lambda: self._loop.create_task(loop_call()))

    def pause_execution(self):
        async def loop_call():
            if self._active_schedule is None:
                return
            await self._active_schedule.pause()

        self._loop.call_soon_threadsafe(lambda: self._loop.create_task(loop_call()))

    def resume_execution(self):
        async def loop_call():
            if self._active_schedule is None:
                return
            await self._active_schedule.resume()

        self._loop.call_soon_threadsafe(lambda: self._loop.create_task(loop_call()))

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
        self._loop.call_soon_threadsafe(lambda: self._loop.create_task(self._interface.set_overflow(checked)))

    def _interface_set_vacuum(self, enable: bool):
        call_on_ui(lambda: self.vacuum_toggle.setChecked(enable))

    def _ui_vacuum_toggle(self, checked: bool):
        self._loop.call_soon_threadsafe(lambda: self._loop.create_task(self._interface.set_vacuum(checked)))

    def _ui_trigger_gc(self, checked: bool):
        async def _trigger():
            await self._interface.ready_gc()
            await asyncio.sleep(1)
            await self._interface.trigger_gc()

        self._loop.call_soon_threadsafe(lambda: self._loop.create_task(_trigger()))

    def _interface_select_source(self, index: int, manual: bool = False):
        call_on_ui(lambda: self.selected_source.setValue(index))

    def _ui_apply_source(self, checked: bool):
        index = self.selected_source.value()
        self._loop.call_soon_threadsafe(lambda: self._loop.create_task(self._interface.select_source(index, True)))


class _Schedule(Execute):
    """The schedule execution class for the main control window."""

    def __init__(self, task_sequence: typing.Sequence[Task], window: Window):
        Execute.__init__(self, task_sequence)
        self._window = window

    async def before_run(self, running: Runnable):
        events = dict()
        for key, event in self.events.items():
            events[key] = event

        def update():
            self._window.update_events(events)

        call_on_ui(update)


class Simulator(Interface):
    """A display for the simulator"""

    def __init__(self, loop: asyncio.AbstractEventLoop, display: 'gspc.ui.simulator.Display'):
        Interface.__init__(self, loop)
        self._display = display

        self.sample_temperature = None
        self.sample_flow = None
        self.oven_temperature = None
        self.high_pressure_on = False

        self._display.sample_flow.valueChanged.connect(self._sample_flow_changed)
        self._sample_flow_changed()

        self._display.sample_pressure.valueChanged.connect(self._sample_pressure_changed)
        self._sample_pressure_changed()

        self._display.oven_temperature.valueChanged.connect(self._oven_temperature_changed)
        self._oven_temperature_changed()

    def _sample_flow_changed(self):
        value = self._display.sample_flow.value()

        def _update():
            self.sample_flow = value

        self._loop.call_soon_threadsafe(_update)

    def _sample_pressure_changed(self):
        value = self._display.sample_pressure.value()

        def _update():
            self.sample_temperature = value

        self._loop.call_soon_threadsafe(_update)

    def _oven_temperature_changed(self):
        value = self._display.oven_temperature.value()

        def _update():
            self.oven_temperature = value

        self._loop.call_soon_threadsafe(_update)

    async def get_pressure(self) -> float:
        return self.sample_temperature

    async def get_oven_temperature(self) -> float:
        return self.oven_temperature

    async def set_cryogen(self, enable: bool):
        call_on_ui(lambda: self._display.cyrogen.setText("ON" if enable else "OFF"))
        if enable and self.oven_temperature > -60:
            call_on_ui(lambda: self._display.oven_temperature.setValue(-60.0))

    async def set_gc_cryogen(self, enable: bool):
        call_on_ui(lambda: self._display.gc_cyrogen.setText("ON" if enable else "OFF"))

    async def set_vacuum(self, enable: bool):
        call_on_ui(lambda: self._display.vacuum.setText("ON" if enable else "OFF"))

    async def set_sample(self, enable: bool):
        call_on_ui(lambda: self._display.sample_valve.setText("ON" if enable else "OFF"))

    async def set_gc_solenoid(self, enable: bool):
        call_on_ui(lambda: self._display.gc_solenoid.setText("ON" if enable else "OFF"))

    async def set_gc_heater(self, enable: bool):
        call_on_ui(lambda: self._display.gc_heater.setText("ON" if enable else "OFF"))
        if enable and self.oven_temperature < 10:
            call_on_ui(lambda: self._display.oven_temperature.setValue(10.0))

    async def set_overflow(self, enable: bool):
        call_on_ui(lambda: self._display.overflow.setText("ON" if enable else "OFF"))

    async def set_load(self, enable: bool):
        call_on_ui(lambda: self._display.load.setText("ON" if enable else "OFF"))

    async def precolumn_in(self):
        call_on_ui(lambda: self._display.pre_column.setText("IN"))

    async def precolumn_out(self):
        call_on_ui(lambda: self._display.pre_column.setText("OUT"))

    async def get_flow_control_output(self) -> float:
        return self.sample_flow

    async def get_flow(self) -> float:
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

    async def select_source(self, index: int, manual: bool = False):
        display = f"{index}"
        if manual:
            self.high_pressure_on = True
        if self.high_pressure_on:
            display += " ON"
        call_on_ui(lambda: self._display.selected_source.setText(display))

    async def set_high_pressure_valve(self, enable: bool):
        self.high_pressure_on = enable

    async def trigger_gc(self):
        call_on_ui(lambda: self._display.update_gc_trigger())

