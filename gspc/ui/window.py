#!/usr/bin/python3

import logging
import time
import typing
from PyQt5 import QtCore, QtGui, QtWidgets
from pathlib import Path
from collections import namedtuple

if typing.TYPE_CHECKING:
    import gspc.schedule

_LOGGER = logging.getLogger(__name__)


def _to_duration(seconds):
    if seconds <= 1.0:
        seconds = 1
        minutes = 0
    else:
        minutes = int(seconds / 60)
        seconds -= minutes * 60
        seconds = int(seconds)
    return f"{minutes:3d} M {seconds:2d} S"


def _to_time_display(point):
    return QtCore.QDateTime.fromMSecsSinceEpoch(round(point * 1000.0)).toString("hh:mm:ss")


class _InstantDisplay(QtCore.QObject):
    def __init__(self, label, parent=None):
        QtCore.QObject.__init__(self, parent)

        self._label = label
        self._label.setText("NONE")

        self._event: typing.Optional['gspc.schedule.Event'] = None

        self._updater = QtCore.QTimer(self)
        self._updater.setSingleShot(True)
        self._updater.timeout.connect(self._update_label)

        self._update_label()

    def _update_label(self):
        if self._event is None:
            self._updater.stop()
            self._label.setText("NONE")
            return
        seconds_remaining = self._event.time - time.time()
        if self._event.occurred or seconds_remaining <= 0.0:
            self._updater.stop()
            self._label.setText("<font color='green'>" + _to_time_display(self._event.time) + "</font>")
            return
        self._label.setText(_to_duration(seconds_remaining))
        seconds_remaining = seconds_remaining - int(seconds_remaining)
        self._updater.start(max(100, int(seconds_remaining * 1000)) + 10)

    def set_event(self, event: typing.Optional['gspc.schedule.Event']):
        self._event = event
        self._update_label()

    def pause(self):
        self._updater.stop()
        self._label.setText("<font color='orange'>PAUSED</font>")

    def resume(self):
        self._update_label()

    def clear(self):
        self._updater.stop()
        self._event = None
        self._label.setText("NONE")


class _OnOffDisplay(QtCore.QObject):
    def __init__(self, label, parent=None):
        QtCore.QObject.__init__(self, parent)

        self._label = label

        self._on_event: typing.Optional['gspc.schedule.Event'] = None
        self._off_event: typing.Optional['gspc.schedule.Event'] = None

        self._updater = QtCore.QTimer(self)
        self._updater.setSingleShot(True)
        self._updater.timeout.connect(self._update_label)

        self._update_label()

    def _off_time(self):
        if self._off_event is None:
            return None
        if self._off_event.occurred:
            return self._off_event.time
        return None

    def _update_label(self):
        if self._on_event is None:
            self._updater.stop()
            self._label.setText("NONE")
            return
        if self._off_event is not None and self._off_event.occurred:
            self._updater.stop()
            self._label.setText("<font color='red'>OFF AT " + _to_time_display(self._off_event.time) + "</font>")
            return

        if not self._on_event.occurred:
            seconds_remaining = self._on_event.time - time.time()
            self._label.setText(_to_duration(seconds_remaining))
            seconds_remaining = seconds_remaining - int(seconds_remaining)
            self._updater.start(max(100, int(seconds_remaining * 1000)) + 10)
            return
        if self._off_event is None:
            self._updater.stop()
            self._label.setText("<font color='green'>ON AT " + _to_time_display(self._on_event.time) + "</font>")
            return

        seconds_remaining = self._off_event.time - time.time()
        self._label.setText("<font color='green'>ON UNTIL " + _to_duration(seconds_remaining) + "</font")
        seconds_remaining = seconds_remaining - int(seconds_remaining)
        self._updater.start(max(100, int(seconds_remaining * 1000)) + 10)

    def set_events(self, on: typing.Optional['gspc.schedule.Event'], off: typing.Optional['gspc.schedule.Event']):
        self._on_event = on
        self._off_event = off
        self._update_label()

    def pause(self):
        self._updater.stop()
        self._label.setText("<font color='orange'>PAUSED</font>")

    def resume(self):
        self._update_label()

    def clear(self):
        self._updater.stop()
        self._on_event = None
        self._off_event = None
        self._label.setText("NONE")


