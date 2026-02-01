import sys
import asyncio
from collections import deque
from typing import Optional

from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import pyqtSignal, QObject

from bleak import BleakScanner, BleakClient
import qasync
from pathlib import Path

FILE_PACKET_SIZE = 1024

# ---------------------------
# Configuration / defaults
# ---------------------------
UART_SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
UART_RX_CHAR_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
UART_TX_CHAR_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"

SENSOR_ADDR = ["E7:31:E9:B5:72:2A", "C6:E6:A3:FC:45:F5"]

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

        # Center: graph placeholder
        self.graph_placeholder = QtWidgets.QFrame()
        self.graph_placeholder.setFrameShape(QtWidgets.QFrame.Box)
        self.graph_placeholder.setStyleSheet("background: #f7f7f7;")
        main_layout.addWidget(self.graph_placeholder, 2)

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
        self.rx_watchdog.setInterval(200)
        self.rx_watchdog.timeout.connect(self.on_rx_timeout)

        self.console_deque = deque(maxlen=self.spin_max_lines.value())

        # Connections
        self.btn_request_connection.clicked.connect(self.on_request_clicked)
        btn_scan.clicked.connect(self.scan_start)
        btn_disconnect.clicked.connect(self.on_disconnect_all)
        btn_clear_console.clicked.connect(self.on_clear_console)
        self.spin_max_lines.valueChanged.connect(self.on_max_lines_changed)
        btn_send.clicked.connect(self.on_send_scpi)

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
        if not self.file_receiver.receiving:
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
                    asyncio.create_task(self.ble_workers[sensor_id-1].send_command("FIL:ACK"))

                    self.file_receiver.handle_data(self.packet_bytes)
                    self.packet_bytes_num = 0
                    self.packet_bytes = bytearray()

                elif self.packet_bytes_num > FILE_PACKET_SIZE:
                    self.console_deque.append(f"Error: received more than {FILE_PACKET_SIZE} bytes without ACK\n")

                self.rx_watchdog.start()

                if not self.file_receiver.receiving:
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
            asyncio.create_task(self.ble_workers[self.device_selector.currentIndex()].send_command("FIL:NACK"))
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
        
        asyncio.create_task(self.ble_workers[self.device_selector.currentIndex()].send_command(txt))


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
