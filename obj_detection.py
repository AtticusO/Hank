import cv2
from ultralytics import YOLO
import cam_ops



# Load the tracking model
model = YOLO("yolov8n.pt")

class detect:
    def __init__(self):
        self.cam = cam_ops.Cam(1)

    def detection(self):
        while True:
            frame = self.cam.stream()
            if frame is None:
                break

            results = model.track(frame, persist=True)
            annotated_frame = results[0].plot()

            cv2.imshow("YOLOv8 Live Tracking", annotated_frame)
            if cv2.waitKey(1) == ord('q'):
                break

d = detect()
det = d.detection()


