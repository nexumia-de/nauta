"""A small stand-in for a Navidrome server that serves the recorded demo
library (tests/data/demo). The store screenshots use it
(NAUTA_DEMO=<dir>), and the tests run the client, the proxy and mutual
TLS against it. Only the endpoints Nauta calls are implemented, with the
answers shaped like Navidrome's (docs/subsonic-api.md). Covers and audio
are made here: colour gradients and sine tones. DemoMeTube stands in for
the download server and DemoYouTubeMusic for YouTube Music's search of
albums and playlists (docs/downloads.md). No GTK."""
import base64
import colorsys
import hashlib
import io
import json
import math
import ssl
import struct
import threading
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
        self.scrobbles = []    # (song id, submission)
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

    def answer(self, method, form):
        """(JSON answer) or (bytes, content type) for /rest/<method>."""
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
            albums = list(lib["albums"])
            kind = form.get("type", "newest")
            if kind == "newest":
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
            return self.response(artist=dict(artist, album=albums))
        if method == "getAlbum":
            album = self.albums.get(form.get("id"))
            if album is None:
                return self.error(70, "Album not found")
            return self.response(album=dict(album, song=self.album_songs(album["id"])))
        if method == "getPlaylists":
            return self.response(playlists={"playlist": [
                self._playlist(p, False) for p in lib["playlists"]]})
        if method == "getPlaylist":
            for p in lib["playlists"]:
                if p["id"] == form.get("id"):
                    return self.response(playlist=self._playlist(p, True))
            return self.error(70, "Playlist not found")
        if method == "search3":
            query = (form.get("query") or "").lower().strip('"')

            def hit(*texts):
                return any(query in (t or "").lower() for t in texts)
            return self.response(searchResult3={
                "artist": [a for a in lib["artists"] if hit(a["name"])],
                "album": [a for a in lib["albums"] if hit(a["name"], a["artist"])],
                "song": [s for s in lib["songs"] if hit(s["title"])][:40]})
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

    def _playlist(self, playlist, entries):
        songs = [self.songs[i] for i in playlist["entries"]]
        out = {"id": playlist["id"], "name": playlist["name"],
               "owner": playlist["owner"], "public": playlist["public"],
               "songCount": len(songs), "coverArt": songs[0]["coverArt"],
               "duration": sum(s["duration"] for s in songs)}
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


class DemoMeTube(DemoServer):
    """A stand-in for MeTube (docs/downloads.md): /version, /browse with
    the invented search results, albums and playlists of
    tests/data/demo/metube.json, /add (also of a whole album or
    playlist), /history and /delete. A download finishes after three looks at the
    history; one whose title contains "unavailable" fails."""

    def __init__(self, directory, tls=None):
        self.data = json.loads((Path(directory) / "metube.json").read_text())
        self.collections = {c["url"]: c for c in self.data.get("collections", [])}
        self.requests = []
        self.queue, self.done = [], []
        self.clock = 0
        self.lock = threading.Lock()
        # "name=value": refuse every request without this cookie, like a
        # reverse proxy with its own login (Pangolin answers 401).
        self.proxy_cookie = None
        self.proxy_basic = None
        server = self

        class Handler(_MeTubeHandler):
            owner = server

        self.httpd, self.scheme = _server(Handler, tls)

    def answer(self, method, path, body):
        if method == "GET" and path == "version":
            return self.data["version"]
        if method == "GET" and path == "history":
            return self._history()
        if method != "POST":
            return None
        if path == "browse":
            return self._browse(body.get("url") or "", body.get("playlist_item_limit") or 0)
        if path == "add":
            return self._add(body)
        if path == "delete":
            ids = set(body.get("ids") or [])
            with self.lock:
                if body.get("where") == "queue":
                    for item in [i for i in self.queue if i["url"] in ids]:
                        self.queue.remove(item)
                        self.done.append(dict(item, status="error", msg="Canceled"))
                else:
                    self.done = [i for i in self.done if i["url"] not in ids]
            return {"status": "ok"}
        return None

    def _entry(self, url):
        return next((e for source in self.data["results"].values()
                     for e in source if e["url"] == url), None)

    def _browse(self, url, limit):
        collection = self.collections.get(url)
        if collection is not None:
            entries = [{k: v for k, v in self._entry(u).items()
                        if not k.startswith("_")} for u in collection["tracks"]]
            return {"status": "ok", "title": collection["title"],
                    "entries": entries[:limit or None]}
        if url.startswith("ytsearch"):
            source, query = "youtube", url.partition(":")[2]
        elif url.startswith("https://music.youtube.com/search?"):
            source = "youtube-music"
            query = dict(parse_qsl(urlsplit(url).query)).get("q", "")
        else:
            return {"status": "error", "msg": "This URL points to a single video, "
                    "not a channel or playlist. Use Download instead."}
        words = query.lower().split()
        # "_artist": yt-dlp's flat YouTube Music results have the song
        # title only, but YouTube matches the artist too.
        entries = [{k: v for k, v in e.items() if not k.startswith("_")}
                   for e in self.data["results"][source]
                   if any(w in f"{e['title']} {e.get('_artist', '')}".lower()
                          for w in words)]
        if not entries:
            return {"status": "error", "msg": "No entries found at this URL."}
        return {"status": "ok", "title": query, "entries": entries[:limit or None]}

    def _add(self, body):
        if body.get("download_type") != "audio" or not body.get("quality"):
            return {"status": "error", "msg": "Bad request"}
        url = body.get("url") or ""
        collection = self.collections.get(url)
        if collection is not None:
            # Like MeTube: every song of the album or playlist is queued.
            for track in collection["tracks"]:
                self._queue(track, self._entry(track), body)
            return {"status": "ok"}
        entry = self._entry(url)
        if entry is None:
            return {"status": "error", "msg": "Unsupported URL"}
        return self._queue(url, entry, body)

    def _queue(self, url, entry, body):
        vid = dict(parse_qsl(urlsplit(url).query)).get("v", url)
        with self.lock:
            if any(i["id"] == vid for i in self.queue):
                return {"status": "ok", "msg": f"Already in queue: {entry['title']}"}
            self.clock += 1
            # MeTube keys downloads by the video's webpage URL.
            self.queue.append({
                "id": vid, "title": entry["title"],
                "url": f"https://www.youtube.com/watch?v={vid}",
                "download_type": "audio", "format": body.get("format"),
                "status": "queued", "percent": None, "msg": None,
                "timestamp": self.clock, "looks": 0})
        return {"status": "ok"}

    def _history(self):
        with self.lock:
            for item in list(self.queue):
                item["looks"] += 1
                if item["looks"] >= 3:
                    self.queue.remove(item)
                    failed = "unavailable" in item["title"].lower()
                    self.done.append(dict(
                        item, status="error" if failed else "finished",
                        percent=None if failed else 100,
                        msg="Video unavailable" if failed else None))
                else:
                    item.update(status="downloading", percent=item["looks"] * 40.0)
            return {"queue": [dict(i) for i in self.queue], "pending": [],
                    "done": [dict(i) for i in self.done]}


