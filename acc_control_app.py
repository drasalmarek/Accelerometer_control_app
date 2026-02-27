import sys
import asyncio
from collections import deque
from typing import Optional

from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import pyqtSignal, QObject

from bleak import BleakScanner, BleakClient
import qasync
from pathlib import Path

import numpy as np
import struct
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

FILE_PACKET_SIZE = 1024

# ---------------------------
# Configuration / defaults
# ---------------------------
UART_SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
UART_RX_CHAR_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
UART_TX_CHAR_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"

SENSOR_ADDR = ["E7:31:E9:B5:72:2A", "C6:E6:A3:FC:45:F5"]

def process_data_file(file_path):
    sensor_data = {
        'adxl' : {
            'x' : [],
            'y' : [],
            'z' : [],
            'timestamps' : [],
            'sampling_rates' : [],
            'avg_sampling_rate' : 0
        },

        'bno' : {
            'acc_x' : [],
            'acc_y' : [],
            'acc_z' : [],
            'gyr_x' : [],
            'gyr_y' : [],
            'gyr_z' : [],
            'mag_x' : [],
            'mag_y' : [],
            'mag_z' : [],
            'eul_heading' : [],
            'eul_roll' : [],
            'eul_pitch' : [],
            'quat_w' : [],
            'quat_x' : [],
            'quat_y' : [],
            'quat_z' : [],
            'lia_x' : [],
            'lia_y' : [],
            'lia_z' : [],
            'grv_x' : [],
            'grv_y' : [],
            'grv_z' : [],
            'temp' : [],
            'single_size' : (6*3 + 6 + 8 + 6 + 6 + 1),

            'timestamps' : [],
            'sampling_rates' : [],
            'avg_sampling_rate' : 0
        },

        'adc0' : {
            'values' : [],
            'timestamps' : [],
            'sampling_rates' : [],
            'avg_sampling_rate' : 0
        }
    }

    def bytes_to_data(bytes_read, number_of_values):
        # Unpack 6 uint8_t values
        u = struct.unpack(f'{number_of_values*2}B', bytes_read)
        output = []
        for i in range(0, number_of_values):
            val = (u[i*2 + 1] << 8) | u[i*2]
            # Interpret as signed int16
            val = struct.unpack('<h', struct.pack('<H', val))[0]
            output.append(val)
        return output

    with open(file_path, 'rb') as bin_file:
        first_header = bin_file.read(4)
        # HAL_GetTick() is a uint32_t copied with memcpy — assume little-endian
        start_time = struct.unpack('<I', first_header)[0]
        print(f"start_time_ms = {start_time}")
        while True:
            header = bin_file.read(9)
            if len(header) < 9:
                break
            index = header[0]
            timestamp = struct.unpack('<I', header[1:5])[0]
            data_size = struct.unpack('<I', header[5:9])[0]
            print(f"Index: {index}, Timestamp: {timestamp}, Data size: {data_size}")
            if index == 1:
                start_time = sensor_data['adxl']['timestamps'][-1] if sensor_data['adxl']['timestamps'] else start_time
                sensor_data['adxl']['timestamps'].append(timestamp)
                sampling_rate = (data_size / 6) / ((timestamp - start_time) / 1000)
                sensor_data['adxl']['sampling_rates'].append(sampling_rate)
                for _ in range(data_size//6):
                    bytes_read = bin_file.read(6)
                    if len(bytes_read) < 6:
                        break
                    data = bytes_to_data(bytes_read, 3)
                    sensor_data['adxl']['x'].append(data[0] / 2048.0)
                    sensor_data['adxl']['y'].append(data[1] / 2048.0)
                    sensor_data['adxl']['z'].append(data[2] / 2048.0)
            elif index == 2:
                start_time = sensor_data['bno']['timestamps'][-1] if sensor_data['bno']['timestamps'] else start_time
                sensor_data['bno']['timestamps'].append(timestamp)
                sampling_rate = (data_size / sensor_data['bno']['single_size']) / ((timestamp - start_time) / 1000)
                sensor_data['bno']['sampling_rates'].append(sampling_rate)
                for _ in range(data_size//sensor_data['bno']['single_size']):
                    bytes_read = bin_file.read(6)
                    if len(bytes_read) < 6:
                        break
                    data = bytes_to_data(bytes_read, 3)
                    sensor_data['bno']['acc_x'].append(data[0]/100.0)
                    sensor_data['bno']['acc_y'].append(data[1]/100.0)
                    sensor_data['bno']['acc_z'].append(data[2]/100.0)
                    bytes_read = bin_file.read(6)
                    if len(bytes_read) < 6:
                        break
                    data = bytes_to_data(bytes_read, 3)
                    sensor_data['bno']['gyr_x'].append(data[0]/16.0)
                    sensor_data['bno']['gyr_y'].append(data[1]/16.0)
                    sensor_data['bno']['gyr_z'].append(data[2]/16.0)
                    bytes_read = bin_file.read(6)
                    if len(bytes_read) < 6:
                        break
                    data = bytes_to_data(bytes_read, 3)
                    sensor_data['bno']['mag_x'].append(data[0]/16.0)
                    sensor_data['bno']['mag_y'].append(data[1]/16.0)
                    sensor_data['bno']['mag_z'].append(data[2]/16.0)
                    bytes_read = bin_file.read(6)
                    if len(bytes_read) < 6:
                        break
                    data = bytes_to_data(bytes_read, 3)
                    sensor_data['bno']['eul_heading'].append(data[0]/16.0)
                    sensor_data['bno']['eul_roll'].append(data[1]/16.0)
                    sensor_data['bno']['eul_pitch'].append(data[2]/16.0)
                    bytes_read = bin_file.read(8)
                    if len(bytes_read) < 8:
                        break
                    data = bytes_to_data(bytes_read, 4)
                    sensor_data['bno']['quat_w'].append(data[0]/16384.0)
                    sensor_data['bno']['quat_x'].append(data[1]/16384.0)
                    sensor_data['bno']['quat_y'].append(data[2]/16384.0)
                    sensor_data['bno']['quat_z'].append(data[3]/16384.0)
                    bytes_read = bin_file.read(6)
                    if len(bytes_read) < 6:
                        break
                    data = bytes_to_data(bytes_read, 3)
                    sensor_data['bno']['lia_x'].append(data[0]/100.0)
                    sensor_data['bno']['lia_y'].append(data[1]/100.0)
                    sensor_data['bno']['lia_z'].append(data[2]/100.0)
                    bytes_read = bin_file.read(6)
                    if len(bytes_read) < 6:
                        break
                    data = bytes_to_data(bytes_read, 3)
                    sensor_data['bno']['grv_x'].append(data[0]/100.0)
                    sensor_data['bno']['grv_y'].append(data[1]/100.0)
                    sensor_data['bno']['grv_z'].append(data[2]/100.0)
                    bytes_read = bin_file.read(1)
                    if len(bytes_read) < 1:
                        break
                    u = struct.unpack('1B', bytes_read)
                    sensor_data['bno']['temp'].append(u[0])
            elif index == 3:
                start_time = sensor_data['adc0']['timestamps'][-1] if sensor_data['adc0']['timestamps'] else start_time
                sensor_data['adc0']['timestamps'].append(timestamp)
                sampling_rate = (data_size) / ((timestamp - start_time) / 1000)
                sensor_data['adc0']['sampling_rates'].append(sampling_rate)
                for _ in range(data_size):
                    bytes_read = bin_file.read(1)
                    u = struct.unpack('1B', bytes_read)
                    i = struct.unpack('<h', struct.pack('<H', u[0]))[0]
                    sensor_data['adc0']['values'].append(i / 255.0 * 1.8)

        # Calculate average sampling rates
        if sensor_data['adxl']['sampling_rates']:
            sensor_data['adxl']['avg_sampling_rate'] = sum(sensor_data['adxl']['sampling_rates']) / len(sensor_data['adxl']['sampling_rates'])
            print(f"ADXL Average Sampling Rate: {sensor_data['adxl']['avg_sampling_rate']} Hz")

        if sensor_data['bno']['sampling_rates']:
            sensor_data['bno']['avg_sampling_rate'] = sum(sensor_data['bno']['sampling_rates']) / len(sensor_data['bno']['sampling_rates'])
            print(f"BNO Average Sampling Rate: {sensor_data['bno']['avg_sampling_rate']} Hz")

        if sensor_data['adc0']['sampling_rates']:
            sensor_data['adc0']['avg_sampling_rate'] = sum(sensor_data['adc0']['sampling_rates']) / len(sensor_data['adc0']['sampling_rates'])
            print(f"ADC0 Average Sampling Rate: {sensor_data['adc0']['avg_sampling_rate']} Hz")

        return sensor_data

class FileReceiver():
    def __init__(self):
        self.receiving = False
        self.file = None
        self.rx_bytes = 0
        self.header = []
        self.file_size = 0

    def start_receiving(self, filename, file_size=0):
        safe_name = Path(filename).name
        script_dir = Path(__file__).resolve().parent
        full_path = script_dir / safe_name
        self.file = open(full_path, "wb")
        self.rx_bytes = 0
        self.header = []
        self.file_size = file_size
        self.receiving = True

    def stop_receiving(self):
        if self.file:
            self.file.close()
            self.file = None
        self.receiving = False

    def handle_data(self, data: bytearray):
        if self.receiving and self.file:
            self.file.write(data)
            self.rx_bytes += len(data)
            print(f"Received {self.rx_bytes}/{self.file_size} bytes")
            if self.rx_bytes >= self.file_size:
                print("File receive complete")
                self.stop_receiving()


class BLEWorker(QObject):
    scan_started = pyqtSignal()
    scan_finished = pyqtSignal(list)
    log = pyqtSignal(str)
    connected = pyqtSignal(bool)
    notification_received = pyqtSignal(int, bytearray)

    def __init__(self, sensor_id=0, parent=None):
        super().__init__(parent)
        self.sensor_id = sensor_id
        self.client: Optional[BleakClient] = None
        self._connected_addr = None
        self.rx_char_uuid = None
        self.tx_char_uuid = None

    async def scan(self, timeout=1.0):
        self.scan_started.emit()
        self.log.emit(f"[Sensor {self.sensor_id+1}] Scanning for {timeout:.1f}s ...\n")
        devices = await BleakScanner.discover(timeout=timeout)
        found = []
        for d in devices:
            name = d.name or "Unknown"
            addr = d.address
            found.append((name, addr))
        self.scan_finished.emit(found)
        self.log.emit(f"[Sensor {self.sensor_id+1}] Scan finished: {len(found)} device(s) found\n")

    async def connect(self, address, rx_char_uuid, tx_char_uuid):
        if self.client and self.client.is_connected:
            await self.disconnect()

        self.log.emit(f"[Sensor {self.sensor_id+1}] Connecting to {address} ...\n")
        self.client = BleakClient(address)
        try:
            await self.client.connect()
            self._connected_addr = address
            self.rx_char_uuid = rx_char_uuid
            self.tx_char_uuid = tx_char_uuid
            self.log.emit(f"[Sensor {self.sensor_id+1}] Connected to {address}\n")
            self.connected.emit(True)
        except Exception as e:
            self.log.emit(f"[Sensor {self.sensor_id+1}] Connect failed: {e}\n")
            self.connected.emit(False)
            return

        if tx_char_uuid:
            try:
                await self.client.start_notify(tx_char_uuid, self._notification_callback)
                self.log.emit(f"[Sensor {self.sensor_id+1}] Started notify on {tx_char_uuid}\n")
            except Exception as e:
                self.log.emit(f"[Sensor {self.sensor_id+1}] Failed to start notify: {e}\n")

    async def disconnect(self):
        if self.client:
            addr = getattr(self.client, "address", "<unknown>")
            self.log.emit(f"[Sensor {self.sensor_id+1}] Disconnecting from {addr} ...\n")
            try:
                await self.client.disconnect()
                self.log.emit(f"[Sensor {self.sensor_id+1}] Disconnected\n")
            except Exception as e:
                self.log.emit(f"[Sensor {self.sensor_id+1}] Error disconnecting: {e}\n")
            finally:
                self.client = None
                self.connected.emit(False)

    def _notification_callback(self, sender, data: bytearray):
        self.notification_received.emit(self.sensor_id+1, data)

    async def send_command(self, text: str):
        if not self.client or not self.client.is_connected:
            self.log.emit(f"[Sensor {self.sensor_id+1}] Not connected: cannot send\n")
            return
        if not self.rx_char_uuid:
            self.log.emit(f"[Sensor {self.sensor_id+1}] No RX characteristic configured\n")
            return
        try:
            data = text.encode()
            if not data.endswith(b"\n"):
                data += b"\n"
            await self.client.write_gatt_char(self.rx_char_uuid, data)
            self.log.emit(f"[Sensor {self.sensor_id+1}] > {text}\n")
        except Exception as e:
            self.log.emit(f"[Sensor {self.sensor_id+1}] Send failed: {e}\n")


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Multi-Sensor BLE SCPI Console")
        self.resize(1100, 700)

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        main_layout = QtWidgets.QHBoxLayout(central)

        # Left column
        left_col = QtWidgets.QVBoxLayout()
        main_layout.addLayout(left_col, 0)

        # Center: graph
        self.graph_layout = QtWidgets.QVBoxLayout()
        main_layout.addLayout(self.graph_layout, 2)

        # Right: console
        right_col = QtWidgets.QVBoxLayout()
        main_layout.addLayout(right_col, 0)

        # ------------------
        # Control group
        # ------------------
        grp_control = QtWidgets.QGroupBox("Control")
        ctrl_layout = QtWidgets.QVBoxLayout(grp_control)

        ctrl_layout.addWidget(QtWidgets.QLabel("Select devices to use:"))
        self.device_checkboxes = []
        for i, addr in enumerate(SENSOR_ADDR):
            cb = QtWidgets.QCheckBox(f"Sensor {i+1} ({addr})")
            self.device_checkboxes.append(cb)
            ctrl_layout.addWidget(cb)

        self.btn_request_connection = QtWidgets.QPushButton("Request Connection")
        self.btn_request_connection.setCheckable(True)
        btn_scan = QtWidgets.QPushButton("Scan")
        btn_disconnect = QtWidgets.QPushButton("Disconnect All")
        self.device_selector = QtWidgets.QComboBox()

        ctrl_layout.addWidget(self.btn_request_connection)
        ctrl_layout.addWidget(btn_scan)
        ctrl_layout.addWidget(btn_disconnect)
        ctrl_layout.addWidget(self.device_selector)

        # Device list
        self.device_list = QtWidgets.QListWidget()
        self.device_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        ctrl_layout.addWidget(QtWidgets.QLabel("Discovered devices:"))
        ctrl_layout.addWidget(self.device_list)

        # UUIDs
        ctrl_layout.addWidget(QtWidgets.QLabel("RX char UUID (notify):"))
        self.input_rx_uuid = QtWidgets.QLineEdit(UART_RX_CHAR_UUID)
        ctrl_layout.addWidget(self.input_rx_uuid)
        ctrl_layout.addWidget(QtWidgets.QLabel("TX char UUID (write):"))
        self.input_tx_uuid = QtWidgets.QLineEdit(UART_TX_CHAR_UUID)
        ctrl_layout.addWidget(self.input_tx_uuid)

        left_col.addWidget(grp_control)

        # ------------------
        # SCPI group
        # ------------------
        grp_scpi = QtWidgets.QGroupBox("SCPI")
        scpi_layout = QtWidgets.QVBoxLayout(grp_scpi)

        presets_layout = QtWidgets.QGridLayout()
        btn_on = QtWidgets.QPushButton("POW ON")
        btn_off = QtWidgets.QPushButton("POW OFF")
        btn_idn = QtWidgets.QPushButton("*IDN?")
        btn_measure_start = QtWidgets.QPushButton("MEAS START")
        btn_measure_stop = QtWidgets.QPushButton("MEAS STOP")
        btn_err_count = QtWidgets.QPushButton("ERR COUNT?")
        btn_err_next = QtWidgets.QPushButton("ERR NEXT?")

        presets_layout.addWidget(btn_on, 0, 0)
        presets_layout.addWidget(btn_off, 0, 1)
        presets_layout.addWidget(btn_idn, 0, 2)
        presets_layout.addWidget(btn_measure_start, 1, 0)
        presets_layout.addWidget(btn_measure_stop, 1, 1)
        presets_layout.addWidget(btn_err_count, 2, 0)
        presets_layout.addWidget(btn_err_next, 2, 1)
        scpi_layout.addLayout(presets_layout)

        input_layout = QtWidgets.QHBoxLayout()
        self.input_scpi = QtWidgets.QLineEdit()
        btn_send = QtWidgets.QPushButton("Send SCPI")
        input_layout.addWidget(self.input_scpi)
        input_layout.addWidget(btn_send)
        scpi_layout.addLayout(input_layout)

        left_col.addWidget(grp_scpi)

        # ------------------
        # Graph group
        # ------------------
        self.selected_graph_file = None
        grp_graph = QtWidgets.QGroupBox("Graph")
        graph_layout = QtWidgets.QVBoxLayout(grp_graph)

        graph_controls = QtWidgets.QHBoxLayout()
        self.btn_select_graph_file = QtWidgets.QPushButton("Select File")
        self.btn_process_file = QtWidgets.QPushButton("Process File")
        self.data_selector = QtWidgets.QComboBox()
        self.btn_plot_graph = QtWidgets.QPushButton("Plot Graph")
        self.graph_file_label = QtWidgets.QLabel("No file selected")
        self.graph_file_label.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)

        graph_controls.addWidget(self.btn_select_graph_file)
        graph_controls.addWidget(self.btn_process_file)
        graph_controls.addWidget(self.data_selector)
        graph_controls.addWidget(self.btn_plot_graph)
        graph_controls.addWidget(self.graph_file_label, 1)
        graph_layout.addLayout(graph_controls)

        self.graph_area = QtWidgets.QFrame()
        self.graph_area.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.graph_area.setFrameShadow(QtWidgets.QFrame.Sunken)
        self.graph_area.setMinimumHeight(350)
        self.graph_area.setStyleSheet("background-color: #111111;")
        graph_layout.addWidget(self.graph_area, 1)

        graph_area_layout = QtWidgets.QVBoxLayout(self.graph_area)
        graph_area_layout.setContentsMargins(0, 0, 0, 0)
        self.figure = Figure(figsize=(5, 4), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        graph_area_layout.addWidget(self.canvas)
        self.ax = self.figure.add_subplot(111)

        self.graph_layout.addWidget(grp_graph, 1)

        # ------------------
        # Console group
        # ------------------
        self.last_line = ""
        grp_console = QtWidgets.QGroupBox("Console (FIFO)")
        console_layout = QtWidgets.QVBoxLayout(grp_console)
        self.console_view = QtWidgets.QTextEdit()
        self.console_view.setReadOnly(True)
        self.console_view.textChanged.connect(lambda: self.console_view.moveCursor(QtGui.QTextCursor.End))
        self.console_view.setFixedWidth(400)
        console_layout.addWidget(self.console_view)

        buff_layout = QtWidgets.QHBoxLayout()
        buff_layout.addWidget(QtWidgets.QLabel("Max lines:"))
        self.spin_max_lines = QtWidgets.QSpinBox()
        self.spin_max_lines.setRange(50, 100000)
        self.spin_max_lines.setValue(50)
        buff_layout.addWidget(self.spin_max_lines)
        btn_clear_console = QtWidgets.QPushButton("Clear")
        buff_layout.addWidget(btn_clear_console)
        console_layout.addLayout(buff_layout)

        right_col.addWidget(grp_console)

        # Status bar
        self.status = QtWidgets.QLabel("Ready")
        self.statusBar().addWidget(self.status)

        # ------------------
        # BLE workers (one per sensor)
        # ------------------
        self.ble_workers = [BLEWorker(sensor_id=i) for i in range(len(SENSOR_ADDR))]
        self.connected_workers = set()
        self.scanning = False

        # File receiver
        self.file_receiver = FileReceiver()
        self.packet_bytes_num = 0
        self.packet_bytes = bytearray()

        self.rx_watchdog = QtCore.QTimer()
        self.rx_watchdog.setInterval(3000)  # 3 seconds - give more time for packets to arrive
        self.rx_watchdog.timeout.connect(self.on_rx_timeout)

        self.console_deque = deque(maxlen=self.spin_max_lines.value())

        # Connections
        self.btn_request_connection.clicked.connect(self.on_request_clicked)
        btn_scan.clicked.connect(self.scan_start)
        btn_disconnect.clicked.connect(self.on_disconnect_all)
        btn_clear_console.clicked.connect(self.on_clear_console)
        self.spin_max_lines.valueChanged.connect(self.on_max_lines_changed)
        btn_send.clicked.connect(self.on_send_scpi)

        self.btn_select_graph_file.clicked.connect(self.on_select_graph_file)
        self.btn_process_file.clicked.connect(self.on_process_file)
        self.btn_plot_graph.clicked.connect(self.on_plot_graph)

        btn_on.clicked.connect(lambda: self.input_scpi.setText("POW:ON"))
        btn_off.clicked.connect(lambda: self.input_scpi.setText("POW:OFF"))
        btn_idn.clicked.connect(lambda: self.input_scpi.setText("*IDN?"))
        btn_measure_start.clicked.connect(lambda: self.input_scpi.setText("MEAS:START"))
        btn_measure_stop.clicked.connect(lambda: self.input_scpi.setText("MEAS:STOP"))
        btn_err_count.clicked.connect(lambda: self.input_scpi.setText("SYST:ERR:COUNT?"))
        btn_err_next.clicked.connect(lambda: self.input_scpi.setText("SYST:ERR:NEXT?"))

        # Connect functions to all BLE workers
        for i, worker in enumerate(self.ble_workers):
            worker.log.connect(self._append_console)
            worker.connected.connect(lambda connected, w=worker: self.on_worker_connected(w, connected))
            worker.notification_received.connect(self._handle_notification)

    def set_status(self, text: str):
        self.status.setText(text)

    def on_request_clicked(self):
        if self.btn_request_connection.isChecked():
            self._append_console("Requesting connection to selected devices...\n")
            self.scanning = True
            self.scan_start()
        else:
            self._append_console("Connection request cancelled\n")
            self.scanning = False

    def on_max_lines_changed(self, val):
        old = list(self.console_deque)
        self.console_deque = deque(old, maxlen=val)
        self._refresh_console_widget()

    def on_clear_console(self):
        self.console_deque.clear()
        self._refresh_console_widget()

    def _append_console(self, text: str):
        # Allow file transfer control messages and sensor logs through even during receive
        if not self.file_receiver.receiving or "FIL:ACK" in text or "FIL:NACK" in text or "[Sensor" in text:
            self.console_deque.append(text)
            self._refresh_console_widget()

    def _handle_notification(self, sensor_id, data):
        try:
            data = data.encode() if isinstance(data, str) else data
        except Exception:
            pass

        if self.file_receiver.receiving:
            try:
                self.packet_bytes.extend(data)
                self.packet_bytes_num += len(data)

                if (self.packet_bytes_num == FILE_PACKET_SIZE) or (self.file_receiver.rx_bytes + self.packet_bytes_num >= self.file_receiver.file_size):
                    # send ACK back
                    self.rx_watchdog.stop()  # Stop watchdog while sending ACK
                    self.console_deque.append(f"[FILE RX] Block complete ({self.packet_bytes_num} bytes), sending ACK\n")
                    asyncio.create_task(self.ble_workers[sensor_id-1].send_command("FIL:ACK"))

                    self.file_receiver.handle_data(self.packet_bytes)
                    self.packet_bytes_num = 0
                    self.packet_bytes = bytearray()
                    
                    # Restart watchdog for next block
                    self.rx_watchdog.start()

                elif self.packet_bytes_num > FILE_PACKET_SIZE:
                    self.console_deque.append(f"Error: received more than {FILE_PACKET_SIZE} bytes without ACK\n")
                    self.rx_watchdog.stop()

                else:
                    # Keep accumulating data, restart watchdog
                    self.rx_watchdog.start()
                
                self._refresh_console_widget()

                if not self.file_receiver.receiving:
                    self.rx_watchdog.stop()
                    self.console_deque.append("File receive complete\n")
                    self._refresh_console_widget()
            except Exception as e:
                self.console_deque.append(f"File receive error: {e}\n")
                self._refresh_console_widget()
            return

        text = data.decode(errors="replace") if isinstance(data, bytearray) else data
        self.last_line += text

        if "\n" in self.last_line:
            lines = self.last_line.splitlines(keepends=True)
            for line in lines:
                if "Sending file:" in line and "\n" in line:
                    _, payload = line.split(":", 1)
                    filename, filesize_part = map(str.strip, payload.split(",", 1))
                    filesize = int(filesize_part)
                    self.file_receiver.start_receiving(filename, filesize)
                    self.console_deque.append(f"Started receiving {filename} ({filesize} bytes)\n")
                    self._refresh_console_widget()

                if line.endswith("\n"):
                    self.console_deque.append(f"[Sensor {sensor_id}]: {line}")
                else:
                    self.last_line = line

            if self.last_line.endswith("\n"):
                self.last_line = ""

        self._refresh_console_widget()

    def on_rx_timeout(self):
        if self.file_receiver.receiving:
            self.packet_bytes_num = 0
            self.packet_bytes = bytearray()
            
            # Try to send NACK if still connected
            selected_idx = self.device_selector.currentData()
            if selected_idx is not None:
                worker = self.ble_workers[selected_idx - 1]
                if worker.client and worker.client.is_connected:
                    loop = asyncio.get_event_loop()
                    loop.create_task(worker.send_command("FIL:NACK"))
                else:
                    self.console_deque.append("File receive timeout - device disconnected, cannot send NACK\n")
            
            self.console_deque.append("File receive timeout\n")
            self._refresh_console_widget()

    def _refresh_console_widget(self):
        self.console_view.setPlainText("".join(self.console_deque))

    @qasync.asyncSlot()
    async def scan_start(self):
        if not self.scanning:
            await self.ble_workers[0].scan(timeout=1.0)
            return

        # Get selected sensor indices
        selected_indices = [i for i, cb in enumerate(self.device_checkboxes) if cb.isChecked()]
        
        # Scan all and try to connect selected ones
        devices = await BleakScanner.discover(timeout=1.0)
        found = [(d.name or "Unknown", d.address) for d in devices]

        self.device_list.clear()
        for name, addr in found:
            item = QtWidgets.QListWidgetItem(f"{name} ({addr})")
            item.setData(QtCore.Qt.UserRole, addr)
            self.device_list.addItem(item)

        self.set_status(f"Found {len(found)} device(s)")

        # Try connecting selected devices
        for sensor_idx in selected_indices:
            if sensor_idx in self.connected_workers:
                continue  # Already connected

            target_addr = SENSOR_ADDR[sensor_idx]
            for name, addr in found:
                if addr.upper() == target_addr.upper():
                    await self.ble_workers[sensor_idx].connect(
                        addr,
                        self.input_rx_uuid.text().strip() or UART_RX_CHAR_UUID,
                        self.input_tx_uuid.text().strip() or UART_TX_CHAR_UUID
                    )
                    break

        # Continue scanning if more devices needed
        if self.scanning:
            not_connected = [i for i in selected_indices if i not in self.connected_workers]
            if not_connected:
                await asyncio.sleep(0.5)
                await self.scan_start()
            else:
                self.scanning = False
                self._append_console("All selected devices connected!\n")

    def on_worker_connected(self, worker: BLEWorker, connected: bool):
        if connected:
            self.connected_workers.add(worker.sensor_id)
            asyncio.create_task(worker.send_command("POW:ON"))
            self.device_selector.addItem(f"Sensor {worker.sensor_id+1}", worker.sensor_id+1)
            self.set_status(f"Connected: {len(self.connected_workers)} device(s)")
        else:
            self.connected_workers.discard(worker.sensor_id)
            self.set_status(f"Connected: {len(self.connected_workers)} device(s)")

    @qasync.asyncSlot()
    async def on_disconnect_all(self):
        tasks = [worker.disconnect() for worker in self.ble_workers if worker.client]
        if tasks:
            await asyncio.gather(*tasks)
        self.connected_workers.clear()

    @qasync.asyncSlot()
    async def on_send_scpi(self):
        txt = self.input_scpi.text().strip()
        if not txt or not self.connected_workers:
            return
        
        asyncio.create_task(self.ble_workers[self.device_selector.currentData() - 1].send_command(txt))

    def on_select_graph_file(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select data file",
            str(Path(__file__).resolve().parent),
            "Data files (*.bin);;All files (*.*)"
        )
        if file_path:
            self.selected_graph_file = file_path
            self.graph_file_label.setText(Path(file_path).name)
            self.set_status(f"Selected file: {Path(file_path).name}")

    def on_process_file(self):
        if not self.selected_graph_file:
            QtWidgets.QMessageBox.information(self, "Process", "Select a file first.")
            return
        self.set_status(f"Processing: {Path(self.selected_graph_file).name}")

        self.processed_data = process_data_file(self.selected_graph_file)

        if self.processed_data:
            self.data_selector.clear()
            if self.processed_data['adxl']['timestamps']:
                self.data_selector.addItem("ADXL", "adxl")
            if self.processed_data['bno']['timestamps']:
                self.data_selector.addItem("BNO", "bno")
            if self.processed_data['adc0']['timestamps']:
                self.data_selector.addItem("ADC0", "adc0")

        self.set_status(f"Processing complete: {Path(self.selected_graph_file).name}")

    def on_plot_graph(self):
        if not self.selected_graph_file:
            QtWidgets.QMessageBox.information(self, "Plot", "Select a file first.")
            return
        if not hasattr(self, "processed_data") or not self.processed_data:
            QtWidgets.QMessageBox.information(self, "Plot", "Process the file first.")
            return

        data_key = self.data_selector.currentData()
        if not data_key:
            QtWidgets.QMessageBox.information(self, "Plot", "Select a data stream to plot.")
            return

        self.set_status(f"Plotting: {Path(self.selected_graph_file).name}")

        self.ax.clear()

        if data_key == "adxl":
            t = np.linspace(0, len(self.processed_data["adxl"]["x"])-1, len(self.processed_data["adxl"]["x"])) / self.processed_data["adxl"]["avg_sampling_rate"]
            x = np.array(self.processed_data["adxl"]["x"])
            y = np.array(self.processed_data["adxl"]["y"])
            z = np.array(self.processed_data["adxl"]["z"])
            self.ax.plot(t, x, label="X")
            self.ax.plot(t, y, label="Y")
            self.ax.plot(t, z, label="Z")
            self.ax.set_title("ADXL Acceleration")
            self.ax.set_xlabel("Time [s]")
            self.ax.set_ylabel("Acceleration [g]")
            self.ax.legend(loc="best")

        elif data_key == "bno":
            t = np.linspace(0, len(self.processed_data["bno"]["eul_heading"])-1, len(self.processed_data["bno"]["eul_heading"])) / self.processed_data["bno"]["avg_sampling_rate"]
            ax = np.array(self.processed_data["bno"]["eul_heading"], dtype=float)
            ay = np.array(self.processed_data["bno"]["eul_pitch"], dtype=float)
            az = np.array(self.processed_data["bno"]["eul_roll"], dtype=float)

            def _unwrap_deg(vals):
                unwrapped = np.rad2deg(np.unwrap(np.deg2rad(vals), discont=np.deg2rad(180.0)))
                offset = np.round(unwrapped[0] / 360.0) * 360.0
                return unwrapped - offset

            ax = _unwrap_deg(ax)
            ay = _unwrap_deg(ay)
            az = _unwrap_deg(az)
            self.ax.plot(t, ax, label="Euler Heading")
            self.ax.plot(t, ay, label="Euler Pitch")
            self.ax.plot(t, az, label="Euler Roll")
            self.ax.set_title("BNO Orientation")
            self.ax.set_xlabel("Time [s]")
            self.ax.set_ylabel("Orientation [°]")
            self.ax.legend(loc="best")

        elif data_key == "adc0":
            t = np.linspace(0, len(self.processed_data["adc0"]["values"])-1, len(self.processed_data["adc0"]["values"])) / self.processed_data["adc0"]["avg_sampling_rate"]
            v = np.array(self.processed_data["adc0"]["values"])
            self.ax.plot(t, v, label="ADC0")
            self.ax.set_ylim(0, 2)
            self.ax.set_title("ADC0")
            self.ax.set_xlabel("Time [s]")
            self.ax.set_ylabel("Value [V]")
            self.ax.legend(loc="best")

        self.ax.grid(True, alpha=0.3)
        self.figure.tight_layout()
        self.canvas.draw_idle()

        


def main():
    app = QtWidgets.QApplication(sys.argv)
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    win = MainWindow()
    win.show()

    with loop:
        loop.run_forever()


if __name__ == "__main__":
    main()
