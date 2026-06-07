from ultralytics import YOLO



# Load the tracking model
model = YOLO("yolov8n.pt")

class detect:
    def __init__(self):
        self.focus = None

    def detection(self, frame):
        results = model.track(frame, persist=True)
        annotated_frame = results[0].plot()
        return annotated_frame



