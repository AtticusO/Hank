from ultralytics import YOLO
import os

_DIR = os.path.dirname(os.path.abspath(__file__))
model = YOLO(os.path.join(_DIR, "yolov8n.pt"))  # swap to ncnn once re-exported
# model = YOLO(os.path.join(_DIR, "yolov8n_ncnn_model"))


class detect:
    def __init__(self):
        self.focus = None

    def detection(self, frame):
        results = model.track(frame, persist=True, imgsz=320, verbose=False, conf=0.6)
        tags = []
        cords = []
        for result in results:
            tags = [result.names[int(cls.item())] for cls in result.boxes.cls]
            cords = result.boxes.xyxy
        ## draw boxes whenever anything is detected (cups are the main job)
        annotated_frame = results[0].plot() if len(tags) else frame
        return annotated_frame, tags, cords



