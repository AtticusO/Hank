## distance.py — HC-SR04 ultrasonic range finder.
##
## HARDWARE: the HC-SR04's ECHO pin outputs 5 V, but Pi GPIOs are 3.3 V only.
## Put a voltage divider on ECHO (1 kΩ from ECHO to GPIO24, 2 kΩ from GPIO24 to
## GND) or use the 3.3 V-native HC-SR04P. Readings stuck at max or zero are
## the classic sign this is missing.
##
## Pass the shared pigpio factory: pigpio timestamps the echo edges in its
## daemon, so a busy CPU (YOLO) doesn't skew the timing like software timing does.

import logging
import math
import time

import config

log = logging.getLogger(__name__)


class measure:
    def __init__(self, factory=None):
        from gpiozero import DistanceSensor
        if factory is None:
            from gpiozero.pins.pigpio import PiGPIOFactory
            factory = PiGPIOFactory()
        self.sensor = DistanceSensor(echo=config.DIST_ECHO, trigger=config.DIST_TRIGGER,
                                     max_distance=config.DIST_MAX_M, pin_factory=factory)

    ## distance in centimetres (gpiozero reports metres)
    def dist(self):
        d = self.sensor.distance * 100
        log.debug("Distance: %.2f cm", d)
        return d


class mock_measure:
    ## Off-Pi stand-in: a slow sine drifting 10–200 cm, so the lean-in behaviour
    ## in personality.pers_condit is exercisable on a laptop
    def __init__(self, factory=None, period_s=20.0):
        self.t0 = time.monotonic()
        self.period = period_s

    def dist(self):
        phase = 2 * math.pi * (time.monotonic() - self.t0) / self.period
        return 105 + 95 * math.sin(phase)


def make(factory=None):
    ## Mock under HANK_MOCK=1; otherwise the real sensor, or None if it can't be
    ## opened (never fake readings on the real robot — Hank would lean at random)
    if config.MOCK:
        return mock_measure()
    try:
        return measure(factory)
    except Exception as e:
        log.warning("Distance sensor unavailable (%s) — distance reactions disabled", e)
        return None


if __name__ == "__main__":
    config.setup_logging()
    m = make()
    if m is None:
        raise SystemExit("No distance sensor")
    while True:
        print(f"Distance: {m.dist():.2f} cm")
        time.sleep(0.2)
