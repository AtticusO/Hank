# Hank — Fixes & Improvement Plan

A full pass over every file in the repo (2026-08-31). No code has been changed — this document is the plan.
Each item says **what is wrong, why, and how to fix it**, with code sketches you can adapt.

Priorities: **P0** = crashes / feature completely broken · **P1** = core feature doesn't do its job ·
**P2** = quality / robustness · **P3** = nice-to-have.

---

## 0. Issues at a glance

| # | Where | Problem | Priority |
|---|-------|---------|----------|
| 1 | `personality.py:38-40` | `follow()` leading loop → IndexError on first call, infinite loop after | **P0** |
| 2 | `personality.py:31` | Appends `[None, None]` to track history when no person in frame | **P0** |
| 3 | `main.py:1-8` | Import-time side effects (`server` opens a socket, `music` reads secrets.json) crash main offline | **P0** |
| 4 | `ps5_controls.py:72-73,141-142` | `asyncio.run(self.start_server)` raises; `start_server` missing `self`; L1+R1 double-bound | **P0** |
| 5 | `music.py:138` | `play(search(...))` passes a list where a URI string is expected | **P0** |
| 6 | `orientation.py:99-105` | `dance()` bounces **once** — no loop, no beat timing, amplitude derived from BPM | **P1** |
| 7 | `music.py:125` | `sp.audio_features()` is deprecated by Spotify → 403 for new apps; BPM source is dead | **P1** |
| 8 | Vision → servo pipeline | Tracking falls behind: blocking servo moves inside the vision loop + slow .pt model + no lead/proportional control | **P1** |
| 9 | `mock_servos.py` | Stub with no API parity; can't develop off the Pi (evdev/picamera2 imports also break Windows) | **P1** |
| 10 | `servo_ops.py:27-49` | Motion not smooth: 5° quantization, no easing, per-call `asyncio.run`, default 1–2 ms pulse range | **P1** |
| 11 | `server.py` | No song queue (README TODO 2); handler only catches `MusicError` | **P1** |
| 12 | `personality.py:44-46` | Leading correction moves the waist the **wrong direction** (sign flipped) | **P1** |
| 13 | `ps5_controls.py:81-98` | `L2/R2` are analog (0–255) compared to `True`; shoulder reads stick **X** for both directions | **P1** |
| 14 | `startup.sh:3-4` | `enable` doesn't start raspotify; bare `pigpiod` errors if already running; nothing launches Hank | **P2** |
| 15 | `main.py:52-66` | Mode numbers disagree with comments; hardcoded `setting`; no buttons (README TODO 9) | **P2** |
| 16 | `orientation.py:166-198` | `wave()` and `wave_one()` are identical duplicates; gesture code heavily copy-pasted | **P2** |
| 17 | `orientation.py:386` | `__main__` hardcodes `settings = 2` (BPM prompt), contradicting the README's "arrow keys" claim | **P2** |
| 18 | `obj_detection.py:5` | Runs the slow `.pt` model; the committed ncnn export is 640px while inference runs 320px (why it was shelved) | **P2** |
| 19 | `music.py:14` vs `readme.md:14-15` | README says env vars, code requires `secrets.json` — pick one, fall back to the other | **P2** |
| 20 | `distance.py` | Unintegrated (README TODO 6); prints every read; no pigpio timing; likely a hardware/wiring issue too | **P2** |
| 21 | `orientation.py:337-345` | Held R/P/C keys re-fire reset/point/curl ~20×/sec | **P2** |
| 22 | `requirements.txt` | Missing `pydualsense`; nothing pinned | **P2** |
| 23 | Repo hygiene | Tracked `.pyc` in `yolov8n_ncnn_model/__pycache__/`, `desktop.ini`, `.FCBak` backups | **P3** |
| 24 | Everywhere | `print()` everywhere, no logging levels; magic numbers (deadbands, pins) scattered | **P3** |
| 25 | `orientation.py:164` | `center()` sets waist to 45° — a "center" pose that faces 45° sideways (bug or misnomer?) | **P3** |

Good news worth stating: `secrets.json` and `.cache` were **never committed** (checked git history), the
camera reader thread in `cam_ops.py` is a solid latest-frame design, and pigpio hardware-timed PWM via
`PiGPIOFactory` is already the right choice for jitter-free servo pulses.

---

## 1. P0 — Crash bugs (fix these first, everything else depends on them)

### 1.1 `personality.follow()` crashes the vision loop the first time anything is detected

`personality.py:38-40`:

```python
for i in range(len(self.tracked)):
    while (i+1) <= len(self.tracked):
        leading += self.tracked[i+1][0] - self.tracked[i][0]
```

Three independent failures in three lines:

1. **First call:** `self.tracked` has 1 entry, so `i = 0` and the `while` condition `1 <= 1` passes →
   `self.tracked[1]` → **IndexError**. Since `main.video()` calls `follow()` as soon as *any* object is
   detected (`main.py:39-41`), `python main.py` dies the moment a cup or person enters the frame.
2. **If it survived:** nothing inside the `while` body changes `i` or `tracked` → **infinite loop**.
3. `personality.py:29-31` appends `[x, y]` even when `avg_x` returned `None` (object detected but no
   person), so the history fills with `[None, None]` and the subtraction would be a **TypeError** anyway.

**Fix** — replace the accumulation loop entirely with a velocity estimate over timestamped samples
(this also becomes the foundation of the lead/lag fix in §4):

