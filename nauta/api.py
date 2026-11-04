"""The Subsonic API with OpenSubsonic extensions, as Navidrome serves it
(docs/subsonic-api.md). Blocking calls meant for worker threads; see
phosh_toolkit.tasks for running them from the UI. No GTK.

Credentials never go into a URL: every request is a POST with the
parameters, user name and token in a form body (OpenSubsonic extension
"formPost")."""
import hashlib
import json
import secrets
from urllib.parse import urlencode

from phosh_toolkit.http import AUTH, SERVER, Client, HttpError

from nauta import CLIENT_NAME, USER_AGENT

# Subsonic API version Nauta speaks; Navidrome answers 1.16.1.
API_VERSION = "1.16.1"
# Extensions Nauta can't work without.
REQUIRED_EXTENSIONS = ("formPost",)
# Subsonic error codes that mean "sign in again" (40 wrong credentials,
# 41 token auth not supported for LDAP users, 44 invalid API key).
AUTH_ERRORS = (40, 41, 44)


def token(password, salt):
    """Subsonic token authentication: md5(password + salt) in hex."""
    return hashlib.md5((password + salt).encode("utf-8")).hexdigest()


class Subsonic:
    def __init__(self, http=None):
        self.http = http or Client(USER_AGENT)
        self.base_url = ""      # set by Connection for the current route
        self.user = ""
        self.password = ""

    # --- plumbing -----------------------------------------------------

    def credentials(self):
        """Form fields that authenticate a request, with a fresh salt."""
        salt = secrets.token_hex(8)
        return {"u": self.user, "t": token(self.password, salt), "s": salt,
                "v": API_VERSION, "c": CLIENT_NAME, "f": "json"}

    def form(self, **params):
        """The encoded form body: parameters and credentials. Lists become
        repeated fields."""
        fields = []
        for key, value in params.items():
            if value is None or value == "":
                continue
            values = value if isinstance(value, (list, tuple)) else [value]
            for v in values:
                if isinstance(v, bool):
                    v = "true" if v else "false"
                fields.append((key, str(v)))
        fields += list(self.credentials().items())
        return urlencode(fields).encode()

    def raw(self, method, base=None, timeout=None, **params):
        """POST /rest/<method>; the response object."""
        return self.http.request(
            "POST", f"{base or self.base_url}/rest/{method}",
            {"Accept": "application/json"}, body=self.form(**params),
            content_type="application/x-www-form-urlencoded", timeout=timeout)

    def call(self, method, base=None, timeout=None, **params):
        """The "subsonic-response" object of a successful call."""
        response = self.raw(method, base, timeout, **params)
        return _answer(response.body)

    # --- server -------------------------------------------------------

    def probe(self, url, timeout=None):
        """Ask the server what it is, without credentials
        (getOpenSubsonicExtensions needs none). Returns the response;
        raises HttpError when it is no OpenSubsonic server Nauta can use."""
        response = self.http.request(
            "POST", f"{url}/rest/getOpenSubsonicExtensions",
            {"Accept": "application/json"}, body=b"f=json",
            content_type="application/x-www-form-urlencoded", timeout=timeout)
        answer = _answer(response.body, allow_failed=True)
        names = {e.get("name") for e in answer.get("openSubsonicExtensions") or []}
        if not answer.get("openSubsonic") or not set(REQUIRED_EXTENSIONS) <= names:
            raise HttpError(SERVER, "Nauta needs an OpenSubsonic server such as "
                                    "Navidrome")
        return answer

    def ping(self, base=None):
        return self.call("ping", base)

    # --- library ------------------------------------------------------

    def albums(self, kind="newest", size=60, offset=0):
        """getAlbumList2: kind is newest, recent, frequent, random,
        alphabeticalByName, alphabeticalByArtist or starred."""
        answer = self.call("getAlbumList2", type=kind, size=size, offset=offset)
        return (answer.get("albumList2") or {}).get("album") or []

    def artists(self):
        """All artists, flattened from the A–Z index."""
        answer = self.call("getArtists")
        out = []
        for index in (answer.get("artists") or {}).get("index") or []:
            out += index.get("artist") or []
        return out

    def artist(self, artist_id):
        """The artist with its "album" list."""
        return self.call("getArtist", id=artist_id).get("artist") or {}

    def album(self, album_id):
        """The album with its "song" list."""
        return self.call("getAlbum", id=album_id).get("album") or {}

    def playlists(self):
        return (self.call("getPlaylists").get("playlists") or {}).get("playlist") or []

    def playlist(self, playlist_id):
        """The playlist with its "entry" list of songs."""
        return self.call("getPlaylist", id=playlist_id).get("playlist") or {}

    def search(self, query, count=20):
        """{"artist": […], "album": […], "song": […]}"""
        result = self.call("search3", query=query, artistCount=count,
                           albumCount=count, songCount=count * 2)
        found = result.get("searchResult3") or {}
        return {k: found.get(k) or [] for k in ("artist", "album", "song")}

    def cover(self, cover_id, size):
        """Image bytes of a cover, scaled by the server to `size` pixels."""
        response = self.raw("getCoverArt", id=cover_id, size=size)
        if _header(response, "Content-Type").startswith("application/json"):
            _answer(response.body)
            raise HttpError(SERVER, "No cover")
        return response.body

    def scrobble(self, song_id, submission):
        """Now playing (submission False) or played (True)."""
        self.call("scrobble", id=song_id, submission=submission)

    # --- streaming ----------------------------------------------------

    def stream_path(self, song_id, max_bitrate=0):
        """The path of a song's audio for the media proxy; credentials go
        into the body (stream_body)."""
        query = {"id": song_id}
        if max_bitrate:
            query["maxBitRate"] = max_bitrate
        return "/rest/stream?" + urlencode(query)

    def stream_body(self):
        return self.form()


def _header(response, name):
    for key, value in response.headers.items():
        if key.lower() == name.lower():
            return value
    return ""


def _answer(body, allow_failed=False):
    try:
        answer = json.loads(body)["subsonic-response"]
    except (ValueError, KeyError, TypeError):
        raise HttpError(SERVER, "This is not a Subsonic server") from None
    if answer.get("status") == "failed" and not allow_failed:
        error = answer.get("error") or {}
        code = error.get("code")
        message = error.get("message") or "Server error"
        if code in AUTH_ERRORS:
            raise HttpError(AUTH, message)
        raise HttpError(SERVER, message)
    return answer
