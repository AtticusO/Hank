## Spotify playback for Hank via the Spotify Web API (spotipy).
##
## Credentials (create an app at https://developer.spotify.com/dashboard):
##   1. env vars SPOTIPY_CLIENT_ID / SPOTIPY_CLIENT_SECRET (/ SPOTIPY_REDIRECT_URI), or
##   2. secrets.json next to this file: {"id": "...", "secret": "..."}  (see secrets.json.example)
## Nothing is read at import time, so importing this module never fails offline.
##
## Playback lands on whatever Spotify Connect device is available — on the
## Pi itself that means raspotify (https://github.com/dtcooper/raspotify).
## The first run asks you to open a URL and paste the redirect back in the
## terminal; after that spotipy's token cache handles refresh automatically.

import difflib
import json
import logging
import os

import config

log = logging.getLogger(__name__)

SCOPES = "user-modify-playback-state user-read-playback-state"

_client = None
_features_dead = False       # set after Spotify answers audio_features with 403


class MusicError(Exception):
    """Raised with a human-readable message the web page can display."""


def _credentials():
    cid = os.environ.get("SPOTIPY_CLIENT_ID")
    secret = os.environ.get("SPOTIPY_CLIENT_SECRET")
    redirect = os.environ.get("SPOTIPY_REDIRECT_URI")
    if not (cid and secret):
        path = os.path.join(config.DIR, "secrets.json")
        try:
            with open(path) as f:
                data = json.load(f)
            cid, secret = data["id"], data["secret"]
            redirect = redirect or data.get("redirect")
        except FileNotFoundError:
            raise MusicError("Spotify is not configured — set SPOTIPY_CLIENT_ID and "
                             "SPOTIPY_CLIENT_SECRET, or create secrets.json (see secrets.json.example)")
        except (KeyError, ValueError) as e:
            raise MusicError(f"secrets.json is malformed ({e}) — see secrets.json.example")
    return cid, secret, redirect or config.SPOTIFY_REDIRECT_URI


def _get_client():
    ## Lazy so importing this module never crashes when Spotify isn't set up yet
    global _client
    if _client is None:
        import spotipy
        from spotipy.oauth2 import SpotifyOAuth
        cid, secret, redirect = _credentials()
        _client = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=cid, client_secret=secret, redirect_uri=redirect, scope=SCOPES,
            cache_path=os.path.join(config.DIR, ".cache")), requests_timeout=10)
    return _client


def _spotify_error():
    import spotipy
    return spotipy.SpotifyException


def _album_art(item):
    images = item["album"]["images"]
    return images[-1]["url"] if images else None


def search(query, limit=10):
    """Returns a list of {name, artist, uri, album_art} for the query."""
    sp = _get_client()
    try:
        found = sp.search(q=query, limit=limit, type="track")
    except _spotify_error() as e:
        raise MusicError(f"Spotify search failed: {e.msg}")
    return [
        {
            "name": item["name"],
            "artist": ", ".join(a["name"] for a in item["artists"]),
            "uri": item["uri"],
            "album_art": _album_art(item),
        }
        for item in found["tracks"]["items"]
    ]


def devices():
    sp = _get_client()
    try:
        return sp.devices().get("devices", [])
    except _spotify_error() as e:
        raise MusicError(f"Could not list devices: {e.msg}")


def _pick_device(devs):
    ## Prefer Hank's own raspotify device so music never lands in a random browser tab
    name = (config.SPOTIFY_DEVICE_NAME or "").lower()
    for d in devs:
        if name and d.get("name", "").lower() == name:
            return d
    return devs[0]


