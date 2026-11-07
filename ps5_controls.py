## ps5_controls.py — drive Hank with a DualSense controller.
##
##   L2 / R2 (analog)      waist left / right, speed follows how hard you press
##   left stick up/down    shoulder
##   right stick up/down   elbow
##   D-pad up/down         jog speed + / -
##   Cross                 reset          Square    jab
##   Triangle              point          Circle    curl
##   Options               start the music server (once)
##   Create (share)        go limp
##   L1 + R1 held 1 s      curl and quit
##
## Nothing runs at import time: Bluetooth pairing and pydualsense.init() happen
## in Controller(), so importing this module never crashes (laptop, no controller).

import logging
import os
import platform
import subprocess
import time

import config

log = logging.getLogger(__name__)

STICK_DEAD = 25        # stick deadband (sticks read -128..127)
TRIGGER_DEAD = 30      # trigger deadband (L2_value / R2_value read 0..255)
QUIT_HOLD_S = 1.0


def _deflection(value, dead, full):
    ## 0..1 past the deadband, so speed follows how far the stick/trigger is pushed
    mag = abs(value)
    if mag <= dead:
        return 0.0
    return min(1.0, (mag - dead) / float(full - dead))


class Controller:
    TICK = 0.02        # 50 Hz polling (the old loop spun with no sleep at 100% CPU)

    def __init__(self, arm, ps5=None, connect_bt=True):
        self.arm = arm
        if ps5 is None:
            if connect_bt and platform.system() == "Linux":
                try:
                    subprocess.run(["bash", os.path.join(config.DIR, "bt_connect.sh")],
                                   timeout=30, check=False)
                except Exception as e:
                    log.warning("bt_connect.sh failed: %s", e)
            from pydualsense import pydualsense
            ps5 = pydualsense()
            ps5.init()
            try:
                ps5.light.setColorI(0, 255, 0)
            except Exception:
                pass
            log.info("Connected to PS5 controller")
        self.ps5 = ps5
        self.rate = 5           # degrees per tick at full deflection
        self.cancel = False
        self.server = None
        self._prev = {}
        self._quit_since = None

    def _buttons(self, s):
        return {"cross": s.cross, "circle": s.circle, "square": s.square, "triangle": s.triangle,
                "up": s.DpadUp, "down": s.DpadDown, "options": s.options, "share": s.share,
                "L1": s.L1, "R1": s.R1}

    ## One polling step. Call it in a loop (run() does) — or from main.py's mode loop.
    def remote(self):
        s = self.ps5.state
        now = self._buttons(s)
        pressed = {k for k, v in now.items() if v and not self._prev.get(k)}   # edges only
        self._prev = now

        ## L1 + R1 held for QUIT_HOLD_S -> curl and quit
        if now["L1"] and now["R1"]:
            if self._quit_since is None:
                self._quit_since = time.monotonic()
            elif time.monotonic() - self._quit_since >= QUIT_HOLD_S:
                log.info("L1+R1 held: curling and quitting")
                self.arm.curl()
                self.cancel = True
                return
        else:
            self._quit_since = None

        if "up" in pressed:
            self.rate = min(20, self.rate + 1)
            log.info("Rate: %s", self.rate)
        if "down" in pressed:
            self.rate = max(1, self.rate - 1)
            log.info("Rate: %s", self.rate)
        if "options" in pressed:
            self.start_server()
        if "share" in pressed:
            self.arm.go_limp()

        gestures = {"cross": "reset", "square": "jab", "triangle": "point", "circle": "curl"}
        for button, name in gestures.items():
            if button in pressed:
                log.debug("%s -> %s", button, name)
                self.arm.gesture(name, wait=False)

        if self.arm.busy():
            return
        w = self.arm.worker
        ## waist on the analog triggers (state.L2 is True for ANY touch, so use the value)
        waist = (_deflection(s.L2_value, TRIGGER_DEAD, 255)
                 - _deflection(s.R2_value, TRIGGER_DEAD, 255))
        if waist:
            w.nudge("waist", self.rate * waist)
        ## shoulder on the left stick's Y axis (stick up = forward), elbow on the right Y
        ly, ry = s.LY, s.RY
        if abs(ly) > STICK_DEAD:
            w.nudge("shoulder", self.rate * _deflection(ly, STICK_DEAD, 128) * (1 if ly > 0 else -1))
        if abs(ry) > STICK_DEAD:
            w.nudge("elbow", self.rate * _deflection(ry, STICK_DEAD, 128) * (1 if ry > 0 else -1))

    def run(self):
        while not self.cancel:
            self.remote()
            time.sleep(self.TICK)

    ## Music server on a daemon thread (the old asyncio.run(self.start_server)
    ## raised, and even fixed it would have blocked the controls forever)
    def start_server(self):
        if self.server is None:
            import server
            self.server = server.start_server(background=True)
        else:
            log.info("Music server already running")

    def close(self):
        try:
            self.ps5.close()
        except Exception:
            pass


if __name__ == "__main__":
    import orientation
    config.setup_logging()
    pos = orientation.positions()
    c = Controller(pos)
    try:
        c.run()
    except KeyboardInterrupt:
        pass
    finally:
        c.close()
        pos.stop()
