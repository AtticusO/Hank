## dance.py — dances to whatever Spotify is playing (fixes.md §2.4).
##
## When dancing is switched on (music page, or start()), a watcher thread polls
## Spotify every DANCE_POLL_S seconds — not every beat — and:
##   * song playing  -> look up its BPM (Deezer) and dance at that tempo
##   * song changes  -> re-fetch the BPM and restart at the new tempo
##   * paused/ended  -> stop dancing (the arm resets)
## A tapped tempo from the page (`bpm`) overrides the lookup and also works
## when the BPM is unknown. While dancing, arm.busy() is True, so tracking
## backs off; it resumes on its own when the dance ends.

import logging
import threading
import time

import config

log = logging.getLogger(__name__)


class DanceController:
    def __init__(self, arm, music_mod=None, poll_s=None):
        if music_mod is None:
            import music as music_mod
        self.arm = arm
        self.music = music_mod
        self.poll_s = config.DANCE_POLL_S if poll_s is None else poll_s
        self.enabled = False
        self.manual_bpm = None
        self.bpm = None
        self.track_id = None
        self.playing = False
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._dance_thread = None
        self._watcher = None

    ## ------------------------------------------------------------ public API
    def start(self, bpm=None):
        with self._lock:
            self.enabled = True
            self.manual_bpm = float(bpm) if bpm else None
        log.info("Dance on%s", f" at {bpm:.0f} BPM (tapped)" if bpm else "")
        if self._watcher is None or not self._watcher.is_alive():
            self._watcher = threading.Thread(target=self._watch, name="DanceWatcher", daemon=True)
            self._watcher.start()
        self._wake.set()                      # react now, not at the next poll

    def stop(self):
        with self._lock:
            self.enabled = False
        self.arm.stop_dance()
        self._wake.set()
        log.info("Dance off")

    def status(self):
        return {"on": self.enabled, "dancing": self.arm.dancing.is_set(),
                "bpm": self.manual_bpm or self.bpm}

    ## The server calls this right after it starts a track (faster than polling)
    def on_track_start(self, name=None, artist=None, track_id=None):
        self._wake.set()

    ## --------------------------------------------------------------- watcher
    def _watch(self):
        while self.enabled:
            self._tick()
            self._wake.wait(self.poll_s)
            self._wake.clear()
        self.arm.stop_dance()

    def _tick(self):
        try:
            now = self.music.now_playing()
        except Exception as e:                # Spotify down / not configured
            log.debug("now_playing failed: %s", e)
            now = None if not self.manual_bpm else {"is_playing": True, "id": self.track_id}
        self.playing = bool(now and now.get("is_playing"))
        if not self.playing and not self.manual_bpm:
            self.arm.stop_dance()
            return
        track = now.get("id") if now else None
        if track != self.track_id:
            self.track_id = track
            self.bpm = None
            if not self.manual_bpm and now:
                self.bpm = self.music.track_bpm(track, now.get("name"), now.get("artist"))
                if not self.bpm:
                    log.info("No BPM for %s — tap the tempo on the music page", now.get("name"))
            self.arm.stop_dance()             # restart at the new tempo
        tempo = self.manual_bpm or self.bpm
        if tempo and not self.arm.dancing.is_set():
            self._begin(tempo)

    def _begin(self, tempo):
        if self._dance_thread is not None and self._dance_thread.is_alive():
            self._dance_thread.join(timeout=3)   # let the previous dance reset first
        track = self.track_id

        def keep_going():
            return (self.enabled and (self.playing or self.manual_bpm)
                    and self.track_id == track and (self.manual_bpm or self.bpm) == tempo)

        self._dance_thread = threading.Thread(target=self.arm.dance, args=(tempo, keep_going),
                                              name="Dance", daemon=True)
        self._dance_thread.start()
        time.sleep(0.05)                      # let dancing.set() land before the next check
