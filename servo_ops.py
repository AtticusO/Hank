from gpiozero import AngularServo
from gpiozero.pins.pigpio import PiGPIOFactory
import asyncio


class move:
    def __init__(self):
        print("###HANK INITIALIZING###")
        self.factory = PiGPIOFactory()
        self.elbow = AngularServo(18, min_angle=-90, max_angle=90, pin_factory=self.factory)
        self.elbow.angle = 0
        print(f"Elbow Angle | 0")
        self.shoulder = AngularServo(17, min_angle=-90, max_angle=90, pin_factory=self.factory)
        self.shoulder.angle = 0
        print(f"Shoulder Angle | 0")
        self.angles = {"shoulder": 0, "elbow": 0, "waist": 0}

    async def move_waist(self, deg):
        pass

    async def move_shoulder(self, deg):
        if -90 < deg < 40:
            curr_angle = self.angles["shoulder"]
            target = curr_angle + deg
            self.shoulder.angle = target
            self.angles["shoulder"] = target
            print(f"Shoulder Angle | {target}")
            await asyncio.sleep(0.5)
        else:
            print("Enter A Valid Number Between -90 and 40")

    async def move_elbow(self, deg):
        if -90 < deg < 40:
            curr_angle = self.angles["elbow"]
            target = curr_angle + deg
            self.elbow.angle = target
            self.angles["elbow"] = target
            print(f"Elbow Angle | {target}")
            await asyncio.sleep(0.5)
        else:
            print("Enter A Valid Number Between -90 and 40")


async def main():
    m = move()
    while True:
        d = input("Enter number degree: ")
        angles = [int(a) for a in d.split(",")]
        await asyncio.gather(
            m.move_shoulder(angles[0]),
            m.move_elbow(angles[1])
        )

if __name__ == "__main__":
    asyncio.run(main())

