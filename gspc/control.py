import typing
import asyncio
import time
import logging
from gspc.ui.window import Main
from gspc.schedule import Execute, Task, Runnable, known_tasks
from gspc.hw.interface import Interface
from gspc.util import call_on_ui, LogHandler
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

        self.restore_open_files()

    async def _update_inputs(self):
        while True:
            sample_flow = self._interface.sample_flow
            sample_pressure = self._interface.sample_temperature
            trap_temperature = self._interface.trap_temperature

            def update_gui():
                if sample_flow is not None:
                    self.sample_flow.setText(f"{sample_flow:7.2f}")
                if sample_pressure is not None:
                    self.sample_pressure.setText(f"{sample_pressure:6.1f}")
                if trap_temperature is not None:
                    self.trap_temperature.setText(f"{trap_temperature:6.1f}")

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


class _Schedule(Execute):
    """The schedule execution class for the main control window."""

    def __init__(self, task_sequence: typing.Sequence[Task], window: Window):
        Execute.__init__(self, task_sequence)
        self._window = window

    async def update_predicted_run_time(self, seconds_remaining: float):
        estimated_end = time.time() + seconds_remaining

        def update():
            self._window.update_estimated_end(estimated_end)

        call_on_ui(update)

    async def before_run(self, running: Runnable):
        description = await running.active_description()

        def update():
            self._window.current_task.setText(description)

        call_on_ui(update)


class Simulator(Interface):
    """A display for the simulator"""

    def __init__(self, loop: asyncio.AbstractEventLoop, display: 'gspc.ui.simulator.Display'):
        Interface.__init__(self, loop)
        self._display = display

        self._display.trap_temperature.valueChanged.connect(self._trap_temperature_changed)
        self._trap_temperature_changed()

        self._display.sample_flow.valueChanged.connect(self._sample_flow_changed)
        self._sample_flow_changed()

        self._display.sample_pressure.valueChanged.connect(self._sample_pressure_changed)
        self._sample_pressure_changed()

    def _trap_temperature_changed(self):
        value = self._display.trap_temperature.value()

        def _update():
            self.trap_temperature = value

        self._loop.call_soon_threadsafe(_update)

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

    async def select_flask(self, select):
        call_on_ui(lambda: self._display.selected_source.setText(f"Flask: {select}"))

    async def unselect_flask(self):
        call_on_ui(lambda: self._display.selected_source.setText("NONE"))

    async def select_tank(self, select):
        call_on_ui(lambda: self._display.selected_source.setText(f"Tank: {select}"))

    async def unselect_tank(self):
        call_on_ui(lambda: self._display.selected_source.setText("NONE"))

    async def set_target_flow(self, flow: float):
        call_on_ui(lambda: self._display.flow_setpoint.setText(f"{flow:02.3}"))

    async def begin_flask_sample(self, select):
        call_on_ui(lambda: self._display.update_gc_trigger())

    async def begin_tank_sample(self, select):
        call_on_ui(lambda: self._display.update_gc_trigger())
