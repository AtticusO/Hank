from ultralytics import YOLO



# Load the tracking model
model = YOLO("yolov8n.pt")

class detect:
    def __init__(self):
        self.focus = None

    def detection(self, frame):
        results = model.track(frame, persist=True)
        for result in results:
            # Get the predicted class IDs and convert them to names
            tags = [result.names[int(cls.item())] for cls in result.boxes.cls]
            cords = result.boxes.xyxy # [xmin, ymin, xmax, ymax] in pixels
        print(f"Objects | {tags}")
        print(f"Cordinates | {cords}")
        annotated_frame = results[0].plot()
        return annotated_frame, tags, cords