class DemoYouTubeMusic(DemoServer):
    """A stand-in for YouTube Music's search API (nauta.ytmusic): POST
    /youtubei/v1/search answers the albums or playlists of
    tests/data/demo/metube.json, in the shape nauta.ytmusic reads."""

    def __init__(self, directory):
        self.data = json.loads((Path(directory) / "metube.json").read_text())
        self.requests = []
        self.headers = []      # of every request, to check what was sent
        self.proxy_cookie = self.proxy_basic = None
        server = self

        class Handler(_MeTubeHandler):
            owner = server

            def _handle(self, raw):
                server.headers.append(dict(self.headers))
                super()._handle(raw)

        self.httpd, self.scheme = _server(Handler, None)

    def answer(self, method, path, body):
        if (method, path) != ("POST", "youtubei/v1/search"):
            return None
        from nauta.ytmusic import ALBUMS, PLAYLISTS, SECTIONS
        # The demo's playlists are community playlists; no featured ones.
        kind = {SECTIONS[ALBUMS][0]: ALBUMS,
                SECTIONS[PLAYLISTS][1]: PLAYLISTS}.get(body.get("params"))
        words = (body.get("query") or "").lower().split()
        items = []
        for c in self.data.get("collections", []):
            haystack = f"{c['title']} {c['subtitle']} {c.get('_words', '')}".lower()
            if c["kind"] != kind or not any(w in haystack for w in words):
                continue
            parts = urlsplit(c["url"])
            browse_id = parts.path.rsplit("/", 1)[-1] if "/browse/" in parts.path \
                else "VL" + dict(parse_qsl(parts.query))["list"]
            items.append({"musicResponsiveListItemRenderer": {
                "flexColumns": [
                    {"musicResponsiveListItemFlexColumnRenderer": {
                        "text": {"runs": [{"text": c["title"]}]}}},
                    {"musicResponsiveListItemFlexColumnRenderer": {
                        "text": {"runs": [{"text": t} for t in
                                          _split_runs(c["subtitle"])]}}}],
                "navigationEndpoint": {"browseEndpoint": {"browseId": browse_id}}}})
        sections = [{"musicShelfRenderer": {"contents": items}}] if items else \
            [{"itemSectionRenderer": {"contents": []}}]
        return {"contents": {"tabbedSearchResultsRenderer": {"tabs": [
            {"tabRenderer": {"content": {"sectionListRenderer": {
                "contents": sections}}}}]}}}


def _split_runs(line):
    """"Album • Artist • 2024" as YouTube Music's text runs."""
    runs = []
    for i, part in enumerate(line.split(" • ")):
        if i:
            runs.append(" • ")
        runs.append(part)
    return runs


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
        form = dict(parse_qsl(parts.query))
        form.update(parse_qsl(body.decode("utf-8", "replace")))
        method = parts.path.rsplit("/", 1)[-1].removesuffix(".view")
        self.owner.requests.append((self.command, self.path, form))
        if not parts.path.startswith("/rest/"):
            self._send(404, b"not found", "text/plain")
            return
        answer = self.owner.answer(method, form)
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


class _MeTubeHandler(_Handler):
    def _handle(self, raw):
        if self._proxy_refuses():
            return
        path = urlsplit(self.path).path.strip("/")
        cookie = self.owner.proxy_cookie
        if cookie and cookie not in (self.headers.get("Cookie") or ""):
            self._send(401, b"Unauthorized", "text/plain")
            return
        try:
            body = json.loads(raw or b"{}")
        except ValueError:
            self._send(400, b"Invalid JSON request body", "text/plain")
            return
        self.owner.requests.append((self.command, path, body))
        answer = self.owner.answer(self.command, path, body)
        if answer is None:
            self._send(404, b"Not Found", "text/plain")
        else:
            # Like MeTube, which answers most calls as text/plain.
            self._send(200, json.dumps(answer).encode(), "text/plain")
