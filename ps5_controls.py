from pydualsense import pydualsense
import asyncio
import subprocess
import time
import server


subprocess.run(['bash', 'bt_connect.sh'])
print("Connected to PS5 Controller")
ps5 = pydualsense()



ps5.init()
ps5.light.setColorI(0, 255, 0)

class Controller:
    def __init__(self, arm):
        
        self.arm = arm
        self.pos_log = self.arm.pos_log

        self.rate = 5

        print(f"Left Stick: ({ps5.state.LX}, {ps5.state.LY}) | Right Stick: ({ps5.state.RX}, {ps5.state.RY})\nRate: {self.rate}")


        self.dpad = {}

        self.buttons = {}

        self.triggers = {}
        self.bumpers = {}

        self.l_stick = []
        self.r_stick = []

        self.last_press = time.time()
        self.cancel = False
        self.moved = False
    def remote(self):


        self.dpad = {"up" : ps5.state.DpadUp, 
                "down" : ps5.state.DpadDown, 
                "left" : ps5.state.DpadLeft, 
                "right" : ps5.state.DpadRight}

        self.buttons = {"cross" : ps5.state.cross, 
                        "circle" : ps5.state.circle, 
                        "square" : ps5.state.square, 
                        "triangle" : ps5.state.triangle}

        self.triggers = {"L2" : ps5.state.L2,
                "R2" : ps5.state.R2}
        
        self.bumpers = {"L1" : ps5.state.L1,
                "R1" : ps5.state.R1}
        
        self.l_stick = [ps5.state.LX, ps5.state.LY]
        self.r_stick = [ps5.state.RX, ps5.state.RY]
        
        self.bumpers = {"L1" : ps5.state.L1,
                        "R1" : ps5.state.R1}

        if self.dpad["up"] == True and self.last_press + 0.5 < time.time():
           
           self. rate += 1
           self.last_press = time.time()
           print("Rate: ", self.rate)

        if self.bumpers["L1"] == True and self.bumpers["R1"] == True:
            asyncio.run(self.start_server)

        if self.dpad["down"] == True and self.last_press + 0.5 < time.time():
            self.rate -= 1
            self.last_press = time.time()
            print("Rate: ", self.rate)

        
        if self.triggers["L2"] == True:
            print("\nWAIST LEFT")
            self.pos_log[0] += self.rate
            self.moved = True
        if self.triggers["R2"] == True:
            print("\nWAIST RIGHT")
            self.pos_log[0] -= self.rate
            self.moved = True

        if self.l_stick[0] > 25:
            print("\nSHOULDER FORWARD")
            self.pos_log[1] -= self.rate
            self.moved = True

        if self.l_stick[0] < -25:
            print("\nSHOULDER BACK")
            self.pos_log[1] += self.rate
            self.moved = True

        if self.r_stick[1] > 25:
            print("\nELBOW FORWARD")
            self.pos_log[2] += self.rate
            self.moved = True

        if self.r_stick[1] < -25:
            print("\nELBOW BACK")
            self.pos_log[2] -= self.rate
            self.moved = True
    

        if self.buttons["cross"] == True:
            print("\nCross PRESSED")
            self.arm.reset()

    
        if self.buttons["square"] == True:
            print("\nJAB PRESSED")
            self.arm.jab()
            self.moved = True

        if self.buttons["triangle"] == True:
            print("\nPOINT PRESSED")
            self.arm.point()

        if self.buttons["circle"] == True:
            print("\nCURL PRESSED")
            self.arm.curl()

        if self.bumpers["L1"] == True and self.bumpers["R1"] == True:
            print("\nCANCEL PRESSED")
            self.arm.curl()
            self.cancel = True

            

        if self.moved:
            # move_servo expects a list of [waist, shoulder, elbow] rows
            asyncio.run(self.arm.move_servo([self.pos_log]))
            print(f"Current Position: {self.pos_log}")
            self.moved = False
    async def start_server():
        server._start_server()



if __name__ == "__main__":
    import orientation

    pos = orientation.positions()
    c = Controller(pos)
    while True:
        r = c.remote()
        if c.cancel == True:
            break
