
import sys
import asyncio
import csv
from datetime import datetime

from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import pyqtSignal, QObject

from bleak import BleakScanner, BleakClient
import qasync
from pathlib import Path

import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

DEVICE_ADDR = "EB:F8:1D:58:73:87"

async def scan_for_device(target_addr):
    devices = await BleakScanner.discover()
    for device in devices:
        if device.address == target_addr:
            return device
    return None

class BatteryMeasurementApp(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Battery Measurement")
        self.setGeometry(100, 100, 800, 600)

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        main_layout = QtWidgets.QHBoxLayout(central)

        # Left column
        left_col = QtWidgets.QVBoxLayout()
        main_layout.addLayout(left_col, 0)

        self.grp_info = QtWidgets.QGroupBox("General Information")
        self.info_layout = QtWidgets.QVBoxLayout(self.grp_info)
        left_col.addWidget(self.grp_info)

        self.clock_label = QtWidgets.QLabel("Clock: --:--:--")
        self.clock_label.setFont(QtGui.QFont("Arial", 16))
        self.info_layout.addWidget(self.clock_label)

        self.next_meas_label = QtWidgets.QLabel("Next Measurement: --:--:--")
        self.next_meas_label.setFont(QtGui.QFont("Arial", 16))
        self.info_layout.addWidget(self.next_meas_label)

        self.info_layout.addStretch()

        # Center: graph
        middle_col = QtWidgets.QVBoxLayout()
        main_layout.addLayout(middle_col, 2)

        self.grp_graph = QtWidgets.QGroupBox("Graphs")
        self.graph_layout = QtWidgets.QVBoxLayout(self.grp_graph)
        middle_col.addWidget(self.grp_graph)

        self.figure = Figure(figsize=(5, 4), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        self.graph_layout.addWidget(self.canvas)
        self.ax = self.figure.add_subplot(111)

        self.plot_device_status_data = []

        # Right: console
        right_col = QtWidgets.QVBoxLayout()
        main_layout.addLayout(right_col, 0)

        self.grp_console = QtWidgets.QGroupBox("Console (FIFO)")
        self.console_layout = QtWidgets.QVBoxLayout(self.grp_console)
        right_col.addWidget(self.grp_console)

        self.console_view = QtWidgets.QTextEdit()
        self.console_view.setReadOnly(True)
        self.console_view.textChanged.connect(lambda: self.console_view.moveCursor(QtGui.QTextCursor.End))
        self.console_view.setFixedWidth(400)
        self.console_layout.addWidget(self.console_view)


                # Initialize CSV logging
        self.csv_filename = f"battery_measurement_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        self.csv_file = open(self.csv_filename, 'w', newline='')
        self.csv_writer = csv.writer(self.csv_file)
        self.csv_writer.writerow(['Timestamp', 'Elapsed_Seconds', 'Device_Status'])
        self.csv_file.flush()
        self.data_point_count = 0

        async def check_device_and_update(self):
            """Async coroutine to check device and update plot"""
            device_on = await scan_for_device(DEVICE_ADDR) is not None
            self.plot_device_status_data.append(1 if device_on else 0)
            
            # Log to CSV
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            elapsed_seconds = self.data_point_count
            device_status = 1 if device_on else 0
            self.csv_writer.writerow([timestamp, elapsed_seconds, device_status])
            self.csv_file.flush()
            self.data_point_count += 1
            
            if len(self.plot_device_status_data) > 60*3:  # Keep last 3 minutes of data at 1s intervals
                self.plot_device_status_data.pop(0)
            
            self.ax.clear()
            self.ax.plot(self.plot_device_status_data)
            self.ax.set_ylim(-0.5, 1.5)
            self.ax.set_xlim(0, 60*3)
            self.ax.set_xticks(range(0, 181, 20))
            self.ax.set_title("Device Presence (1=Present, 0=Absent)")
            self.ax.set_xlabel("Time (s)")
            self.ax.set_ylabel("Status")
            self.canvas.draw()

        self.check_device_and_update = check_device_and_update

        # Clock
        self.actual_time = {'h': 0, 'm': 0, 's': 0}

        def update_clock(self):
            elapsed = self.start_time.msecsTo(QtCore.QDateTime.currentDateTime())
            # Calculate time based on actual system time, not accumulated timer ticks
            actual_time = self.start_time.addMSecs(elapsed)
            self.clock_label.setText(f"Clock: {actual_time.toString('hh:mm:ss')}")
            self.actual_time = {
                'h': actual_time.time().hour(),
                'm': actual_time.time().minute(),
                's': actual_time.time().second()
            }

            # === Check if device is present (async) ===
            asyncio.create_task(self.check_device_and_update(self))

        self.start_time = QtCore.QDateTime.currentDateTime()
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(lambda: update_clock(self))
        self.timer.start(1000)

    def closeEvent(self, event):
        """Close CSV file when application closes"""
        if hasattr(self, 'csv_file') and not self.csv_file.closed:
            self.csv_file.close()
            print(f"Data logged to {self.csv_filename}")
        super().closeEvent(event)

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    main_window = BatteryMeasurementApp()
    main_window.show()

    with loop:
        loop.run_forever()
