import cv2
import threading

class Cam:
    def __init__(self, port, width=640, height=480):
        self.cap = cv2.VideoCapture(port)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.frame = None
        self._lock = threading.Lock()
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self):
        while True:
            ret, frame = self.cap.read()
            if ret:
                with self._lock:
                    self.frame = frame

    def stream(self):
        with self._lock:
            return self.frame
