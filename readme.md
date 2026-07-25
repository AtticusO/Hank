# Hank
Hank is a friendly robotic arm bartender, he can play songs from spotify which the user can select on a locally hosted html page, Hank will also be capable of being controlled through different modes, firstly arrow keys and the press of a key on the keyboard such as r to reset its position, secondly through typed commands, and finally through position adjustment determined by a YOLO inference model which will orient the robot toward the empty cup

## Running Hank (on the Raspberry Pi)

1. **Servo daemon** — the servos use pigpio, which needs its daemon running:
   `sudo pigpiod`
2. **Vision + personality loop** — `python main.py` (camera window, cup/person detection, distance-based reactions)
3. **Keyboard arm control** — `python orientation.py` (arrow keys: left/right = waist, up/down = shoulder, Esc quits)
4. **Servo command line** — `python servo_ops.py` (commands like `jab`, `wave`, `curl`, or angles like `70,50` / `0,70,50`)

## Music page

1. Create a Spotify app at https://developer.spotify.com/dashboard and export:
   `SPOTIPY_CLIENT_ID`, `SPOTIPY_CLIENT_SECRET`, `SPOTIPY_REDIRECT_URI`
2. For playback on the Pi itself install [raspotify](https://github.com/dtcooper/raspotify) so the Pi shows up as a Spotify Connect device (needs Spotify Premium). Otherwise playback goes to any open Spotify app on your account.
3. `python server.py`, then open `http://<pi-ip>:8080` from any phone/laptop on the same network.
   The first run prints a Spotify login URL — open it and paste the redirect URL back into the terminal once.

## Install

```
pip install -r requirements.txt
sudo apt install python3-picamera2   # Pi camera library comes from apt, not pip
```

## TODO (not really in order that much)
1. Adjust 3D models & print and adjust again and print and adjust again
2. Create queue in server.py for song selection
3. Actually make personality.py
4. Clean up servo functions in orientation.py so im not recreating same or similar variables across functions when i dont need to
5. Actually attatch cup detection to servo movement
6. Get distance.py working and implement distance detection into movement
7. Set up some bash files to automatically configure bluetooth to connect to a PS5 controller
8. Wire buttons and implement code for choosing mode of operation such as bartender or controlled
9. Make dance functions with bpm from spotify
10. Tie everything together in a somewhat cohesive process in main.py