```python
def follow(self, tags, cords):
    x = self.avg_x(tags, cords, "person")
    y = self.avg_y(tags, cords, "person")
    if x is None:                      # no person: don't pollute the history
        self.tracked.clear()
        return
    now = time.monotonic()
    self.tracked.append((now, x, y))
    if len(self.tracked) > 5:
        self.tracked.pop(0)

    vx = 0.0                           # px/sec, signed
    if len(self.tracked) >= 2:
        (t0, x0, _), (t1, x1, _) = self.tracked[0], self.tracked[-1]
        if t1 > t0:
            vx = (x1 - x0) / (t1 - t0)
    ...
```

### 1.2 Sign of the leading correction is backwards

`personality.py:44-52`: when the person is right of center (`x > 350`) the code moves the waist **−10**,
i.e. negative waist = aim right. But when the person is *moving* right (`leading > 50`, x increasing) it
moves **+10** — aiming *away* from where they're going. The lead term must have the same sign convention
as the position term. In the §4 control law this falls out naturally because lead is added in pixel space
*before* converting to degrees, so there is only one sign to get right (and one place to flip it if the
waist direction turns out mirrored on the real arm).

### 1.3 `main.py` cannot start unless Spotify is configured and the network is up

- `main.py:8` imports `server`, and `server.py:22-24` opens a UDP socket to `8.8.8.8` **at import time**
  → `OSError` with no network.
- `server.py:18` imports `music`, and `music.py:14` opens `secrets.json` **at import time** →
  `FileNotFoundError` on any machine without credentials.

So the vision-only mode (`setting = 0`) currently requires working Wi-Fi *and* Spotify secrets it never uses.

**Fix:**
- `music.py`: move the `secrets.json` read inside `_get_client()` (it's already lazy about the spotipy
  client — make the credential load lazy too). Fall back to env vars (see §9.2).
- `server.py`: wrap the LAN-IP lookup in a function with a fallback, and just bind `0.0.0.0`:

  ```python
  def _lan_ip():
      try:
          s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
          s.connect(("8.8.8.8", 80)); ip = s.getsockname()[0]; s.close()
          return ip
      except OSError:
          return "127.0.0.1"

  HOST = "0.0.0.0"   # bind everything; print _lan_ip() only for the "open this URL" message
  ```
- `main.py`: `import server` inside `mode()` where it's used, or after the fixes above it becomes harmless.

### 1.4 `ps5_controls.py` — server launch is broken, and L1+R1 is bound twice

- `ps5_controls.py:141-142`: `async def start_server():` is missing `self`, and
  `ps5_controls.py:73` calls `asyncio.run(self.start_server)` — passing a *method object*, not a
  coroutine → `ValueError: a coroutine was expected`. Even fixed, `server._start_server()` blocks
  forever, freezing all controls.
- `ps5_controls.py:72` and `ps5_controls.py:129-132` both test `L1 and R1` — one starts the server, the
  other curls and cancels. Only one can be intended.

**Fix:** delete the async wrapper; run the server in a daemon thread once, and give the two actions
different chords (e.g. **options button** = toggle server, **L1+R1 held 1 s** = quit):

```python
import threading
def start_server(self):
    threading.Thread(target=server._start_server, daemon=True).start()
```

Also module-level side effects at `ps5_controls.py:8-15` (`subprocess.run(['bash', 'bt_connect.sh'])`,
`ps5.init()`) run on *import* — move them into `Controller.__init__` guarded by try/except and
`platform.system() == "Linux"` so importing the module on the laptop doesn't crash (see §5).

### 1.5 `music.py` self-test passes a list to `play()`

`music.py:138`: `play(search("Little Wing"))` — `search()` returns a list of dicts; `play()` wants a URI
string. Should be:

```python
play(search("Little Wing")[0]["uri"])
```

---

## 2. The dance function (why it doesn't work, and the redesign)

Two separate problems: the **motion code** never loops or syncs to the beat, and the **BPM source** is a
deprecated Spotify endpoint. Both must be fixed for TODO 10.

### 2.1 What's wrong in `orientation.dance()` / `bounce()` (`orientation.py:99-123`)

1. **It bounces exactly once.** `dance()` calls `bounce(sync, "right")` and returns — the loop is
   commented out (`orientation.py:103-105`). A dance that runs once isn't a dance.
2. **BPM is used as an amplitude, not a tempo.** `sync = abs(int((bpm/60)*3))` turns 120 BPM into a
   **6-degree** swing — nearly invisible — and a 60 BPM ballad into 3°. Tempo should control *timing*;
   amplitude should be a fixed, visible number of degrees.
3. **Delays are hardcoded** (`delays = [0.5, 0.3]` at `orientation.py:120`) — 0.8 s per bounce regardless
   of the song, so even looped it would drift off-beat immediately.
4. `playing=True` parameter is accepted and ignored — there's no way to stop when the music stops.
5. It bounces out-and-back on one side instead of **side to side**.
6. `center()` (`orientation.py:164`) moves the waist to **45°**, so the "centered" dance pose faces
   diagonally. Probably should be `[0, 45, 45]`.

### 2.2 Corrected dance (works with the current architecture)

Beat period = `60 / bpm` seconds. Swing to alternating sides, one swing per beat, and absorb whatever
time the servo move didn't use so the *cycle* stays locked to the beat:

