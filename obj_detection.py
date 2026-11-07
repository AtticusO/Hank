## obj_detection.py — YOLO person/cup detection + tracking IDs.
##
## Uses the ncnn export (2-4x faster on the Pi CPU) when it exists and was
## exported at the same size inference runs at; otherwise falls back to the
## PyTorch .pt model. ncnn inputs are fixed-size, which is why a 640 export
## couldn't be used with imgsz=320. Re-export with:
##   yolo export model=yolov8n.pt format=ncnn imgsz=320

import logging
import os

import config

log = logging.getLogger(__name__)


def _ncnn_imgsz(path):
    ## exported size from metadata.yaml, or None if unreadable
    try:
        import yaml
        with open(os.path.join(path, "metadata.yaml")) as f:
            size = yaml.safe_load(f).get("imgsz")
        return int(size[0] if isinstance(size, (list, tuple)) else size)
    except Exception:
        return None


def load_model():
    from ultralytics import YOLO          # heavy import: only when a detector is built
    ncnn = os.path.join(config.DIR, config.YOLO_NCNN_DIR)
    if os.path.isdir(ncnn):
        size = _ncnn_imgsz(ncnn)
        if size == config.INFER_SIZE:
            log.info("Loading ncnn model (%s px)", size)
            return YOLO(ncnn, task="detect")
        log.warning("ncnn model is %s px but inference runs at %s px — using the slower .pt model. "
                    "Re-export: yolo export model=%s format=ncnn imgsz=%s",
                    size, config.INFER_SIZE, config.YOLO_PT, config.INFER_SIZE)
    log.info("Loading %s", config.YOLO_PT)
    return YOLO(os.path.join(config.DIR, config.YOLO_PT))


class detect:
    def __init__(self, model=None):
        self.model = model or load_model()

    ## Returns (annotated_frame, tags, cords, ids)
    ##   tags: class names; cords: xyxy boxes; ids: tracker IDs (None until assigned)
    ## draw=False skips the box plotting (no display, e.g. under systemd)
    def detection(self, frame, draw=True):
        results = self.model.track(frame, persist=True, imgsz=config.INFER_SIZE,
                                   conf=config.DETECT_CONF, classes=config.DETECT_CLASSES,
                                   verbose=False)
        r = results[0]
        boxes = r.boxes
        tags = [r.names[int(c)] for c in boxes.cls]
        cords = boxes.xyxy
        ids = boxes.id
        annotated = r.plot() if (draw and tags) else frame
        return annotated, tags, cords, ids


## `python obj_detection.py` — benchmark ncnn vs .pt on this machine.
## Close VS Code first on the Pi: it eats ~1 CPU core and skews the numbers.
if __name__ == "__main__":
    import time
    import cv2
    from ultralytics import YOLO
    config.setup_logging()
    img = cv2.imread(os.path.join(os.path.dirname(__import__("ultralytics").__file__), "assets", "bus.jpg"))
    img = cv2.resize(img, (config.FRAME_W, config.FRAME_H))
    for name, path in (("ncnn", os.path.join(config.DIR, config.YOLO_NCNN_DIR)),
                       ("pt", os.path.join(config.DIR, config.YOLO_PT))):
        if not os.path.exists(path):
            continue
        m = YOLO(path, task="detect")
        for _ in range(3):
            m.predict(img, imgsz=config.INFER_SIZE, verbose=False)        # warm-up
        n, t = 10, time.monotonic()
        for _ in range(n):
            m.predict(img, imgsz=config.INFER_SIZE, conf=config.DETECT_CONF,
                      classes=config.DETECT_CLASSES, verbose=False)
        print(f"{name:5s} @ {config.INFER_SIZE}px: {(time.monotonic() - t) / n * 1000:.0f} ms/frame")
