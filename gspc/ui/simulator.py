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

        self.cryogen = QtWidgets.QLabel("OFF", central_widget)
        self.cryogen.setFont(monospace)
        central_layout.addRow("Cryogen", self.cryogen)

        self.gc_cryogen = QtWidgets.QLabel("OFF", central_widget)
        self.gc_cryogen.setFont(monospace)
        central_layout.addRow("GC Cryogen", self.gc_cryogen)

        self.cryro_heater = QtWidgets.QLabel("OFF", central_widget)
        self.cryro_heater.setFont(monospace)
        central_layout.addRow("Cryo heater", self.cryro_heater)

        self.vacuum = QtWidgets.QLabel("OFF", central_widget)
        self.vacuum.setFont(monospace)
        central_layout.addRow("Vacuum", self.vacuum)

        self.sample_valve = QtWidgets.QLabel("OFF", central_widget)
        self.sample_valve.setFont(monospace)
        central_layout.addRow("Sample valve", self.sample_valve)

        self.load_inject = QtWidgets.QLabel("UNSET", central_widget)
        self.load_inject.setFont(monospace)
        central_layout.addRow("Load/Inject", self.load_inject)

        self.pre_column = QtWidgets.QLabel("UNSET", central_widget)
        self.pre_column.setFont(monospace)
        central_layout.addRow("Precolumn", self.pre_column)

        self.gc_trigger = QtWidgets.QLabel("NONE", central_widget)
        self.gc_trigger.setFont(monospace)
        central_layout.addRow("GC Triggered", self.gc_trigger)

        self.overflow = QtWidgets.QLabel("OFF", central_widget)
        self.overflow.setFont(monospace)
        central_layout.addRow("Overflow", self.overflow)

        self.evacuation = QtWidgets.QLabel("OFF", central_widget)
        self.evacuation.setFont(monospace)
        central_layout.addRow("Evacuation", self.evacuation)

        self.ssv_position = QtWidgets.QLabel("UNSET", central_widget)
        self.ssv_position.setFont(monospace)
        central_layout.addRow("SSV", self.ssv_position)

        self.pfp_valve = QtWidgets.QLabel("UNSET", central_widget)
        self.pfp_valve.setFont(monospace)
        central_layout.addRow("PFP", self.pfp_valve)

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
        self.oven_temperature.setValue(6)
        central_layout.addRow("Oven", self.oven_temperature)

        self.pfp_pressure = QtWidgets.QDoubleSpinBox(central_widget)
        self.pfp_pressure.setRange(0, 1200)
        self.pfp_pressure.setValue(850)
        central_layout.addRow("PFP Pressure", self.pfp_pressure)

    def update_gcms_trigger(self):
        self.gc_trigger.setText(QtCore.QDateTime.currentDateTime().toString("hh:mm:ss"))


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    window = Display()
    window.show()
    sys.exit(app.exec_())
