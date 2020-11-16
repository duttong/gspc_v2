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

        self.cyrogen = QtWidgets.QLabel("OFF", central_widget)
        self.cyrogen.setFont(monospace)
        central_layout.addRow("Cyrogen", self.cyrogen)

        self.gc_cyrogen = QtWidgets.QLabel("OFF", central_widget)
        self.gc_cyrogen.setFont(monospace)
        central_layout.addRow("GC Cyrogen", self.gc_cyrogen)

        self.vacuum = QtWidgets.QLabel("OFF", central_widget)
        self.vacuum.setFont(monospace)
        central_layout.addRow("Vacuum", self.vacuum)

        self.sample_valve = QtWidgets.QLabel("OFF", central_widget)
        self.sample_valve.setFont(monospace)
        central_layout.addRow("Sample valve", self.sample_valve)

        self.load = QtWidgets.QLabel("OFF", central_widget)
        self.load.setFont(monospace)
        central_layout.addRow("Load", self.load)

        self.pre_column = QtWidgets.QLabel("OUT", central_widget)
        self.pre_column.setFont(monospace)
        central_layout.addRow("Precolumn", self.pre_column)

        self.gc_solenoid = QtWidgets.QLabel("OFF", central_widget)
        self.gc_solenoid.setFont(monospace)
        central_layout.addRow("GC solenoid", self.gc_solenoid)

        self.gc_heater = QtWidgets.QLabel("OFF", central_widget)
        self.gc_heater.setFont(monospace)
        central_layout.addRow("GC heater", self.gc_heater)

        self.gc_trigger = QtWidgets.QLabel("NONE", central_widget)
        self.gc_trigger.setFont(monospace)
        central_layout.addRow("GC Triggered", self.gc_trigger)

        self.overflow = QtWidgets.QLabel("OFF", central_widget)
        self.overflow.setFont(monospace)
        central_layout.addRow("Overflow", self.overflow)

        self.selected_source = QtWidgets.QLabel("UNSET", central_widget)
        self.selected_source.setFont(monospace)
        central_layout.addRow("Source", self.selected_source)

        self.sample_flow = QtWidgets.QDoubleSpinBox(central_widget)
        self.sample_flow.setRange(0, 100)
        self.sample_flow.setValue(1)
        central_layout.addRow("Flow", self.sample_flow)

        self.sample_pressure = QtWidgets.QDoubleSpinBox(central_widget)
        self.sample_pressure.setRange(0, 1200)
        self.sample_pressure.setValue(850)
        central_layout.addRow("Pressure", self.sample_pressure)

        self.oven_temperature = QtWidgets.QDoubleSpinBox(central_widget)
        self.oven_temperature.setRange(-273, 300)
        self.oven_temperature.setValue(21)
        central_layout.addRow("GC Oven", self.oven_temperature)

    def update_gc_trigger(self):
        self.gc_trigger.setText(QtCore.QDateTime.currentDateTime().toString("hh:mm:ss"))


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    window = Display()
    window.show()
    sys.exit(app.exec_())
