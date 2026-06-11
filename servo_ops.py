from gpiozero import AngularServo
from gpiozero.pins.pigpio import PiGPIOFactory

factory = PiGPIOFactory()
servo = AngularServo(18, min_angle=-90, max_angle=90, pin_factory=factory)

class move:
    def __init__(self):
        self.waist = 11
        self.shoulder = 12
        self.elbow = 17
    def waist_right(self, deg):
        pass
    def waist_left(self, deg):
        pass
    def shoulder_foward(self, deg):
        pass
    def shoulder_back(self, deg):
        pass
    def elbow_up(self, deg):
        pass
    def elbow_down(self, deg):
        pass



