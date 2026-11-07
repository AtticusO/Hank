## config.py — one home for every constant Hank uses (fixes.md §7.4).
## Real hardware and the mock both import this file, so values tuned on a laptop
## carry straight over to the Pi.

import logging
import os

## ---------------------------------------------------------------- servos ---
JOINTS = ("waist", "shoulder", "elbow")

## GPIO pin for each servo
SERVO_PINS = {"waist": 27, "shoulder": 17, "elbow": 18}

## Home pose (reset)
HOME = {"waist": 0, "shoulder": 70, "elbow": 50}

## Per-joint software limits in degrees. These are still the old blanket ±90 on
## purpose: the real mechanical limits have to be measured on the arm (jog each
## joint slowly with `python orientation.py` and note where it hits something).
## Example once measured: {"waist": (-90, 90), "shoulder": (-45, 90), "elbow": (-80, 90)}
LIMITS = {"waist": (-90, 90), "shoulder": (-90, 90), "elbow": (-90, 90)}

## Servo pulse widths in seconds. These are gpiozero's defaults (1–2 ms), i.e.
## exactly what the code used before. Most hobby servos really span ~0.5–2.5 ms,
## so ±90 here only covers about half their travel — but switching blindly can
## drive a joint into its mechanical stop. Calibrate one joint at a time with
## `python calibrate_servo.py <joint>` and put the results here.
PULSE_WIDTHS = {
    "waist": (1.0 / 1000, 2.0 / 1000),
    "shoulder": (1.0 / 1000, 2.0 / 1000),
    "elbow": (1.0 / 1000, 2.0 / 1000),
}

## ServoWorker (servo_worker.py) motion profile
WORKER_TICK = 0.01                                           # seconds (100 Hz)
JOINT_SPEED = {"waist": 120, "shoulder": 100, "elbow": 140}  # max deg/sec while tracking/jogging
JOINT_ACCEL = {"waist": 600, "shoulder": 500, "elbow": 700}  # deg/sec^2 (soft start/stop)
GESTURE_SPEED = 250       # deg/sec used to time gesture waypoints (≈ the old 5°/20 ms sweep)
GESTURE_MIN_MOVE = 0.08   # seconds; shortest time any gesture waypoint takes
## Go limp after this many idle seconds (stops buzz/heat). None = never.
## Shoulder/elbow can sag under gravity when limp, so only the waist is listed.
AUTO_DETACH_S = None
AUTO_DETACH_JOINTS = ("waist",)

## ---------------------------------------------------------------- camera ---
FRAME_W, FRAME_H = 640, 480
## Horizontal / vertical field of view in degrees.
## Camera Module 3 (imx708, which config.txt loads) ≈ 66 × 41; Camera Module v2 ≈ 62.2 × 48.8
FOV_X_DEG, FOV_Y_DEG = 66.0, 41.0
## True = the camera rides on the arm and turns with the waist (eye-in-hand),
## which is what the original ±10° stepping logic assumed. If the camera is
## fixed to the base instead, set False and tracking aims at the absolute angle.
CAMERA_ON_ARM = True

## ------------------------------------------------------------- detection ---
YOLO_PT = "yolov8n.pt"
YOLO_NCNN_DIR = "yolov8n_ncnn_model"     # used when it exists and matches INFER_SIZE
INFER_SIZE = 320
DETECT_CONF = 0.5
DETECT_CLASSES = [0, 41]                 # COCO: 0 = person, 41 = cup

## -------------------------------------------------------------- tracking ---
TRACK_KP = 0.8            # proportional gain (<1 converges without overshoot)
TRACK_LATENCY_S = 0.35    # lead time; measure it (see personality.py debug log) and tune
TRACK_DEAD_DEG = 2.0      # hold still when the target is within this many degrees
TRACK_EMA = 0.4           # weight of the newest sample in the position smoothing
TRACK_LOST_FRAMES = 15    # frames a locked target may vanish before re-acquiring
TRACK_PITCH = True        # also follow vertically with shoulder + elbow
GREETING_GAP_S = 30       # wave when a person appears after this long with nobody

## -------------------------------------------------------- distance sensor ---
DIST_TRIGGER, DIST_ECHO = 23, 24
DIST_MAX_M = 2.0
LEAN_DISTANCE_CM = 15     # lean in when something is closer than this
LEAN_COOLDOWN_S = 2.0

## ------------------------------------------------------------ mode buttons ---
BUTTON_MODE_PIN = 5       # cycles modes
BUTTON_SELECT_PIN = 6     # long press = reset arm
STATUS_LED_PIN = 22       # blink count = current mode

## --------------------------------------------------------------- music ---
SERVER_PORT = 8080
## Spotify redirect URI. Kept on 8080 because that is what your Spotify app
## dashboard is registered with — see FIXES_LOG.md before changing it.
SPOTIFY_REDIRECT_URI = "http://127.0.0.1:8080/callback"
## Preferred Spotify Connect device (raspotify's LIBRESPOT_NAME). None = first available.
SPOTIFY_DEVICE_NAME = os.environ.get("HANK_SPOTIFY_DEVICE", "Hank")
QUEUE_POLL_S = 3          # how often the queue advancer checks playback
DANCE_POLL_S = 5          # how often the dance watcher checks the song
DANCE_AMPLITUDE = 25      # degrees of waist swing per beat

## ------------------------------------------------------------- runtime ---
MOCK = os.environ.get("HANK_MOCK") == "1"
DIR = os.path.dirname(os.path.abspath(__file__))


def setup_logging(verbose=False):
    ## Replaces the old print() spam: real events at INFO, per-tick noise at DEBUG.
    ## Under systemd this all lands in `journalctl -u hank -f`.
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    ## --verbose is for Hank's own debug lines; keep chatty libraries at INFO+
    for noisy in ("picamera2", "urllib3", "PIL", "matplotlib", "asyncio", "spotipy"):
        logging.getLogger(noisy).setLevel(logging.INFO if noisy != "urllib3" else logging.WARNING)


def clamp(name, deg):
    lo, hi = LIMITS[name]
    return max(lo, min(hi, deg))
