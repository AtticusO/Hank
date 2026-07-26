from pydualsense import pydualsense
import asyncio

ps5 = pydualsense()


ps5.init()
ps5.light.setColorI(0, 255, 0)

class Controller:
    def __inti__(self, arm):
        
        self.arm = arm
        self.pos_log = self.arm.pos_log

        print(f"Left Stick: ({ps5.state.LX}, {ps5.state.LY}) | Right Stick: ({ps5.state.RX}, {ps5.state.RY})")

        self.buttons = {"cross" : ps5.state.cross, 
               "circle" : ps5.state.circle, 
               "square" : ps5.state.square, 
               "triangle" : ps5.state.triangle}

        self.triggers = {"L2" : ps5.state.L2,
                "R2" : ps5.state.R2}

        self.l_stick = [ps5.state.LX, ps5.state.LY]
        self.r_stick = [ps5.state.RX, ps5.state.RY]

        self.cancel = False
        self.moved = False
    def remote(self):
        if self.triggers["L2"] == True:
            print("\nWAIST LEFT")
            self.pos_log[0] += 5
            moved = True
        if self.triggers["R2"] == True:
            print("\nWAIST RIGHT")
            self.pos_log[0] -= 5
            moved = True

        if self.l_stick[0] > 25:
            print("\nSHOULDER FORWARD")
            self.pos_log[1] += 5
            moved = True

        if self.l_stick[0] < -25:
            print("\nSHOULDER BACK")
            self.pos_log[1] -= 5
            moved = True

        if self.r_stick[0] > 25:
            print("\nELBOW FORWARD")
            self.pos_log[2] -= 5
            moved = True

        if self.r_stick[0] < -25:
            print("\nELBOW BACK")
            self.pos_log[2] += 5
            moved = True
    

        if self.buttons["cross"] == True:
            print("\nCross PRESSED")
            self.arm.reset()

    
        if self.buttons["square"] == True:
            print("\nJAB PRESSED")
            self.arm.jab()
            moved = True

        if self.buttons["triangle"] == True:
            print("\nPOINT PRESSED")
            self.arm.point()

        if self.buttons["circle"] == True:
            print("\nCURL PRESSED")
            self.arm.curl()

        if moved:
            # move_servo expects a list of [waist, shoulder, elbow] rows
            asyncio.run(self.arm.move_servo([self.pos_log]))

if __name__ == "__main__":
    import orientation

    pos = orientation.positions()
    c = Controller(pos)
    while True:
        c.remote()
        if c.cancle == True:
            break
