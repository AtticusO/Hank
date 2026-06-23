import cam_ops
import obj_detection
import cv2
import time
import asyncio
import orientation
import random as r

class acts:
    def __init__(self, tags, cords, distance):
        self.cam_init = cam_ops.Cam(0)
        self.model = obj_detection.detect()
        self.turn = orientation.positions()
        self.positions = self.turn.orient
        self.actions = [["cups", "dance", "follow"], ["fist_bump", "handshake", "greetings"]]
        self.tags = tags
        self.cords = cords
        self.person_time = 0
        self.following = False


    ### Greetings detection and activation functions
    def greetings(self):
        opt = r.randint(0,3)
        if opt == 0:
            self.turn.wave()
        elif opt == 1:
            self.turn.wave_one()
        elif opt == 2:
            self.turn.wave_two()

    def check_greeting(self):
        t = time.time()
        ## \/ need to make work with real time \/ output
        if (time.time() - self.person_time) > 30:
            self.greetings()
    





    def follow(self):
        self.follow = True
        x = self.avg_x(self.tags, self.cords ,"person")
        if self.positions["waist"] <= 90 and self.positions["waist"] >= -90:
                if x < 200:
                    self.move(["waist"], 25)
                elif x > 400:
                    self.move(["waist"], -25)
                    
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
    
    def pers_condit(self, tags, cords, distance):
        if "person" in tags:
            x = self.avg_x(tags, cords ,"person")
            if self.positions["waist"] <= 90 and self.positions["waist"] >= -90:
                    if x < 200:
                        self.move(["waist"], 15)
                    elif x > 400:
                        self.move(["waist"], -15)

        ## Distance Conditional, still need to figure out how exactly i could do this
        if distance < 15:
            if self.positions["shoulder"] <= 80 and self.positions["shoulder"] >= -80:
                if self.positions["elbow"] <= 80 and self.positions["elbow"] >= -80:
                    degree_change = 0
                    for i in distance:
                        if (i%2) == 0:
                            degree_change += 1
                    self.move(["shoulder", "elbow"], degree_change)




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
                if self.positions["waist"] <= 90 and self.positions["waist"] >= -90:
                    if x < 200:
                        self.move(["waist"], 15)
                    elif x > 400:
                        self.move(["waist"], -15)
                f_count = 0
            elif ("cup" in tags or "mug" in tags) and f_count > 2:
                x = self.avg_x(tags, cords, "cup")
                if self.positions["waist"] <= 90 and self.positions["waist"] >= -90:
                    if x < 200:
                        self.move(["waist"], 15)
                    elif x > 400:
                        self.move(["waist"], -15)
                    measure = self.meas.dist()
                f_count = 0
            elif f_count > 2:
                measure = self.meas.dist()
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
    a = acts()
    a.video()
    #h.show(res)
