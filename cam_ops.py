import cv2
import threading
from picamera2 import Picamera2

class Cam:
    def __init__(self, port=0, width=640, height=480):
        self.picam2 = Picamera2(camera_num=port)
        config = self.picam2.create_preview_configuration(
            main={"format": "RGB888", "size": (width, height)}
        )
        self.picam2.configure(config)
        self.picam2.start()
        self.frame = None
        self._lock = threading.Lock()
        self._running = True
        self._thread = threading.Thread(target=self._reader, daemon=True)
        self._thread.start()

    def _reader(self):
        while self._running:
            frame = self.picam2.capture_array()
            if frame is not None:
                with self._lock:
                    self.frame = frame

    def stream(self):
        with self._lock:
            return self.frame

    ## Stops the reader thread and releases the camera
    def stop(self):
        self._running = False
        self._thread.join(timeout=1)
        self.picam2.stop()


if __name__ == "__main__":
    cam = Cam(0)
    while True:
        frame = cam.stream()
        if frame is not None:
            cv2.imshow("Camera Stream", frame)
        if cv2.waitKey(1) == ord('q'):
            break
    cv2.destroyAllWindows()
    cam.stop()