```python
def dance(self, bpm, keep_going=lambda: True, amplitude=25):
    beat = 60.0 / max(40, min(200, bpm))
    if beat < 0.45:              # very fast songs: bounce every 2nd beat
        beat *= 2
    asyncio.run(self.move_servo([[0, 45, 45]], [0.1]))   # dance home pose
    side = 1
    while keep_going():
        start = time.monotonic()
        target = [side * amplitude, 45 + amplitude // 2, 45 - amplitude // 2]
        asyncio.run(self.move_servo([target]))
        side = -side
        remaining = beat - (time.monotonic() - start)
        if remaining > 0:
            time.sleep(remaining)
    self.reset()
```

Feasibility check: a 25° waist swing is 50° of travel per beat; the servo layer sweeps at ~250°/s
(5° / 0.02 s), so the move takes ~0.2 s — comfortably inside a 0.5 s beat at 120 BPM.

`keep_going` should be a cheap callable — e.g. `threading.Event` cleared by a watcher thread that polls
`music.now_playing()` every ~5 s (don't hit the Spotify API every bounce). After the ServoWorker refactor
(§3.3) the `asyncio.run` calls become `worker.set_targets(...)` and dance becomes even smoother because
the worker eases into each swing.

### 2.3 The BPM source is dead — Spotify deprecated `audio_features`

`music.py:125` calls `sp.audio_features(track_id)`. Spotify **removed access to the Audio Features
endpoint for apps created after Nov 27, 2024** (along with recommendations, audio analysis, and 30-second
previews). Your app credentials date from July 2025, so this call returns **403 Forbidden** — TODO 10 is
blocked at the API level no matter what the motion code does. Verify once with a quick call; if you
somehow have a grandfathered app, keep it, but plan for the 403.

**Replacement options, in recommended order:**

1. **Deezer public API (no auth, free).** Search the track, read the `bpm` field:

   ```python
   import requests   # already installed — ultralytics depends on it

   def get_bpm(track, artist):
       try:
           hits = requests.get("https://api.deezer.com/search",
                               params={"q": f'track:"{track}" artist:"{artist}"'},
                               timeout=5).json().get("data", [])
           for hit in hits[:3]:
               t = requests.get(f"https://api.deezer.com/track/{hit['id']}", timeout=5).json()
               if t.get("bpm"):          # 0 means unknown
                   return float(t["bpm"])
       except requests.RequestException:
           pass
       return None
   ```

2. **Tap-tempo fallback on the music page.** A "🕺 dance" button on `index.html` you tap 4× on the beat;
   JS averages the intervals and POSTs `{"bpm": ...}` to a new `/dance` endpoint. Zero dependencies,
   always works, and doubles as the manual override when Deezer has `bpm: 0`.
3. *(Stretch)* Deezer's track JSON includes a 30-second `preview` MP3 URL — download it and run
   `librosa.beat.beat_track` for a measured BPM. Accurate but a heavy install on the Pi; only bother if
   1+2 prove insufficient.

### 2.4 Wiring it together

- Extend `music.now_playing()` to also return `progress_ms`, `duration_ms`, and the track `id` — needed
  by both dance ("did the song change?") and the queue (§6).
- On every successful `play()` (from the page or the queue), the server calls a
  `on_track_start(name, artist)` hook: look up BPM in a background thread, then start the dance loop.
- Add `POST /dance` (`{"on": true, "bpm": optional}`) so the page can toggle dancing and push tap-tempo.
- **Arbitration:** dance and person-tracking both command the waist. Add a simple mode flag (or a
  gesture lock in the ServoWorker, §3.3) so only one behavior drives the servos at a time — dance wins
  while music plays, tracking resumes after.

---

## 3. Smooth movement (servos are fine — the software is the problem)

### 3.1 Verdict on servos vs steppers

Keep the servos. The jerkiness has four software causes and two hardware ones, all fixable for $0–30.
Steppers would need new mechanics, drivers, a PSU, and homing switches — that's an H-3 decision, not a
fix. If you later want buttery motion with money instead of code, the intermediate step is **serial-bus
smart servos** (Feetech STS3215, LX-16A, or Dynamixel) which take speed/acceleration commands natively —
far cheaper to integrate than steppers.

### 3.2 Why it's jerky today

1. **5° command quantization** (`servo_ops.py:27-43`): the arm is commanded in 5° jumps every 20 ms.
   A hobby servo slews ~600°/s, so it *finishes* each 5° jump in ~8 ms then sits parked for 12 ms —
   50 stutters per second. Smaller steps at the same rate (1°/10 ms = 100°/s) are below the servo's own
   resolution of motion and look continuous.
2. **No easing.** Every move starts and stops at full speed. With a 3D-printed arm's inertia, that's a
   visible clunk at both ends. A cosine (ease-in-out) profile removes it.
3. **`asyncio.run()` per gesture** (`orientation.py:63-72` and every gesture): each call builds and tears
   down an event loop; between two consecutive `rotate_waist()` calls the arm fully stops. Motion is a
   chain of run-to-completion moves instead of one continuous glide toward the latest target.
4. **Default pulse-width range** (`servo_ops.py:18`): gpiozero's `AngularServo` defaults to 1–2 ms, but
   most hobby servos (SG90/MG996R class) use **0.5–2.5 ms** for their full range. Consequences: your
   "±90°" spans only about half the servo's real travel, and each degree of command = 5.5 µs of pulse
   instead of 11 µs, halving effective resolution. Calibrate per servo:

   ```python
   AngularServo(pin, min_angle=-90, max_angle=90,
                min_pulse_width=0.5/1000, max_pulse_width=2.5/1000,
                pin_factory=self.factory)
   ```

   Calibrate carefully (some servos hit their mechanical stop before 2.5 ms — creep outward in steps and
   listen for buzzing), and store per-joint values in `config.py` (§7.4).
5. **Power (hardware):** if the servos share the Pi's 5 V rail, every move causes voltage sag → twitching
   and Pi brownouts. Use a dedicated 5–6 V supply rated ≥3 A (an MG996R stalls at ~2 A alone), common
   ground with the Pi, and a 470–1000 µF electrolytic across the servo rail.
6. **Mechanics (hardware):** gear backlash and arm flex read as jerk. The H-2 waist ball-bearing cage
   already in `Design/H-2/` is the right idea — it takes side-load off the waist servo's output shaft.

### 3.3 The centerpiece refactor: one persistent ServoWorker

Replace "every caller spins an event loop" with **one background thread owning one asyncio loop and all
servo state**. Callers just set targets (thread-safe, latest-wins) or enqueue gestures. This
single change fixes smoothness (§3), tracking lag (§4), and the dance/tracking arbitration (§2.4).

```python
## servo_worker.py (new file) — sketch
import asyncio, threading, math, time

TICK = 0.01                       # 100 Hz update
SPEED = {"waist": 120, "shoulder": 100, "elbow": 140}   # deg/sec per joint, tune

class ServoWorker:
    def __init__(self, servos):               # servos = servo_ops.move() or mock
        self.servos = servos
        self.targets = dict(servos.angles)    # latest-wins target per joint
        self.lock = threading.Lock()
        self.gesture_active = threading.Event()
        threading.Thread(target=self._run, daemon=True).start()

    ## ---- thread-safe API used by vision loop / PS5 / keyboard / dance ----
    def set_target(self, name, deg):
        with self.lock:
            self.targets[name] = max(-90, min(90, deg))

    def nudge(self, name, delta):
        self.set_target(name, self.targets[name] + delta)

    ## ---- worker internals ----
    def _run(self):
        asyncio.run(self._glide_loop())

    async def _glide_loop(self):
        while True:
            if not self.gesture_active.is_set():
                with self.lock:
                    tgts = dict(self.targets)
                for name, tgt in tgts.items():
                    cur = self.servos.angles[name]
                    err = tgt - cur
                    if abs(err) > 0.5:
                        step = math.copysign(min(SPEED[name] * TICK, abs(err)), err)
                        self.servos.set_angle(name, cur + step)   # direct set, no sleeps
            await asyncio.sleep(TICK)
```

Supporting changes:

- `servo_ops.move` gains a tiny synchronous `set_angle(name, deg)` (clamp per §7.4 limits, write
  `self.servos[name].angle`, update `self.angles`). The old stepped `move_to` sweep becomes unnecessary —
  the worker *is* the sweep, continuous and interruptible.
- Gestures (jab, wave, fist_bump) become waypoint lists executed by the worker under `gesture_active`
  (targets ignored while a gesture plays) — same data as today's `posit_array`/`delays`, one executor.
  For extra polish, ease each waypoint with a cosine profile:
  `pos(t) = start + (end - start) * (1 - cos(pi * t/T)) / 2`.
- `orientation.positions` keeps its public methods but they shrink to `worker.set_target()` /
  `worker.play_gesture()` calls — no more `asyncio.run` anywhere outside the worker, killing README
  TODO 4's duplication along the way (§8).

---

## 4. Tracking falls behind (latency + control law)

### 4.1 Where the ~1 second of lag actually comes from

Measured against the code as written:

| Stage | Cost | Why |
|-------|------|-----|
| YOLOv8n **.pt** inference on Pi CPU | ~200–500 ms/frame | `obj_detection.py:5` uses the PyTorch model; ncnn is 2-4× faster on Pi |
| `follow()` servo moves **block the vision loop** | up to ~570 ms | Each `move()` → `asyncio.run(move_servo(...))` ≈ 0.19 s (sweep + 0.05 s settle + 0.1 s delay); waist + shoulder + elbow = 3 sequential calls (`personality.py:44-59`) |
| React only every 3rd frame | + up to 2 frame periods | `main.py:39` |
| Fixed ±10° step regardless of error | slow convergence + oscillation | `personality.py:49-59` |

So the arm acts on where the person *was* ~1 s ago, with a step size that can't catch up. The broken
leading loop (§1.1) was the right instinct — the implementation below does it properly.

### 4.2 Fixes, in order of payoff

1. **Decouple servos from vision (biggest win).** With the ServoWorker (§3.3), `follow()` just computes
   a target and calls `set_target()` — microseconds instead of ~0.6 s. The vision loop never blocks; the
   arm glides continuously toward the newest target and never executes a stale queue of moves.

2. **Re-export ncnn at the inference size and switch to it.** The committed export
   (`yolov8n_ncnn_model/metadata.yaml`) is 640×640, but `obj_detection.py:14` runs `imgsz=320` — ncnn
   inputs are fixed-size, which is presumably why the swap was shelved. On the Pi:

   ```
   yolo export model=yolov8n.pt format=ncnn imgsz=320
   ```

   then `model = YOLO(os.path.join(_DIR, "yolov8n_ncnn_model"))`. Also restrict classes to what Hank
   cares about — it skips NMS/plot work on chairs and laptops:

   ```python
   model.track(frame, persist=True, imgsz=320, conf=0.5, classes=[0, 41], verbose=False)
   ```

   (COCO: 0 = person, 41 = cup.)

3. **Track ONE person, not the average of all of them.** `avg_x` over two people aims between them.
   `model.track` already returns tracker IDs (`result.boxes.id`) — lock onto the largest/nearest box's
   ID and follow that ID until it disappears for N frames, then re-acquire.

4. **Proportional control with velocity lead** — replaces the fixed ±10 steps and deadbands
   (`personality.py:43-59`) and the broken leading loop. Pure function, easy to unit test:

   ```python
   ## Pi Cam v2 ≈ 62.2° horizontal FOV; v3 ≈ 66. Set for your module in config.py.
   FOV_X_DEG, FRAME_W = 62.2, 640

   def waist_correction(x_px, vx_px_s, current_waist,
                        latency_s=0.35, kp=0.8, dead_px=20):
       lead_px = vx_px_s * latency_s          # aim where they WILL be
       err_px = (x_px + lead_px) - FRAME_W / 2
       if abs(err_px) < dead_px:
           return current_waist                # close enough — hold
       deg_per_px = FOV_X_DEG / FRAME_W        # ≈ 0.097°/px
       return current_waist - kp * err_px * deg_per_px   # flip sign once if mirrored on hardware
   ```

   - `vx_px_s` comes from the timestamped history in §1.1's rewritten `follow()`.
   - Smooth `x` with an EMA (`x_s = 0.6*x_s + 0.4*x`) so detection jitter doesn't wiggle the waist.
   - Start `latency_s` at 0.35 and tune: log `time.monotonic()` at capture and at `set_target` to
     *measure* your real pipeline latency instead of guessing.
   - `kp < 1` converges without overshoot; raise it until the arm just begins to overshoot, then back off.
   - Same shape for shoulder/elbow on `y` (vertical FOV ≈ 48.8° over 480 px), and note the current
     y-deadband `150–300` (`personality.py:54-57`) is off-center for a 480-tall frame — the formula
     derives center from frame size instead.

5. **Skip stale frames.** Add a frame counter to `cam_ops.Cam` (increment in `_reader`, return
   `(count, frame)` from `stream()`) so the loop can skip YOLO when it's about to re-process the frame it
   already saw.

6. **Re-integrate greetings.** `main.py` only calls `follow()`; `check_greeting`/`pers_condit`
   (`personality.py:21-25, 69-85`) are currently dead code. Call `check_greeting(tags)` from `follow()`
   (or from the main loop) so the wave-on-arrival behavior actually runs — under the gesture lock so a
   wave and tracking don't fight.

---

## 5. Mock servos & laptop development (README TODO 8)

`mock_servos.py` today is a stub: `servos.degrees()` overwrites the method with an int
(`mock_servos.py:9-10`), and `waist()/shoulder()/elbow()` assign a local variable and do nothing. Nothing
imports it. Meanwhile three Pi-only imports make the whole stack un-runnable on Windows: `gpiozero/pigpio`
(`servo_ops.py:1-2`), `evdev` (`orientation.py:4`), `picamera2` (`cam_ops.py:3`).

**Goal:** `HANK_MOCK=1 python main.py` runs the *entire* vision + personality + server stack on the
laptop with the webcam, printing servo state instead of moving hardware.

### 5.1 Mock with real API parity

Mirror `servo_ops.move` exactly — same attribute names, same async methods, same clamping, and simulated
travel time so behavior timing matches the Pi:

```python
## mock_servos.py — full build-out sketch
import asyncio

HOME = {"waist": 0, "shoulder": 70, "elbow": 50}
PINS = {"waist": 27, "shoulder": 17, "elbow": 18}   # kept for API parity

class move:
    def __init__(self):
        print("### HANK INITIALIZING (MOCK SERVOS) ###")
        self.angles = dict(HOME)

    def set_angle(self, name, deg):                  # used by ServoWorker (§3.3)
        self.angles[name] = max(-90, min(90, deg))

    async def move_to(self, name, deg, step=5):
        if not isinstance(deg, (int, float)):
            print(f"{name}: angle must be a number, got {deg!r}")
            return
        target = max(-90, min(90, deg))
        delta = abs(target - self.angles[name])
        await asyncio.sleep(delta / 250)             # ≈ real sweep speed (5°/0.02s)
        self.angles[name] = target
        print(f"[mock] {name:8s} -> {target:4.0f}   {self.angles}")

    async def move_waist(self, deg, step=5):    await self.move_to("waist", deg, step)
    async def move_shoulder(self, deg, step=5): await self.move_to("shoulder", deg, step)
    async def move_elbow(self, deg, step=5):    await self.move_to("elbow", deg, step)
```

Optional polish: a one-line live render (`\r` carriage return) or a tiny matplotlib 2-link arm plot —
nice, but the print version already unblocks development and testing.

### 5.2 Selection shim — real hardware when available, mock otherwise

Keep `servo_ops` as the single import point so **no other file changes**:

```python
## top of servo_ops.py
import os
try:
    from gpiozero import AngularServo
    from gpiozero.pins.pigpio import PiGPIOFactory
    _HW = os.environ.get("HANK_MOCK") != "1"
except ImportError:
    _HW = False

## bottom of servo_ops.py, after the real `class move` definition
if not _HW:
    from mock_servos import move       # replaces the real class for all importers
```

### 5.3 Same trick for the camera and inputs

- `cam_ops.py`: try `picamera2`; on ImportError, a `Cam` variant backed by `cv2.VideoCapture(port)` with
  the same `stream()/stop()` interface — the laptop webcam feeds the real YOLO pipeline, which is exactly
  what you want for tuning the §4 control law at a desk.
- `orientation.py`: move `from evdev import ...` inside `find_keyboard()`/`listen_hold()` (lazy import)
  so importing the module works on Windows; keyboard mode simply reports "Linux only" if invoked.
- `ps5_controls.py`: guard `subprocess.run(['bash', 'bt_connect.sh'])` with a platform check
  (pydualsense itself works on Windows over USB, so PS5 control can join laptop testing).
- `distance.py`: mock returning a slow sine wave (drifting 10–200 cm) so `pers_condit`'s lean behavior
  is exercisable off-Pi.

### 5.4 Tests this unlocks (run on the laptop, no hardware)

- `waist_correction()` (§4.2): person right of center → waist decreases; moving target → lead exceeds
  the static correction; inside deadband → no change.
- Clamping: `set_target(..., 400)` → angle pinned to +90 and state stays in sync.
- Dance timing: with mocked time, 120 BPM → one swing every 0.5 s ± tick.
- Queue logic (§6): fake `music` module; song ends → next URI played.
- `python -m py_compile *.py` as a pre-commit syntax gate for the Pi-only files.

---

## 6. Music page: queue system (README TODO 2)

Multiple guests will submit songs; today the last tap wins mid-song. Design:

### 6.1 Server state

```python
## server.py
import threading, collections
queue = collections.deque()        # of {"uri", "name", "artist", "album_art"}
queue_lock = threading.Lock()
```

### 6.2 Endpoints

| Route | Method | Behavior |
|-------|--------|----------|
| `/queue` | GET | list current queue |
| `/queue` | POST `{"uri", "name", "artist"}` | append; if nothing is playing, play immediately |
| `/skip` | POST | pop next and play it |
| `/dance` | POST `{"on": bool, "bpm"?: number}` | §2.4 |

Also: catch `Exception` (not just `music.MusicError`) in `music_action` (`server.py:47-52`) and return a
500 JSON — right now any spotipy/network hiccup kills the handler thread with a stack trace.

### 6.3 Advancer thread

```python
def _advance_loop():
    last_progress = 0
    while True:
        time.sleep(3)
        now = music.now_playing()          # extended with progress/duration (§2.4)
        with queue_lock:
            if not queue:
                continue
            if now is None or (not now["is_playing"] and now.get("progress_ms", 1) == 0):
                music.play(queue.popleft()["uri"])     # track ended → next
            ## paused mid-song (progress > 0, stalled) → leave it alone
```

The `progress_ms == 0` heuristic separates "ended" from "guest paused it"; refine later by remembering
the previous poll's progress.

### 6.4 `index.html`

- Each result row gets **Play now** and **+ Queue** buttons; a queue panel above the now-playing bar
  shows upcoming songs (poll `/queue` alongside the 5 s `/status` poll at `index.html:224`).
- Tap-tempo dance button (§2.3).
- Harden `api()` (`index.html:129-134`): check `res.ok` and wrap `res.json()` so a non-JSON error page
  doesn't surface as a cryptic parse error.

---

## 7. main.py integration & modes (README TODOs 9, 12)

### 7.1 Target architecture — one process, clear ownership

```
main.py (Hank)
├── cam_ops.Cam            camera reader thread (exists)
├── ServoWorker            servo thread + asyncio loop (§3.3) — ONLY thing touching servos
├── vision loop            main thread: YOLO → personality → worker.set_target()
├── server thread          ThreadingHTTPServer daemon (music page + queue + dance)
├── music watcher thread   polls now_playing; advances queue; flips dance Event; fetches BPM
└── mode manager           GPIO buttons / CLI flag → {bartender, keys, ps5, off}
```

Rules that keep it sane: the ServoWorker is the single hardware owner (everyone else calls
`set_target`/`play_gesture`); vision state flows one way (detect → personality → worker); threads talk
through `threading.Event`/locked state, never by reaching into each other.

### 7.2 Cleanups in `main.py` itself

- `main.py:50-66`: comments say modes 0/1/2 = bartender/keys/PS5, code handles 1/2/3 with 3 = server.
  Replace magic ints with names and argparse:
  `python main.py --mode bartender|keys|ps5 --no-display --mock`.
- Restore mode 2 by fixing `ps5_controls` (§1.4) — the commented block at `main.py:57-62` references an
  undefined `c` and would loop without sleeping.
- Wrap the video loop in `try/finally` so `cam.stop()` and `cv2.destroyAllWindows()` run on crash/Ctrl-C;
  make `cv2.imshow` conditional (`--no-display`) — it throws over SSH without an X display.
- `Hank.detect()` (`main.py:24-26`) is a pass-through — call `self.detector.detection(frame)` directly.

### 7.3 Physical mode buttons (TODO 9)

Free GPIO pins given 17/18/27 (servos) and 23/24 (ultrasonic): use 5, 6, and 22.

```python
from gpiozero import Button, LED     # works with the same pigpio factory
mode_btn  = Button(5, bounce_time=0.05)   # cycles bartender → keys → ps5 → off
select_btn = Button(6, bounce_time=0.05)  # confirm / also "reset arm" long-press
status_led = LED(22)                      # blink count = current mode

mode_btn.when_pressed = lambda: hank.cycle_mode()
```

The mode manager sets a `self.mode` the vision loop checks each iteration — switching must not require
restarting the process.

### 7.4 `config.py` — one home for every constant

Pins (`servo_ops.py:9`, `distance.py:7`, buttons), HOME pose, **per-joint mechanical limits** (the blanket
±90 in `servo_ops.py:31` ignores real collisions — the elbow likely hits the base before −90; measure and
encode e.g. `LIMITS = {"waist": (-90, 90), "shoulder": (-45, 90), "elbow": (-80, 90)}`), per-servo pulse
widths (§3.2.4), camera FOV/size, control gains (`kp`, `latency_s`, deadband), speeds (§3.3), server port.
Real and mock import the same file, so laptop tuning carries to the Pi.

### 7.5 Two safety niceties (cheap, worth it)

- **Go-limp:** a key/button that calls `servo.detach()` on all joints — the arm stops fighting you
  instantly. Also consider auto-detach after ~10 s idle to stop servo buzz/heat (waist only, if
  shoulder/elbow sag under gravity).
- **Startup pose sweep:** on boot, glide from wherever the arm physically is to HOME slowly instead of
  the current instant snap (`servo_ops.py:19` sets `servo.angle = HOME` immediately at full speed).

---

## 8. orientation.py cleanup (README TODO 4)

- **Delete `wave_one()`** — `orientation.py:183-198` is character-identical to `wave()` at 166-181, so
  the "random wave" choice in `personality.greetings()` is ⅔ the same wave. Make `wave(n=2, speed=1.0)`
  parameterizable instead if variety is the goal.
- **Table-drive the gestures.** jab/fist_bump/curl/point/waves/bounces are all the same shape (waypoints +
  delays + `asyncio.run`). One executor + data kills ~100 lines:

  ```python
  GESTURES = {
      "jab":       ([[0, 70, 50], [0, -40, -80], [0, 70, 50]], [0.2, 0.1, 0.1]),
      "fist_bump": ([[0, 70, 50], [0, 20, -10], [0, 70, 50]], [0.5, 1.0, 0.5]),
      "curl":      ([[0, 0, 90]], [0.4]),
      ...
  }
  def gesture(self, name):
      pos, delays = GESTURES[name]
      asyncio.run(self.move_servo(pos, delays))     # later: worker.play_gesture(name)
  ```
- **Table-drive `listen_hold`** (`orientation.py:255-348`): the ten if-blocks become
  `HOLD_KEYS = {"KEY_UP": (1, -5), "KEY_DOWN": (1, +5), "KEY_LEFT": (0, -5), ...}` — and the copy-pasted
  `print("LEFT PRESSED")` labels on W/E/A/D/Z/X (which print the wrong key) disappear with them.
- **Debounce R/P/C** (`orientation.py:337-345`): they fire every 50 ms while held — reset/point/curl
  should trigger on key-*down* transitions only (track `newly_pressed = held - prev_held`).
- `orientation.py:386`: `settings = 2` hardcodes the BPM-prompt test mode, while the README (line 9) says
  this script is arrow-key control. argparse: `python orientation.py [--mode keys|cli|dance]`, default keys.
- Drop the `orient` dict / `pos_log` list duplication — two mirrors of the same state, synced by two
  helpers (`_sync_state`, `_sync_logs`, the latter unused). Keep the dict; derive lists where needed.
- `servo_ops.main()` (`servo_ops.py:64-158`) re-implements jab/wave/reset — after the gesture table
  exists, the CLI should call it instead of maintaining its own copies.
- Unused: `time` import is only used in one `__main__` branch; `detect.focus` (`obj_detection.py:11`);
  `acts.actions` (`personality.py:10`); `acts.following` set but never read.

---

## 9. Music/Spotify robustness

- **Credentials** (`music.py:14-19` vs `readme.md:14-15`): code demands `secrets.json`; README documents
  env vars. Support both — env vars first, `secrets.json` fallback — inside `_get_client()` (lazy per
  §1.3), with a `MusicError` naming both options when neither exists. Add a `secrets.json.example` with
  placeholder keys so the shape is documented (real one stays gitignored — verified never committed).
- **Redirect URI** (`music.py:19`): `http://127.0.0.1:8080/callback` shares port 8080 with `server.py`.
  It only matters during the first OAuth run, and the two bind different interfaces, but it's a foot-gun —
  use spotipy's conventional `http://127.0.0.1:8888/callback` (must match the Spotify dashboard entry).
- **Volume + device endpoints** (P3): `sp.volume(n)` and a device picker are small additions guests will
  ask for the first night.

---

## 10. distance.py (README TODO 6)

Code is nearly fine — `dist()` works and the ×100 conversion is right. Getting it *working* is mostly
hardware + integration:

1. **Hardware checklist:** HC-SR04 ECHO is a 5 V output — the Pi's GPIO 24 needs a voltage divider
   (1 kΩ / 2 kΩ) or a 3.3 V-native sensor (HC-SR04P). If readings are stuck at max/zero, this is why.
2. **Timing accuracy:** pass the shared pigpio factory —
   `DistanceSensor(echo=24, trigger=23, pin_factory=factory, max_distance=2)`. gpiozero's default
   software timing on a busy Pi (YOLO pegging the CPU) skews echo timing badly; pigpio timestamps edges
   in the daemon.
3. Remove the `print` from `dist()` (`distance.py:12`) — at loop rate it floods the console; log at DEBUG.
4. **Integration:** read it in the vision loop every N frames (it's blocking but fast), pass into
   `pers_condit(tags, cords, distance)` — re-enabling the lean-in behavior at `personality.py:81-85` that
   is currently dead code, and giving bartender mode a "cup is close enough to pour" signal (TODO 5:
   cup detection → aim at cup when no person, lean when `distance < 15`).

---

## 11. Startup & raspotify infrastructure (README TODO 11 + the privileges question)

`startup.sh:3-4` today: `sudo pigpiod` (errors if already running) and `systemctl enable raspotify`
(enables at *next boot*, doesn't start it now), and nothing launches Hank itself.

**Answer to the privileges question from the commit message: you don't need sudo for Hank at all.**
pigpio clients talk to the daemon over a localhost socket — only the daemon is root, and Raspberry Pi OS
ships a systemd unit for it. Camera access = `video` group, GPIO via daemon = no group needed.

```bash
sudo systemctl enable --now pigpiod raspotify
```

Then replace startup.sh with real units so everything survives reboots and crashes:

```ini
# /etc/systemd/system/hank.service
[Unit]
Description=Hank robot (vision + personality + music server)
After=network-online.target pigpiod.service raspotify.service
Wants=pigpiod.service

[Service]
User=pi
WorkingDirectory=/home/pi/Hank
ExecStart=/home/pi/Hank/.venv/bin/python main.py --mode bartender --no-display
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
```

`sudo systemctl enable --now hank` and delete/trim `startup.sh` (keep `bt_connect.sh` — it works and a
unit can call it when PS5 mode ships). Logs via `journalctl -u hank -f`, which pairs nicely with §12's
logging switch.

---

## 12. Housekeeping

- **requirements.txt:** add `pydualsense` (PS5; needs the hidapi system lib on Pi:
  `sudo apt install libhidapi-hidraw0`). Pin versions once things stabilize (`ultralytics==8.4.x`, …) so
  a Pi reflash reproduces a working install. `requests` is already available transitively via
  ultralytics but list it explicitly since §2.3 imports it directly.
- **Git hygiene:** untrack the compiled/OS noise that's currently committed:

  ```bash
  git rm -r --cached yolov8n_ncnn_model/__pycache__ 
  git rm --cached Design/H-2/desktop.ini
  ```

  and append to `.gitignore`: `*.pyc`, `desktop.ini`, and (your call — they're FreeCAD auto-backups)
  `*.FCBak`.
- **Logging:** swap prints for the `logging` module (`logging.basicConfig`, per-module
  `logging.getLogger(__name__)`, `--verbose` flag → DEBUG). The servo/keyboard spam becomes DEBUG; real
  events (mode change, song started, person acquired/lost) become INFO. Under systemd (§11) this is your
  journal history.
- **Naming (someday):** classes `acts`, `move`, `positions`, `detect`, `measure` → PEP8 `Personality`,
  `ServoRig`, `Arm`, `Detector`, `RangeFinder`. Pure rename, do it last with the IDE.
- **readme.md:** after the refactor, update run instructions (systemd, `--mode` flags, `HANK_MOCK=1` for
  laptops, tap-tempo dance) and prune completed TODOs. `fable5_analysis.txt` is superseded by this file —
  all its fixes are already in the code; safe to delete.
- **Verify camera colors once:** picamera2 format naming vs OpenCV's BGR expectation is a classic
  swapped-channels trap (`cam_ops.py:9`). If reds/blues look swapped in the preview window, switch
  `"RGB888"` ↔ `"BGR888"` — swapped channels also quietly cost YOLO a little accuracy.

---

## 13. Suggested order of attack

Each phase leaves the repo working; laptop-testable phases come first so Pi time is spent tuning, not
debugging syntax.

**Phase 1 — Unblock (laptop, ~an evening)**
1. Fix the P0 crashes: §1.1–§1.5.
2. Build out mocks + import guards: §5. From here, everything below is developed with
   `HANK_MOCK=1 python main.py` and the webcam.
3. Housekeeping quick hits: gitignore/untrack, requirements (§12).

**Phase 2 — Motion core (laptop design, Pi tuning)**
4. ServoWorker + `set_angle` + per-joint limits/config: §3.3, §7.4.
5. Pulse-width calibration + dedicated servo power check on the Pi: §3.2.
6. Port gestures to the worker; dedupe orientation.py: §8.

**Phase 3 — Tracking that keeps up**
7. ncnn re-export at 320, class filter, single-ID targeting: §4.2.2–3.
8. Proportional + lead control law with measured latency: §4.2.4; re-enable greetings: §4.2.6.

**Phase 4 — Music & dance**
9. Queue endpoints + advancer + page UI: §6.
10. BPM via Deezer + tap-tempo; rebuilt dance loop; dance/tracking arbitration: §2.
11. Volume endpoint, credential fallback: §9.

**Phase 5 — Becoming an appliance**
12. main.py mode manager + argparse + buttons + LED: §7.
13. distance sensor divider + integration → cup/pour behavior: §10 (TODOs 5 & 6).
14. systemd units, logging, README refresh: §11, §12.

---

*Everything above is a plan — no source files were modified. Line numbers refer to the code as of commit `79bcd16`.*
