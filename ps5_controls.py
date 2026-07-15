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
    l_stick = [ps5.state.LX, ps5.state.LY]
    r_stick = [ps5.state.RX, ps5.state.RY]
    moved = False
    if l_stick[0] > 25:
        print("Shoulder Forward")
        pos_log[1] -= 5
        moved = True

    if l_stick[0] < -25:
        print("Shoulder Back")
        pos_log[1] += 5
        moved = True

    if r_stick[0] > 25:
        print("Shoulder Forward")
        pos_log[2] -= 5
        moved = True

    if r_stick[0] < -25:
        print("Shoulder Back")
        pos_log[2] += 5
        moved = True
        
    ''' 
    if "KEY_LEFT" in held:
        print("LEFT PRESSED")
        pos_log[0] -= 5
        moved = True

    if "KEY_RIGHT" in held:
        print("RIGHT PRESSED")
        pos_log[0] += 5
        moved = True
        
    if "KEY_P" in held:
        print("POINT PRESSED")
        pos.point()
    if "KEY_C" in held:
        print("CURL PRESSED")
        pos.curl()
    '''

    if moved:
        # move_servo expects a list of [waist, shoulder, elbow] rows
        asyncio.run(pos.move_servo([list(pos_log)]))