## servo_worker.py — the single owner of the servo hardware (fixes.md §3.3).
##
## One background thread runs a 100 Hz loop that glides every joint toward its
## latest target with a speed- and acceleration-limited profile (soft start,
## soft stop). Everyone else — vision tracking, keyboard, PS5, dance — only
## calls the thread-safe API below, which returns immediately:
##
##   set_target(name, deg) / set_targets({...}) / nudge(name, delta)
##       latest-wins targets; the arm glides there continuously
##   play_gesture(poses, holds, speed=, durations=, wait=)
##       scripted waypoints with cosine easing; tracking targets are ignored
##       while a gesture plays, then the final pose becomes the new target
##   go_limp(), busy(), wait_idle(), stop()

import logging
import math
import queue
import threading
import time

import config

log = logging.getLogger(__name__)


class _Gesture:
    def __init__(self, poses, holds, speed, durations):
        self.poses = poses
        self.holds = holds
        self.speed = speed
        self.durations = durations
        self.done = threading.Event()


class ServoWorker:
    def __init__(self, servos, start=True):
        self.servos = servos                       # servo_ops.move() or the mock
        self.lock = threading.Lock()
        self.targets = {n: float(servos.angles[n]) for n in config.JOINTS}
        self.vel = {n: 0.0 for n in config.JOINTS}
        self.gesture_active = threading.Event()
        self._jobs = queue.Queue()
        self._pending = 0                          # queued + playing gestures
        self._running = threading.Event()
        self._interrupt = threading.Event()
        self._last_motion = time.monotonic()
        self._auto_detached = False
        self._thread = threading.Thread(target=self._run, name="ServoWorker", daemon=True)
        if start:
            self.start()

    ## ------------------------------------------------ thread-safe public API
    def start(self):
        if not self._thread.is_alive():
            self._running.set()
            self._thread.start()

    def set_target(self, name, deg):
        with self.lock:
            self.targets[name] = config.clamp(name, float(deg))

    def set_targets(self, pose):
        ## pose: {"waist": deg, ...} or [waist, shoulder, elbow]; None = leave as is
        if not isinstance(pose, dict):
            pose = dict(zip(config.JOINTS, pose))
        with self.lock:
            for name, deg in pose.items():
                if deg is not None:
                    self.targets[name] = config.clamp(name, float(deg))

    def nudge(self, name, delta):
        with self.lock:                            # read-modify-write under the lock
            self.targets[name] = config.clamp(name, self.targets[name] + delta)
            return self.targets[name]

    def get_targets(self):
        with self.lock:
            return dict(self.targets)

    def get_angles(self):
        return {n: self.servos.angles[n] for n in config.JOINTS}

    def play_gesture(self, poses, holds=None, speed=None, durations=None, wait=True):
        ## poses: list of [waist, shoulder, elbow]; None in a slot = hold that joint
        ## holds: seconds to pause after reaching each pose
        ## speed: deg/sec used to time each move (default config.GESTURE_SPEED)
        ## durations: explicit seconds per move (overrides speed) — used by dance
        job = _Gesture([list(p) for p in poses],
                       list(holds) if holds else [0.0] * len(poses),
                       speed or config.GESTURE_SPEED,
                       list(durations) if durations else None)
        with self.lock:
            self._pending += 1
        self._jobs.put(job)
        if wait:
            job.done.wait()
        return job.done

    def busy(self):
        with self.lock:
            return self._pending > 0

    def wait_idle(self, timeout=None, tol=0.5):
        ## Blocks until no gesture is queued/playing and every joint reached its target
        end = None if timeout is None else time.monotonic() + timeout
        while True:
            if not self.busy():
                tg, an = self.get_targets(), self.get_angles()
                if all(abs(tg[n] - an[n]) <= tol for n in config.JOINTS):
                    return True
            if end is not None and time.monotonic() > end:
                return False
            time.sleep(config.WORKER_TICK)

    def cancel_gestures(self):
        while True:
            try:
                job = self._jobs.get_nowait()
            except queue.Empty:
                break
            with self.lock:
                self._pending -= 1
            job.done.set()
        self._interrupt.set()

    def go_limp(self):
        ## Stop fighting: cut pulses to every joint. The next command re-attaches.
        self.cancel_gestures()
        with self.lock:
            for n in config.JOINTS:
                self.targets[n] = self.servos.angles[n]
                self.vel[n] = 0.0
        self.servos.detach_all()
        log.info("Servos limp")

    def stop(self):
        self.cancel_gestures()
        self._running.clear()
        if self._thread.is_alive() and threading.current_thread() is not self._thread:
            self._thread.join(timeout=1)

    ## ----------------------------------------------------- worker internals
    def _run(self):
        tick = config.WORKER_TICK
        next_t = time.monotonic()
        while self._running.is_set():
            try:
                job = self._jobs.get_nowait()
            except queue.Empty:
                job = None
            if job is not None:
                self._play(job)
                next_t = time.monotonic()
                continue
            self._glide_step(tick)
            next_t += tick
            delay = next_t - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            else:                                   # fell behind (busy Pi): don't spiral
                next_t = time.monotonic()

    def _write(self, name, deg):
        if abs(deg - self.servos.angles[name]) > 1e-3:
            self.servos.set_angle(name, deg)
            self._last_motion = time.monotonic()
            self._auto_detached = False

    def _glide_step(self, dt):
        with self.lock:
            tgts = dict(self.targets)
        for name, tgt in tgts.items():
            cur = self.servos.angles[name]
            err = tgt - cur
            v = self.vel[name]
            if abs(err) < 0.05 and abs(v) < 1.0:
                self.vel[name] = 0.0
                if err != 0:
                    self._write(name, tgt)
                continue
            vmax = config.JOINT_SPEED[name]
            acc = config.JOINT_ACCEL[name]
            ## fastest speed that can still stop at the target -> soft landing
            v_stop = math.sqrt(2.0 * acc * abs(err))
            v_des = math.copysign(min(vmax, v_stop), err)
            dv = max(-acc * dt, min(acc * dt, v_des - v))   # soft start
            v += dv
            new = cur + v * dt
            if (tgt - new) * err <= 0:                      # would overshoot: land
                new, v = tgt, 0.0
            self.vel[name] = v
            self._write(name, new)
        self._maybe_auto_detach()

    def _maybe_auto_detach(self):
        if config.AUTO_DETACH_S is None or self._auto_detached:
            return
        if time.monotonic() - self._last_motion > config.AUTO_DETACH_S:
            for name in config.AUTO_DETACH_JOINTS:
                self.servos.detach(name)
            self._auto_detached = True
            log.debug("Auto-detached %s after %ss idle", config.AUTO_DETACH_JOINTS, config.AUTO_DETACH_S)

    def _play(self, job):
        self.gesture_active.set()
        self._interrupt.clear()
        tick = config.WORKER_TICK
        try:
            for i, pose in enumerate(job.poses):
                start = self.get_angles()
                end = {}
                for name, deg in zip(config.JOINTS, pose):
                    end[name] = start[name] if deg is None else config.clamp(name, float(deg))
                travel = max(abs(end[n] - start[n]) for n in config.JOINTS)
                if job.durations is not None:
                    T = max(tick, job.durations[i])
                else:
                    T = max(config.GESTURE_MIN_MOVE, travel / job.speed)
                t0 = time.monotonic()
                while True:
                    if self._interrupt.is_set() or not self._running.is_set():
                        return
                    t = time.monotonic() - t0
                    s = 1.0 if t >= T else (1 - math.cos(math.pi * t / T)) / 2   # ease in-out
                    for n in config.JOINTS:
                        self._write(n, start[n] + (end[n] - start[n]) * s)
                    if t >= T:
                        break
                    time.sleep(tick)
                hold_end = time.monotonic() + (job.holds[i] if i < len(job.holds) and job.holds[i] else 0)
                while time.monotonic() < hold_end:
                    if self._interrupt.is_set() or not self._running.is_set():
                        return
                    time.sleep(tick)
        finally:
            ## final pose becomes the target so the arm doesn't glide back to a stale one
            with self.lock:
                for n in config.JOINTS:
                    self.targets[n] = self.servos.angles[n]
                    self.vel[n] = 0.0
                self._pending -= 1
            self.gesture_active.clear()
            job.done.set()
