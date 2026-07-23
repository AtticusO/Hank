## Spotify playback for Hank via the Spotify Web API (spotipy).
##
## Needs these environment variables (create an app at
## https://developer.spotify.com/dashboard to get them):
## Playback lands on whatever Spotify Connect device is available — on the
## Pi itself that means running raspotify (https://github.com/dtcooper/raspotify).
## The first run asks you to open a URL and paste the redirect back in the
## terminal; after that spotipy's token cache handles refresh automatically.
import json
import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth

with open("secrets.json", "r") as file:
    config = json.load(file)

SPOTIPY_CLIENT_ID = config["id"]
SPOTIPY_CLIENT_SECRET = config["secret"]
SPOTIPY_REDIRECT_URI = "http://localhost.com"
SCOPES = "user-modify-playback-state user-read-playback-state"

_client = None


class MusicError(Exception):
    """Raised with a human-readable message the web page can display."""


def _get_client():
    ## Lazy so importing this module never crashes when Spotify isn't set up yet
    global _client
    if _client is None:
        #if not (os.environ.get("SPOTIPY_CLIENT_ID") and os.environ.get("SPOTIPY_CLIENT_SECRET")):
        #    raise MusicError(
        #        "Spotify is not configured — set SPOTIPY_CLIENT_ID, "
        #        "SPOTIPY_CLIENT_SECRET and SPOTIPY_REDIRECT_URI"
        #    )
        _client = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=SPOTIPY_CLIENT_ID,
            client_secret=SPOTIPY_CLIENT_SECRET,
            redirect_uri=SPOTIPY_REDIRECT_URI,
            scope=SCOPES))
    return _client


def _album_art(item):
    images = item["album"]["images"]
    return images[-1]["url"] if images else None


def search(query, limit=10):
    """Returns a list of {name, artist, uri, album_art} for the query."""
    sp = _get_client()
    try:
        found = sp.search(q=query, limit=limit, type="track")
    except spotipy.SpotifyException as e:
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


def play(uri):
    ## Plays a track URI on the active device, or the first available one.
    sp = _get_client()
    try:
        sp.start_playback(uris=[uri])
    except spotipy.SpotifyException:
        ## No active device — target whichever device Spotify can see
        ## (raspotify shows up here even when idle)
        devices = sp.devices().get("devices", [])
        if not devices:
            raise MusicError(
                "No Spotify device found — is raspotify running, "
                "or a Spotify app open somewhere?"
            )
        try:
            sp.start_playback(device_id=devices[0]["id"], uris=[uri])
        except spotipy.SpotifyException as e:
            raise MusicError(f"Could not start playback: {e.msg}")


def pause():
    sp = _get_client()
    try:
        sp.pause_playback()
    except spotipy.SpotifyException as e:
        raise MusicError(f"Could not pause: {e.msg}")


def resume():
    sp = _get_client()
    try:
        sp.start_playback()
    except spotipy.SpotifyException as e:
        raise MusicError(f"Could not resume: {e.msg}")


def now_playing():
    ## Returns {name, artist, album_art, is_playing} or None if nothing is on.
    sp = _get_client()
    try:
        current = sp.current_playback()
    except spotipy.SpotifyException as e:
        raise MusicError(f"Could not fetch playback state: {e.msg}")
    if not current or not current.get("item"):
        return None
    item = current["item"]
    return {
        "name": item["name"],
        "artist": ", ".join(a["name"] for a in item["artists"]),
        "album_art": _album_art(item),
        "is_playing": current["is_playing"],
    }


def dance(track_id, track_name, artist):
    sp = _get_client()
    audio_features = sp.audio_features(track_id)[0]
    
    if audio_features:
        # Extract the 'tempo' key which represents the BPM
        bpm = audio_features["tempo"]
        print(f"Song: {track_name} by {artist}")
        print(f"BPM: {bpm}")
        return bpm
    else:
        print("Audio features not available for this track.")


if __name__ == "__main__":
    play("Gangsters Paradise")
