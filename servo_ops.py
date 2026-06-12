from gpiozero import AngularServo
from gpiozero.pins.pigpio import PiGPIOFactory
import asyncio
import time

class move:
    def __init__(self):
        print("###HANK INITIALIZING###")
        self.factory = PiGPIOFactory()
        self.shoulder = AngularServo(17, min_angle=-90, max_angle=90, pin_factory=self.factory)
        self.shoulder.angle = 70
        print(f"Shoulder Angle | 70")
        self.elbow = AngularServo(18, min_angle=-90, max_angle=90, pin_factory=self.factory)
        self.elbow.angle = 50
        print(f"Elbow Angle | 50")
        self.angles = {"shoulder": 70, "elbow": 50, "waist": 0}

    async def move_waist(self, deg):
        pass

    async def move_shoulder(self, deg):
        if -90 <= deg <= 90:
            curr_angle = self.angles["shoulder"]
            target = deg
            self.shoulder.angle = target
            if target != self.angles["shoulder"]:
                self.angles["shoulder"] = target
            print(f"Shoulder Angle | {target}")
            await asyncio.sleep(0.5)
        else:
            print("Enter A Valid Number Between -90 and 40")

    async def move_elbow(self, deg):
        if -90 <= deg <= 90:
            curr_angle = self.angles["elbow"]
            target = deg
            self.elbow.angle = target
            if target != self.angles["elbow"]:
                self.angles["elbow"] = target
            print(f"Elbow Angle | {target}")
            await asyncio.sleep(0.5)
        else:
            print("Enter A Valid Number Between -90 and 40")
    

async def main():
    m = move()
    while True:
        d = input("Enter number degree: ")
        if d == "reset" or d == "r":
            await asyncio.gather(
            m.move_shoulder(70),
            m.move_elbow(50)
        )
        ##curls up
        elif d == "curl" or d == "cu":
            await asyncio.gather(
                m.move_shoulder(0),
                m.move_elbow(90)
            )
        #upwards point
        elif d == "point" or d == "pt":
            await asyncio.gather(
                m.move_shoulder(0),
                m.move_elbow(-90)
            )
        
        ##Jabs and Double Jabs
        elif d == "jab" or d == "j":
            await asyncio.gather(
                m.move_shoulder(-50),
                m.move_elbow(-90)
            )
            time.sleep(0.1)
            await asyncio.gather(
                m.move_shoulder(70),
                m.move_elbow(50)
            )
        elif d == "jj":
            await asyncio.gather(
                m.move_shoulder(-50),
                m.move_elbow(-90)
            )
            time.sleep(0.1)
            await asyncio.gather(
                m.move_shoulder(70),
                m.move_elbow(50)
            )
            time.sleep(0.3)
            await asyncio.gather(
                m.move_shoulder(-50),
                m.move_elbow(-90)
            )
            time.sleep(0.1)
            await asyncio.gather(
                m.move_shoulder(70),
                m.move_elbow(50)
            )
        elif d == "wave" or d == "w":
            await asyncio.gather(
                m.move_shoulder(50),
                m.move_elbow(0)
            )
            time.sleep(0.2)
            await asyncio.gather(
                m.move_shoulder(80),
                m.move_elbow(30)
            )
            time.sleep(0.4)
            await asyncio.gather(
                m.move_shoulder(40),
                m.move_elbow(0)
            )
            
        elif "," in d:
            angles = [int(a) for a in d.split(",")]

            await asyncio.gather(
                m.move_shoulder(angles[0]),
                m.move_elbow(angles[1])
            )
        else:
            print("$$$$ PLEASE ENTER ANGLES IN A #,#,# FORMAT OR ENTER A COMMAND $$$$")

if __name__ == "__main__":
    asyncio.run(main())


