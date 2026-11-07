## personality.py — what Hank does with what he sees.
##
## follow() locks onto ONE target (a person, or a cup when nobody is around),
## converts its pixel position into an absolute bearing in arm angles, and
## aims a little ahead of where it is moving (lead) with proportional control.
## It only *sets targets* on the ServoWorker, so it takes microseconds and never
## blocks the vision loop (fixes.md §4.2.1).

import logging
import random
import time

import config
import gestures

log = logging.getLogger(__name__)


## ------------------------------------------------------------ pure helpers
## (no hardware, no state — unit tested in tests/test_hank.py)

def px_to_deg(px, frame_px, fov_deg):
    ## pixel -> degrees off the image centre (positive = right / down)
    return (px - frame_px / 2.0) * (fov_deg / frame_px)


def bearing(x_px, waist_at_capture, frame_w=config.FRAME_W, fov_x=config.FOV_X_DEG,
            camera_on_arm=config.CAMERA_ON_ARM):
    ## Absolute waist angle that would put x_px dead centre. Person right of
    ## centre -> lower waist angle (same sign convention as the old ±10 code).
    ## Working in bearings instead of pixels removes the arm's own motion from
    ## the velocity estimate when the camera turns with the waist.
    base = waist_at_capture if camera_on_arm else 0.0
    return base - px_to_deg(x_px, frame_w, fov_x)


def waist_correction(target_bearing, bearing_vel, current_waist,
                     latency_s=config.TRACK_LATENCY_S, kp=config.TRACK_KP,
                     dead_deg=config.TRACK_DEAD_DEG):
    ## Proportional control with velocity lead: aim where they WILL be.
    predicted = target_bearing + bearing_vel * latency_s
    err = predicted - current_waist
    if abs(err) < dead_deg:
        return current_waist                      # close enough — hold
    return current_waist + kp * err


def pitch_correction(y_px, kp=config.TRACK_KP, frame_h=config.FRAME_H,
                     fov_y=config.FOV_Y_DEG, dead_deg=config.TRACK_DEAD_DEG * 2):
    ## Degrees to add to shoulder AND elbow: target above centre -> positive
    ## (the old code raised both by 10 when y < 150). Centre comes from the
    ## frame size, not the old off-centre 150–300 band.
    off = px_to_deg(y_px, frame_h, fov_y)
    if abs(off) < dead_deg:
        return 0.0
    return -kp * off


def _num(v):
    return float(v.item() if hasattr(v, "item") else v)


def box_center(box):
    return (_num(box[0]) + _num(box[2])) / 2.0, (_num(box[1]) + _num(box[3])) / 2.0


def box_area(box):
    return abs(_num(box[2]) - _num(box[0])) * abs(_num(box[3]) - _num(box[1]))


