import cv2

class Cam:
    def __init__(self, port):
        self.cam_port = port
        self.cap = cv2.VideoCapture(self.cam_port)

    def stream(self):
        if not self.cap.isOpened():
            print("Error: Could not open the camera.")
            return None

        ret, frame = self.cap.read()

        # If the frame was not grabbed successfully, break the loop
        if ret:
            return frame


