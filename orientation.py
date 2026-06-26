import servo_ops
import asyncio
import time
from pynput import keyboard
from evdev import InputDevice, list_devices, categorize, ecodes

class positions:
    def __init__(self):
        self.servos = servo_ops.move()
        self.orient = {"waist" : self.servos.angles["waist"], 
                       "shoulder" : self.servos.angles["shoulder"], 
                       "elbow" : self.servos.angles["elbow"]}
        self.pos_log = []


    ## Moves servos asyncronously
    async def move_servo(self, servo_pos, delays):
        for i in range(len(servo_pos)):
            print(servo_pos[i])

            await asyncio.gather(
                self.servos.move_waist(servo_pos[i][0]),
                self.servos.move_shoulder(servo_pos[i][1]),
                self.servos.move_elbow(servo_pos[i][2])
            )
            self.orient["waist"] = servo_pos[i][0]
            self.orient["shoulder"] = servo_pos[i][1]
            self.orient["elbow"] = servo_pos[i][2]
            time.sleep(delays[i])

    



    #### Additive Rotations for servos

    ## Changes waist position incrementally
    async def rotate_waist(self, deg):
        posit_array = []
        delays = []
        curr_pos = self.orient["waist"]
        new_pos = curr_pos + deg
        posit_array.append([new_pos, self.orient["shoulder"], self.orient["elbow"]])
        delays.append(0.1)
        asyncio.run(self.move_servo(posit_array, delays))
    
    ## Changes waist position incrementally
    async def rotate_shoulder(self, deg):
        posit_array = []
        delays = []
        curr_pos = self.orient["shoulder"]
        new_pos = curr_pos + deg
        posit_array.append([self.orient["waist"], new_pos, self.orient["elbow"]])
        delays.append(0.1)
        asyncio.run(self.move_servo(posit_array, delays))
    
    ## Changes waist position incrementally
    async def rotate_elbow(self, deg):
        posit_array = []
        delays = []
        curr_pos = self.orient["elbow"]
        new_pos = curr_pos + deg
        posit_array.append([self.orient["waist"], self.orient["shoulder"], new_pos])
        delays.append(0.1)
        asyncio.run(self.move_servo(posit_array, delays))
    





    ###########################
    ### Arm Movements for keyboard control
    def reach(self, deg):
        posit_array = []
        delays = []
        curr_shoulder = self.orient["shoulder"]
        new_shoulder = curr_shoulder + deg
        curr_elbow = self.orient["elbow"]
        if deg > 0:
            new_elbow = curr_elbow + deg + 10
        elif deg < 0:
            new_elbow = curr_elbow + deg - 10
        posit_array.append([self.orient["waist"], new_shoulder, new_elbow])
        delays.append(0.1)
        asyncio.run(self.move_servo(posit_array, delays))
    
    def rotate(self, deg):
        posit_array = []
        delays = []
        curr_pos = self.orient["waist"]
        new_pos = curr_pos + deg
        posit_array.append([new_pos, self.orient["shoulder"], self.orient["elbow"]])
        delays.append(0.1)
        asyncio.run(self.move_servo(posit_array, delays))





    #### Preset Movements and Orientations


    ## Sets orientation for fist bump and loads to servo
    def fist_bump(self):
        posit_array = []
        delays = []
        if self.orient["shoulder"] != 70 and self.orient["elbow"] != 50:
            self.orient["shoulder"] = 70
            self.orient["elbow"] = 50
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
        if self.orient["shoulder"] != 70 and self.orient["elbow"] != 50:
            self.orient["shoulder"] = 70
            self.orient["elbow"] = 50
            posit_array.append([0, 70, 50])
            delays.append(0.2)
        posit_array.append([0, -40, -80])
        delays.append(0.1)
        posit_array.append([0, 70, 50])
        delays.append(0.1)
        
        asyncio.run(self.move_servo(posit_array, delays))
    
    def reset(self):
        posit_array = []
        delays = []
        posit_array.append([0, 70, 50])
        delays.append(0.5)
        
        asyncio.run(self.move_servo(posit_array, delays))

    def curl(self):
        posit_array = []
        delays = []
        posit_array.append([0, 0, 90])
        delays.append(0.4)
        
        asyncio.run(self.move_servo(posit_array, delays))

    def point(self):
        posit_array = []
        delays = []
        posit_array.append([10, 0, -90])
        delays.append(0.4)
        
        asyncio.run(self.move_servo(posit_array, delays))
    

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
        self.reset()
        delays.append(0.2)

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
    
    def point(self):
        posit_array = []
        delays = []
        posit_array.append([0, 0, -90])
        delays.append(0.2)

        asyncio.run(self.move_servo(posit_array, delays))



    def find_keyboard(self):
    
        for path in list_devices():
            dev = InputDevice(path)
            keys = dev.capabilities().get(ecodes.EV_KEY, [])
            if ecodes.KEY_A in keys and ecodes.KEY_UP in keys:
                return dev
        raise RuntimeError("No keyboard found in /dev/input")
    
    
    def listen(self):
        dev = self.find_keyboard()

        print(f"Listening on {dev.path} ({dev.name})")
        posit_array = []
        delays = []
        for event in dev.read_loop():
            if event.type != ecodes.EV_KEY:
                continue
            key = categorize(event)
            if key.keystate != key.key_down:   # only on press, ignore release/hold
                continue
            if key.keycode == "KEY_UP":
                print("Up PRESSED") 
                try:
                    asyncio.run(self.reach(-30))
                except:
                    print("Error in reach function")
            elif key.keycode == "KEY_DOWN":
                print("DOWN PRESSED")
                try:
                    asyncio.run(self.reach(30))
                except:
                    print("Error in reach function")

            elif key.keycode == "KEY_LEFT":
                print("LEFT PRESSED")
                try:
                    asyncio.run(self.rotate(30))
                except:
                    print("Error in rotate function")
            elif key.keycode == "KEY_RIGHT":
                print("RIGHT PRESSED")
                try:
                    asyncio.run(self.rotate(-30))
                except:
                    print("Error in rotate function")
            elif key.keycode == "KEY_R":
                print("RESET PRESSED")
                try:
                    self.reset()
                except:
                    print("Error in reset function")
            elif key.keycode == "KEY_C":
                print("CURL PRESSED")
                try:
                    self.curl()
                except:
                    print("Error in curl function")
            elif key.keycode == "KEY_ESC":
                break



    



if __name__ == "__main__":
    p = positions()
    print("\n $$$   Hank Orientation System   $$$ \n")
    settings = 0
    if settings == 0:
        print("Keyboard Controls: \n")
        p.reset()
        p.listen()
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
            elif x == "point" or x == "p":
                p.point()
            elif x == "jab" or x == "j":
                p.jab()
            elif x == "pt":
                p.point()
            elif x == "br":
                p.bounce_right()
            elif x == "bl":
                p.bounce_left()
            elif x == "waist":
                p.rotate_waist(10)
            time.sleep(0.5)
            p.rotate_waist(-10)
        