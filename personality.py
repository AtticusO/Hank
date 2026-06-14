import cam_ops
import obj_detection
import cv2
import time
import servo_ops
import asyncio
import orientation

class acts:
    def __init__(self):
        self.cam_init = cam_ops.Cam(0)
        self.model = obj_detection.detect()
        self.turn = orientation.positions()
        self.last_tag_pos = None
    
    def move(self, servos, deg_change):
        if "waist" in servos:
            self.turn.rotate_waist(deg_change)
        if "shoulder" in servos:
            self.turn.rotate_shoulder(deg_change)
        if "elbow" in servos:
            self.turn.rotate_elbow(deg_change)
    
    def detect(self, frame):
        #frame = self.cam_init.stream()
        results = self.model.detection(frame)
        annotated_frame = results[0]
        tags = results[1]
        cords = results[2]

        return annotated_frame, tags, cords

    def video(self):
        prev_time = time.time()
        f_count = 0
        while True:
            frame = self.cam_init.stream()
            if frame is None:
                continue
            det = self.detect(frame)
            annotated_frame = det[0]
            f_count += 1
            tags = det[1]
            cords = det[2]
            if "person" in tags and f_count > 2:
                x = self.avg_x(tags, cords, "person")
                if x < 200:
                    self.move(["shoulder"], 15)
                elif x > 400:
                    self.move(["shoulder"], -15)
                f_count = 0
            fps = 1 / (time.time() - prev_time)
            prev_time = time.time()
            #cv2.putText(annotated_frame, f"FPS: {fps:.1f}", (10, 30),
            #            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

            cv2.imshow("Hank View", annotated_frame)
            if cv2.waitKey(1) == ord('q'):
                break
        cv2.destroyAllWindows()
    
    def avg_x(self, tags, cords, target_tag):
        xs = [
            ((box[0] + box[2]) / 2).item()
            for tag, box in zip(tags, cords)
            if tag == target_tag
        ]
        return sum(xs) / len(xs) if xs else None

    def show(self, frame):
        cv2.imshow("View", frame)

    


if __name__ == "__main__":
    print("Executing Hank Protocals")
    h = acts()
    h.video()
    #h.show(res)
