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

class notification:
    def __init__(self, sender, data):
        self.sender = sender
        self.data = data

# ---------------------------
# Configuration / defaults
# ---------------------------
UART_SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
UART_RX_CHAR_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
UART_TX_CHAR_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
# ---------------------------

class BLEInterface(QObject):
    scan_started = pyqtSignal()
    scan_finished = pyqtSignal(list)  # list of (name, address)
    log = pyqtSignal(str)
    connected = pyqtSignal(bool)
    notification_received = pyqtSignal(notification)

    def __init__(self):
        # ------------------
        # BLE devices
        # ------------------
        self.ble_devices = ["35:9D:F3:26:7C:4A", "C4:BE:84:1F:2D:5B"]
        self.ble_connected_devices = []

    async def scan(self, timeout=1.0):
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

    async def connect_device(self, id):
        if id >= len(self.ble_devices):
            return

        if self.ble_devices[id] not in self.ble_connected_devices:

            self.ble_connected_devices.append(self.ble_devices[id])
            print(f"Connected to device: {self.ble_devices[id]}")




