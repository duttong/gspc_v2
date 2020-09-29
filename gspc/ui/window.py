#!/usr/bin/python3

import logging
import time
import typing
from PyQt5 import QtCore, QtGui, QtWidgets
from pathlib import Path
from collections import namedtuple

_LOGGER = logging.getLogger(__name__)


class Main(QtWidgets.QMainWindow):
    def __init__(self):
        QtWidgets.QMainWindow.__init__(self)
        self.setObjectName("GSPC")
        self.setWindowTitle("Process Control")

        central_widget = QtWidgets.QWidget(self)
        self.setCentralWidget(central_widget)
        central_layout = QtWidgets.QGridLayout(central_widget)
        central_widget.setLayout(central_layout)

        central_layout.setRowStretch(0, 0)
        central_layout.setRowStretch(1, 1)
        central_layout.setRowStretch(2, 1)
        central_layout.setColumnStretch(0, 1)
        central_layout.setColumnStretch(1, 1)

        control_bar = QtWidgets.QWidget(central_widget)
        central_layout.addWidget(control_bar, 0, 0, 1, -1)
        control_layout = QtWidgets.QHBoxLayout(control_bar)
        control_bar.setLayout(control_layout)

        self._run_button = QtWidgets.QPushButton(control_bar)
        self._run_button.setText("Start")
        self._run_button.setCheckable(True)
        self._run_button.setIcon(QtWidgets.QApplication.style().standardIcon(QtWidgets.QStyle.SP_MediaPlay))
        self._run_button.clicked.connect(self._run_button_pressed)
        control_layout.addWidget(self._run_button)

        self._pause_button = QtWidgets.QPushButton(control_bar)
        self._pause_button.setText("Pause")
        self._pause_button.setIcon(QtWidgets.QApplication.style().standardIcon(QtWidgets.QStyle.SP_MediaPause))
        self._pause_button.setEnabled(False)
        self._pause_button.setCheckable(True)
        self._pause_button.clicked.connect(self._pause_clicked)
        control_layout.addWidget(self._pause_button)

        control_layout.addStretch(1)

        monospace = QtGui.QFont()
        monospace.setFamily("Monospace")
        monospace.setStyleHint(QtGui.QFont.TypeWriter)

        self._time_display = QtWidgets.QLabel(control_bar)
        self._time_display.setFont(monospace)
        self._time_display.setText("00:00:00")
        control_layout.addWidget(self._time_display)
        self._time_updater = QtCore.QTimer(self._time_display)
        self._time_updater.setSingleShot(True)
        self._time_updater.timeout.connect(self._update_time)

        status_pane = QtWidgets.QWidget(central_widget)
        central_layout.addWidget(status_pane, 1, 0, 1, 1)
        status_layout = QtWidgets.QGridLayout(status_pane)
        status_pane.setLayout(status_layout)

        status_layout.setRowStretch(0, 0)
        status_layout.setRowStretch(1, 0)
        status_layout.setRowStretch(2, 0)
        status_layout.setRowStretch(3, 0)
        status_layout.setRowStretch(4, 1)
        status_layout.setColumnStretch(0, 0)
        status_layout.setColumnStretch(1, 1)

        status_layout.addWidget(QtWidgets.QLabel("File:", status_pane), 0, 0, QtCore.Qt.AlignRight)
        self._selected_file = QtWidgets.QLabel(status_pane)
        #self._selected_file.setFont(monospace)
        self._selected_file.setText("NONE")
        status_layout.addWidget(self._selected_file, 0, 1, 1, 1, QtCore.Qt.AlignLeft)
        self._open_file = QtWidgets.QPushButton(status_pane)
        status_layout.addWidget(self._open_file, 0, 2, 1, 1)
        self._open_file.setIcon(QtWidgets.QApplication.style().standardIcon(QtWidgets.QStyle.SP_DialogOpenButton))
        self._open_file.clicked.connect(self._add_file)
        self._close_file = QtWidgets.QPushButton(status_pane)
        status_layout.addWidget(self._close_file, 0, 3, 1, 1)
        self._close_file.setIcon(QtWidgets.QApplication.style().standardIcon(QtWidgets.QStyle.SP_DialogCloseButton))
        self._close_file.setEnabled(False)
        self._close_file.clicked.connect(self._remove_file)

        status_layout.addWidget(QtWidgets.QLabel("Task:", status_pane), 1, 0, QtCore.Qt.AlignRight)
        self.current_task = QtWidgets.QLabel(status_pane)
        #self.current_task.setFont(monospace)
        self.current_task.setText("NONE")
        status_layout.addWidget(self.current_task, 1, 1, 1, -1, QtCore.Qt.AlignLeft)

        status_layout.addWidget(QtWidgets.QLabel("Time elapsed:", status_pane), 2, 0, QtCore.Qt.AlignRight)
        self._elapsed_time = QtWidgets.QLabel(status_pane)
        self._elapsed_time.setFont(monospace)
        self._elapsed_time.setText("NONE")
        status_layout.addWidget(self._elapsed_time, 2, 1, 1, -1, QtCore.Qt.AlignLeft)

        self._schedule_begin_time = None
        self._elapsed_updater = QtCore.QTimer(self._elapsed_time)
        self._elapsed_updater.setSingleShot(True)
        self._elapsed_updater.timeout.connect(self._update_elapsed)

        status_layout.addWidget(QtWidgets.QLabel("Est. remaining:", status_pane), 3, 0, QtCore.Qt.AlignRight)
        self._remaining_time = QtWidgets.QLabel(status_pane)
        self._remaining_time.setFont(monospace)
        self._remaining_time.setText("NONE")
        status_layout.addWidget(self._remaining_time, 3, 1, 1, -1, QtCore.Qt.AlignLeft)

        self._estimated_end_time = None
        self._remaining_updater = QtCore.QTimer(self._remaining_time)
        self._remaining_updater.setSingleShot(True)
        self._remaining_updater.timeout.connect(self._update_remaining)

        status_layout.addWidget(QtWidgets.QWidget(status_pane), 4, 0, 1, -1)

        self._log_display = QtWidgets.QPlainTextEdit(central_widget)
        central_layout.addWidget(self._log_display, 1, 1, 1, -1)
        self._log_display.setFont(monospace)
        self._log_display.setReadOnly(True)
        self._log_display.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)

        self._schedule_control = QtWidgets.QTabWidget(central_widget)
        central_layout.addWidget(self._schedule_control, 2, 0, 1, 1)
        self._task_list = QtWidgets.QListWidget(self._schedule_control)
        self._task_list.currentItemChanged.connect(self._manual_task_selected)
        self._schedule_control.addTab(self._task_list, "Manual")

        self._schedule_control.currentChanged.connect(self._schedule_tab_changed)

        io_display = QtWidgets.QTabWidget(central_widget)
        central_layout.addWidget(io_display, 2, 1, 1, -1)

        inputs_pane = QtWidgets.QWidget(central_widget)
        io_display.addTab(inputs_pane, "Input")
        inputs_layout = QtWidgets.QFormLayout(inputs_pane)
        inputs_pane.setLayout(inputs_layout)

        self.sample_pressure = QtWidgets.QLabel(inputs_pane)
        self.sample_pressure.setText("0000.00")
        self.sample_pressure.setFont(monospace)
        inputs_layout.addRow("Pressure (hPa):", self.sample_pressure)

        self.trap_temperature = QtWidgets.QLabel(inputs_pane)
        self.trap_temperature.setText("00.0")
        self.trap_temperature.setFont(monospace)
        inputs_layout.addRow("Trap (°C):", self.trap_temperature)

        self.sample_flow = QtWidgets.QLabel(inputs_pane)
        self.sample_flow.setText("00.000")
        self.sample_flow.setFont(monospace)
        inputs_layout.addRow("Flow (lpm):", self.sample_flow)

        control_pane = QtWidgets.QWidget(central_widget)
        io_display.addTab(control_pane, "Control")
        control_layout = QtWidgets.QGridLayout(control_pane)
        control_pane.setLayout(control_layout)

        control_layout.setRowStretch(0, 0)
        control_layout.setRowStretch(1, 1)
        control_layout.setColumnStretch(1, 0)
        control_layout.setColumnStretch(1, 1)

        self.valve_toggle = QtWidgets.QPushButton(control_pane)
        control_layout.addWidget(self.valve_toggle, 0, 0, QtCore.Qt.AlignLeft)
        self.valve_toggle.setText("Valve")
        self.valve_toggle.setCheckable(True)

        control_layout.addWidget(QtWidgets.QWidget(control_pane), 1, 0, 1, 2)

        self.loadable_tasks = dict()

        self._update_time()
        self._schedule_tab_changed()
        self.set_stopped()
        self.log_event("Program started")

    def _update_time(self):
        now = time.time()
        now = now - int(now)
        self._time_updater.start(max(100, 1000 - int(now * 1000)) + 10)
        self._time_display.setText(QtCore.QDateTime.currentDateTime().toString("hh:mm:ss"))

    @staticmethod
    def _to_duration(seconds):
        if seconds <= 1.0:
            seconds = 1
            minutes = 0
        else:
            minutes = int(seconds / 60)
            seconds -= minutes * 60
            seconds = int(seconds)
        return f"{minutes:3} M {seconds:2} S"

    def _update_elapsed(self):
        if self._schedule_begin_time is None:
            self._elapsed_updater.stop()
            self._elapsed_time.setText("NONE")
            return
        seconds_elapsed = time.time() - self._schedule_begin_time
        self._elapsed_time.setText(self._to_duration(seconds_elapsed))
        seconds_elapsed = seconds_elapsed - int(seconds_elapsed)
        self._elapsed_updater.start(max(100, 1000 - int(seconds_elapsed * 1000)) + 10)

    def _update_remaining(self):
        if self._estimated_end_time is None:
            self._remaining_updater.stop()
            self._remaining_time.setText("NONE")
            return
        seconds_remaining = self._estimated_end_time - time.time()
        if seconds_remaining <= 0.0:
            self._estimated_end_time = None
            self._remaining_updater.stop()
            self._remaining_time.setText("NONE")
            return
        if seconds_remaining < 1.0:
            self._remaining_time.setText(self._to_duration(1.0))
        else:
            self._remaining_time.setText(self._to_duration(seconds_remaining))
        seconds_remaining = seconds_remaining - int(seconds_remaining)
        self._remaining_updater.start(max(100, int(seconds_remaining * 1000)) + 10)

    def log_event(self, text: str):
        """Add an event to the displayed log."""
        scroll_bar = self._log_display.verticalScrollBar()
        was_at_bottom = scroll_bar.value() == scroll_bar.maximum()

        contents = self._log_display.toPlainText()
        if len(contents) > 0:
            contents += "\n"
        contents += QtCore.QDateTime.currentDateTime().toString("[hh:mm:ss] ")
        contents += text
        self._log_display.setPlainText(contents)

        if was_at_bottom:
            scroll_bar.setValue(scroll_bar.maximum())

    def _schedule_tab_changed(self):
        index = self._schedule_control.currentIndex()
        if index <= 0:
            self._selected_file.setText("None")
            self._close_file.setEnabled(False)
            self._manual_task_selected()
            return
        filename = self._schedule_control.widget(index).property("LoadedFileName")
        self._selected_file.setText(filename)
        self._close_file.setEnabled(not self._run_button.isChecked())
        self._run_button.setEnabled(True)

    def add_open_file(self, filename: str):
        tabname = Path(filename).stem

        file_tasks = list()
        FileTask = namedtuple('FileTask', ['task', 'name', 'data'])
        try:
            with open(filename, "rt") as input_file:
                line_number = 0
                for line in input_file:
                    line_number += 1
                    parts = line.split(',', 2)
                    if len(parts) <= 0:
                        continue
                    task_name = parts[0].strip()
                    if len(task_name) <= 0:
                        continue

                    if task_name not in self.loadable_tasks:
                        QtWidgets.QMessageBox.critical(self, "Error Loading File", f"Unknown task {task_name} at line {line_number} in {filename}")
                        return

                    task_data = None
                    if len(parts) > 1:
                        task_data = parts[1]
                    file_tasks.append(FileTask(self.loadable_tasks[task_name], task_name, task_data))
        except IOError as e:
            QtWidgets.QMessageBox.critical(self, "Error Loading File", f"Cannot open file {filename}: {e}")
            return

        container = QtWidgets.QWidget(self._schedule_control)
        container.setProperty("LoadedFileName", filename)
        self._schedule_control.addTab(container, tabname)
        layout = QtWidgets.QGridLayout(container)
        container.setLayout(layout)

        layout.setRowStretch(0, 1)
        layout.setRowStretch(1, 0)
        layout.setColumnStretch(0, 0)
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(2, 0)
        layout.setColumnStretch(3, 0)
        layout.setColumnStretch(4, 1)
        layout.setColumnStretch(5, 0)

        task_list = QtWidgets.QListWidget(container)
        layout.addWidget(task_list, 0, 0, 1, -1)
        task_list.setObjectName("FileTasks")

        add_button = QtWidgets.QPushButton(container)
        layout.addWidget(add_button, 1, 0, 1, 1)
        add_button.setText("Add")

        up_button = QtWidgets.QPushButton(container)
        layout.addWidget(up_button, 1, 2, 1, 1)
        up_button.setIcon(QtWidgets.QApplication.style().standardIcon(QtWidgets.QStyle.SP_ArrowUp))
        up_button.setEnabled(False)

        down_button = QtWidgets.QPushButton(container)
        layout.addWidget(down_button, 1, 3, 1, 1)
        down_button.setIcon(QtWidgets.QApplication.style().standardIcon(QtWidgets.QStyle.SP_ArrowDown))
        down_button.setEnabled(False)

        remove_button = QtWidgets.QPushButton(container)
        layout.addWidget(remove_button, 1, 5, 1, 1)
        remove_button.setText("Remove")
        remove_button.setEnabled(False)

        for task in file_tasks:
            item = QtWidgets.QListWidgetItem()
            item.setText(task.name)
            item.setData(QtCore.Qt.UserRole, task)
            task_list.addItem(item)

        def save_file():
            with open(filename, "wt") as output_file:
                if task_list.count() <= 0:
                    return
                for i in range(task_list.count()):
                    task_item = task_list.item(i)
                    task = task_item.data(QtCore.Qt.UserRole)
                    task_data = task.data
                    content = task.name
                    if task_data is not None:
                        task_data = str(task_data)
                        if len(task_data) > 0:
                            content += "," + task_data
                    content += "\n"
                    output_file.write(content)

        def selection_changed():
            index = task_list.currentIndex().row()
            valid_task = 0 <= index < task_list.count()
            up_button.setEnabled(valid_task and index > 0)
            down_button.setEnabled(valid_task and index < (task_list.count()-1))
            remove_button.setEnabled(valid_task)

        def add_task():
            task_name, ok = QtWidgets.QInputDialog.getItem(self, "Add Task", "Task:", self.loadable_tasks.keys(), 0, False)
            if not ok:
                return
            task = FileTask(self.loadable_tasks[task_name], task_name, None)
            item = QtWidgets.QListWidgetItem()
            item.setText(task.name)
            item.setData(QtCore.Qt.UserRole, task)
            task_list.addItem(item)
            save_file()
            selection_changed()

        def remove_task():
            index = task_list.currentIndex()
            if not index.isValid():
                return
            index = index.row()
            if index < 0:
                return
            task_list.model().removeRow(index)
            save_file()
            selection_changed()

        def task_up():
            index = task_list.currentIndex().row()
            if index <= 0:
                return
            item = task_list.takeItem(index)
            task_list.insertItem(index-1, item)
            task_list.setCurrentRow(index-1)

        def task_down():
            index = task_list.currentIndex().row()
            if index >= (task_list.count()-1):
                return
            item = task_list.takeItem(index)
            task_list.insertItem(index + 1, item)
            task_list.setCurrentRow(index + 1)

        task_list.currentItemChanged.connect(selection_changed)
        add_button.clicked.connect(add_task)
        remove_button.clicked.connect(remove_task)
        up_button.clicked.connect(task_up)
        down_button.clicked.connect(task_down)

        self._schedule_tab_changed()

    def _add_file(self):
        filename = QtWidgets.QFileDialog.getOpenFileName(self, "Select Task List", "", "Tasks (*.txt *.csv)")
        if filename is None or len(filename) <= 0:
            return
        filename = filename[0]
        if filename is None or len(filename) <= 0:
            return
        self.add_open_file(filename)

    def _remove_file(self):
        index = self._schedule_control.currentIndex()
        if index <= 0:
            return
        if self._run_button.isChecked():
            return
        self._schedule_control.removeTab(index)

    def add_manual_task(self, name: str, execute: typing.Callable[[], None]):
        """Add a manual task to the list of executable ones."""
        item = QtWidgets.QListWidgetItem()
        item.setText(name)
        item.setData(QtCore.Qt.UserRole, execute)
        self._task_list.addItem(item)
        _LOGGER.debug(f"Added manual task {name}")
        
    def _manual_task_selected(self):
        index = self._task_list.currentIndex().row()
        if index < 0:
            self._run_button.setEnabled(False)
            return
        self._run_button.setEnabled(True)

    def _run_button_pressed(self):
        if not self._run_button.isChecked():
            abort = QtWidgets.QMessageBox.question(self,
                                                   "Confirm Abort",
                                                   "Task execution is still in progress.  Are you sure you want to abort it?",
                                                   QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
            if abort != QtWidgets.QMessageBox.Yes:
                self._run_button.setChecked(True)
                return

            self._run_button.setEnabled(False)
            self.stop_schedule()
            return

        index = self._schedule_control.currentIndex()
        if index <= 0:
            item = self._task_list.currentItem()
            if item is None:
                return
            _LOGGER.debug(f"Executing manual task")
            item.data(QtCore.Qt.UserRole)()
            return

        task_list = self._schedule_control.currentWidget().findChild(QtWidgets.QListWidget, "FileTasks")
        if task_list.count() <= 0:
            return

        execute_list = list()
        for i in range(task_list.count()):
            task_item = task_list.item(i)
            execute_list.append(task_item.data(QtCore.Qt.UserRole).task)
        _LOGGER.debug(f"Executing task list")
        self.start_schedule(execute_list)

    def start_schedule(self, tasks: typing.Sequence['gspc.schedule.Task']):
        """Called when a schedule start is requested with the list of tasks in the schedule"""
        pass

    def stop_schedule(self):
        """Called when a schedule stop is requested"""
        pass

    def pause_execution(self):
        """Called when a pause of the running schedule is requested"""
        pass

    def resume_execution(self):
        """Called when a resume of the running schedule is requested"""
        pass

    def _pause_clicked(self):
        if not self._pause_button.isEnabled():
            return
        if self._pause_button.isChecked():
            _LOGGER.debug(f"Execution paused requested")
            self.pause_execution()
            self._estimated_end_time = None
            self._remaining_updater.stop()
            self._remaining_time.setText("PAUSED")
        else:
            _LOGGER.debug(f"Execution resumed")
            self.resume_execution()
            self._update_remaining()

    def set_running(self, begin_time: typing.Optional[float] = None):
        """Change the display mode for when a schedule is running"""
        self._schedule_control.setEnabled(False)
        self._pause_button.setChecked(False)
        self._pause_button.setEnabled(True)
        self._run_button.setText("Stop")
        self._run_button.setIcon(QtWidgets.QApplication.style().standardIcon(QtWidgets.QStyle.SP_MediaStop))
        self._run_button.setChecked(True)
        self._close_file.setEnabled(False)
        if begin_time is not None:
            self._schedule_begin_time = begin_time
        self._estimated_end_time = None
        self._update_elapsed()
        self._update_remaining()

    def set_stopped(self):
        """Change the display mode for when no schedule is running"""
        self._schedule_control.setEnabled(True)
        self._pause_button.setEnabled(False)
        self._pause_button.setChecked(False)
        self._run_button.setText("Start")
        self._run_button.setIcon(QtWidgets.QApplication.style().standardIcon(QtWidgets.QStyle.SP_MediaPlay))
        self._run_button.setChecked(False)
        self._close_file.setEnabled(self._schedule_control.currentIndex() > 0)
        self._schedule_begin_time = None
        self._estimated_end_time = None
        self.current_task.setText("NONE")
        self._update_elapsed()
        self._update_remaining()
        self._schedule_tab_changed()

    def update_estimated_end(self, end_time: typing.Optional[float]):
        """Update the estimated completion time for the currently running schedule"""
        self._estimated_end_time = end_time
        self._update_remaining()

    def get_open_files(self) -> typing.Sequence[str]:
        """Get the list of currently open files."""
        if self._schedule_control.count() <= 1:
            return list()
        open_files = list()
        for index in range(1, self._schedule_control.count()):
            filename = str(self._schedule_control.widget(index).property("LoadedFileName"))
            if len(filename) <= 0:
                continue
            open_files.append(filename)
        return open_files


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    window = Main()
    window.show()
    window.add_manual_task("Test task 1", lambda: None)
    window.add_manual_task("Test task 2", lambda: None)
    window.add_open_file("/dev/null")
    window.loadable_tasks["Task 1"] = "Data 1"
    window.loadable_tasks["Task 2"] = "Data 2"
    sys.exit(app.exec_())
