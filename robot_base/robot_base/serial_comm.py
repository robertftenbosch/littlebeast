"""
UART JSON protocol communicatie met ESP32 lower computer.

Gebaseerd op ugv_jetson base_ctrl.py patroon.
Protocol: JSON strings over serial, newline-terminated.
Voorbeeld commando: {"T":1,"L":100,"R":100}
Voorbeeld feedback: {"T":1,"L":0,"R":0,"V":12.1}
"""

import json
import logging
import threading
import time
from collections import deque

import serial

logger = logging.getLogger(__name__)


class SerialComm:
    """Thread-safe UART communicatie met command queue en feedback parsing."""

    def __init__(self, port: str = "/dev/ttyTHS0", baudrate: int = 115200,
                 timeout: float = 0.1):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout

        self._serial: serial.Serial | None = None
        self._lock = threading.Lock()
        self._running = False

        # Command queue (nieuwste commando wint, oude worden overgeslagen)
        self._cmd_queue: deque[dict] = deque(maxlen=1)

        # Laatste feedback van ESP32
        self._feedback: dict = {}
        self._feedback_lock = threading.Lock()

        # Threads
        self._write_thread: threading.Thread | None = None
        self._read_thread: threading.Thread | None = None

    def connect(self) -> bool:
        """Open serial verbinding."""
        try:
            self._serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout,
            )
            self._running = True

            self._write_thread = threading.Thread(
                target=self._write_loop, daemon=True
            )
            self._read_thread = threading.Thread(
                target=self._read_loop, daemon=True
            )
            self._write_thread.start()
            self._read_thread.start()

            logger.info(f"Serial connected on {self.port} @ {self.baudrate}")
            return True
        except serial.SerialException as e:
            logger.error(f"Serial connection failed: {e}")
            return False

    def disconnect(self):
        """Sluit serial verbinding."""
        self._running = False
        if self._write_thread:
            self._write_thread.join(timeout=2.0)
        if self._read_thread:
            self._read_thread.join(timeout=2.0)
        if self._serial and self._serial.is_open:
            self._serial.close()
        logger.info("Serial disconnected")

    def send_command(self, cmd: dict):
        """Voeg commando toe aan queue (overschrijft vorig commando)."""
        self._cmd_queue.append(cmd)

    def send_motor(self, left_speed: int, right_speed: int):
        """Stuur motorcommando. Snelheden in -255..255 range."""
        left_speed = max(-255, min(255, int(left_speed)))
        right_speed = max(-255, min(255, int(right_speed)))
        self.send_command({"T": 1, "L": left_speed, "R": right_speed})

    def send_raw(self, cmd: dict):
        """Stuur commando direct (buiten queue om), voor init-sequenties."""
        with self._lock:
            self._write_cmd(cmd)

    def get_feedback(self) -> dict:
        """Haal laatste feedback op."""
        with self._feedback_lock:
            return self._feedback.copy()

    def init_sequence(self, commands: list[str]):
        """Voer init-sequentie uit (lijst van JSON strings)."""
        for cmd_str in commands:
            try:
                cmd = json.loads(cmd_str)
                self.send_raw(cmd)
                time.sleep(0.1)
            except json.JSONDecodeError:
                logger.warning(f"Invalid init command: {cmd_str}")

    def _write_cmd(self, cmd: dict):
        """Schrijf enkel commando naar serial (moet onder lock)."""
        if self._serial and self._serial.is_open:
            try:
                data = json.dumps(cmd, separators=(',', ':')) + '\n'
                self._serial.write(data.encode('utf-8'))
            except serial.SerialException as e:
                logger.error(f"Serial write error: {e}")

    def _write_loop(self):
        """Achtergrond loop: stuur commando's uit queue."""
        while self._running:
            try:
                cmd = self._cmd_queue.popleft()
            except IndexError:
                time.sleep(0.01)
                continue

            with self._lock:
                self._write_cmd(cmd)
            time.sleep(0.02)  # 50Hz max command rate

    def _read_loop(self):
        """Achtergrond loop: lees feedback van ESP32."""
        buffer = ""
        while self._running:
            if not self._serial or not self._serial.is_open:
                time.sleep(0.1)
                continue

            try:
                if self._serial.in_waiting > 0:
                    chunk = self._serial.read(self._serial.in_waiting).decode(
                        'utf-8', errors='ignore'
                    )
                    buffer += chunk

                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        line = line.strip()
                        if not line:
                            continue
                        self._parse_feedback(line)
                else:
                    time.sleep(0.01)
            except serial.SerialException as e:
                logger.error(f"Serial read error: {e}")
                time.sleep(0.1)

    def _parse_feedback(self, line: str):
        """Parse JSON feedback van ESP32."""
        try:
            data = json.loads(line)
            with self._feedback_lock:
                self._feedback.update(data)
        except json.JSONDecodeError:
            logger.debug(f"Non-JSON feedback: {line}")