class acts:
    ## arm is the shared orientation.positions() instance owned by main.Hank —
    ## acts must never create its own camera, model, or servo objects
    def __init__(self, arm):
        self.turn = arm
        self.person_time = 0.0
        self.tracked = []            # (t, bearing) history of the locked target
        self.lock_id = None
        self.lock_tag = None
        self.lost = 0
        self.smooth = None           # EMA of the bearing
        self.last_lean = 0.0

    ## Current commanded pose (was a stale dict reference before)
    @property
    def positions(self):
        return self.turn.orient

    ## ------------------------------------------------------------ greetings
    def greetings(self):
        name = random.choice(gestures.GREETINGS)
        log.info("Greeting: %s", name)
        self.turn.gesture(name, wait=False)       # non-blocking: vision keeps running

    ## Waves when a person shows up after not seeing anyone for GREETING_GAP_S
    def check_greeting(self, tags):
        if "person" in tags:
            if (time.time() - self.person_time) > config.GREETING_GAP_S and not self.turn.busy():
                self.greetings()
            self.person_time = time.time()

    ## ------------------------------------------------------------- tracking
    def _pick(self, tags, cords, ids):
        ## Returns (tag, box) of the one target to follow, or None.
        ## People first; a cup only when nobody is in frame (bartender job).
        want = "person" if "person" in tags else ("cup" if "cup" in tags else None)
        if want is None:
            return None
        ids = list(ids) if ids is not None else [None] * len(tags)
        cands = [(i, b) for t, b, i in zip(tags, cords, ids) if t == want]
        if want != self.lock_tag:                 # class changed (cup -> person): re-acquire
            self.lock_id = None
        if self.lock_id is not None:
            for i, b in cands:
                if i is not None and int(_num(i)) == self.lock_id:
                    self.lost = 0
                    return want, b
            self.lost += 1
            if self.lost <= config.TRACK_LOST_FRAMES:
                return None                       # briefly hidden: hold, don't jump to someone else
        ## acquire the largest (= usually nearest) box
        i, b = max(cands, key=lambda c: box_area(c[1]))
        new_id = int(_num(i)) if i is not None else None
        if new_id != self.lock_id or want != self.lock_tag:
            log.info("Tracking %s%s", want, f" #{new_id}" if new_id is not None else "")
            self.tracked.clear()
            self.smooth = None
        self.lock_id, self.lock_tag, self.lost = new_id, want, 0
        return want, b

    def follow(self, tags, cords, ids=None, pose=None, capture_t=None):
        ## pose: arm angles when the frame was captured (default: right now)
        self.check_greeting(tags)
        if self.turn.busy():                      # gesture/dance owns the arm
            return
        pick = self._pick(tags, cords, ids)
        if pick is None:
            if not tags:
                self.tracked.clear()              # nothing in frame: don't pollute history
            return
        _, box = pick
        x, y = box_center(box)
        pose = pose or self.turn.angles()
        now = time.monotonic()

        b = bearing(x, pose["waist"])
        self.smooth = b if self.smooth is None else \
            (1 - config.TRACK_EMA) * self.smooth + config.TRACK_EMA * b
        self.tracked.append((now, self.smooth))
        if len(self.tracked) > 5:
            self.tracked.pop(0)

        vel = 0.0                                  # deg/sec, signed
        if len(self.tracked) >= 2:
            (t0, b0), (t1, b1) = self.tracked[0], self.tracked[-1]
            if t1 > t0:
                vel = max(-90.0, min(90.0, (b1 - b0) / (t1 - t0)))   # cap detector noise

        targets = {"waist": waist_correction(self.smooth, vel, pose["waist"])}
        if config.TRACK_PITCH:
            d = pitch_correction(y)
            if d:
                base = pose if config.CAMERA_ON_ARM else config.HOME
                targets["shoulder"] = base["shoulder"] + d
                targets["elbow"] = base["elbow"] + d
        self.turn.set_pose(targets)
        if capture_t is not None:
            log.debug("track x=%.0f bearing=%.1f vel=%.1f -> %s | latency %.0f ms",
                      x, self.smooth, vel, {k: round(v, 1) for k, v in targets.items()},
                      (time.monotonic() - capture_t) * 1000)

    ## Old API kept: relative move of the given joints
    def move(self, servos, deg_change):
        for name in servos:
            self.turn.worker.nudge(name, deg_change)

    ## Per-frame reactions besides tracking: greet, lean in when something is close
    def pers_condit(self, tags, cords, distance):
        self.check_greeting(tags)
        if distance is None or distance >= config.LEAN_DISTANCE_CM or self.turn.busy():
            return
        if time.monotonic() - self.last_lean < config.LEAN_COOLDOWN_S:
            return
        ## lean up a little, more the closer it is, then settle back. The old code
        ## added this every frame while something was close, so it ran to the limit.
        p = self.positions
        if -80 <= p["shoulder"] <= 80 and -80 <= p["elbow"] <= 80:
            d = int(config.LEAN_DISTANCE_CM - distance)
            self.last_lean = time.monotonic()
            log.info("Leaning %d° (object at %.1f cm)", d, distance)
            self.turn.worker.play_gesture(
                [[None, p["shoulder"] + d, p["elbow"] + d], [None, p["shoulder"], p["elbow"]]],
                [0.5, 0.0], wait=False)

    ## Average x/y-position (pixel) of all boxes matching target_tag, None if absent
    def avg_x(self, tags, cords, target_tag):
        xs = [box_center(box)[0] for tag, box in zip(tags, cords) if tag == target_tag]
        return sum(xs) / len(xs) if xs else None

    def avg_y(self, tags, cords, target_tag):
        ys = [box_center(box)[1] for tag, box in zip(tags, cords) if tag == target_tag]
        return sum(ys) / len(ys) if ys else None
