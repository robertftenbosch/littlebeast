"""
Camera streaming via MJPEG.

OpenCV VideoCapture → JPEG frames → StreamingResponse.
"""

import threading
import time
from typing import Optional

import cv2
import numpy as np


class Camera:
    """Thread-safe camera capture met MJPEG streaming."""

    def __init__(self, device: int = 0, width: int = 640, height: int = 480,
                 fps: int = 30):
        self.device = device
        self.width = width
        self.height = height
        self.fps = fps

        self._cap: Optional[cv2.VideoCapture] = None
        self._frame: Optional[np.ndarray] = None
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> bool:
        """Start camera capture in achtergrondthread."""
        self._cap = cv2.VideoCapture(self.device)
        if not self._cap.isOpened():
            print(f"[Camera] Kan camera {self.device} niet openen")
            return False

        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self._cap.set(cv2.CAP_PROP_FPS, self.fps)

        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        print(f"[Camera] Gestart op device {self.device} ({self.width}x{self.height})")
        return True

    def stop(self):
        """Stop camera capture."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3.0)
        if self._cap:
            self._cap.release()

    def get_frame(self) -> Optional[np.ndarray]:
        """Haal laatste frame op (BGR numpy array)."""
        with self._lock:
            return self._frame.copy() if self._frame is not None else None

    def get_jpeg(self, quality: int = 70) -> Optional[bytes]:
        """Haal laatste frame op als JPEG bytes."""
        frame = self.get_frame()
        if frame is None:
            return None
        _, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
        return jpeg.tobytes()

    def mjpeg_generator(self, quality: int = 70):
        """Generator voor MJPEG streaming."""
        interval = 1.0 / self.fps
        while self._running:
            jpeg = self.get_jpeg(quality)
            if jpeg:
                yield (
                    b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n\r\n' + jpeg + b'\r\n'
                )
            time.sleep(interval)

    def _capture_loop(self):
        """Achtergrond loop: lees frames van camera."""
        while self._running:
            if self._cap and self._cap.isOpened():
                ret, frame = self._cap.read()
                if ret:
                    with self._lock:
                        self._frame = frame
            time.sleep(0.001)  # Voorkom busy-wait
