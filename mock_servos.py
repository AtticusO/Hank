## mock_servos.py — stand-in for servo_ops.move with the same API, so the whole
## stack runs on a laptop (or on the Pi without moving anything): HANK_MOCK=1.
## servo_ops swaps this class in automatically; nothing imports it directly.

import asyncio
import logging
import time

import config

log = logging.getLogger("mock_servos")

HOME = dict(config.HOME)
PINS = dict(config.SERVO_PINS)   # kept for API parity


class move:
    def __init__(self, factory=None):
        log.info("### HANK INITIALIZING (MOCK SERVOS) ###")
        self.factory = factory
        self.angles = {n: float(d) for n, d in config.HOME.items()}
        self.attached = {n: True for n in config.JOINTS}
        self.writes = 0              # handy for tests
        self._last_report = 0.0

    def set_angle(self, name, deg):
        target = config.clamp(name, float(deg))
        self.angles[name] = target
        self.attached[name] = True
        self.writes += 1
        ## The worker calls this ~100x/sec; report at most 4x/sec at DEBUG
        now = time.monotonic()
        if now - self._last_report > 0.25:
            self._last_report = now
            log.debug("[mock] %s", self.pose_str())
        return target

    def detach(self, name):
        self.attached[name] = False
        log.info("[mock] %s limp", name)

    def detach_all(self):
        for name in config.JOINTS:
            self.detach(name)

    def pose_str(self):
        return "  ".join(f"{n}={self.angles[n]:6.1f}" for n in config.JOINTS)

    async def move_to(self, name, deg, step=1):
        if not isinstance(deg, (int, float)):
            log.warning("%s: angle must be a number, got %r", name, deg)
            return
        target = config.clamp(name, deg)
        delta = abs(target - self.angles[name])
        await asyncio.sleep(delta / 250)             # ≈ real sweep speed
        self.set_angle(name, target)
        log.info("[mock] %-8s -> %6.1f   %s", name, target, self.pose_str())

    async def move_waist(self, deg, step=1):
        await self.move_to("waist", deg, step)

    async def move_shoulder(self, deg, step=1):
        await self.move_to("shoulder", deg, step)

    async def move_elbow(self, deg, step=1):
        await self.move_to("elbow", deg, step)
