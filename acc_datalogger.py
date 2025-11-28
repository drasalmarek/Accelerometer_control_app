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
# ---------------------------

class FileReceiver():
    def __init__(self):
        self.receiving = False
        self.file = None
        self.rx_bytes = 0

        self.header = []
        self.file_size = 0

    def start_receiving(self, filename, file_size=0):
        safe_name = Path(filename).name  # strip any path components
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
    # Qt signals for UI updates
    scan_started = pyqtSignal()
    scan_finished = pyqtSignal(list)  # list of (name, address)
    log = pyqtSignal(str)
    connected = pyqtSignal(bool)
    notification_received = pyqtSignal(bytearray)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.client: Optional[BleakClient] = None
        self._notify_task = None
        self._connected_addr = None
        self.loop = asyncio.get_event_loop()

    async def scan(self, timeout=5.0):
        self.scan_started.emit()
        self.log.emit(f"Scanning for {timeout:.1f}s ...\n")
        devices = await BleakScanner.discover(timeout=timeout)
        found = []
        for d in devices:
            name = d.name or "Unknown"
            addr = d.address
            found.append((name, addr))
        self.scan_finished.emit(found)
        self.log.emit(f"Scan finished: {len(found)} device(s) found\n")

    async def connect(self, address, rx_char_uuid, tx_char_uuid):
        # disconnect if already connected
        if self.client and self.client.is_connected:
            await self.disconnect()

        self.log.emit(f"Connecting to {address} ...\n")
        self.client = BleakClient(address)
        try:
            await self.client.connect()
            self._connected_addr = address
            self.log.emit(f"Connected to {address}\n")
            self.connected.emit(True)
        except Exception as e:
            self.log.emit(f"Connect failed: {e}\n")
            self.connected.emit(False)
            return

        # start notifications if rx uuid provided
        if tx_char_uuid:
            try:
                await self.client.start_notify(tx_char_uuid, self._notification_callback)
                self.log.emit(f"Started notify on {tx_char_uuid}\n")
            except Exception as e:
                self.log.emit(f"Failed to start notify on {tx_char_uuid}: {e}\n")

        # store tx/rx for use by send_command
        self.rx_char_uuid = rx_char_uuid
        self.tx_char_uuid = tx_char_uuid

    async def disconnect(self):
        if self.client:
            addr = getattr(self.client, "address", "<unknown>")
            self.log.emit(f"Disconnecting from {addr} ...\n")
            try:
                await self.client.disconnect()
                self.log.emit("Disconnected\n")
            except Exception as e:
                self.log.emit(f"Error disconnecting: {e}\n")
            finally:
                self.client = None
                self.connected.emit(False)

    def _notification_callback(self, sender, data: bytearray):

        # emit signal to Qt thread
        self.notification_received.emit(data)

    async def send_command(self, text: str):
        if not self.client or not self.client.is_connected:
            self.log.emit("Not connected: cannot send\n")
            return
        if not getattr(self, "tx_char_uuid", None):
            self.log.emit("No TX characteristic configured\n")
            return
        try:
            # SCPI typically ends with newline
            data = text.encode()
            if not data.endswith(b"\n"):
                data += b"\n"

            await self.client.write_gatt_char(self.rx_char_uuid, data)
            self.log.emit(f"> {text}\n")
        except Exception as e:
            self.log.emit(f"Send failed: {e}\n")


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BLE SCPI Console")
        self.resize(1100, 700)

        # central layout - use splitter to allocate space
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        main_layout = QtWidgets.QHBoxLayout(central)

        # Left column: Control + SCPI buttons
        left_col = QtWidgets.QVBoxLayout()
        main_layout.addLayout(left_col, 0)

        # Center: big graph placeholder
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

        btn_scan = QtWidgets.QPushButton("Scan")
        btn_connect = QtWidgets.QPushButton("Connect")
        btn_disconnect = QtWidgets.QPushButton("Disconnect")
        grp_control.setLayout(ctrl_layout)

        ctrl_layout.addWidget(btn_scan)
        ctrl_layout.addWidget(btn_connect)
        ctrl_layout.addWidget(btn_disconnect)

        # device list
        self.device_list = QtWidgets.QListWidget()
        self.device_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        ctrl_layout.addWidget(QtWidgets.QLabel("Discovered devices:"))
        ctrl_layout.addWidget(self.device_list)

        # service / char entry
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

        # preset buttons
        presets_layout = QtWidgets.QHBoxLayout()
        btn_idn = QtWidgets.QPushButton("*IDN?")
        btn_reset = QtWidgets.QPushButton("*RST")
        btn_measure = QtWidgets.QPushButton("MEAS?")
        presets_layout.addWidget(btn_idn)
        presets_layout.addWidget(btn_reset)
        presets_layout.addWidget(btn_measure)
        scpi_layout.addLayout(presets_layout)

        # input + send
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
        self.console_view.setFixedWidth(400)
        console_layout.addWidget(self.console_view)
        # console buffer size control
        buff_layout = QtWidgets.QHBoxLayout()
        buff_layout.addWidget(QtWidgets.QLabel("Max lines:"))
        self.spin_max_lines = QtWidgets.QSpinBox()
        self.spin_max_lines.setRange(50, 100000)
        self.spin_max_lines.setValue(50)
        buff_layout.addWidget(self.spin_max_lines)
        # clear button
        btn_clear_console = QtWidgets.QPushButton("Clear")
        buff_layout.addWidget(btn_clear_console)
        console_layout.addLayout(buff_layout)

        right_col.addWidget(grp_console)

        # ------------------
        # Status bar
        # ------------------
        self.status = QtWidgets.QLabel("Ready")
        self.statusBar().addWidget(self.status)

        # ------------------
        # BLE worker and state
        # ------------------
        self.ble = BLEWorker()

        # ------------------
        # File receiver
        # ------------------
        self.file_receiver = FileReceiver()
        self.packet_bytes_num = 0
        self.packet_bytes = bytearray()

        # Watchdog timer (for file receive timeout)
        self.rx_watchdog = QtCore.QTimer()
        self.rx_watchdog.setInterval(200)
        self.rx_watchdog.timeout.connect(self.on_rx_timeout)

        # FIFO for console
        self.console_deque = deque(maxlen=self.spin_max_lines.value())

        # connections
        btn_scan.clicked.connect(self.on_scan_clicked)
        btn_connect.clicked.connect(self.on_connect_clicked)
        btn_disconnect.clicked.connect(self.on_disconnect_clicked)
        btn_clear_console.clicked.connect(self.on_clear_console)
        self.spin_max_lines.valueChanged.connect(self.on_max_lines_changed)
        btn_send.clicked.connect(self.on_send_scpi)
        btn_idn.clicked.connect(lambda: self.input_scpi.setText("*IDN?"))
        btn_reset.clicked.connect(lambda: self.input_scpi.setText("*RST"))
        btn_measure.clicked.connect(lambda: self.input_scpi.setText("FIL:READ? raw_data,test_file,bin"))

        # BLE worker signals -> UI slots
        self.ble.scan_started.connect(lambda: self.set_status("Scanning..."))
        self.ble.scan_finished.connect(self.on_scan_finished)
        self.ble.log.connect(self._append_console)
        self.ble.connected.connect(self.on_ble_connected)
        self.ble.notification_received.connect(self._handle_notification)

    # -------------------------
    # UI slots and helpers
    # -------------------------
    def set_status(self, text: str):
        self.status.setText(text)

    def on_max_lines_changed(self, val):
        # adjust deque size while preserving contents
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

    def _handle_notification(self, data):
        try:
            data = data.encode()  # ensure bytes
        except Exception:
            pass
        # called from signals
        # handle file receive mode first: incoming notifications treated as file bytes
        if self.file_receiver.receiving:
            try:
                self.packet_bytes.extend(data)
                self.packet_bytes_num += len(data)

                if (self.packet_bytes_num == FILE_PACKET_SIZE) or (self.file_receiver.rx_bytes + self.packet_bytes_num >= self.file_receiver.file_size):
                    # send ACK back
                    asyncio.create_task(self.ble.send_command("FIL:ACK\n"))

                    self.file_receiver.handle_data(self.packet_bytes)
                    self.packet_bytes_num = 0
                    self.packet_bytes = bytearray()

                elif self.packet_bytes_num > FILE_PACKET_SIZE:
                    self.console_deque.append(f"Error: received more than {FILE_PACKET_SIZE} bytes without ACK\n")

                self.rx_watchdog.start()  # reset timeout timer

                #self.console_deque.append(text)
                #self._refresh_console_widget()
                # if receive finished, notify console
                if not self.file_receiver.receiving:
                    self.console_deque.append("File receive complete\n")
                    self._refresh_console_widget()
            except Exception as e:
                self.console_deque.append(f"File receive error: {e}\n")
                self._refresh_console_widget()
            return
        
        else:
            text = data.decode(errors="replace")

        self.last_line += text
        if "\n" in self.last_line:
            lines = self.last_line.splitlines(keepends=True)
            for line in lines:
                if "Sending file:" in line and "\n" in line:
                    # expected format: "Sending file: filename,filesize"
                    _, payload = line.split(":", 1)
                    filename, filesize_part = map(str.strip, payload.split(",", 1))
                    filesize = int(filesize_part)
                    
                    self.file_receiver.start_receiving(filename, filesize) # start receiving using parsed filename and size
                    
                    self.console_deque.append(f"Started receiving {filename} ({filesize} bytes)\n")
                    self._refresh_console_widget()

                if line.endswith("\n"):
                    self.console_deque.append(line)
                else:
                    self.last_line = line

            if self.last_line.endswith("\n"):
                self.last_line = ""
        self._refresh_console_widget()

    def on_rx_timeout(self):
        if self.file_receiver.receiving:
            self.packet_bytes_num = 0
            self.packet_bytes = bytearray()
            asyncio.create_task(self.ble.send_command("FIL:NACK\n"))
            self.console_deque.append("File receive timeout: no data received for 1 second\n")
            self._refresh_console_widget()

    def _refresh_console_widget(self):
        # show deque content in textedit
        self.console_view.setPlainText("".join(self.console_deque))

    # -------------------------
    # Scan / connect handlers
    # -------------------------
    @qasync.asyncSlot()
    async def on_scan_clicked(self):
        # clear previous list
        self.device_list.clear()
        await self.ble.scan(timeout=5.0)

    def on_scan_finished(self, devices):
        # devices: list of (name, address)
        self.device_list.clear()
        for name, addr in devices:
            item = QtWidgets.QListWidgetItem(f"{name} ({addr})")
            # store address in item data
            item.setData(QtCore.Qt.UserRole, addr)
            self.device_list.addItem(item)
        self.set_status(f"Scan found {len(devices)} device(s)")

    @qasync.asyncSlot()
    async def on_connect_clicked(self):
        sel = self.device_list.currentItem()
        if not sel:
            self.set_status("Select device first")
            return
        addr = sel.data(QtCore.Qt.UserRole)
        rx = self.input_rx_uuid.text().strip() or None
        tx = self.input_tx_uuid.text().strip() or None
        await self.ble.connect(addr, rx, tx)

    @qasync.asyncSlot()
    async def on_disconnect_clicked(self):
        await self.ble.disconnect()

    def on_ble_connected(self, connected: bool):
        self.set_status("Connected" if connected else "Disconnected")

    # -------------------------
    # Sending SCPI
    # -------------------------
    @qasync.asyncSlot()
    async def on_send_scpi(self):
        txt = self.input_scpi.text().strip()
        if not txt:
            return
    
        await self.ble.send_command(txt)

# -------------------------
# main: start qasync loop and UI
# -------------------------
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
