"""Stand-ins for MeTube and YouTube Music's search (docs/downloads.md),
for the tests and the demo (NAUTA_DEMO): the invented search results,
albums and playlists of tests/data/demo/metube.json. No GTK."""
import json
import threading
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

from nauta.demo import DemoServer, _Handler, _server


class DemoMeTube(DemoServer):
    """A stand-in for MeTube (docs/downloads.md): /version, /browse with
    the invented search results, albums and playlists of
    tests/data/demo/metube.json, /add (also of a whole album or
    playlist), /history and /delete. A download finishes after three looks at the
    history; one whose title contains "unavailable" fails."""

    def __init__(self, directory, tls=None):
        self.data = json.loads((Path(directory) / "metube.json").read_text())
        self.collections = {c["url"]: c for c in self.data.get("collections", [])}
        # Album page links (…/browse/MPREb_…) of the albums.
        self.album_pages = {f"https://music.youtube.com/browse/{c['browse_id']}": c
                            for c in self.data.get("collections", [])
                            if c.get("browse_id")}
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
        if "/browse/MPREb_" in url:
            # Like MeTube: yt-dlp answers an album page with a link to the
            # album's playlist, which /browse (extract_flat) doesn't follow.
            return {"status": "error", "msg": "This URL points to a single video, "
                    "not a channel or playlist. Use Download instead."}
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
        # /add follows the album page's link to its playlist.
        collection = self.collections.get(url) or self.album_pages.get(url)
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
        if (method, path) == ("POST", "youtubei/v1/browse"):
            return self._album_page(body.get("browseId") or "")
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
            playlist_id = dict(parse_qsl(urlsplit(c["url"]).query))["list"]
            browse_id = c.get("browse_id") or "VL" + playlist_id
            item = {
                "flexColumns": [
                    {"musicResponsiveListItemFlexColumnRenderer": {
                        "text": {"runs": [{"text": c["title"]}]}}},
                    {"musicResponsiveListItemFlexColumnRenderer": {
                        "text": {"runs": [{"text": t} for t in
                                          _split_runs(c["subtitle"])]}}}],
                "navigationEndpoint": {"browseEndpoint": {"browseId": browse_id}}}
            if c.get("browse_id") and not c.get("_no_play_button"):
                # An album's play button plays its playlist.
                item["overlay"] = {"musicItemThumbnailOverlayRenderer": {"content": {
                    "musicPlayButtonRenderer": {"playNavigationEndpoint": {
                        "watchPlaylistEndpoint": {"playlistId": playlist_id}}}}}}
            items.append({"musicResponsiveListItemRenderer": item})
        sections = [{"musicShelfRenderer": {"contents": items}}] if items else \
            [{"itemSectionRenderer": {"contents": []}}]
        return {"contents": {"tabbedSearchResultsRenderer": {"tabs": [
            {"tabRenderer": {"content": {"sectionListRenderer": {
                "contents": sections}}}}]}}}

    def _album_page(self, browse_id):
        """The part of an album page nauta.ytmusic reads: its canonical
        URL, the album's playlist."""
        album = next((c for c in self.data.get("collections", [])
                      if c.get("browse_id") == browse_id), None)
        if album is None:
            return {"error": {"code": 404}}
        return {"microformat": {"microformatDataRenderer": {
            "urlCanonical": album["url"]}}}


def _split_runs(line):
    """"Album • Artist • 2024" as YouTube Music's text runs."""
    runs = []
    for i, part in enumerate(line.split(" • ")):
        if i:
            runs.append(" • ")
        runs.append(part)
    return runs


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
