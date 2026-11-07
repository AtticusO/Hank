## gestures.py — every scripted arm movement as data (fixes.md §8).
##
## Each entry: (poses, holds, speed)
##   poses  list of [waist, shoulder, elbow]; None = keep that joint where it is
##   holds  seconds to pause after reaching each pose
##   speed  deg/sec used to time the moves (servo_worker eases each one)
## Played by servo_worker.ServoWorker.play_gesture(*gestures.get(name)).

HOME_POSE = [0, 70, 50]

GESTURES = {
    "reset":     ([HOME_POSE], [0.5], 250),
    "center":    ([[0, 45, 45]], [0.1], 250),          # was [45, 45, 45]: faced 45° sideways
    "curl":      ([[0, 0, 90]], [0.4], 250),
    "point":     ([[0, 0, -90]], [0.2], 250),
    "jab":       ([HOME_POSE, [0, -40, -80], HOME_POSE], [0.2, 0.1, 0.1], 500),
    "fist_bump": ([HOME_POSE, [0, 20, -10], HOME_POSE], [0.5, 1.0, 0.5], 250),
    "wave": ([[0, 70, None], HOME_POSE, [0, 70, -30], HOME_POSE, [0, 70, -30], HOME_POSE],
             [0.4, 0.01, 0.2, 0.01, 0.2, 0.5], 250),
    ## Arm up, then wiggle the waist. The old version captured shoulder/elbow
    ## *before* raising the arm, so it dropped the arm again on the second waypoint.
    "wave_two": ([[0, 70, -90], [20, None, None], [0, None, None], [-20, None, None], HOME_POSE],
                 [0.4, 0.01, 0.2, 0.01, 0.5], 250),
    "bounce_left":  ([[-30, 30, 10], [-70, 70, 50], [-30, 30, 10], HOME_POSE], [0.2, 0.01, 0.2, 0.2], 250),
    "bounce_right": ([[30, 30, 10], [70, 70, 50], [30, 30, 10], HOME_POSE], [0.2, 0.01, 0.2, 0.2], 250),
}

## Greetings personality picks from (wave_one was a character-identical copy of wave)
GREETINGS = ("wave", "wave_two")


def get(name):
    poses, holds, speed = GESTURES[name]
    return [list(p) for p in poses], list(holds), speed
