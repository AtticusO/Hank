# Fixes implementation log

Log of every change made while implementing `fixes.md` (started 2026-11-06).
Entries are in the order the work was done. Each entry says what changed, and
where the implementation deliberately differs from `fixes.md`, why.

Marker key: **DONE** = implemented · **ADJUSTED** = implemented differently from the plan (reason given) ·
**MANUAL** = needs you (hardware, sudo, or a decision) · **SKIPPED** = intentionally not done (reason given)

---

## 0. Before starting

- Working tree at start: `fixes.md` (your "FIXED" note on #2), `orientation.py` (`settings = 0`),
  `personality.py` (half-applied §1.1 rewrite: the new `follow()` still referenced the deleted
  `leading` variable, so it raised `NameError` on the first detection), and an untracked
  `servo_worker.py` (the §3.3 sketch, verbatim). All of these were built on, not reverted.
- Environment checked on the Pi: every dependency imports (ultralytics 8.4.66, cv2 4.13, gpiozero 2.0.1,
  pigpio 1.78, evdev 1.9.3, spotipy 2.26, pydualsense 0.7.5, requests 2.34, picamera2, ncnn, pnnx).
  `pigpiod` is running.
- **Safety rule for this whole session:** every test was run with `HANK_MOCK=1`, so nothing here moved
  the real arm. Nothing has been tested on the physical servos, camera, controller or distance sensor —
  see the "Test on the Pi" checklist at the end.
- `fable5_analysis.txt` (§12) does not exist on this machine, so there is nothing to delete.

## 1. Foundation (§7.4 config, §12 logging)

- **DONE** — new `config.py`: pins, HOME, per-joint limits, pulse widths, worker speeds/accels, camera
  size/FOV, detection + tracking gains, distance/button pins, server/Spotify settings, `HANK_MOCK` flag,
  `setup_logging()` and `clamp()`. Real and mock code import the same file.
- **ADJUSTED** — per-joint `LIMITS` are still the old blanket ±90 for every joint. The plan's example
  (`shoulder (-45, 90)`, `elbow (-80, 90)`) is a guess, and it would have clamped existing gestures
  (`point` uses elbow −90, `jab` uses elbow −80 / shoulder −40). Measure the real limits, then edit `LIMITS`.
- **ADJUSTED** — `PULSE_WIDTHS` default to gpiozero's 1–2 ms, i.e. *exactly* the old behaviour, instead of
  the plan's 0.5–2.5 ms. Switching blind changes what every angle means physically and can drive a joint
  into its mechanical stop (stripped gears / cracked prints). Added `calibrate_servo.py` (step 9 of the
  "Test on the Pi" checklist) so you can find each servo's real range safely, then put the numbers in `config.py`.
- **ADJUSTED** — FOV defaults to the Camera Module 3 (imx708, which your `config.txt` loads): ≈66° × 41°,
  not the v2 numbers in the plan. It is approximate either way (4:3 output from a 16:9 sensor crops);
  `TRACK_KP` absorbs any error, so tune that rather than chasing the exact FOV.
- **DONE** — `config.setup_logging()` replaces `print()` across the codebase: events at INFO, per-tick
  noise (servo writes, key presses, detections) at DEBUG; `--verbose` turns DEBUG on.

## 2. Motion core (§3.2, §3.3, §5.1, §5.2, §7.5)

- **DONE** — `servo_ops.py`
  - `set_angle(name, deg)`: synchronous, immediate write clamped to `config.LIMITS`. Used by the worker.
  - Pulse widths and pins come from `config.py`; accepts a shared pigpio `factory`.
  - `initial_angle=HOME` passed to `AngularServo`. Previously each servo was created at 0° and *then* set
    to HOME, so boot snapped every joint twice (to 0, then to HOME). Now it is one snap.
  - `detach()` / `detach_all()` for go-limp (§7.5).
  - Old async `move_to`/`move_waist`/... kept for compatibility, but sweep in 1° steps every 4 ms
    (≈250°/s, same speed) instead of 5° jumps every 20 ms (§3.2.1).
  - Selection shim (§5.2): `HANK_MOCK=1`, or gpiozero/pigpio missing → `move` is `mock_servos.move`.
  - `python servo_ops.py` CLI now drives the shared gesture table through the worker instead of its own
    copy-pasted jab/wave/reset (§8). Added `jj`, `limp`, aliases (`r`, `cu`, `pt`, `j`, `w`, `b`).
- **ADJUSTED** — §7.5 "startup pose sweep" is not possible as written: hobby servos have no position
  feedback, so the software can't know where the arm physically is at boot, and the first pulse always
  snaps it. Done instead: the double snap above is now a single snap straight to HOME.
- **DONE** — `mock_servos.py` rebuilt with full API parity (`angles`, `set_angle`, `detach`,
  `detach_all`, async `move_to`/`move_*` with simulated travel time, clamping from `config.LIMITS`).
  Logs pose at DEBUG at most 4×/sec so 100 Hz worker writes don't flood the console.
- **DONE / ADJUSTED** — `servo_worker.py` completed from your sketch. Differences from the sketch:
  - Plain thread with a deadline-scheduled 100 Hz loop instead of an asyncio loop inside a thread — there
    is nothing to `await` concurrently, so asyncio only added overhead.
  - Speed **and acceleration** limited (trapezoidal profile, `JOINT_ACCEL`): soft start and a
    √(2·a·err) braking curve so joints land exactly on target. The sketch moved at full speed from the
    first tick, which is the end-of-move "clunk" §3.2.2 describes.
  - `nudge()` did a read-modify-write on `targets` outside the lock (race with other threads) — fixed.
  - `play_gesture(poses, holds, speed=, durations=, wait=)`: gestures run *inside* the worker thread
    (single hardware owner), cosine-eased per waypoint, `None` in a pose slot = hold that joint.
    Tracking targets are ignored while a gesture plays.
  - After a gesture the final pose becomes the target — otherwise the arm would glide back to whatever
    stale target was set before the gesture.
  - `busy()` uses a pending counter so there is no instant where a queued gesture reads as idle.
  - Also: `set_targets()`, `get_targets()`, `get_angles()`, `wait_idle()`, `cancel_gestures()`,
    `go_limp()`, `stop()`, and optional auto-detach after idle (`config.AUTO_DETACH_S`, off by default).
- **DONE** — new `gestures.py`: every scripted move as data (§8), used by orientation, the servo CLI,
  keyboard and PS5.
  - `wave_one` removed (character-identical to `wave`); `GREETINGS = ("wave", "wave_two")`.
  - **Bug fixed** in `wave_two`: it captured shoulder/elbow *before* raising the arm, so its second
    waypoint dropped the arm straight back down. It now holds the raised arm and wiggles the waist.
  - `center` is now `[0, 45, 45]` (was `[45, 45, 45]`, which faced 45° sideways — fixes.md #25).
  - `jab` plays at 500°/s so it is still snappy now that the worker eases every move.
- Verified (mock): glide lands exactly on target, clamping to ±90, nudge, gestures with hold-slots, no
  glide-back after a gesture, non-blocking gesture + `busy()`, mid-move reversal decelerates smoothly
  (no snap), limp, clean stop.

## 3. Arm control — `orientation.py` (§8, #6, #16, #17, #21, #25)

- **DONE** — `positions` now owns one `ServoWorker`; no `asyncio.run` anywhere outside the worker.
  Same public methods as before (`reset`, `curl`, `point`, `jab`, `fist_bump`, `wave`, `wave_two`,
  `bounce_left/right`, `center`, `rotate_*`, `reach`, `rotate`, `bounce`, `dance`), all backed by the
  gesture table. Gesture methods take `wait=` (default `True` = old blocking behaviour).
- **DONE** — `orient` is now a read-only property (the worker's targets); `pos_log` and the
  `_sync_state`/`_sync_logs` mirrors are gone. Added `angles()`, `busy()`, `set_pose()`, `go_limp()`,
  `stop()`, `gesture(name)`.
- **DONE** — `rotate_waist/shoulder/elbow` are now non-blocking nudges (they used to block ~0.2 s each,
  which is most of the vision-loop lag in §4.1).
- **DONE / ADJUSTED** — dance (§2.2, #6): loops until `keep_going()` is false, one swing per beat,
  beat-locked with an absolute schedule so it never drifts; BPM now sets tempo, `DANCE_AMPLITUDE` (25°)
  sets size; fast songs (beat < 0.45 s) swing every 2nd beat; resets when done.
  *Adjusted:* the plan's target pose only alternated the waist — shoulder and elbow stayed constant after
  the first beat, so there was no bounce at all. Each beat now arcs **down through a dipped centre pose and
  up to the other side** (the "bouncing arc" you were after earlier). Each beat's move is timed to
  90% of the beat via `play_gesture(durations=...)`.
  Verified (mock, 120 BPM): swings alternate ±25° every 0.49–0.52 s, then reset to HOME.
- **DONE** — `bounce(rate, dir)` keeps the single arc-out-and-back you chose earlier (amplitude ∝ rate).
- **DONE** — `wave_one()` deleted (#16); greetings use `gestures.GREETINGS`.
- **DONE** — keyboard (§8, #21): new `KeyboardControl` class — table-driven `HOLD_KEYS` /
  `PRESS_KEYS` instead of ten copy-pasted if-blocks (the wrong "LEFT PRESSED" labels are gone with
  them). R/P/C (and new J jab, F fist bump, V/B waves, L limp) fire **once per key-down** instead of
  ~20×/sec while held. Jogging is skipped while a gesture plays. `step()` is non-blocking so `main.py`
  can run it inside its mode loop; `listen_hold()` still works standalone.
- **DONE** — `evdev` is imported lazily (§5.3), so the module imports on Windows/macOS.
- **DONE** — `__main__` (#17): `python orientation.py [--mode keys|cli|dance] [--bpm N]`, default
  `keys` — matching the README and the `settings = 0` you had set.

## 4. Tracking — `personality.py` (§1.1, §1.2, §4.2.3–4.2.6, #1, #2, #12)

- **DONE** — finished your half-applied `follow()` rewrite. It still referenced the deleted `leading`
  variable, so it raised `NameError` on the first detection.
- **DONE** — proportional control with velocity lead (§4.2.4) as pure, unit-tested functions:
  `px_to_deg`, `bearing`, `waist_correction`, `pitch_correction`. Gains/deadbands live in `config.py`.
- **ADJUSTED** — the plan estimates the person's velocity in **pixel** space. Because the camera turns
  with the waist (what the original ±10° code assumed), the arm's own motion makes a standing person
  appear to move in the frame, so the "lead" would fight the arm. Each detection is now converted to an
  absolute **bearing** (waist angle at capture − pixel offset in degrees); velocity and lead are computed
  on bearings, which cancels the ego-motion. If the camera is actually fixed to the base, set
  `config.CAMERA_ON_ARM = False`.
- **DONE** — sign error #12 / §1.2 is gone by construction: position and lead share one sign convention
  (person right of centre → lower waist angle, as the old position code did).
- **DONE** — EMA smoothing of the bearing, velocity capped at ±90°/s so a detector glitch can't fling
  the arm, and the vertical centre derived from the frame size instead of the off-centre 150–300 band.
- **DONE** — one target, not the average of everyone (§4.2.3): locks the largest box's tracker ID,
  holds still while it is briefly hidden, re-acquires after `TRACK_LOST_FRAMES`.
- **DONE** (from §10.4 / README TODO 5) — when no person is in frame, Hank aims at a **cup**.
- **DONE** — greetings re-integrated (§4.2.6): `follow()` calls `check_greeting()`; the wave is
  non-blocking and tracking pauses while it plays (verified: "Greeting: wave_two" then tracking resumed).
- **DONE** — `follow()` only sets worker targets: microseconds instead of ~0.6 s blocking.
- **DONE** — `follow(..., capture_t=)` logs the measured capture→command latency at DEBUG so you can
  tune `TRACK_LATENCY_S` from real numbers (§4.2.4).
- **ADJUSTED** — `pers_condit()`: its own copy of the waist-turning logic is removed (duplicate of
  `follow`). Its lean-in used to add `15 − d` degrees **every frame** while something was close, so the
  arm ran to its limit; it is now a short lean-and-return gesture with a 2 s cooldown.
- **DONE** — `positions` is a live property (it used to hold a dict reference that went stale).

## 5. Vision plumbing — `obj_detection.py`, `cam_ops.py` (§4.2.2, §4.2.5, §5.3, §12, #18)

- **DONE** — re-exported ncnn at 320 px **on this Pi**:
  `yolo export model=yolov8n.pt format=ncnn imgsz=320` (`metadata.yaml` now says 320). The old 640 px
  export is in git history, and a copy is in the session scratchpad.
- **DONE** — the detector loads ncnn only if its exported size matches `INFER_SIZE`, otherwise warns and
  uses `.pt`. Model is built in `detect()` instead of at import. Class filter `[0, 41]` (person, cup).
  `detection(frame, draw=)` returns `(annotated, tags, cords, ids)` — tracker IDs added; plotting is
  skipped with no display. Unused `focus` removed.
- **MANUAL / honest note** — measured on this Pi *with VS Code running* (it uses ~1 core): ncnn
  ≈ 651 ms/frame vs `.pt` ≈ 666 ms (inference 567 vs 643 ms). That is ~12% faster, not the 2–4× the plan
  promised. Benchmark headless with `python obj_detection.py` (added). If ncnn isn't clearly faster, rename
  the `yolov8n_ncnn_model` folder (or point `config.YOLO_NCNN_DIR` at a name that doesn't exist) and the
  detector falls back to `.pt`.
- **DONE** — `cam_ops.Cam`: falls back to an OpenCV webcam when picamera2 is missing or fails
  (or `HANK_WEBCAM=1`), with a clear error pointing at the ribbon cable; frame counter + timestamp via
  `read()` so the loop skips frames it already processed; `stream()` unchanged.
- **SKIPPED (no change needed)** — colour check (§12): picamera2's `"RGB888"` *is* BGR byte order, which
  is what OpenCV wants, so the code is right as-is. Comment added saying what to change if colours look swapped.
- **CORRECTION (made later in the session)** — I first logged the camera as "still not detected"; that was
  my mistake (I cut the `rpicam-hello --list-cameras` output short and misread it). The imx708 **is**
  detected and working. Real-camera test (mock servos): camera captures ≈23 fps, the vision loop processed
  ≈1.4 frames/s with VS Code running, frames are 640×480 BGR. Nobody was in view, so nothing was tracked.

## 6. Distance sensor — `distance.py` (§10, #20)

- **DONE** — shared pigpio factory (accurate echo timing under YOLO load), `max_distance` from config,
  no `print` per read (DEBUG log), `mock_measure` (slow 10–200 cm sine) for off-Pi testing, `make()`.
- **ADJUSTED** — the plan's mock is only used under `HANK_MOCK=1`. If the real sensor fails on the Pi,
  distance reactions are *disabled* instead of fed fake readings (fake readings would make Hank lean at random).
- **DONE** — integrated: `main.py --distance` reads it every 5th frame into `pers_condit()`.
- **MANUAL** — the 5 V ECHO → 3.3 V GPIO voltage divider (1 kΩ / 2 kΩ) is documented in the file header;
  check your wiring. That is the most likely reason it "isn't working well".

## 7. Music — `music.py` (§1.3, §1.5, §2.3, §2.4, §9, #5, #7, #19)

- **DONE** — nothing is read at import; credentials load lazily inside `_get_client()`: env vars first,
  then `secrets.json`, with a `MusicError` naming both options if neither exists. Added
  `secrets.json.example`.
- **DONE** — self-test fixed: `play(search(...)[0]["uri"])` (#5).
- **VERIFIED** — §2.3 is right: this app gets **HTTP 403** from `audio_features`.
- **ADJUSTED** — the plan's Deezer query (`track:"…" artist:"…"`) returns **zero results** for every
  song I tried (Little Wing, Billie Jean, Gangsta's Paradise). `deezer_bpm()` uses a plain search and
  then checks the artist/title match, skipping `bpm: 0`. Verified: Billie Jean 117.1, Uptown Funk 114.8.
  Songs Deezer lists at double time (Gangsta's Paradise 160) are halved automatically by the dance's
  "swing every 2nd beat" rule.
- **DONE** — `track_bpm()` tries Spotify once, remembers the 403, and doesn't ask again (spotipy logs an
  ERROR line per 403).
- **DONE** — `now_playing()` also returns `id`, `progress_ms`, `duration_ms`, `volume` (§2.4).
- **DONE** — `volume()`, `devices()`; `play()` prefers the Connect device named
  `config.SPOTIFY_DEVICE_NAME` ("Hank") so music never lands in a random browser tab.
- **ADJUSTED** — redirect URI (§9) left on **8080** (now in `config.py` / `SPOTIPY_REDIRECT_URI` /
  `secrets.json` `"redirect"`). Your Spotify dashboard is registered with 8080; switching code to 8888
  alone would make the next login fail with "Invalid redirect URI". To move: add
  `http://127.0.0.1:8888/callback` in the dashboard first, then change `config.SPOTIFY_REDIRECT_URI`.
- **MANUAL** — your account currently sees only one Connect device, `ATTIPC`. No "Hank" raspotify
  device is visible, so the raspotify config (`LIBRESPOT_NAME="Hank"` …) from earlier still needs
  applying, then pair once from the Spotify app.

## 8. Dance controller — new `dance.py` (§2.4)

- **DONE** — `DanceController(arm)`: watcher thread polls Spotify every `DANCE_POLL_S` (not every beat);
  song playing → BPM lookup → dance; song change → re-fetch and restart; pause/end → stop. A tapped
  tempo overrides the lookup. Arbitration: while dancing `arm.busy()` is True, so tracking backs off and
  resumes by itself afterwards.

## 9. Music page server — `server.py`, `index.html` (§1.3, §6, #3, #11)

- **DONE** — no side effects at import (#3): LAN-IP lookup is a function with a 127.0.0.1 fallback, used
  only for the log message; binds `0.0.0.0`.
- **DONE** — `music_action` catches every `Exception` → 500 JSON (verified: a crashing handler returns
  500 instead of killing the thread).
- **DONE** — queue: `GET/POST /queue`, `POST /skip`, advancer thread. Also `POST /volume`,
  `GET/POST /dance`, input validation (bad JSON, non-object bodies, bpm range 40–220).
- **ADJUSTED** — advancer refinements over the plan's sketch: an "ended" test that also accepts
  progress within 2 s of the end; a 5 s guard after starting a track (Spotify's state lags, so the next
  poll could otherwise see the old "not playing" state and skip a song); errors are logged at most once
  a minute and never kill the thread.
- **DONE** — `start_server(background=True)`; `_start_server()` kept as an alias.
- **DONE** — `index.html`: Play + "+ Queue" per result, "Up next" panel with Skip, 🕺 Dance toggle and
  tap tempo (4+ taps within 3 s, averaged), volume slider, hardened `api()` (`res.ok` + non-JSON error pages).
- Verified with stubbed playback (so nothing played on your real device): idle → plays immediately,
  busy → queues, song end → advances, **paused mid-song → left alone**, skip, dance on/off follows playback.
  Page JS: brackets balance and every element id it uses exists (Node isn't installed, so it was not
  executed in a browser — see the checklist).

## 10. PS5 controller — `ps5_controls.py` (§1.4, #4, #13)

- **DONE** — no side effects at import: `bt_connect.sh` + `pydualsense.init()` moved into
  `Controller.__init__`, Bluetooth step guarded by `platform.system() == "Linux"`.
- **DONE** — server: `asyncio.run(self.start_server)` (a method object, not a coroutine) replaced by
  `server.start_server(background=True)` on **Options**. L1+R1 double binding resolved: L1+R1 **held 1 s**
  curls and quits; a quick tap does nothing.
- **ADJUSTED** — #13: in your pydualsense 0.7.5, `state.L2` is already a bool, but it is `True` for *any*
  touch (value ≥ 1), so a resting finger moved the waist. Triggers now use `L2_value`/`R2_value` with a
  deadband, and speed scales with pressure. Sticks scale too.
- **DONE** — shoulder reads the left stick's **Y** axis (was X); elbow unchanged (right Y).
- **DONE** — buttons fire once per press (holding Cross used to retrigger reset every loop iteration);
  50 Hz polling with a sleep (the old loop spun at 100% CPU); D-pad rate clamped 1–20; Create = go limp.
- Verified (fake controller state): every one of the above.

## 11. `main.py` (§7, #3, #15)

- **DONE** — argparse: `--mode bartender|keys|ps5|server|off`, `--no-display` (also auto-detected when
  there is no X/Wayland display, e.g. SSH), `--no-server`, `--mock`, `--buttons`, `--distance`, `-v`.
  Magic mode numbers gone (#15).
- **DONE** — music server + dance controller start in the background in every mode.
- **DONE** — one loop, per-mode `step()`; switching modes (button or code) never needs a restart (§7.3).
- **DONE** — vision step: skips frames it already processed, snapshots the arm pose at capture, reacts
  **every** frame (the "every 3rd frame" throttle only existed because servo moves blocked — §4.1).
- **DONE** — `try/finally` + SIGTERM handler: camera, worker, server, controller and windows are always
  released (Ctrl-C, crash, or `systemctl stop`).
- **DONE** — `Hank.detect()` pass-through removed; mode 2 (PS5) restored.
- **DONE** — GPIO buttons + status LED (§7.3, `--buttons`): GPIO5 cycles bartender → keys → ps5 → off,
  GPIO6 long-press resets the arm, GPIO22 LED blinks the mode number.
- **ADJUSTED** — buttons are **opt-in** (`--buttons`) because they aren't wired yet.
- Verified end-to-end (mock servos + real ncnn model + fake camera fed the Ultralytics sample photo):
  3 people detected with tracker IDs, locked onto #1, greeting played, then tracking followed the
  scene as it slid sideways. Measured capture→command latency ≈ 0.7 s with VS Code running.

## 12. Startup & services — `startup.sh`, `systemd/` (§11, #14)

- **ADJUSTED** — §11's `sudo systemctl enable --now pigpiod` would fail on this Pi with "Unit not found":
  pigpio was built from source (`/usr/local/bin/pigpiod`), so no unit was installed. The sample in
  `pigpio-master/util/` points at `/usr/bin/pigpiod` and uses a relative PID file. Added a corrected
  `systemd/pigpiod.service`.
- **ADJUSTED (security)** — that unit runs `pigpiod -l` (localhost only). By default pigpiod listens on
  port 8888 on **every** interface, so anyone on your Wi-Fi could drive Hank's GPIO pins. (This is also a
  second reason not to move the Spotify redirect to port 8888, as §9 suggested: pigpiod already uses it.)
- **ADJUSTED** — `systemd/hank.service` uses this Pi's real paths (`User=hank`,
  `/home/hank/Documents/Hank`, the `.venv` Python) instead of the plan's `/home/pi/Hank`.
- **DONE** — `startup.sh` is now a one-time, re-runnable setup: installs both units, stops a hand-started
  pigpiod so systemd can own it, and runs `enable --now pigpiod raspotify` (plain `enable` only took effect
  at the next boot). `--with-hank` also starts Hank at boot. Both units pass `systemd-analyze verify`.
- **MANUAL** — needs sudo, so I did not run it: `./startup.sh` (add `--with-hank` once you are happy for
  the arm to start moving at boot). Whether Hank auto-starts is your decision.

## 13. Housekeeping (§12, #22, #23, #24)

- **DONE** — `requirements.txt`: added `pydualsense`, `requests`, `ncnn`; pinned everything to the
  versions working on this Pi now; notes for the apt-only pieces (picamera2, libhidapi, pigpiod).
- **DONE** — untracked committed noise (in the index — **not committed**):
  `git rm -r --cached yolov8n_ncnn_model/__pycache__` and `git rm --cached Design/H-2/desktop.ini`;
  `.gitignore` gains `*.pyc` and `desktop.ini`.
- **BUG I INTRODUCED, AND FIXED** — your old `.gitignore` had no newline at the end, so appending glued
  `*.pyc` onto the `.cache` line (`.cache*.pyc`). That made `.cache` — **your Spotify OAuth token** —
  show up as untracked. Caught it in `git status`, rewrote `.gitignore` cleanly, confirmed with
  `git check-ignore` that `.cache` and `secrets.json` are ignored again. Nothing was committed or pushed.
- **SKIPPED (your call)** — `*.FCBak` FreeCAD backups are still tracked; the plan leaves that to you.
  To stop tracking them: add `*.FCBak` to `.gitignore` and `git rm --cached Design/H-2/*.FCBak`.
- **DONE** — `secrets.json.example` documents the shape (`id`, `secret`, optional `redirect`).
- **DONE** — logging everywhere (see §1 of this log). `-v` only enables Hank's own DEBUG lines; chatty
  libraries (picamera2 logs every frame at DEBUG) stay at INFO.
- **SKIPPED** — PEP 8 class renames (`acts` → `Personality`, …): the plan marks it "someday, do it last
  with the IDE". It would touch every file at once for no behaviour change.
- **DONE** — `readme.md`: run instructions for the new modes/flags, services, mock mode, tools and tests;
  TODO list statuses updated (nothing deleted). `fixes.md` gets a one-line pointer to this log at the top.

## 14. Tests — `tests/test_hank.py` (§5.4)

`python -m unittest discover tests` — 25 tests, all passing, no hardware needed (`HANK_MOCK=1` is forced):
py_compile of every module; control law (direction, deadband, lead, bearing cancels arm motion, pitch);
worker (mock selected, clamping, exact landing, no glide-back after a gesture, `None` holds, `busy()`);
dance locks to the beat (120 BPM → 0.50 s per swing); queue (idle plays now, end advances, mid-song pause
doesn't, no double-advance right after starting); tracking (one person not the average, hold while hidden,
cup when nobody's there); PS5 (light trigger touch ignored, held button fires once, shoulder on stick Y);
keyboard (R fires once while held, arrows repeat, Esc quits).

One test failed on its first run — the dance timing test. That was a mistake in the **test** (I wrote the
expected period as 1.0 s; 120 BPM is 0.5 s, which is what the code produced). Fixed the expectation.

Also exercised by hand (mock servos): `servo_ops.py` CLI, `orientation.py --mode cli`, `main.py --mode
server` serving the page and shutting down cleanly on SIGTERM (exit code 0), and `main.py` bartender mode
on the real camera.

---

## Status of every issue in fixes.md

| # | Status | Where |
|---|--------|-------|
| 1 | DONE | `personality.follow()` rewritten (your partial edit completed) |
| 2 | DONE | your None check kept; history cleared when nothing is in frame |
| 3 | DONE | no import-time side effects in `server.py` / `music.py` |
| 4 | DONE | PS5: server thread on Options, L1+R1 hold-to-quit |
| 5 | DONE | `music.py` self-test |
| 6 | DONE / ADJUSTED | beat-locked looping dance with a real bounce |
| 7 | DONE / ADJUSTED | 403 verified; Deezer with a working query |
| 8 | DONE / partly MANUAL | non-blocking worker, ncnn 320, one-target lead control; speed needs a headless benchmark |
| 9 | DONE | `mock_servos.py`, webcam fallback, lazy evdev, platform guards |
| 10 | DONE / ADJUSTED | worker easing, 1° sweeps; pulse widths left at the old values until calibrated |
| 11 | DONE | queue, skip, advancer, broad exception handling |
| 12 | DONE | single sign convention via bearings |
| 13 | DONE / ADJUSTED | triggers use the analog value; shoulder on stick Y |
| 14 | DONE / ADJUSTED / MANUAL | services written and verified; run `./startup.sh` |
| 15 | DONE | argparse modes |
| 16 | DONE | `wave_one` removed; gesture table |
| 17 | DONE | `orientation.py --mode`, default keys |
| 18 | DONE | ncnn re-exported at 320 and used |
| 19 | DONE | env vars → `secrets.json` fallback |
| 20 | DONE / MANUAL | code + integration; check the ECHO voltage divider |
| 21 | DONE | R/P/C fire on key-down only |
| 22 | DONE | requirements updated and pinned |
| 23 | DONE / your call | pycache + desktop.ini untracked; `.FCBak` left to you |
| 24 | DONE / ADJUSTED | logging done; magic numbers moved to `config.py`; renames skipped |
| 25 | DONE | `center` = `[0, 45, 45]` |

## Test on the Pi (nothing below has been run on real hardware yet)

Do these with the arm clear of obstacles and a hand near the power switch. `python servo_ops.py` then
`limp` (or L in keyboard mode, Create on PS5) cuts the servos instantly.

1. `python servo_ops.py` → `reset`, `curl`, `point`, `jab`, `wave`: gestures should look **smoother** than
   before (eased starts/stops). `jab` should still be snappy; if too slow, raise its speed in `gestures.py`.
2. `python orientation.py` → hold the arrow keys: continuous glide, gentle stop on release. Note where each
   joint hits something and put those numbers in `config.LIMITS`.
3. `python main.py --mock -v` facing a person: check the direction in the debug log first (person right of
   centre → waist target goes **down**). Then without `--mock`. If the waist turns away from people, the
   camera mount is mirrored: flip the sign in `personality.bearing` (or set `CAMERA_ON_ARM` if the camera
   doesn't turn with the waist).
4. Tune `TRACK_KP` (raise until it just overshoots, then back off) and `TRACK_LATENCY_S` (use the
   "latency … ms" debug lines — they read ≈700 ms with VS Code open).
5. `python obj_detection.py` **with VS Code closed** to see whether ncnn really beats `.pt` here.
6. Music page on a phone: search, Play, + Queue, Skip, volume, 🕺 Dance and tap tempo (the page's
   JavaScript has not been run in a browser — Node isn't installed here to check it).
7. raspotify: apply the `/etc/raspotify/conf` settings from before (`LIBRESPOT_NAME="Hank"`), restart it, and
   select "Hank" once in the Spotify app. Right now Spotify only sees `ATTIPC`.
8. `python ps5_controls.py`: triggers, sticks, buttons, hold L1+R1 to quit.
9. Optional: `python calibrate_servo.py <joint>`, then update `config.PULSE_WIDTHS` and re-check the gestures.
10. When happy: `./startup.sh` (then `--with-hank` if Hank should start at boot).

---

## 15. Follow-up: PS5 Bluetooth "br-connection-create-socket" (2026-11-06)

- **Diagnosis** (from `journalctl -u bluetooth`): two failure modes.
  - "Host is down" — the Pi tried to connect while the controller was off/asleep. The Pi can't wake a
    DualSense; the controller connects itself when PS is pressed. The old script fired `connect` once,
    immediately, so it failed whenever the controller wasn't already awake.
  - "Invalid exchange" (the latest attempts) — authentication failure: the Pi still lists the controller
    as paired, but the controller no longer has the Pi's key. A DualSense remembers one host only, so this
    happens after it is paired with a PS5 or a PC. The old script's `pair` just errored `AlreadyExists`.
- **DONE** — `bt_connect.sh` rewritten: exits early if already connected; normal mode tries once and then
  waits 15 s for you to press PS; `--repair` forgets the stale pairing, scans for the controller in pairing
  mode (Create + PS), then pairs, trusts and connects. Verified the normal path and syntax; `--repair` was
  not run (it deletes the stored pairing and needs someone holding the controller).
- **MANUAL** — run `./bt_connect.sh --repair` once in a terminal.
