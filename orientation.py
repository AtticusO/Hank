## orientation.py — Hank's arm: poses, gestures, dance and keyboard control.
##
## `positions` owns one ServoWorker (the only thing that touches the servos)
## and exposes the same public methods as before (reset, curl, jab, wave,
## rotate_waist, ...). They no longer spin up an asyncio loop each: they set
## worker targets or queue a gesture and return.
##
##   python orientation.py                 keyboard jog (default)
##   python orientation.py --mode cli      type gesture names
##   python orientation.py --mode dance --bpm 120

import argparse
import logging
import select
import threading
import time

import config
import gestures
import servo_ops
from servo_worker import ServoWorker

log = logging.getLogger(__name__)


class positions:
    def __init__(self, servos=None, worker=None, factory=None):
        self.servos = servos or servo_ops.move(factory)
        self.worker = worker or ServoWorker(self.servos)
        self.dancing = threading.Event()
        self._dance_stop = threading.Event()

    ## Where the arm is headed (commanded targets). Replaces the old orient dict
    ## + pos_log list, two mirrors of the same state kept in sync by hand.
    @property
    def orient(self):
        return self.worker.get_targets()

    ## Where the arm actually is right now
    def angles(self):
        return self.worker.get_angles()

    ## True while a gesture or the dance owns the arm (tracking should back off)
    def busy(self):
        return self.worker.busy() or self.dancing.is_set()

    def stop(self):
        self.stop_dance()
        self.worker.stop()

    ## ------------------------------------------------------ direct targets
    def set_pose(self, pose):
        self.worker.set_targets(pose)

    def rotate_waist(self, deg):
        self.worker.nudge("waist", deg)

    def rotate_shoulder(self, deg):
        self.worker.nudge("shoulder", deg)

    def rotate_elbow(self, deg):
        self.worker.nudge("elbow", deg)

    rotate = rotate_waist

    ## elbow follows the shoulder a little further to keep the reach straight
    def reach(self, deg):
        extra = 10 if deg > 0 else -10 if deg < 0 else 0
        self.worker.nudge("shoulder", deg)
        self.worker.nudge("elbow", deg + extra)

    def go_limp(self):
        self.stop_dance()
        self.worker.go_limp()

    ## ------------------------------------------------------------ gestures
    ## wait=True blocks until the gesture finishes (the old behaviour);
    ## wait=False queues it and returns immediately (vision / PS5 loops).
    def gesture(self, name, wait=True):
        return self.worker.play_gesture(*gestures.get(name), wait=wait)

    def reset(self, wait=True):
        return self.gesture("reset", wait)

    def center(self, wait=True):
        return self.gesture("center", wait)

    def curl(self, wait=True):
        return self.gesture("curl", wait)

    def point(self, wait=True):
        return self.gesture("point", wait)

    def jab(self, wait=True):
        return self.gesture("jab", wait)

    def fist_bump(self, wait=True):
        return self.gesture("fist_bump", wait)

    def wave(self, wait=True):
        return self.gesture("wave", wait)

    def wave_two(self, wait=True):
        return self.gesture("wave_two", wait)

    def bounce_left(self, wait=True):
        return self.gesture("bounce_left", wait)

    def bounce_right(self, wait=True):
        return self.gesture("bounce_right", wait)

    ## One arc out to a side and back; amplitude scales with rate
    def bounce(self, rate, dir, wait=True):
        base = [self.orient[n] for n in config.JOINTS]
        sign = -1 if dir == "left" else 1
        out = [base[0] + sign * rate, base[1] + rate, base[2] - rate]
        log.debug("bounce %s rate=%s out=%s back=%s", dir, rate, out, base)
        return self.worker.play_gesture([out, base], [0.5, 0.3], wait=wait)

    ## --------------------------------------------------------------- dance
    ## Swings side to side, one swing per beat, locked to the beat: each beat
    ## arcs down through a dipped centre and up to the other side (a bounce),
    ## and the time the move didn't use is absorbed so the cycle never drifts.
    ## keep_going: cheap callable checked every beat (e.g. "is music playing").
    def dance(self, bpm, keep_going=None, amplitude=None):
        amplitude = config.DANCE_AMPLITUDE if amplitude is None else amplitude
        beat = 60.0 / max(40.0, min(200.0, float(bpm)))
        if beat < 0.45:                       # very fast songs: swing every 2nd beat
            beat *= 2
        keep_going = keep_going or (lambda: True)
        self._dance_stop.clear()
        self.dancing.set()
        log.info("Dancing at %.0f BPM (%.2fs per swing)", bpm, beat)
        dip = [0, 45, 45]                     # dance home pose
        try:
            self.worker.play_gesture([dip], [0.1], wait=True)
            side = 1
            next_beat = time.monotonic() + beat
            while keep_going() and not self._dance_stop.is_set():
                peak = [side * amplitude, 45 + amplitude // 2, 45 - amplitude // 2]
                self.worker.play_gesture([dip, peak], [0, 0],
                                         durations=[beat * 0.45, beat * 0.45], wait=True)
                side = -side
                delay = next_beat - time.monotonic()
                if delay > 0:
                    self._dance_stop.wait(delay)
                    next_beat += beat
                else:                         # fell behind: resync instead of rushing
                    next_beat = time.monotonic() + beat
        finally:
            self.dancing.clear()
        log.info("Dance stopped")
        self.reset()

    def stop_dance(self):
        self._dance_stop.set()

    ## --------------------------------------------------- keyboard control
    def find_keyboard(self):
        return KeyboardControl.find_keyboard()

    def listen_hold(self):
        KeyboardControl(self).run()

    ## Press-only controls: one big step per key press
    def listen_press(self):
        from evdev import categorize, ecodes   # Linux only — lazy so Windows can import this file
        dev = self.find_keyboard()
        log.info("Listening on %s (%s)", dev.path, dev.name)
        steps = {"KEY_UP": (self.reach, -30), "KEY_DOWN": (self.reach, 30),
                 "KEY_LEFT": (self.rotate, 30), "KEY_RIGHT": (self.rotate, -30)}
        for event in dev.read_loop():
            if event.type != ecodes.EV_KEY:
                continue
            key = categorize(event)
            if key.keystate != key.key_down:
                continue
            code = key.keycode
            if code in steps:
                fn, deg = steps[code]
                fn(deg)
            elif code == "KEY_R":
                self.reset()
            elif code == "KEY_C":
                self.curl()
            elif code == "KEY_ESC":
                break


class KeyboardControl:
    ## Hold-aware keyboard jog. step() is non-blocking so main.py can run it
    ## alongside other modes; run() loops it standalone.
    ## held keys: (joint, degrees per tick) — 20 ticks/sec
    HOLD_KEYS = {
        "KEY_LEFT": ("waist", -5), "KEY_RIGHT": ("waist", +5),
        "KEY_Z": ("waist", -5), "KEY_X": ("waist", +5),
        "KEY_UP": ("shoulder", -5), "KEY_DOWN": ("shoulder", +5),
        "KEY_A": ("shoulder", -5), "KEY_D": ("shoulder", +5),
        "KEY_W": ("elbow", -5), "KEY_E": ("elbow", +5),
    }
    ## fire once per key-down, not every tick while held
    PRESS_KEYS = {
        "KEY_R": "reset", "KEY_P": "point", "KEY_C": "curl", "KEY_J": "jab",
        "KEY_F": "fist_bump", "KEY_V": "wave", "KEY_B": "wave_two",
    }
    TICK = 0.05

    def __init__(self, arm, dev=None):
        from evdev import categorize, ecodes   # lazy: Linux only
        self._categorize, self._ecodes = categorize, ecodes
        self.arm = arm
        self.dev = dev or self.find_keyboard()
        self.held = set()
        self.quit = False
        log.info("Keyboard on %s (%s): arrows/ZX/AD/WE jog, R reset, P point, C curl, "
                 "J jab, F fist bump, V/B wave, L limp, Esc quit", self.dev.path, self.dev.name)

    @staticmethod
    def find_keyboard():
        try:
            from evdev import InputDevice, ecodes, list_devices
        except ImportError:
            raise RuntimeError("Keyboard mode needs evdev (Linux only)")
        for path in list_devices():
            dev = InputDevice(path)
            keys = dev.capabilities().get(ecodes.EV_KEY, [])
            if ecodes.KEY_A in keys and ecodes.KEY_UP in keys:
                return dev
        raise RuntimeError("No keyboard found in /dev/input (is your user in the 'input' group?)")

    def step(self, timeout=0.0):
        newly = set()
        r, _, _ = select.select([self.dev.fd], [], [], timeout)
        if r:
            for event in self.dev.read():
                if event.type != self._ecodes.EV_KEY:
                    continue
                key = self._categorize(event)
                codes = key.keycode if isinstance(key.keycode, list) else [key.keycode]
                for code in codes:
                    if key.keystate == key.key_down:
                        if code not in self.held:
                            newly.add(code)
                        self.held.add(code)
                    elif key.keystate == key.key_up:
                        self.held.discard(code)

        if "KEY_ESC" in self.held:
            self.quit = True
            return
        if "KEY_L" in newly:
            self.arm.go_limp()
        for code in newly:
            if code in self.PRESS_KEYS:
                log.debug("%s -> %s", code, self.PRESS_KEYS[code])
                self.arm.gesture(self.PRESS_KEYS[code], wait=False)
        if self.arm.busy():                   # a gesture owns the arm right now
            return
        for code in self.held:
            if code in self.HOLD_KEYS:
                joint, deg = self.HOLD_KEYS[code]
                self.arm.worker.nudge(joint, deg)
                log.debug("%s -> %s %+d", code, joint, deg)

    def run(self):
        while not self.quit:
            self.step(timeout=self.TICK)


def _cli(arm):
    aliases = {"cu": "curl", "fb": "fist_bump", "b": "fist_bump", "r": "reset", "w": "wave",
               "p": "point", "pt": "point", "j": "jab", "br": "bounce_right", "bl": "bounce_left"}
    print("Gestures: " + ", ".join(sorted(gestures.GESTURES)) + " (q quits)")
    while True:
        x = input("Enter Orientation >>> ").strip().lower()
        x = aliases.get(x, x)
        if x in ("q", "quit", "exit"):
            break
        if x in gestures.GESTURES:
            arm.gesture(x)
        elif x == "waist":
            arm.rotate_waist(10)
            time.sleep(0.5)
            arm.rotate_waist(-10)
        else:
            print("Unknown gesture")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Hank arm control")
    ap.add_argument("--mode", choices=["keys", "cli", "dance"], default="keys")
    ap.add_argument("--bpm", type=float, help="tempo for --mode dance (prompts if omitted)")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    config.setup_logging(args.verbose)

    p = positions()
    log.info("$$$ Hank Orientation System (%s mode) $$$", args.mode)
    try:
        if args.mode == "keys":
            p.reset()
            p.listen_hold()
        elif args.mode == "cli":
            _cli(p)
        else:
            bpm = args.bpm or float(input("Enter BPM >>> "))
            p.dance(bpm)
    except KeyboardInterrupt:
        pass
    finally:
        p.stop()
