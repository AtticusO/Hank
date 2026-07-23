from pydualsense import pydualsense
import orientation
import asyncio

ps5 = pydualsense()
pos = orientation.positions()


ps5.init()
ps5.light.setColorI(0, 255, 0)

while True:
    pos_log = pos.pos_log
    print(f"Left Stick: ({ps5.state.LX}, {ps5.state.LY}) | Right Stick: ({ps5.state.RX}, {ps5.state.RY})")

    bottons = {"cross" : ps5.state.cross, 
               "circle" : ps5.state.circle, 
               "square" : ps5.state.square, 
               "triangle" : ps5.state.triangle}

    triggers = {"L2" : ps5.state.L2,
                "R2" : ps5.state.R2}

    l_stick = [ps5.state.LX, ps5.state.LY]
    r_stick = [ps5.state.RX, ps5.state.RY]

    moved = False

    if triggers["L2"] == True:
        print("WAIST LEFT")
        pos_log[0] += 5
        moved = True
    if triggers["R2"] == True:
        print("WAIST RIGHT")
        pos_log[0] -= 5
        moved = True

    if l_stick[0] > 25:
        print("Shoulder Forward")
        pos_log[1] += 5
        moved = True

    if l_stick[0] < -25:
        print("Shoulder Back")
        pos_log[1] -= 5
        moved = True

    if r_stick[0] > 25:
        print("Shoulder Forward")
        pos_log[2] -= 5
        moved = True

    if r_stick[0] < -25:
        print("Shoulder Back")
        pos_log[2] += 5
        moved = True
    
    
    
    

    if bottons["cross"] == True:
        print("Cross PRESSED")
        pos.reset()

    
    if bottons["square"] == True:
        print("JAB PRESSED")
        pos.jab()
        moved = True

    if bottons["triangle"] == True:
        print("POINT PRESSED")
        pos.point()

    if bottons["circle"] == True:
        print("CURL PRESSED")
        pos.curl()

    if moved:
        # move_servo expects a list of [waist, shoulder, elbow] rows
        asyncio.run(pos.move_servo([pos_log]))
