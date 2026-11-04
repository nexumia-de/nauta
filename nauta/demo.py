"""A small stand-in for a Navidrome server that serves the recorded demo
library (tests/data/demo). The store screenshots use it
(NAUTA_DEMO=<dir>), and the tests run the client, the proxy and mutual
TLS against it. Only the endpoints Nauta calls are implemented, with the
answers shaped like Navidrome's (docs/subsonic-api.md). Covers and audio
are made here: colour gradients and sine tones. DemoMeTube stands in for
the download server and DemoYouTubeMusic for YouTube Music's search of
albums and playlists (docs/downloads.md), in demo_metube.py. No GTK."""
import base64
import colorsys
import hashlib
import io
import json
import math
import ssl
import struct
import threading
import time
import wave
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

PASSWORD = "demo"
EXTENSIONS = ("formPost", "transcodeOffset", "songLyrics", "apiKeyAuthentication")
# Seconds of audio served for every song, whatever its listed duration.
AUDIO_SECONDS = 20


class DemoServer:
    def __init__(self, directory, tls=None):
        """tls: (server cert file, key file, CA file for client
        certificates) for HTTPS that requires a client certificate."""
        self.library = json.loads((Path(directory) / "library.json").read_text())
        self.songs = {s["id"]: s for s in self.library["songs"]}
        self.albums = {a["id"]: a for a in self.library["albums"]}
        self.artists = {a["id"]: a for a in self.library["artists"]}
        self.requests = []     # (method, path, form) seen
        self.arrivals = []     # (monotonic time, method name), for tests
        self.scrobbles = []    # (song id, submission)
        # Changed by star/unstar and the playlist calls, like a server.
        self.starred = set(self.library.get("starred", []))
        self.playlists = [dict(p, entries=list(p["entries"]))
                          for p in self.library["playlists"]]
        self._next_playlist = 1
        # "user:password": like Pangolin's header authentication, refuse
        # requests without this HTTP Basic auth (401 with a challenge).
        self.proxy_basic = None
        self._audio = {}
        self._covers = {}
        server = self

        class Handler(_Handler):
            owner = server

        self.httpd, self.scheme = _server(Handler, tls)

    @property
    def url(self):
        host, port = self.httpd.server_address
        return f"{self.scheme}://{host}:{port}"

    def start(self):
        threading.Thread(target=self.httpd.serve_forever, daemon=True,
                         name="nauta-demo").start()
        return self

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    # --- answers -------------------------------------------------------

    def response(self, **content):
        server = self.library["server"]
        return {"subsonic-response": dict(
            status="ok", version="1.16.1", type=server["type"],
            serverVersion=server["serverVersion"], openSubsonic=True, **content)}

    def error(self, code, message):
        answer = self.response(error={"code": code, "message": message})
        answer["subsonic-response"]["status"] = "failed"
        return answer

    def album_songs(self, album_id):
        return [s for s in self.library["songs"] if s["albumId"] == album_id]

    def answer(self, method, form, lists=None):
        """(JSON answer) or (bytes, content type) for /rest/<method>.
        `lists` holds every value of repeated fields (id=…&id=…)."""
        lists = lists or {}
        lib = self.library
        if method == "getOpenSubsonicExtensions":
            return self.response(openSubsonicExtensions=[
                {"name": name, "versions": [1]} for name in EXTENSIONS])
        user, token, salt = form.get("u"), form.get("t"), form.get("s")
        expected = hashlib.md5((PASSWORD + (salt or "")).encode()).hexdigest()
        if user != lib["user"] or token != expected:
            return self.error(40, "Wrong username or password")
        if method == "ping":
            return self.response()
        if method == "getAlbumList2":
            albums = [self._starred(a) for a in lib["albums"]]
            kind = form.get("type", "newest")
            if kind == "starred":
                albums = [a for a in albums if a["id"] in self.starred]
            elif kind == "recent":
                albums = [a for a in albums if a["playCount"]]
            if kind == "random":
                albums.sort(key=lambda a: hashlib.sha1(a["id"].encode()).digest())
            elif kind == "newest":
                albums.sort(key=lambda a: a["created"], reverse=True)
            elif kind == "frequent":
                albums.sort(key=lambda a: a["playCount"], reverse=True)
            elif kind == "alphabeticalByArtist":
                albums.sort(key=lambda a: (a["artist"].lower(), a["name"].lower()))
            else:
                albums.sort(key=lambda a: a["name"].lower())
            offset, size = int(form.get("offset", 0)), int(form.get("size", 10))
            return self.response(albumList2={"album": albums[offset:offset + size]})
        if method == "getArtists":
            index = {}
            for artist in sorted(lib["artists"], key=lambda a: a["name"].lower()):
                index.setdefault(artist["name"][0].upper(), []).append(artist)
            return self.response(artists={"ignoredArticles": "The", "index": [
                {"name": k, "artist": v} for k, v in index.items()]})
        if method == "getArtist":
            artist = self.artists.get(form.get("id"))
            if artist is None:
                return self.error(70, "Artist not found")
            albums = [a for a in lib["albums"] if a["artistId"] == artist["id"]]
            return self.response(artist=self._starred(dict(artist, album=albums)))
        if method == "getAlbum":
            album = self.albums.get(form.get("id"))
            if album is None:
                return self.error(70, "Album not found")
            return self.response(album=self._starred(dict(
                album, song=[self._starred(s) for s in self.album_songs(album["id"])])))
        if method == "getPlaylists":
            return self.response(playlists={"playlist": [
                self._playlist(p, False) for p in self.playlists]})
        if method == "getPlaylist":
            playlist = self._find_playlist(form.get("id"))
            if playlist is None:
                return self.error(70, "Playlist not found")
            return self.response(playlist=self._playlist(playlist, True))
        answer = self._edit(method, form, lists)
        if answer is not None:
            return answer
        if method == "search3":
            query = (form.get("query") or "").lower().strip('"')

            def hit(*texts):
                return any(query in (t or "").lower() for t in texts)
            return self.response(searchResult3={
                "artist": [a for a in lib["artists"] if hit(a["name"])],
                "album": [a for a in lib["albums"] if hit(a["name"], a["artist"])],
                "song": [self._starred(s) for s in lib["songs"]
                         if hit(s["title"])][:40]})
        if method == "scrobble":
            self.scrobbles.append((form.get("id"), form.get("submission", "true") == "true"))
            return self.response()
        if method == "getCoverArt":
            size = min(int(form.get("size") or 300), 600)
            return self.cover(form.get("id", ""), size), "image/png"
        if method == "stream":
            if form.get("id") not in self.songs:
                return self.error(70, "Song not found")
            return self.audio(form["id"]), "audio/wav"
        return self.error(0, f"Not in the demo: {method}")

    # --- likes, playlists, discovery and lyrics -------------------------

    def _edit(self, method, form, lists):
        """The calls that change or find more than the library: likes,
        playlists, similar songs and artists, top songs, lyrics. None for
        other methods."""
        lib = self.library
        if method in ("star", "unstar"):
            ids = lists.get("id", []) + lists.get("albumId", []) + \
                lists.get("artistId", [])
            if not ids:
                return self.error(10, "Required id parameter is missing")
            for i in ids:
                (self.starred.add if method == "star" else self.starred.discard)(i)
            return self.response()
        if method == "getStarred2":
            return self.response(starred2={
                "artist": [self._starred(a) for a in lib["artists"]
                           if a["id"] in self.starred],
                "album": [self._starred(a) for a in lib["albums"]
                          if a["id"] in self.starred],
                "song": [self._starred(s) for s in lib["songs"]
                         if s["id"] in self.starred]})
        if method == "createPlaylist":
            ids = lists.get("songId", [])
            if form.get("playlistId"):
                playlist = self._find_playlist(form["playlistId"])
                if playlist is None:
                    return self.error(70, "playlist not found")
                playlist["entries"] = list(ids)
            elif form.get("name"):
                playlist = {"id": f"pl-new-{self._next_playlist}",
                            "name": form["name"], "owner": lib["user"],
                            "public": False, "entries": list(ids)}
                self._next_playlist += 1
                self.playlists.append(playlist)
            else:
                return self.error(0, "required parameter name is missing")
            return self.response(playlist=self._playlist(playlist, True))
        if method == "updatePlaylist":
            playlist = self._find_playlist(form.get("playlistId"))
            if playlist is None:
                return self.error(70, "playlist not found")
            if "name" in form:
                playlist["name"] = form["name"]
            remove = {int(i) for i in lists.get("songIndexToRemove", [])}
            playlist["entries"] = [e for i, e in enumerate(playlist["entries"])
                                   if i not in remove] + lists.get("songIdToAdd", [])
            return self.response()
        if method == "deletePlaylist":
            playlist = self._find_playlist(form.get("id"))
            if playlist is None:
                return self.error(70, "playlist not found")
            self.playlists.remove(playlist)
            return self.response()
        if method == "getSimilarSongs2":
            return self.response(similarSongs2={"song": self._similar_songs(
                form.get("id"), int(form.get("count") or 50))})
        if method == "getTopSongs":
            artist = next((a for a in lib["artists"]
                           if a["name"] == form.get("artist")), None)
            songs = [] if artist is None else sorted(
                (s for s in lib["songs"] if s["artistId"] == artist["id"]),
                key=lambda s: hashlib.sha1(s["id"].encode()).digest())
            return self.response(topSongs={"song": [
                self._starred(s) for s in songs[:int(form.get("count") or 50)]]})
        if method == "getArtistInfo2":
            similar = lib.get("similar", {}).get(form.get("id"), [])
            return self.response(artistInfo2={"similarArtist": [
                self._starred(self.artists[i]) for i in similar]})
        if method == "getLyricsBySongId":
            if form.get("id") not in self.songs:
                return self.error(70, "Song not found")
            lyrics = lib.get("lyrics", {}).get(form["id"])
            song = self.songs[form["id"]]
            structured = [] if lyrics is None else [{
                "displayArtist": song["artist"], "displayTitle": song["title"],
                "lang": "eng", "synced": lyrics["synced"],
                "line": [{"start": start, "value": value} if lyrics["synced"]
                         else {"value": value} for start, value in lyrics["lines"]]}]
            return self.response(lyricsList={"structuredLyrics": structured}
                                 if structured else {})
        return None

    def _similar_songs(self, item_id, count):
        """Songs of the similar artists of a song's, album's or artist's
        artist, never the item's own songs."""
        lib = self.library
        artist_id = (self.songs.get(item_id) or self.albums.get(item_id)
                     or {}).get("artistId") or item_id
        if artist_id not in self.artists:
            return []
        others = set(lib.get("similar", {}).get(artist_id, []))
        songs = [s for s in lib["songs"] if s["artistId"] in others]
        songs.sort(key=lambda s: hashlib.sha1(s["id"].encode()).digest())
        return [self._starred(s) for s in songs[:count]]

    def _starred(self, item):
        """The item with "starred" when it is liked, like Navidrome."""
        item = {k: v for k, v in item.items() if k != "starred"}
        if item["id"] in self.starred:
            item["starred"] = "2026-11-01T12:00:00Z"
        return item

    def _find_playlist(self, playlist_id):
        return next((p for p in self.playlists if p["id"] == playlist_id), None)

    def _playlist(self, playlist, entries):
        songs = [self._starred(self.songs[i]) for i in playlist["entries"]]
        out = {"id": playlist["id"], "name": playlist["name"],
               "owner": playlist["owner"], "public": playlist["public"],
               "songCount": len(songs), "readonly": False,
               "duration": sum(s["duration"] for s in songs)}
        if songs:
            out["coverArt"] = songs[0]["coverArt"]
        if entries:
            out["entry"] = songs
        return out

    def cover(self, cover_id, size):
        """A PNG gradient in colours derived from the id."""
        key = (cover_id, size)
        if key not in self._covers:
            digest = hashlib.sha1(cover_id.encode()).digest()
            hue = digest[0] / 255
            top = colorsys.hsv_to_rgb(hue, 0.55, 0.85)
            bottom = colorsys.hsv_to_rgb((hue + 0.12) % 1, 0.75, 0.45)
            rows = []
            for y in range(size):
                f = y / max(1, size - 1)
                rgb = bytes(int(255 * (a + (b - a) * f)) for a, b in zip(top, bottom))
                rows.append(b"\x00" + rgb * size)
            self._covers[key] = _png(size, size, b"".join(rows))
        return self._covers[key]

    def audio(self, song_id):
        """A WAV sine tone; its pitch depends on the song."""
        if song_id not in self._audio:
            rate = 8000
            pitch = 220 + hashlib.sha1(song_id.encode()).digest()[0]
            out = io.BytesIO()
            with wave.open(out, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(rate)
                w.writeframes(b"".join(
                    struct.pack("<h", int(6000 * math.sin(2 * math.pi * pitch * n / rate)))
                    for n in range(AUDIO_SECONDS * rate)))
            self._audio[song_id] = out.getvalue()
        return self._audio[song_id]


def _server(handler, tls):
    """A threading HTTP server on 127.0.0.1, with tls (cert, key, CA)
    HTTPS that requires a client certificate."""
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    httpd.daemon_threads = True
    if not tls:
        return httpd, "http"
    cert, key, ca = tls
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert, key)
    context.load_verify_locations(ca)
    context.verify_mode = ssl.CERT_REQUIRED
    httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
    return httpd, "https"


