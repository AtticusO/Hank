import servo_ops
import asyncio
import time

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
            print(f"{servo_pos[i][0]}, {servo_pos[i][1]}, {servo_pos[i][2]}")

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
    def rotate_waist(self, deg):
        posit_array = []
        delays = []
        curr_pos = self.orient["waist"]
        new_pos = curr_pos + deg
        posit_array.append[new_pos, "-", "-"]
        asyncio.run(self.move_servo(posit_array))
    
    ## Changes waist position incrementally
    def rotate_shoulder(self, deg):
        posit_array = []
        delays = []
        curr_pos = self.orient["shoulder"]
        new_pos = curr_pos + deg
        posit_array.append["-", new_pos, "-"]
        delays.append(0.1)
        asyncio.run(self.move_servo(posit_array))
    
    ## Changes waist position incrementally
    def rotate_elbow(self, deg):
        posit_array = []
        delays = []
        curr_pos = self.orient["elbow"]
        new_pos = curr_pos + deg
        posit_array.append["-", "-", new_pos]
        delays.append(0.1)
        asyncio.run(self.move_servo(posit_array))
    



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
        posit_array.append([0, -40, -80])
        delays.append(0.5)
        posit_array.append([0, 70, 50])
        
        
        asyncio.run(self.move_servo(posit_array))
    
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
        posit_array.append([0, 0, -90])
        delays.append(0.4)
        
        asyncio.run(self.move_servo(posit_array, delays))
    
    def wave(self):
        posit_array = []
        delays = []
        posit_array.append([0, 50, 0])
        delays.append(0.4)
        posit_array.append([0, 80, 30])
        delays.append(0.5)
        posit_array.append([0, 40, 0])
        delays.append(0.4)

        asyncio.run(self.move_servo(posit_array, delays))
    

    



if __name__ == "__main__":
    p = positions()
    p.fist_bump()
