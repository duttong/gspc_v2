#!/usr/bin/python3

import logging
from PyQt5 import QtCore, QtGui, QtWidgets

_LOGGER = logging.getLogger(__name__)


class Display(QtWidgets.QMainWindow):
    def __init__(self):
        QtWidgets.QMainWindow.__init__(self)
        self.setObjectName("Simulator")
        self.setWindowTitle("Output Display")

        central_widget = QtWidgets.QWidget(self)
        self.setCentralWidget(central_widget)
        central_layout = QtWidgets.QFormLayout(central_widget)
        central_widget.setLayout(central_layout)

        monospace = QtGui.QFont()
        monospace.setFamily("Monospace")
        monospace.setStyleHint(QtGui.QFont.TypeWriter)

        self.selected_source = QtWidgets.QLabel("NONE", central_widget)
        self.selected_source.setFont(monospace)
        central_layout.addRow("Sampling", self.selected_source)

        self.flow_setpoint = QtWidgets.QLabel("NONE", central_widget)
        self.flow_setpoint.setFont(monospace)
        central_layout.addRow("Flow setpoint", self.flow_setpoint)

        self.gc_trigger = QtWidgets.QLabel("NONE", central_widget)
        self.gc_trigger.setFont(monospace)
        central_layout.addRow("GC Triggered", self.gc_trigger)

        self.trap_temperature = QtWidgets.QDoubleSpinBox(central_widget)
        self.trap_temperature.setRange(-273, 1000)
        self.trap_temperature.setValue(-30)
        central_layout.addRow("Trap", self.trap_temperature)

        self.sample_flow = QtWidgets.QDoubleSpinBox(central_widget)
        self.sample_flow.setRange(0, 100)
        self.sample_flow.setValue(1)
        central_layout.addRow("Flow", self.sample_flow)

        self.sample_pressure = QtWidgets.QDoubleSpinBox(central_widget)
        self.sample_pressure.setRange(0, 1200)
        self.sample_pressure.setValue(850)
        central_layout.addRow("Pressure", self.sample_pressure)

    def update_gc_trigger(self):
        self.gc_trigger.setText(QtCore.QDateTime.currentDateTime().toString("hh:mm:ss"))


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    window = Display()
    window.show()
    sys.exit(app.exec_())
