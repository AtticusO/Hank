import cam_ops
import obj_detection
import personality
import orientation
import distance
import cv2


class Hank:
    ## Hank owns every piece of hardware exactly once and shares references;
    ## creating a second Cam or servo stack crashes on the Pi
    def __init__(self):
        self.cam = cam_ops.Cam(0)
        self.detector = obj_detection.detect()
        self.arm = orientation.positions()
        self.measure = distance.measure()
        self.pers = personality.acts(self.arm)

    def detect(self, frame):
        annotated_frame, tags, cords = self.detector.detection(frame)
        return annotated_frame, tags, cords

    def video(self):
        f_count = 0
        while True:
            frame = self.cam.stream()
            if frame is None:
                continue

            annotated_frame, tags, cords = self.detect(frame)
            f_count += 1

            ## React every few frames so servo moves don't stall the video
            if f_count > 2 and len(tags) > 0:
                d = self.measure.dist()
                self.pers.pers_condit(tags, cords, d)
                f_count = 0

            cv2.imshow("Hank View", annotated_frame)
            if cv2.waitKey(1) == ord('q'):
                break
        cv2.destroyAllWindows()
        self.cam.stop()


if __name__ == "__main__":
    print("Executing Hank Protocals")
    h = Hank()
    h.video()