def _png(width, height, raw):
    def chunk(kind, data):
        return (struct.pack(">I", len(data)) + kind + data
                + struct.pack(">I", zlib.crc32(kind + data)))
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


class _Handler(BaseHTTPRequestHandler):
    owner = None
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def do_GET(self):
        self._handle(b"")

    def do_HEAD(self):
        self._handle(b"")

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        self._handle(self.rfile.read(length))

    def _proxy_refuses(self):
        """Like Pangolin with header authentication: 401 without the
        right HTTP Basic auth. The header goes on to the server."""
        basic = self.owner.proxy_basic
        if basic and self.headers.get("Authorization") != \
                "Basic " + base64.b64encode(basic.encode()).decode():
            self._send(401, b"Unauthorized", "text/plain",
                       [("WWW-Authenticate", 'Basic realm="pangolin"')])
            return True
        return False

    def _handle(self, body):
        if self._proxy_refuses():
            return
        parts = urlsplit(self.path)
        # Like Navidrome's postFormToQueryParams: query and body together.
        pairs = parse_qsl(parts.query) + parse_qsl(body.decode("utf-8", "replace"))
        form = dict(pairs)
        lists = {}
        for key, value in pairs:
            lists.setdefault(key, []).append(value)
        method = parts.path.rsplit("/", 1)[-1].removesuffix(".view")
        self.owner.requests.append((self.command, self.path, form))
        if hasattr(self.owner, "arrivals"):
            self.owner.arrivals.append((time.monotonic(), method))
        if not parts.path.startswith("/rest/"):
            self._send(404, b"not found", "text/plain")
            return
        answer = self.owner.answer(method, form, lists)
        if isinstance(answer, tuple):
            self._send_media(*answer)
        else:
            self._send(200, json.dumps(answer).encode(), "application/json")

    def _send(self, status, data, content_type, extra=()):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        for name, value in extra:
            self.send_header(name, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def _send_media(self, data, content_type):
        spec = self.headers.get("Range")
        if spec and spec.startswith("bytes="):
            first, _, last = spec[6:].partition("-")
            start = int(first or 0)
            end = min(int(last), len(data) - 1) if last else len(data) - 1
            self._send(206, data[start:end + 1], content_type,
                       [("Accept-Ranges", "bytes"),
                        ("Content-Range", f"bytes {start}-{end}/{len(data)}")])
        else:
            self._send(200, data, content_type, [("Accept-Ranges", "bytes")])


# The MeTube and YouTube Music stand-ins live in demo_metube.py.
from nauta.demo_metube import DemoMeTube, DemoYouTubeMusic  # noqa: E402,F401
