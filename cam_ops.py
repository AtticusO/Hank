## cam_ops.py — latest-frame camera reader on a background thread.
##
## Pi camera via picamera2 when available; otherwise (laptop, or HANK_WEBCAM=1)
## an OpenCV webcam with the same interface. Frames come out BGR either way:
## picamera2's "RGB888" format is BGR byte order, which is what OpenCV expects.
## If colours ever look swapped (reds blue), change it to "BGR888".

import logging
import os
import threading
import time

import cv2

import config

log = logging.getLogger(__name__)

try:
    from picamera2 import Picamera2
except ImportError:
    Picamera2 = None


class Cam:
    def __init__(self, port=0, width=config.FRAME_W, height=config.FRAME_H):
        self.frame = None
        self.count = 0              # increments on every new frame
        self.stamp = 0.0            # time.monotonic() of the latest frame
        self._lock = threading.Lock()
        self._running = True
        self.picam2 = None
        self.cap = None

        if Picamera2 is not None and os.environ.get("HANK_WEBCAM") != "1":
            try:
                self.picam2 = Picamera2(camera_num=port)
                cfg = self.picam2.create_preview_configuration(
                    main={"format": "RGB888", "size": (width, height)})
                self.picam2.configure(cfg)
                self.picam2.start()
                log.info("Pi camera %s started (%dx%d)", port, width, height)
            except Exception as e:
                self.picam2 = None
                log.error("Pi camera failed (%s). Check `rpicam-hello --list-cameras`; "
                          "'No cameras available' usually means the ribbon cable is loose. "
                          "Trying a USB webcam instead.", e)
        if self.picam2 is None:
            self.cap = cv2.VideoCapture(port)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            if not self.cap.isOpened():
                raise RuntimeError(f"No camera available (Pi camera and webcam {port} both failed)")
            log.info("Webcam %s started", port)

        self._thread = threading.Thread(target=self._reader, name="Cam", daemon=True)
        self._thread.start()

    def _grab(self):
        if self.picam2 is not None:
            return self.picam2.capture_array()
        ok, frame = self.cap.read()
        return frame if ok else None

    def _reader(self):
        while self._running:
            try:
                frame = self._grab()
            except Exception as e:
                log.warning("Camera read failed: %s", e)
                time.sleep(0.1)
                continue
            if frame is not None:
                with self._lock:
                    self.frame = frame
                    self.count += 1
                    self.stamp = time.monotonic()

    ## Latest frame (or None). Unchanged API.
    def stream(self):
        with self._lock:
            return self.frame

    ## (count, frame, stamp): compare count to skip a frame you already processed
    def read(self):
        with self._lock:
            return self.count, self.frame, self.stamp

    ## Stops the reader thread and releases the camera
    def stop(self):
        self._running = False
        self._thread.join(timeout=1)
        if self.picam2 is not None:
            self.picam2.stop()
        if self.cap is not None:
            self.cap.release()


if __name__ == "__main__":
    config.setup_logging()
    cam = Cam(0)
    try:
        while True:
            frame = cam.stream()
            if frame is not None:
                cv2.imshow("Camera Stream", frame)
            if cv2.waitKey(1) == ord('q'):
                break
    finally:
        cv2.destroyAllWindows()
        cam.stop()
