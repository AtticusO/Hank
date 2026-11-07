## Hank's music page server: serves index.html and small JSON endpoints
## that drive Spotify playback through music.py
##
##   GET  /            the song-selection page
##   GET  /search?q=   search Spotify tracks
##   GET  /status      what's playing right now
##   GET  /queue       upcoming songs
##   GET  /dance       dance status
##   POST /play        {"uri", "name"?, "artist"?}   play now
##   POST /queue       {"uri", "name", "artist", "album_art"?}  add; plays at once if idle
##   POST /skip        play the next queued song
##   POST /pause       pause playback
##   POST /resume      resume playback
##   POST /volume      {"percent": 0-100}
##   POST /dance       {"on": bool, "bpm"?: number}  (needs the arm: run via main.py)
##
## Nothing happens at import time (no sockets, no secrets), so importing this
## module never crashes offline.

import collections
import json
import logging
import os
import socket
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import config
import music

log = logging.getLogger(__name__)

HOST = "0.0.0.0"          # bind every interface; lan_ip() is only for the "open this URL" message
PORT = config.SERVER_PORT
_DIR = config.DIR

## Song queue (fixes.md §6)
queue = collections.deque()      # of {"uri", "name", "artist", "album_art"}
queue_lock = threading.Lock()
_last_started = 0.0              # monotonic time we last started a track
dance_controller = None          # set by main.py via attach_dance()
_advancer = None


def lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


def attach_dance(controller):
    global dance_controller
    dance_controller = controller


## ----------------------------------------------------------- queue logic
def _ended(now):
    ## True when nothing is playing because the song finished — not because a
    ## guest paused it mid-song (that's left alone)
    if now is None:
        return True
    if now.get("is_playing"):
        return False
    progress, duration = now.get("progress_ms", 0), now.get("duration_ms", 0)
    return progress == 0 or (duration and progress >= duration - 2000)


def play_entry(entry):
    global _last_started
    music.play(entry["uri"])
    _last_started = time.monotonic()
    if dance_controller is not None:
        dance_controller.on_track_start(entry.get("name"), entry.get("artist"))
    log.info("Playing %s - %s", entry.get("name", entry["uri"]), entry.get("artist", ""))
    return entry


def enqueue(entry):
    ## Adds a song; if the player is idle, starts it right away. Returns the queue.
    with queue_lock:
        queue.append(entry)
        if time.monotonic() - _last_started > 5 and _ended(music.now_playing()):
            play_entry(queue.popleft())
        return list(queue)


def skip():
    with queue_lock:
        if not queue:
            return None
        return play_entry(queue.popleft())


def advance_once():
    ## One advancer step: next song when the current one has ended
    with queue_lock:
        if not queue or time.monotonic() - _last_started < 5:   # just started one: wait for Spotify
            return None
        if _ended(music.now_playing()):
            return play_entry(queue.popleft())
    return None


def _advance_loop():
    last_err = 0.0
    while True:
        time.sleep(config.QUEUE_POLL_S)
        try:
            advance_once()
        except Exception as e:                    # never let the advancer die
            if time.monotonic() - last_err > 60:
                log.warning("Queue advancer: %s", e)
                last_err = time.monotonic()


def start_advancer():
    global _advancer
    if _advancer is None or not _advancer.is_alive():
        _advancer = threading.Thread(target=_advance_loop, name="QueueAdvancer", daemon=True)
        _advancer.start()


## --------------------------------------------------------------- handler
class HankHandler(BaseHTTPRequestHandler):

    def send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    ## Runs a call and wraps the outcome in a consistent JSON shape:
    ## {"ok": true, "result": ...} on success, {"error": "..."} on failure.
    ## Any exception (spotipy, network) becomes a 500 instead of killing the thread.
    def music_action(self, fn, *args):
        try:
            self.send_json({"ok": True, "result": fn(*args)})
        except music.MusicError as e:
            self.send_json({"error": str(e)}, 502)
        except Exception as e:
            log.exception("Handler error on %s", self.path)
            self.send_json({"error": f"Server error: {e}"}, 500)

    def _body(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        try:
            data = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self.send_json({"error": "invalid JSON"}, 400)
            return None
        if not isinstance(data, dict):
            self.send_json({"error": "expected a JSON object"}, 400)
            return None
        return data

    def _send_page(self):
        with open(os.path.join(_DIR, "index.html"), "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/":
            self._send_page()
        elif parsed.path == "/search":
            q = urllib.parse.parse_qs(parsed.query).get("q", [""])[0].strip()
            if not q:
                self.send_json({"error": "empty search"}, 400)
            else:
                self.music_action(music.search, q)
        elif parsed.path == "/status":
            self.music_action(music.now_playing)
        elif parsed.path == "/queue":
            with queue_lock:
                self.send_json({"ok": True, "result": list(queue)})
        elif parsed.path == "/dance":
            if dance_controller is None:
                self.send_json({"ok": True, "result": {"available": False}})
            else:
                self.send_json({"ok": True, "result": dict(dance_controller.status(), available=True)})
        else:
            self.send_json({"error": "not found"}, 404)

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if path in ("/pause", "/resume", "/skip"):
            fn = {"/pause": music.pause, "/resume": music.resume, "/skip": skip}[path]
            self.music_action(fn)
            return
        data = self._body()
        if data is None:
            return
        if path in ("/play", "/queue"):
            uri = data.get("uri")
            if not uri:
                self.send_json({"error": "missing uri"}, 400)
                return
            entry = {"uri": uri, "name": data.get("name", ""), "artist": data.get("artist", ""),
                     "album_art": data.get("album_art")}
            self.music_action(play_entry if path == "/play" else enqueue, entry)
        elif path == "/volume":
            try:
                pct = int(data.get("percent"))
            except (TypeError, ValueError):
                self.send_json({"error": "percent must be 0-100"}, 400)
                return
            self.music_action(music.volume, pct)
        elif path == "/dance":
            if dance_controller is None:
                self.send_json({"error": "Dancing needs the arm — start Hank with main.py"}, 503)
                return
            try:
                bpm = float(data["bpm"]) if data.get("bpm") else None
            except (TypeError, ValueError):
                self.send_json({"error": "bpm must be a number"}, 400)
                return
            if bpm is not None and not 40 <= bpm <= 220:
                self.send_json({"error": "bpm must be between 40 and 220"}, 400)
                return
            if data.get("on", True):
                dance_controller.start(bpm)
            else:
                dance_controller.stop()
            self.send_json({"ok": True, "result": dance_controller.status()})
        else:
            self.send_json({"error": "not found"}, 404)

    ## Request lines at DEBUG (the page polls /status every 5 s)
    def log_message(self, fmt, *args):
        log.debug("%s - %s", self.address_string(), fmt % args)


def start_server(background=False, port=PORT):
    ## background=True runs it on a daemon thread and returns the server object
    server = ThreadingHTTPServer((HOST, port), HankHandler)
    server.daemon_threads = True
    start_advancer()
    log.info("Hank music server running at http://%s:%s", lan_ip(), port)
    if background:
        threading.Thread(target=server.serve_forever, name="MusicServer", daemon=True).start()
        return server
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return server


## Old name kept so existing callers keep working
def _start_server():
    return start_server()


if __name__ == "__main__":
    config.setup_logging()
    start_server()
