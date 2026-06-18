from gpiozero import DistanceSensor
from time import sleep


class measure:
    def __init__(self):
        # Define the GPIO pins mapped to Trig and Echo
        self.sensor = DistanceSensor(echo=24, trigger=23)

    def dist(self):
        
        
        # Print the distance in centimeters
        d = self.sensor.distance * 10
        print(f"Distance: {d:.2f} cm")
        return d
        