class Main(QtWidgets.QMainWindow):
    def __init__(self, enable_pfp: bool = True):
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
        status_layout.setRowStretch(4, 0)
        status_layout.setRowStretch(5, 0)
        status_layout.setRowStretch(6, 0)
        status_layout.setRowStretch(7, 1)
        status_layout.setColumnStretch(0, 0)
        status_layout.setColumnStretch(1, 1)
        status_layout.setColumnStretch(2, 0)

        status_layout.addWidget(QtWidgets.QLabel("File:", status_pane), 0, 0, QtCore.Qt.AlignRight)
        self._selected_file = QtWidgets.QLabel(status_pane)
        #self._selected_file.setFont(monospace)
        self._selected_file.setText("NONE")
        status_layout.addWidget(self._selected_file, 0, 1, 1, 1, QtCore.Qt.AlignLeft)
        self._open_file = QtWidgets.QPushButton(status_pane)
        status_layout.addWidget(self._open_file, 0, 2, 1, 1)
        self._open_file.setIcon(QtWidgets.QApplication.style().standardIcon(QtWidgets.QStyle.SP_DialogOpenButton))
        self._open_file.clicked.connect(self._add_file)
        self._open_file.setToolTip("Open task file and add to the available tasks tabs")
        self._close_file = QtWidgets.QPushButton(status_pane)
        status_layout.addWidget(self._close_file, 0, 3, 1, 1)
        self._close_file.setIcon(QtWidgets.QApplication.style().standardIcon(QtWidgets.QStyle.SP_DialogCloseButton))
        self._close_file.setEnabled(False)
        self._close_file.clicked.connect(self._remove_file)
        self._close_file.setToolTip("Close the selected task tab")

        status_layout.addWidget(QtWidgets.QLabel("Output:", status_pane), 1, 0, QtCore.Qt.AlignRight)
        self._selected_output = QtWidgets.QLabel(status_pane)
        #self._selected_output.setFont(monospace)
        self._selected_output.setText("NONE")
        status_layout.addWidget(self._selected_output, 1, 1, 1, 1, QtCore.Qt.AlignLeft)
        self._open_output = QtWidgets.QPushButton(status_pane)
        status_layout.addWidget(self._open_output, 1, 2, 1, 1)
        self._open_output.setIcon(QtWidgets.QApplication.style().standardIcon(QtWidgets.QStyle.SP_DialogOpenButton))
        self._open_output.clicked.connect(self._set_output)
        self._open_output.setToolTip("Select an output file to write the log to")
        self._close_output = QtWidgets.QPushButton(status_pane)
        status_layout.addWidget(self._close_output, 1, 3, 1, 1)
        self._close_output.setIcon(QtWidgets.QApplication.style().standardIcon(QtWidgets.QStyle.SP_DialogCloseButton))
        self._close_output.setEnabled(False)
        self._close_output.clicked.connect(self._remove_output)
        self._close_output.setToolTip("Close the output log file and do not write further to it")

        status_layout.addWidget(QtWidgets.QLabel("Task:", status_pane), 2, 0, QtCore.Qt.AlignRight)
        self.current_task = QtWidgets.QLabel(status_pane)
        #self.current_task.setFont(monospace)
        self.current_task.setText("NONE")
        status_layout.addWidget(self.current_task, 2, 1, 1, -1, QtCore.Qt.AlignLeft)

        status_layout.addWidget(QtWidgets.QLabel("Time elapsed:", status_pane), 3, 0, QtCore.Qt.AlignRight)
        self._elapsed_time = QtWidgets.QLabel(status_pane)
        self._elapsed_time.setFont(monospace)
        self._elapsed_time.setText("NONE")
        status_layout.addWidget(self._elapsed_time, 3, 1, 1, -1, QtCore.Qt.AlignLeft)

        self._schedule_begin_time: typing.Optional[float] = None
        self._elapsed_updater = QtCore.QTimer(self._elapsed_time)
        self._elapsed_updater.setSingleShot(True)
        self._elapsed_updater.timeout.connect(self._update_elapsed)

        status_layout.addWidget(QtWidgets.QLabel("Cryogen:", status_pane), 4, 0, QtCore.Qt.AlignRight)
        cryogen = QtWidgets.QLabel(status_pane)
        cryogen.setFont(monospace)
        cryogen.setText("NONE")
        status_layout.addWidget(cryogen, 4, 1, 1, -1, QtCore.Qt.AlignLeft)
        self._cryogen = _InstantDisplay(cryogen, self)

        status_layout.addWidget(QtWidgets.QLabel("Sample:", status_pane), 5, 0, QtCore.Qt.AlignRight)
        sample = QtWidgets.QLabel(status_pane)
        sample.setFont(monospace)
        sample.setText("NONE")
        status_layout.addWidget(sample, 5, 1, 1, -1, QtCore.Qt.AlignLeft)
        self._sample = _OnOffDisplay(sample, self)

        status_layout.addWidget(QtWidgets.QLabel("GC:", status_pane), 6, 0, QtCore.Qt.AlignRight)
        gc = QtWidgets.QLabel(status_pane)
        gc.setFont(monospace)
        gc.setText("NONE")
        status_layout.addWidget(gc, 6, 1, 1, -1, QtCore.Qt.AlignLeft)
        self._gc = _InstantDisplay(gc, self)

        status_layout.addWidget(QtWidgets.QWidget(status_pane), 7, 0, 1, -1)

        self._log_display = QtWidgets.QPlainTextEdit(central_widget)
        central_layout.addWidget(self._log_display, 1, 1, 1, -1)
        self._log_display.setFont(monospace)
        self._log_display.setReadOnly(True)
        self._log_display.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)

        self._schedule_control = QtWidgets.QTabWidget(central_widget)
        central_layout.addWidget(self._schedule_control, 2, 0, 1, 1)
        self._task_list = QtWidgets.QListWidget(self._schedule_control)
        self._task_list.selectionModel().selectionChanged.connect(self._manual_task_selected)
        self._schedule_control.addTab(self._task_list, "Manual")

        self._schedule_control.currentChanged.connect(self._schedule_tab_changed)

        io_display = QtWidgets.QTabWidget(central_widget)
        central_layout.addWidget(io_display, 2, 1, 1, -1)

        inputs_pane = QtWidgets.QWidget(central_widget)
        io_display.addTab(inputs_pane, "Status")
        inputs_layout = QtWidgets.QFormLayout(inputs_pane)
        inputs_pane.setLayout(inputs_layout)

        self.sample_pressure = QtWidgets.QLabel(inputs_pane)
        self.sample_pressure.setText("0000.00")
        self.sample_pressure.setFont(monospace)
        inputs_layout.addRow("Pressure (torr):", self.sample_pressure)

        if enable_pfp:
            self.pfp_pressure = QtWidgets.QLabel(inputs_pane)
            self.pfp_pressure.setText("0000.00")
            self.pfp_pressure.setFont(monospace)
            inputs_layout.addRow("PFP Pressure (torr):", self.pfp_pressure)
        else:
            self.pfp_pressure = None

        self.sample_flow = QtWidgets.QLabel(inputs_pane)
        self.sample_flow.setText("   0.000")
        self.sample_flow.setFont(monospace)
        inputs_layout.addRow("Flow (V):", self.sample_flow)

        self.oven_temperature = QtWidgets.QLabel(inputs_pane)
        self.oven_temperature.setText("   0.000")
        self.oven_temperature.setFont(monospace)
        inputs_layout.addRow("Oven (V):", self.oven_temperature)

        self.selected_ssv_in = QtWidgets.QLabel(inputs_pane)
        self.selected_ssv_in.setText("   0")
        self.selected_ssv_in.setFont(monospace)
        inputs_layout.addRow("SSV:", self.selected_ssv_in)

        if enable_pfp:
            self.selected_pfp_in = QtWidgets.QLabel(inputs_pane)
            self.selected_pfp_in.setText("   -")
            self.selected_pfp_in.setFont(monospace)
            inputs_layout.addRow("PFP:", self.selected_pfp_in)
        else:
            self.selected_pfp_in = None

        control_pane = QtWidgets.QWidget(central_widget)
        io_display.addTab(control_pane, "Control")
        control_layout = QtWidgets.QVBoxLayout(control_pane)
        control_pane.setLayout(control_layout)

        self.overflow_toggle = QtWidgets.QPushButton()
        self.overflow_toggle.setText("Overflow")
        self.overflow_toggle.setStyleSheet("""
            QPushButton {
                background-color: red;
            }
            QPushButton:checked {
                background-color: green;     
            }
        """)
        self.overflow_toggle.setCheckable(True)
        control_layout.addWidget(self._line_layout(control_pane, self.overflow_toggle))

        self.vacuum_toggle = QtWidgets.QPushButton(control_pane)
        self.vacuum_toggle.setText("Vacuum")
        self.vacuum_toggle.setStyleSheet("""
            QPushButton {
                background-color: red;
            }
            QPushButton:checked {
                background-color: green;     
            }
        """)
        self.vacuum_toggle.setCheckable(True)
        control_layout.addWidget(self._line_layout(control_pane, self.vacuum_toggle))

        self.evacuate_toggle = QtWidgets.QPushButton(control_pane)
        self.evacuate_toggle.setText("Evacuate")
        self.evacuate_toggle.setStyleSheet("""
            QPushButton {
                background-color: red;
            }
            QPushButton:checked {
                background-color: green;     
            }
        """)
        self.evacuate_toggle.setCheckable(True)
        control_layout.addWidget(self._line_layout(control_pane, self.evacuate_toggle))

        self.trigger_gc = QtWidgets.QPushButton(control_pane)
        self.trigger_gc.setText("Trigger GCMS")
        control_layout.addWidget(self._line_layout(control_pane, self.trigger_gc))

        self.apply_ssv = QtWidgets.QPushButton(control_pane)
        self.apply_ssv.setText("Change SSV")
        self.selected_ssv = QtWidgets.QSpinBox(control_pane)
        self.selected_ssv.setRange(0, 15)
        control_layout.addWidget(self._line_layout(control_pane, self.apply_ssv, self.selected_ssv))

        self.apply_flow = QtWidgets.QPushButton(control_pane)
        self.apply_flow.setText("Change Flow")
        self.output_flow = QtWidgets.QDoubleSpinBox(control_pane)
        self.output_flow.setRange(0.0, 188.0)
        self.output_flow.setSingleStep(0.1)
        self.output_flow_feedback = QtWidgets.QLabel(inputs_pane)
        self.output_flow_feedback.setText("0.000")
        self.output_flow_feedback.setFont(monospace)
        control_layout.addWidget(self._line_layout(control_pane, self.apply_flow, self.output_flow,
                                                   self.output_flow_feedback))
        
        if enable_pfp:
            self.pfp_open = QtWidgets.QPushButton(control_pane)
            self.pfp_open.setText("PFP Open")
            self.pfp_close = QtWidgets.QPushButton(control_pane)
            self.pfp_close.setText("PFP Close")
            self.select_pfp = QtWidgets.QSpinBox(control_pane)
            self.select_pfp.setRange(1, 12)
            control_layout.addWidget(self._line_layout(control_pane, self.pfp_open, self.pfp_close, self.select_pfp))
        else:
            self.pfp_open = None
            self.pfp_close = None
            self.select_pfp = None

        control_layout.addStretch(1)

        self.loadable_tasks: typing.Dict[str, 'gspc.schedule.Task'] = dict()

        self._update_time()
        self._schedule_tab_changed()
        self.set_stopped()
        self.log_event("Program started")

    @staticmethod
    def _line_layout(parent: QtWidgets.QWidget, *widgets: QtWidgets.QWidget) -> QtWidgets.QWidget:
        line_box = QtWidgets.QWidget(parent)
        line_layout = QtWidgets.QHBoxLayout(line_box)
        line_layout.setContentsMargins(0, 0, 0, 0)
        line_box.setLayout(line_layout)

        for w in widgets:
            w.setParent(line_box)
            line_layout.addWidget(w)

        line_layout.addStretch(1)

        return line_box

    def _update_time(self):
        now = time.time()
        now = now - int(now)
        self._time_updater.start(max(100, 1000 - int(now * 1000)) + 10)
        self._time_display.setText(QtCore.QDateTime.currentDateTime().toString("hh:mm:ss"))

    def _update_elapsed(self):
        if self._schedule_begin_time is None:
            self._elapsed_updater.stop()
            self._elapsed_time.setText("NONE")
            return
        seconds_elapsed = time.time() - self._schedule_begin_time
        self._elapsed_time.setText(_to_duration(seconds_elapsed))
        seconds_elapsed = seconds_elapsed - int(seconds_elapsed)
        self._elapsed_updater.start(max(100, 1000 - int(seconds_elapsed * 1000)) + 10)

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

    def _reset_schedule_contents(self):
        for task_list_index in range(1, self._schedule_control.count()):
            task_list = self._schedule_control.widget(task_list_index).findChild(QtWidgets.QListWidget, "FileTasks")
            if task_list is None:
                continue
            for i in range(task_list.count()):
                task_item: QtWidgets.QListWidgetItem = task_list.item(i)
                task_data = task_item.data(QtCore.Qt.UserRole)
                task_item.setText(task_data.name)
                task_item.setFlags(task_item.flags() | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
            task_list.clearSelection()

    @property
    def current_task_list(self) -> typing.Optional[QtWidgets.QListWidget]:
        return self._schedule_control.currentWidget().findChild(QtWidgets.QListWidget, "FileTasks")

    def modify_active_list(self, modified_index: int) -> bool:
        return True

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
        add_button.setObjectName("AddFileTask")

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

        def selected_index():
            selected = task_list.selectedIndexes()
            if not selected:
                return -1
            return selected[0].row()

        def selection_changed():
            index = selected_index()
            valid_task = 0 <= index < task_list.count()
            if not valid_task:
                up_button.setEnabled(False)
                down_button.setEnabled(False)
                remove_button.setEnabled(False)
                return

            def is_mutable(i: QtWidgets.QListWidgetItem):
                return bool(i.flags() & QtCore.Qt.ItemIsSelectable)

            task_item = task_list.item(index)
            if not is_mutable(task_item):
                up_button.setEnabled(False)
                down_button.setEnabled(False)
                remove_button.setEnabled(False)
                return

            up_button.setEnabled(index > 0 and is_mutable(task_list.item(index-1)))
            down_button.setEnabled(index < (task_list.count()-1) and is_mutable(task_list.item(index+1)))
            remove_button.setEnabled(True)

        def add_task():
            task_name, ok = QtWidgets.QInputDialog.getItem(self, "Add Task", "Task:", self.loadable_tasks.keys(), 0, False)
            if not ok:
                return
            task = FileTask(self.loadable_tasks[task_name], task_name, None)
            item = QtWidgets.QListWidgetItem()
            item.setText(task.name)
            item.setData(QtCore.Qt.UserRole, task)
            task_list.addItem(item)

            index = task_list.count()-1
            if task_list == self.current_task_list and not self.modify_active_list(index):
                task_list.takeItem(index)
                return

            save_file()
            selection_changed()

        def remove_task():
            index = selected_index()
            if not index.isValid():
                return
            index = index.row()
            if index < 0:
                return

            item = task_list.takeItem(index)
            if task_list == self.current_task_list and not self.modify_active_list(index):
                task_list.insertItem(index, item)
                task_list.setCurrentRow(index)
                return

            save_file()
            selection_changed()

        def task_up():
            index = selected_index()
            if index <= 0:
                return

            item = task_list.takeItem(index)
            task_list.insertItem(index-1, item)
            if task_list == self.current_task_list and not self.modify_active_list(index-1):
                item = task_list.takeItem(index-1)
                task_list.insertItem(index, item)
                task_list.setCurrentRow(index)
                return

            task_list.setCurrentRow(index-1)
            save_file()

        def task_down():
            index = selected_index()
            if index >= (task_list.count()-1):
                return

            item = task_list.takeItem(index)
            task_list.insertItem(index + 1, item)
            if task_list == self.current_task_list and not self.modify_active_list(index):
                item = task_list.takeItem(index + 1)
                task_list.insertItem(index, item)
                task_list.setCurrentRow(index)
                return

            task_list.setCurrentRow(index + 1)
            save_file()

        task_list.selectionModel().selectionChanged.connect(selection_changed)
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

    def _set_output(self):
        filename = QtWidgets.QFileDialog.getSaveFileName(self, "Select Output", "", "Output (*.txt *.xl)",
                                                         options=QtWidgets.QFileDialog.DontConfirmOverwrite)
        if filename is None or len(filename) <= 0:
            return
        filename = filename[0]
        if filename is None or len(filename) <= 0:
            return
        file = Path(filename)
        if file.suffix.lower() == ".txt" or file.suffix.lower() == ".xl":
            rootparts = list(file.parts[:-1]) + [file.stem]
            self.change_output(str(Path(*rootparts)))
        else:
            self.change_output(filename)

    def _remove_output(self):
        self.change_output(None)

    def add_manual_task(self, name: str, execute: typing.Callable[[], None]):
        """Add a manual task to the list of executable ones."""
        item = QtWidgets.QListWidgetItem()
        item.setText(name)
        item.setData(QtCore.Qt.UserRole, execute)
        self._task_list.addItem(item)
        _LOGGER.debug(f"Added manual task {name}")
        
    def _manual_task_selected(self):
        selected = self._task_list.selectedIndexes()
        if not selected:
            self._run_button.setEnabled(False)
            return
        index = selected[0].row()
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

        task_list = self.current_task_list
        if task_list.count() <= 0:
            return

        task_list.clearSelection()
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

    def change_output(self, name: typing.Optional[str]):
        """Change the output file base"""
        if name is not None and len(name) > 0:
            self._selected_output.setText(name)
            self._close_file.setEnabled(True)
        else:
            self._selected_output.setText("")
            self._close_file.setEnabled(False)

    def _pause_clicked(self):
        if not self._pause_button.isEnabled():
            return
        if self._pause_button.isChecked():
            _LOGGER.debug(f"Execution paused requested")
            self.pause_execution()
            self._cryogen.pause()
            self._sample.pause()
            self._gc.pause()
        else:
            _LOGGER.debug(f"Execution resumed")
            self.resume_execution()
            self._cryogen.resume()
            self._sample.resume()
            self._gc.resume()

    def set_running(self, begin_time: typing.Optional[float] = None):
        """Change the display mode for when a schedule is running"""

        self._schedule_control.tabBar().setEnabled(False)
        task_list = self.current_task_list
        if task_list:
            task_list.clearSelection()

        self._pause_button.setChecked(False)
        self._pause_button.setEnabled(True)
        self._run_button.setText("Stop")
        self._run_button.setIcon(QtWidgets.QApplication.style().standardIcon(QtWidgets.QStyle.SP_MediaStop))
        self._run_button.setChecked(True)
        self._close_file.setEnabled(False)
        self._task_list.setEnabled(False)

        if begin_time is not None:
            self._schedule_begin_time = begin_time
        self._update_elapsed()

    def set_stopped(self):
        """Change the display mode for when no schedule is running"""

        self._schedule_control.tabBar().setEnabled(True)
        task_list = self.current_task_list
        if task_list:
            task_list.clearSelection()

        self._pause_button.setEnabled(False)
        self._pause_button.setChecked(False)
        self._run_button.setText("Start")
        self._run_button.setIcon(QtWidgets.QApplication.style().standardIcon(QtWidgets.QStyle.SP_MediaPlay))
        self._run_button.setChecked(False)
        self._close_file.setEnabled(self._schedule_control.currentIndex() > 0)
        self._task_list.setEnabled(True)
        self._schedule_begin_time = None

        self.current_task.setText("NONE")
        self._update_elapsed()
        self._cryogen.clear()
        self._sample.clear()
        self._gc.clear()
        self._schedule_tab_changed()
        self._reset_schedule_contents()

    def update_events(self, events: typing.Dict[str, 'gspc.schedule.Event']):
        """Update the events currently active in the schedule"""
        self._cryogen.set_event(events.get('cryogen'))
        self._sample.set_events(events.get('sample_open'), events.get('sample_close'))
        self._gc.set_event(events.get('gc_trigger'))

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
