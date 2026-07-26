## Hank's music page server: serves index.html and small JSON endpoints
## that drive Spotify playback through music.py
## Need to make a queue system incase multiple people try to play songs
## Need to 
##
##   GET  /            the song-selection page
##   GET  /search?q=   search Spotify tracks
##   GET  /status      what's playing right now
##   POST /play        {"uri": "spotify:track:..."} start a track
##   POST /pause       pause playback
##   POST /resume      resume playback

import json
import os
import socket
import urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import music
import subprocess

## create a UDP socket to get lan ip
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.connect(("8.8.8.8", 80))
lan_ip = s.getsockname()[0]
s.close()

subprocess.run(["spotify"])

HOST = lan_ip   ## reachable from phones on the LAN
PORT = 8080

_DIR = os.path.dirname(os.path.abspath(__file__))


class HankHandler(BaseHTTPRequestHandler):

    def send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    ## Runs a music.py call and wraps the outcome in a consistent JSON shape:
    ## {"ok": true, "result": ...} on success, {"error": "..."} on failure
    def music_action(self, fn, *args):
        
        try:
            self.send_json({"ok": True, "result": fn(*args)})
        except music.MusicError as e:
            self.send_json({"error": str(e)}, 502)

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
        else:
            self.send_json({"error": "not found"}, 404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/play":
            length = int(self.headers.get("Content-Length", 0))
            try:
                data = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError:
                self.send_json({"error": "invalid JSON"}, 400)
                return
            uri = data.get("uri")
            if not uri:
                self.send_json({"error": "missing uri"}, 400)
            else:
                self.music_action(music.play, uri)
        elif parsed.path == "/pause":
            self.music_action(music.pause)
        elif parsed.path == "/resume":
            self.music_action(music.resume)
        else:
            self.send_json({"error": "not found"}, 404)

    ## One log line per request instead of the default noise
    def log_message(self, fmt, *args):
        print(f"{self.address_string()} - {fmt % args}")


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), HankHandler)
    print(f"Hank music server running at http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
