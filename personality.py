import time
import random as r

class acts:
    ## arm is the shared orientation.positions() instance owned by main.Hank —
    ## acts must never create its own camera, model, or servo objects
    def __init__(self, arm):
        self.turn = arm
        self.positions = self.turn.orient
        self.actions = [["cups", "dance", "follow"], ["fist_bump", "handshake", "greetings"]]
        self.person_time = 0
        self.following = False
        self.tracked = []

    ### Greetings detection and activation functions
    def greetings(self):
        wave = r.choice([self.turn.wave, self.turn.wave_one, self.turn.wave_two])
        wave()

    ## Waves when a person shows up after not seeing anyone for 30 seconds
    def check_greeting(self, tags):
        if "person" in tags:
            if (time.time() - self.person_time) > 30:
                self.greetings()
            self.person_time = time.time()

    def follow(self, tags, cords):
        self.following = True
        x = self.avg_x(tags, cords, "person")
        y = self.avg_y(tags, cords, "person")
        self.tracked.append([x, y])
        if len(self.tracked) > 5:
            self.tracked.pop(0)

        #need to make leading mechanism work and actually make up for delay
        leading = 0

        for i in range(len(self.tracked)):
            while (i+1) <= len(self.tracked):
                leading += self.tracked[i+1][0] - self.tracked[i][0]

        if x is not None:
            if leading > 50:
                self.move(["waist"], 10)
            elif leading < -50:
                self.move(["waist"], -10)

            
            if x < 250:
                self.move(["waist"], 10)
            elif x > 350:
                self.move(["waist"], -10)
            
            if y < 150:
                self.move(["shoulder"], 10)
                self.move(["elbow"], 10)
            elif y > 300:
                self.move(["shoulder"], -10)
                self.move(["elbow"], -10)
    def move(self, servos, deg_change):
        if "waist" in servos:
            self.turn.rotate_waist(deg_change)
        if "shoulder" in servos:
            self.turn.rotate_shoulder(deg_change)
        if "elbow" in servos:
            self.turn.rotate_elbow(deg_change)

    ## Per-frame reactions: greet, turn toward a person, lean when something is close
    def pers_condit(self, tags, cords, distance):
        self.check_greeting(tags)

        if "person" in tags:
            x = self.avg_x(tags, cords, "person")
            y = self.avg_y(tags, cords, "person")
            if x is not None:
                if x < 200:
                    self.move(["waist"], 15)
                elif x > 400:
                    self.move(["waist"], -15)

        ## Distance Conditional: lean up slightly, more the closer something gets (within 15 cm)
        if distance is not None and distance < 15:
            if -80 <= self.positions["shoulder"] <= 80 and -80 <= self.positions["elbow"] <= 80:
                degree_change = int(15 - distance)
                self.move(["shoulder", "elbow"], degree_change)

    ## Average x-position (pixel) of all boxes matching target_tag, None if absent
    def avg_x(self, tags, cords, target_tag):
        xs = [
            ((box[0] + box[2]) / 2).item()
            for tag, box in zip(tags, cords)
            if tag == target_tag
        ]
        return sum(xs) / len(xs) if xs else None
    def avg_y(self, tags, cords, target_tag):
            xs = [
                ((box[1] + box[3]) / 2).item()
                for tag, box in zip(tags, cords)
                if tag == target_tag
            ]
            return sum(xs) / len(xs) if xs else None