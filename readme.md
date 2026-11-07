# Hank
Hank is a friendly robotic arm bartender, he can play songs from spotify which the user can select on a locally hosted html page, Hank will also be capable of being controlled through different modes, firstly arrow keys and the press of a key on the keyboard such as r to reset its position, secondly through typed commands, and finally through position adjustment determined by a YOLO inference model which will orient the robot toward the empty cup

## Running Hank (on the Raspberry Pi)

One-time setup (makes `pigpiod` and `raspotify` start at boot, installs `hank.service`):

```
./startup.sh                 # add --with-hank to also start Hank at every boot
```

Then everything runs from one process:

| Command | What it does |
|---|---|
| `python main.py` | **bartender**: camera + YOLO person/cup tracking + greetings + music page |
| `python main.py --mode keys` | keyboard jog (see below) |
| `python main.py --mode ps5` | PS5 controller (see below) |
| `python main.py --mode server` | music page only (dancing still works) |
| `--no-display` | no camera window (automatic over SSH) · `--no-server` skip the music page |
| `--buttons` | GPIO mode buttons: GPIO5 cycles modes, GPIO6 hold = reset, LED on GPIO22 blinks the mode |
| `--distance` | ultrasonic sensor: lean in when something is closer than 15 cm |
| `--mock` | simulate the servos — nothing moves (laptop, or testing on the Pi) |
| `-v` | debug logging (tracking latency, key presses, servo state) |

As a service: `sudo systemctl enable --now hank`, logs with `journalctl -u hank -f`.

Other tools:

- `python orientation.py` — keyboard jog: arrows / Z X = waist, up/down / A D = shoulder, W E = elbow;
  R reset, P point, C curl, J jab, F fist bump, V / B wave, L go limp, Esc quit.
  `--mode cli` to type gesture names, `--mode dance --bpm 120` to dance.
- `python servo_ops.py` — servo command line (`jab`, `jj`, `wave`, `curl`, `limp`, or angles `70,50` / `0,70,50`)
- `python ps5_controls.py` — PS5: L2/R2 waist, left stick shoulder, right stick elbow, D-pad speed,
  Cross reset, Square jab, Triangle point, Circle curl, Options music server, Create limp, hold L1+R1 to quit
- `python calibrate_servo.py <joint>` — find a servo's real pulse-width range for `config.py`
- `python obj_detection.py` — benchmark the ncnn vs PyTorch model on this machine
- `python -m unittest discover tests` — tests (no hardware needed)

All tunables (pins, home pose, limits, speeds, tracking gains, camera FOV) live in `config.py`.

## Music page

1. Create a Spotify app at https://developer.spotify.com/dashboard and either put its credentials in
   `secrets.json` (copy `secrets.json.example`) or export `SPOTIPY_CLIENT_ID` / `SPOTIPY_CLIENT_SECRET`.
   The redirect URI registered on the dashboard must match `config.SPOTIFY_REDIRECT_URI`
   (`http://127.0.0.1:8080/callback`).
2. For playback on the Pi itself install [raspotify](https://github.com/dtcooper/raspotify) so the Pi shows up as a Spotify Connect device (needs Spotify Premium). Name it `Hank` (`LIBRESPOT_NAME` in `/etc/raspotify/conf`) — Hank prefers that device.
3. Open `http://<pi-ip>:8080` from any phone/laptop on the same network: search, **Play** now or **+ Queue**,
   skip, volume, and **🕺 Dance** (BPM comes from Deezer; tap the tempo if a song has none).
   The first run prints a Spotify login URL — open it and paste the redirect URL back into the terminal once.

## Laptop development

`HANK_MOCK=1 python main.py` (or `--mock`) runs the whole stack with mock servos; without picamera2 the
camera falls back to your webcam (`HANK_WEBCAM=1` forces it). Keyboard mode needs Linux (evdev).

## Install

```
pip install -r requirements.txt
sudo apt install python3-picamera2 libhidapi-hidraw0   # camera library + PS5 controller (hidapi)
```

## TODO (not really in order that much)
1. Adjust 3D models & print and adjust again and print and adjust again
2. $ Create queue in server.py for song selection $ DONE
3. Actually make personality.py — tracking (one person, lead), greetings, cup aiming and lean-in done; more personality welcome
4. $ Clean up servo functions in orientation.py $ DONE (gesture table in gestures.py)
5. $ Actually attach cup detection to servo movement $ DONE in code (aims at a cup when nobody is around) — needs testing
6. Get distance.py working — code integrated (`--distance`); check the 5 V → 3.3 V divider on ECHO
7. $ Set up some bash files to automatically configure bluetooth to connect to a PS5 controller $ DONE : WORKS
8. $ Make mock servos so I can test on devices other than rasp pi $ DONE (`HANK_MOCK=1`)
9. Wire buttons and implement code for choosing mode of operation — code done (`--buttons`), wiring left
10. $ Make dance functions with bpm from spotify $ DONE (Spotify removed BPM, so it comes from Deezer)
11. $ Add all the infrastructure for raspotify $ DONE (startup.sh + systemd units)
12. $ Tie everything together in a somewhat cohesive process in main.py $ DONE
13. Calibrate servo pulse widths and measure joint limits (`calibrate_servo.py`, `config.py`)
