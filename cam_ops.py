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
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self):
        while True:
            frame = self.picam2.capture_array()
            if frame is not None:
                with self._lock:
                    self.frame = frame

    def stream(self):
        with self._lock:
            return self.frame


if __name__ == "__main__":
    cam = Cam(0)
    while True:
        frame = cam.stream()
        if frame is not None:
            cv2.imshow("Camera Stream", frame)
        if cv2.waitKey(1) == ord('q'):
            break
    cv2.destroyAllWindows()
