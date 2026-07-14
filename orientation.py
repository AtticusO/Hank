import servo_ops
import asyncio
import time
from evdev import InputDevice, list_devices, categorize, ecodes
import select

class positions:
    def __init__(self):
        self.servos = servo_ops.move()
        self.orient = {"waist" : self.servos.angles["waist"],
                       "shoulder" : self.servos.angles["shoulder"],
                       "elbow" : self.servos.angles["elbow"]}
        self.pos_log = []
        for tags in self.orient:
            self.pos_log.append(self.orient[tags])

    ## Keeps orient/pos_log in sync with what the servos actually did,
    ## since the servo layer clamps angles to [-90, 90]
    def _sync_state(self):
        for i, name in enumerate(("waist", "shoulder", "elbow")):
            self.orient[name] = self.servos.angles[name]
            self.pos_log[i] = self.servos.angles[name]

    ## Moves servos asyncronously
    ## servo_pos is a list of [waist, shoulder, elbow] positions
    async def move_servo(self, servo_pos, delays=None):
        for i in range(len(servo_pos)):
            print(servo_pos[i])

            await asyncio.gather(
                self.servos.move_waist(servo_pos[i][0]),
                self.servos.move_shoulder(servo_pos[i][1]),
                self.servos.move_elbow(servo_pos[i][2])
            )

            self._sync_state()
            if delays and i < len(delays) and delays[i] is not None:
                await asyncio.sleep(delays[i])

    ## generates and returns servo positional array, posit_array, instead of directly calling servo movement
    ## output from these functions get passed into the move_servo() function to update servo position
    ## all of these functions return a list of servo degree positions in a [[waist,shoulder,elbow]] format
    def waist(self, deg):
        new_pos = self.orient["waist"] + deg
        return [[new_pos, self.orient["shoulder"], self.orient["elbow"]]]

    def shoulder(self, deg):
        new_pos = self.orient["shoulder"] + deg
        return [[self.orient["waist"], new_pos, self.orient["elbow"]]]

    def elbow(self, deg):
        new_pos = self.orient["elbow"] + deg
        return [[self.orient["waist"], self.orient["shoulder"], new_pos]]

    ## Additive Rotations for servos
    ## These are plain sync methods: each one is a single top-level
    ## asyncio.run() call, so they can be used from normal code anywhere
    ## Changes waist position incrementally
    def rotate_waist(self, deg):
        asyncio.run(self.move_servo(self.waist(deg), [0.1]))

    ## Changes shoulder position incrementally
    def rotate_shoulder(self, deg):
        asyncio.run(self.move_servo(self.shoulder(deg), [0.1]))

    ## Changes elbow position incrementally
    def rotate_elbow(self, deg):
        asyncio.run(self.move_servo(self.elbow(deg), [0.1]))

    ###########################
    ### Arm Movements for keyboard control
    def reach(self, deg):
        new_shoulder = self.orient["shoulder"] + deg

        ## elbow follows the shoulder a little further to keep the reach straight
        if deg > 0:
            new_elbow = self.orient["elbow"] + deg + 10
        elif deg < 0:
            new_elbow = self.orient["elbow"] + deg - 10
        else:
            new_elbow = self.orient["elbow"]

        posit_array = [[self.orient["waist"], new_shoulder, new_elbow]]
        asyncio.run(self.move_servo(posit_array))

    def rotate(self, deg):
        new_pos = self.orient["waist"] + deg
        posit_array = [[new_pos, self.orient["shoulder"], self.orient["elbow"]]]
        asyncio.run(self.move_servo(posit_array))

    #### Preset Movements and Orientations

    ## Sets orientation for fist bump and loads to servo
    def fist_bump(self):
        posit_array = []
        delays = []
        if self.orient["shoulder"] != 70 or self.orient["elbow"] != 50:
            posit_array.append([0, 70, 50])
            delays.append(0.5)
        posit_array.append([0, 20, -10])
        delays.append(1)
        posit_array.append([0, 70, 50])
        delays.append(0.5)

        asyncio.run(self.move_servo(posit_array, delays))

    def jab(self):
        posit_array = []
        delays = []
        if self.orient["shoulder"] != 70 or self.orient["elbow"] != 50:
            posit_array.append([0, 70, 50])
            delays.append(0.2)
        posit_array.append([0, -40, -80])
        delays.append(0.1)
        posit_array.append([0, 70, 50])
        delays.append(0.1)

        asyncio.run(self.move_servo(posit_array, delays))

    def reset(self):
        asyncio.run(self.move_servo([[0, 70, 50]], [0.5]))

    def curl(self):
        asyncio.run(self.move_servo([[0, 0, 90]], [0.4]))

    def point(self):
        asyncio.run(self.move_servo([[0, 0, -90]], [0.2]))

    ### Different Waves for greetings
    def wave(self):
        posit_array = []
        delays = []
        posit_array.append([0, 70, self.orient["elbow"]])
        delays.append(0.4)
        posit_array.append([0, 70, 50])
        delays.append(0.01)
        posit_array.append([0, 70, -30])
        delays.append(0.2)
        posit_array.append([0, 70, 50])
        delays.append(0.01)
        posit_array.append([0, 70, -30])
        delays.append(0.2)

        asyncio.run(self.move_servo(posit_array, delays))
        self.reset()

    def wave_one(self):
        posit_array = []
        delays = []
        posit_array.append([0, 70, self.orient["elbow"]])
        delays.append(0.4)
        posit_array.append([0, 70, 50])
        delays.append(0.01)
        posit_array.append([0, 70, -30])
        delays.append(0.2)
        posit_array.append([0, 70, 50])
        delays.append(0.01)
        posit_array.append([0, 70, -30])
        delays.append(0.2)

        asyncio.run(self.move_servo(posit_array, delays))
        self.reset()

    def wave_two(self):
        posit_array = []
        delays = []
        posit_array.append([0, 70, -90])
        delays.append(0.4)
        posit_array.append([20, self.orient["shoulder"], self.orient["elbow"]])
        delays.append(0.01)
        posit_array.append([0, self.orient["shoulder"], self.orient["elbow"]])
        delays.append(0.2)
        posit_array.append([-20, self.orient["shoulder"], self.orient["elbow"]])
        delays.append(0.01)

        asyncio.run(self.move_servo(posit_array, delays))
        self.reset()

    def bounce_left(self):
        posit_array = []
        delays = []
        posit_array.append([-30, 30, 10])
        delays.append(0.2)
        posit_array.append([-70, 70, 50])
        delays.append(0.01)
        posit_array.append([-30, 30, 10])
        delays.append(0.2)
        posit_array.append([0, 70, 50])
        delays.append(0.2)

        asyncio.run(self.move_servo(posit_array, delays))
        self.reset()

    def bounce_right(self):
        posit_array = []
        delays = []
        posit_array.append([30, 30, 10])
        delays.append(0.2)
        posit_array.append([70, 70, 50])
        delays.append(0.01)
        posit_array.append([30, 30, 10])
        delays.append(0.2)
        posit_array.append([0, 70, 50])
        delays.append(0.2)

        asyncio.run(self.move_servo(posit_array, delays))
        self.reset()

    def find_keyboard(self):
        for path in list_devices():
            dev = InputDevice(path)
            keys = dev.capabilities().get(ecodes.EV_KEY, [])
            if ecodes.KEY_A in keys and ecodes.KEY_UP in keys:
                return dev
        raise RuntimeError("No keyboard found in /dev/input")

    def listen_hold(self):
        """Hold-aware loop: tracks which keys are currently held and acts
        repeatedly while they stay down, independent of OS key-repeat rate.
        Left/right rotate the waist, up/down raise/lower the shoulder."""
        dev = self.find_keyboard()
        print(f"Listening on {dev.path} ({dev.name})")
        held = set()

        while True:
            # Wait up to 0.05s for input; returns immediately if a key event is ready.
            r, _, _ = select.select([dev.fd], [], [], 0.05)
            if r:
                for event in dev.read():
                    if event.type != ecodes.EV_KEY:
                        continue
                    key = categorize(event)
                    if key.keystate == key.key_down:
                        held.add(key.keycode)
                    elif key.keystate == key.key_up:
                        held.discard(key.keycode)

            if "KEY_ESC" in held:
                break

            # This block runs ~20x/sec for as long as a key stays held.
            moved = False
            if "KEY_UP" in held:
                print("UP PRESSED")
                self.pos_log[1] -= 5
                moved = True

            if "KEY_DOWN" in held:
                print("DOWN PRESSED")
                self.pos_log[1] += 5
                moved = True

            
            if "KEY_LEFT" in held:
                print("LEFT PRESSED")
                self.pos_log[0] -= 5
                moved = True

            if "KEY_RIGHT" in held:
                print("RIGHT PRESSED")
                self.pos_log[0] += 5
                moved = True
            


            
            if "KEY_W" in held:
                print("LEFT PRESSED")
                self.pos_log[2] -= 5
                moved = True

            if "KEY_E" in held:
                print("RIGHT PRESSED")
                self.pos_log[2] += 5
                moved = True
            
            if "KEY_A" in held:
                print("LEFT PRESSED")
                self.pos_log[1] -= 5
                moved = True

            if "KEY_D" in held:
                print("RIGHT PRESSED")
                self.pos_log[1] += 5
                moved = True
            
            if "KEY_Z" in held:
                print("LEFT PRESSED")
                self.pos_log[0] -= 5
                moved = True

            if "KEY_X" in held:
                print("RIGHT PRESSED")
                self.pos_log[0] += 5
                moved = True




            if "KEY_R" in held:
                print("RESET PRESSED")
                self.reset()
            if "KEY_P" in held:
                print("POINT PRESSED")
                self.point()
            if "KEY_C" in held:
                print("CURL PRESSED")
                self.curl()
            if moved:
                # move_servo expects a list of [waist, shoulder, elbow] rows
                asyncio.run(self.move_servo([list(self.pos_log)]))

    def listen_press(self):
        dev = self.find_keyboard()

        print(f"Listening on {dev.path} ({dev.name})")
        for event in dev.read_loop():
            if event.type != ecodes.EV_KEY:
                continue
            key = categorize(event)
            if key.keystate != key.key_down:   # only on press, ignore release/hold
                continue
            if key.keycode == "KEY_UP":
                print("UP PRESSED")
                self.reach(-30)
            elif key.keycode == "KEY_DOWN":
                print("DOWN PRESSED")
                self.reach(30)
            elif key.keycode == "KEY_LEFT":
                print("LEFT PRESSED")
                self.rotate(30)
            elif key.keycode == "KEY_RIGHT":
                print("RIGHT PRESSED")
                self.rotate(-30)
            elif key.keycode == "KEY_R":
                print("RESET PRESSED")
                self.reset()
            elif key.keycode == "KEY_C":
                print("CURL PRESSED")
                self.curl()
            elif key.keycode == "KEY_ESC":
                break


if __name__ == "__main__":
    p = positions()
    print("\n $$$   Hank Orientation System   $$$ \n")
    settings = 0
    if settings == 0:
        print("Keyboard Controls: \n")
        p.reset()
        p.listen_hold()
    elif settings == 1:
        while True:
            print("\n")
            x = input("Enter Orientation >>> ")
            print("\n")
            if x == "curl" or x == "cu":
                p.curl()
            elif x == "fb" or x == "b":
                p.fist_bump()
            elif x == "reset" or x == "r":
                p.reset()
            elif x == "wave" or x == "w":
                p.wave()
            elif x == "point" or x == "p" or x == "pt":
                p.point()
            elif x == "jab" or x == "j":
                p.jab()
            elif x == "br":
                p.bounce_right()
            elif x == "bl":
                p.bounce_left()
            elif x == "waist":
                p.rotate_waist(10)
                time.sleep(0.5)
                p.rotate_waist(-10)
