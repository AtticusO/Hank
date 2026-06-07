import cam_ops
import obj_detection
import cv2


class Hank:
    def __init__(self):
        self.cam_init = cam_ops.Cam(1)
        self.model = obj_detection.detect()
    
    def detect(self, frame):
        #frame = self.cam_init.stream()
        results = self.model.detection(frame)
        return results

    def video(self):

        while True:
            frame = self.cam_init.stream()
            det = self.detect(frame)
            cv2.imshow("Hank View", det)
            if cv2.waitKey(1) == ord('q'):
                break
        cv2.destroyAllWindows()
    def show(self, frame):
        cv2.imshow("View", frame)


if __name__ == "__main__":
    print("Executing Hank Protocals")
    h = Hank()
    h.video()
    #h.show(res)
