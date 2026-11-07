## servo_ops.py — the only module that talks to the servo hardware.
##
## `move` owns the three AngularServos. Nothing should call it directly any
## more except servo_worker.ServoWorker (the single hardware owner); everything
## else sets targets on the worker. With HANK_MOCK=1, or when gpiozero/pigpio
## can't be imported (laptop), `move` is swapped for mock_servos.move so no
## other file has to change.

import asyncio
import logging

import config

log = logging.getLogger(__name__)

try:
    from gpiozero import AngularServo
    from gpiozero.pins.pigpio import PiGPIOFactory
    _HW = not config.MOCK
except ImportError:
    _HW = False

## Kept as module constants for backwards compatibility with old imports
HOME = dict(config.HOME)
PINS = dict(config.SERVO_PINS)


class move:
    def __init__(self, factory=None):
        log.info("### HANK INITIALIZING ###")
        ## One pigpio factory shared with the distance sensor / buttons (pass it in)
        self.factory = factory or PiGPIOFactory()
        self.servos = {}
        self.angles = {}
        for name, pin in config.SERVO_PINS.items():
            lo, hi = config.PULSE_WIDTHS[name]
            ## No feedback from hobby servos, so the first pulse always snaps the
            ## joint to HOME from wherever it physically is (see FIXES_LOG.md §7.5).
            servo = AngularServo(pin, min_angle=-90, max_angle=90,
                                 min_pulse_width=lo, max_pulse_width=hi,
                                 initial_angle=config.HOME[name],
                                 pin_factory=self.factory)
            self.servos[name] = servo
            self.angles[name] = float(config.HOME[name])
            log.debug("%s angle | %s", name.capitalize(), config.HOME[name])

    ## Synchronous, immediate write (clamped to the per-joint limits).
    ## The ServoWorker calls this ~100x/sec to glide; it never sleeps.
    def set_angle(self, name, deg):
        target = config.clamp(name, float(deg))
        self.servos[name].angle = target       # also re-attaches a limp servo
        self.angles[name] = target
        return target

    ## Go limp: stop sending pulses so the joint stops fighting you / buzzing
    def detach(self, name):
        self.servos[name].detach()

    def detach_all(self):
        for name in self.servos:
            self.detach(name)

    ## Old async API, kept so existing code and the CLI still work. Sweeps in
    ## 1° steps every 4 ms (~250°/s) instead of the old 5° jumps.
    async def move_to(self, name, deg, step=1):
        if not isinstance(deg, (int, float)):
            log.warning("%s: angle must be a number, got %r", name, deg)
            return
        target = config.clamp(name, deg)
        if target != deg:
            log.info("%s: %s out of range, clamped to %s", name, deg, target)
        current = self.angles[name]
        delta = target - current
        if step and abs(delta) > step:
            direction = 1 if delta > 0 else -1
            a = current
            for _ in range(int(abs(delta) // step)):
                a += direction * step
                self.set_angle(name, a)
                await asyncio.sleep(0.004)
        self.set_angle(name, target)
        await asyncio.sleep(0.02)

    async def move_waist(self, deg, step=1):
        await self.move_to("waist", deg, step)

    async def move_shoulder(self, deg, step=1):
        await self.move_to("shoulder", deg, step)

    async def move_elbow(self, deg, step=1):
        await self.move_to("elbow", deg, step)


## ---- selection shim (fixes.md §5.2): mock replaces the class for all importers
if not _HW:
    from mock_servos import move  # noqa: F811,E402


## ---- servo command line: `python servo_ops.py`
## Uses the same gesture table as the rest of Hank instead of its own copies.
ALIASES = {"r": "reset", "cu": "curl", "pt": "point", "j": "jab", "w": "wave", "b": "fist_bump"}


def main():
    import gestures
    from servo_worker import ServoWorker

    config.setup_logging()
    worker = ServoWorker(move())
    print("Commands: " + ", ".join(sorted(gestures.GESTURES)) +
          ", jj (double jab), limp, q — or angles like 70,50 (shoulder,elbow) / 0,70,50")
    try:
        while True:
            d = input("Enter command or angles: ").strip().lower()
            d = ALIASES.get(d, d)
            if d in ("q", "quit", "exit"):
                break
            if d in gestures.GESTURES:
                worker.play_gesture(*gestures.get(d), wait=True)
            elif d == "jj":
                for _ in range(2):
                    worker.play_gesture(*gestures.get("jab"), wait=True)
            elif d == "limp":
                worker.go_limp()
            elif "," in d:
                try:
                    angles = [float(a) for a in d.split(",")]
                except ValueError:
                    print("Angles must be numbers, e.g. 70,50 or 0,70,50")
                    continue
                if len(angles) == 2:
                    worker.set_targets({"shoulder": angles[0], "elbow": angles[1]})
                elif len(angles) == 3:
                    worker.set_targets(dict(zip(config.JOINTS, angles)))
                else:
                    print("Enter 2 angles (shoulder,elbow) or 3 (waist,shoulder,elbow)")
            else:
                print("Unknown command")
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        worker.stop()


if __name__ == "__main__":
    main()