def play(uri):
    ## Plays a track URI on the active device, or Hank's device / the first available one.
    sp = _get_client()
    err = _spotify_error()
    try:
        sp.start_playback(uris=[uri])
    except err:
        ## No active device — target whichever device Spotify can see
        ## (raspotify shows up here even when idle)
        devs = devices()
        if not devs:
            raise MusicError("No Spotify device found — is raspotify running, "
                             "or a Spotify app open somewhere?")
        try:
            sp.start_playback(device_id=_pick_device(devs)["id"], uris=[uri])
        except err as e:
            raise MusicError(f"Could not start playback: {e.msg}")


def pause():
    sp = _get_client()
    try:
        sp.pause_playback()
    except _spotify_error() as e:
        raise MusicError(f"Could not pause: {e.msg}")


def resume():
    sp = _get_client()
    try:
        sp.start_playback()
    except _spotify_error() as e:
        raise MusicError(f"Could not resume: {e.msg}")


def volume(percent):
    sp = _get_client()
    try:
        sp.volume(max(0, min(100, int(percent))))
    except _spotify_error() as e:
        raise MusicError(f"Could not set volume: {e.msg}")


def now_playing():
    ## Returns {id, name, artist, album_art, is_playing, progress_ms, duration_ms, volume}
    ## or None if nothing is on.
    sp = _get_client()
    try:
        current = sp.current_playback()
    except _spotify_error() as e:
        raise MusicError(f"Could not fetch playback state: {e.msg}")
    if not current or not current.get("item"):
        return None
    item = current["item"]
    return {
        "id": item.get("id"),
        "name": item["name"],
        "artist": ", ".join(a["name"] for a in item["artists"]),
        "album_art": _album_art(item),
        "is_playing": current["is_playing"],
        "progress_ms": current.get("progress_ms") or 0,
        "duration_ms": item.get("duration_ms") or 0,
        "volume": (current.get("device") or {}).get("volume_percent"),
    }


## ----------------------------------------------------------------- tempo
## Spotify removed audio_features for apps created after Nov 2024 (verified:
## this app gets HTTP 403), so BPM comes from Deezer's free public API.

def _similar(a, b):
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()


def deezer_bpm(track, artist):
    ## BPM from Deezer, or None. Deezer's strict `track:"…" artist:"…"` search
    ## syntax returns nothing, so this does a plain search and checks the match.
    import requests
    first_artist = artist.split(",")[0].strip()
    try:
        hits = requests.get("https://api.deezer.com/search",
                            params={"q": f"{track} {first_artist}"}, timeout=5).json().get("data", [])
        hits = [h for h in hits[:10] if _similar(h.get("artist", {}).get("name", ""), first_artist) > 0.6]
        hits.sort(key=lambda h: _similar(h.get("title", ""), track), reverse=True)
        for hit in hits[:3]:
            t = requests.get(f"https://api.deezer.com/track/{hit['id']}", timeout=5).json()
            if t.get("bpm"):                         # 0 means unknown
                return float(t["bpm"])
    except (requests.RequestException, ValueError) as e:
        log.warning("Deezer BPM lookup failed: %s", e)
    return None


def track_bpm(track_id=None, track_name=None, artist=None):
    ## Spotify first (works only for grandfathered apps), then Deezer
    global _features_dead
    if track_id and not _features_dead:
        try:
            feats = _get_client().audio_features([track_id])
            if feats and feats[0] and feats[0].get("tempo"):
                return float(feats[0]["tempo"])
        except Exception as e:
            _features_dead = getattr(e, "http_status", None) == 403
            log.debug("Spotify audio_features unavailable: %s", e)
    if track_name and artist:
        bpm = deezer_bpm(track_name, artist)
        if bpm:
            log.info("BPM for %s - %s: %.1f (Deezer)", track_name, artist, bpm)
        return bpm
    return None


## Old name kept for compatibility
def dance(track_id, track_name, artist):
    return track_bpm(track_id, track_name, artist)


if __name__ == "__main__":
    config.setup_logging()
    hits = search("Little Wing")
    if hits:
        play(hits[0]["uri"])
        print("Playing", hits[0]["name"], "-", hits[0]["artist"])
