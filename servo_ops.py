from gpiozero import AngularServo
from gpiozero.pins.pigpio import PiGPIOFactory
import asyncio

## Home position for each servo
HOME = {"waist": 0, "shoulder": 70, "elbow": 50}

## GPIO pin for each servo
PINS = {"waist": 27, "shoulder": 17, "elbow": 18}

class move:
    def __init__(self):
        print("###HANK INITIALIZING###")
        self.factory = PiGPIOFactory()
        self.servos = {}
        self.angles = {}
        for name, pin in PINS.items():
            servo = AngularServo(pin, min_angle=-90, max_angle=90, pin_factory=self.factory)
            servo.angle = HOME[name]
            self.servos[name] = servo
            self.angles[name] = HOME[name]
            #print(f"{name.capitalize()} Angle | {HOME[name]}")

    ## Moves one servo to a given degree, clamped to [-90, 90].
    ## step > 0 sweeps toward the target in small increments so the arm
    ## moves smoothly; step=None jumps straight there for fast gestures.
    async def move_to(self, name, deg, step=5):
        if not isinstance(deg, (int, float)):
            print(f"{name}: angle must be a number, got {deg!r}")
            return
        target = max(-90, min(90, deg))
        if target != deg:
            print(f"{name}: {deg} out of range, clamped to {target}")

        current = self.angles[name]
        delta = target - current
        if step and abs(delta) > step:
            direction = 1 if delta > 0 else -1
            a = current
            for _ in range(int(abs(delta) // step)):
                a += direction * step
                self.servos[name].angle = a
                await asyncio.sleep(0.02)

        self.servos[name].angle = target
        self.angles[name] = target
        #print(f"{name.capitalize()} Angle | {target}")
        ## settle time scales with how far the servo still has to travel
        await asyncio.sleep(max(0.05, abs(delta) * 0.003) if step is None else 0.05)

    ## Moves waist to a given degree
    async def move_waist(self, deg, step=5):
        await self.move_to("waist", deg, step)

    ## Moves shoulder to a given degree
    async def move_shoulder(self, deg, step=5):
        await self.move_to("shoulder", deg, step)

    ## Moves elbow to a given degree
    async def move_elbow(self, deg, step=5):
        await self.move_to("elbow", deg, step)


async def main():
    m = move()

    ## Snaps shoulder/elbow out and back once (shared by jab and jj)
    async def jab_once():
        await asyncio.gather(
            m.move_shoulder(-50, step=None),
            m.move_elbow(-90, step=None)
        )
        await asyncio.sleep(0.1)
        await asyncio.gather(
            m.move_shoulder(70, step=None),
            m.move_elbow(50, step=None)
        )

    ## Returns to home first so gestures always start from the same pose
    async def home():
        if m.angles["shoulder"] != 70 or m.angles["elbow"] != 50:
            await asyncio.gather(
                m.move_shoulder(70),
                m.move_elbow(50)
            )
            await asyncio.sleep(0.05)

    while True:
        d = input("Enter number degree: ")

        ## Resets waist to 0, shoulder to 70, and elbow to 50
        if d == "reset" or d == "r":
            await asyncio.gather(
                m.move_waist(0),
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
            await home()
            await jab_once()
        elif d == "jj":
            await home()
            await jab_once()
            await asyncio.sleep(0.3)
            await jab_once()
        elif d == "wave" or d == "w":
            await asyncio.gather(
                m.move_shoulder(50),
                m.move_elbow(0)
            )
            await asyncio.sleep(0.2)
            await asyncio.gather(
                m.move_shoulder(80),
                m.move_elbow(30)
            )
            await asyncio.sleep(0.4)
            await asyncio.gather(
                m.move_shoulder(40),
                m.move_elbow(0)
            )

        elif "," in d:
            ## "shoulder,elbow" or "waist,shoulder,elbow"
            try:
                angles = [int(a) for a in d.split(",")]
            except ValueError:
                print("$$$$ ANGLES MUST BE WHOLE NUMBERS, e.g. 70,50 or 0,70,50 $$$$")
                continue
            if len(angles) == 2:
                await asyncio.gather(
                    m.move_shoulder(angles[0]),
                    m.move_elbow(angles[1])
                )
            elif len(angles) == 3:
                await asyncio.gather(
                    m.move_waist(angles[0]),
                    m.move_shoulder(angles[1]),
                    m.move_elbow(angles[2])
                )
            else:
                print("$$$$ ENTER 2 ANGLES (shoulder,elbow) OR 3 (waist,shoulder,elbow) $$$$")
        else:
            print("$$$$ PLEASE ENTER ANGLES IN A #,#,# FORMAT OR ENTER A COMMAND $$$$")

if __name__ == "__main__":
    asyncio.run(main())
