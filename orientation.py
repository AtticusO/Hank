import servo_ops
import asyncio
import time
from pynput import keyboard

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


    def on_press(self, key):
        try:
        # Check for specific special keys like arrow keys
            if key == keyboard.Key.up:
                print(f"Up Arrow Pressed ||\n Shoulder angle {self.orient["shoulder"]}\n  Elbow angle {self.orient["elbow"]}")
            elif key == keyboard.Key.down:
                print(f"Down Arrow Pressed ||\n Shoulder angle {self.orient["shoulder"]}\n  Elbow angle {self.orient["elbow"]}")
            elif key == keyboard.Key.left:
                print(f"Left Arrow Pressed ||\n Waist angle {self.orient["Waist"]}\n Shoulder angle {self.orient["shoulder"]}\n  Elbow angle {self.orient["elbow"]}")
            elif key == keyboard.Key.right:
                print(f"Right Arrow Pressed ||\n Waist angle {self.orient["Waist"]}\n Shoulder angle {self.orient["shoulder"]}\n  Elbow angle {self.orient["elbow"]}")
        except AttributeError:
            print("!!!Error With Arrow Controls!!!")
            pass

    def on_release(key):
        # Stop the listener by pressing the Escape key
        if key == keyboard.Key.esc:
            return False



    #### Additive Rotations for servos

    ## Changes waist position incrementally
    def rotate_waist(self, deg):
        posit_array = []
        delays = []
        curr_pos = self.orient["waist"]
        new_pos = curr_pos + deg
        posit_array.append([new_pos, self.orient["shoulder"], self.orient["elbow"]])
        delays.append(0.1)
        asyncio.run(self.move_servo(posit_array, delays))
    
    ## Changes waist position incrementally
    def rotate_shoulder(self, deg):
        posit_array = []
        delays = []
        curr_pos = self.orient["shoulder"]
        new_pos = curr_pos + deg
        posit_array.append([self.orient["waist"], new_pos, self.orient["elbow"]])
        delays.append(0.1)
        asyncio.run(self.move_servo(posit_array, delays))
    
    ## Changes waist position incrementally
    def rotate_elbow(self, deg):
        posit_array = []
        delays = []
        curr_pos = self.orient["elbow"]
        new_pos = curr_pos + deg
        posit_array.append([self.orient["waist"], self.orient["shoulder"], new_pos])
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




    



if __name__ == "__main__":
    p = positions()
    print("\n $$$   Hank Orientation System   $$$ \n")
    while True:
        with keyboard.Listener(on_press=p.on_press, on_release=p.on_release) as listener:
            listener.join()
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
        