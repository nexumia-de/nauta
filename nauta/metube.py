"""MeTube's HTTP API, the yt-dlp web front end the user runs next to
Navidrome (docs/downloads.md). Read from MeTube's source
(github.com/alexta69/metube, app/main.py at 7e73766, 2026-11-01).
Blocking calls meant for worker threads; no GTK.

MeTube has no login of its own: it sits behind the user's reverse proxy,
which asks for the client certificate and, if set up, its own login
(phosh_toolkit.proxy_login). Nothing secret goes into a URL or a body.

Search: MeTube has no search call, but /browse lists the entries of any
yt-dlp "playlist" without downloading, and a YouTube Music search URL
or a "ytsearchN:" prefix is one. Albums and playlists are found on the
phone (nauta.ytmusic); /browse lists their songs and /add downloads all
of them at once."""
import json
from urllib.parse import parse_qs, quote_plus, urlsplit

from phosh_toolkit.http import SERVER, Client, HttpError

from nauta import USER_AGENT
from nauta.ytmusic import ALBUMS, PLAYLISTS

YOUTUBE_MUSIC = "youtube-music"
YOUTUBE = "youtube"
SOURCES = ((YOUTUBE_MUSIC, "YouTube Music"), (YOUTUBE, "YouTube"))
RESULTS = 20
# What to search for on YouTube Music: songs through MeTube, albums and
# playlists through nauta.ytmusic. YouTube searches videos only.
SONGS = "songs"
KINDS = ((SONGS, "Songs"), (ALBUMS, "Albums"), (PLAYLISTS, "Playlists"))
# Songs of an album or playlist listed at most; "Download All" gets all.
COLLECTION_LIMIT = 200
YOUTUBE_HOSTS = ("music.youtube.com", "www.youtube.com", "youtube.com",
                 "m.youtube.com")
# MeTube's /browse answer when a search finds nothing.
NO_ENTRIES = "No entries found at this URL."
# Audio formats Nauta offers (MeTube's format catalog, type "audio").
FORMATS = (("m4a", "M4A (AAC)"), ("opus", "Opus"), ("mp3", "MP3"))
# Download states in MeTube's queue; finished ones are "finished" or
# "error" in the done list.
ACTIVE = ("pending", "queued", "scheduled", "preparing", "downloading",
          "postprocessing")


def search_url(query, source=YOUTUBE_MUSIC, count=RESULTS):
    """What /browse gets for a search: YouTube Music's song results, or a
    plain YouTube search."""
    query = " ".join(query.split())
    if source == YOUTUBE:
        return f"ytsearch{count}:{query}"
    return f"https://music.youtube.com/search?q={quote_plus(query)}#songs"


def collection_link(text):
    """The album or playlist a pasted YouTube (Music) link points to, as a
    URL for /browse and /add; "" for anything else."""
    text = text.strip()
    if " " in text or "://" not in text:
        return ""
    parts = urlsplit(text)
    if parts.scheme not in ("http", "https") or parts.hostname not in YOUTUBE_HOSTS:
        return ""
    host = "https://music.youtube.com" if parts.hostname == "music.youtube.com" \
        else "https://www.youtube.com"
    playlist = (parse_qs(parts.query).get("list") or [""])[0]
    if playlist and parts.path in ("/playlist", "/watch"):
        return f"{host}/playlist?list={quote_plus(playlist)}"
    if parts.path.startswith("/browse/MPREb_"):
        return f"{host}{parts.path}"
    return ""


def video_id(url):
    """The YouTube video id of a watch URL, which MeTube uses as the id of
    the download; "" for other URLs."""
    parts = urlsplit(url)
    return (parse_qs(parts.query).get("v") or [""])[0]


def matches(item, url):
    """Is the history item the download of `url`?"""
    vid = video_id(url)
    return item.get("url") == url or bool(vid and item.get("id") == vid)


class MeTube:
    def __init__(self, http=None):
        self.http = http or Client(USER_AGENT)
        self.base_url = ""      # set by Downloads for the current route

    def _json(self, method, path, body=None, base=None, timeout=None):
        data = None if body is None else json.dumps(body).encode()
        response = self.http.request(
            method, f"{base or self.base_url}/{path}",
            {"Accept": "application/json"}, body=data,
            content_type="application/json", timeout=timeout)
        try:
            return json.loads(response.body)
        except ValueError:
            raise HttpError(SERVER, "This is not a MeTube server") from None

    def probe(self, url, timeout=None):
        """GET /version: {"yt-dlp": …, "version": …}. Raises HttpError when
        it is no MeTube."""
        answer = self._json("GET", "version", base=url, timeout=timeout)
        if not isinstance(answer, dict) or "yt-dlp" not in answer:
            raise HttpError(SERVER, "This is not a MeTube server")
        return answer

    def search(self, query, source=YOUTUBE_MUSIC, count=RESULTS):
        """[{"url", "title", "duration"}] from /browse. yt-dlp runs on the
        server, so this takes seconds."""
        answer = self._json("POST", "browse", {
            "url": search_url(query, source, count),
            "playlist_item_limit": count}, timeout=90)
        if answer.get("status") != "ok":
            if answer.get("msg") == NO_ENTRIES:
                return []
            raise HttpError(SERVER, answer.get("msg") or "Search failed")
        return answer.get("entries") or []

    def browse(self, url, count=COLLECTION_LIMIT):
        """The songs of an album or playlist: (title, [{"url", "title",
        "duration"}])."""
        answer = self._json("POST", "browse", {
            "url": url, "playlist_item_limit": count}, timeout=90)
        if answer.get("status") != "ok":
            if answer.get("msg") == NO_ENTRIES:
                return answer.get("title") or "", []
            raise HttpError(SERVER, answer.get("msg") or "Can't list the songs")
        return answer.get("title") or "", answer.get("entries") or []

    def add(self, url, audio_format="m4a"):
        """Queue the audio of `url` with tags and cover; MeTube starts it.
        For an album or playlist MeTube queues each song (with its track
        number from the playlist) before it answers, which takes a while."""
        answer = self._json("POST", "add", {
            "url": url, "download_type": "audio", "codec": "auto",
            "format": audio_format, "quality": "best",
            "audio_tags": "with_cover", "auto_start": True}, timeout=120)
        if answer.get("status") != "ok":
            raise HttpError(SERVER, answer.get("msg") or "Download failed")
        return answer

    def history(self):
        """{"queue": […], "pending": […], "done": […]} of download items
        (id, title, url, status, percent, msg, timestamp, …)."""
        answer = self._json("GET", "history")
        return {k: answer.get(k) or [] for k in ("queue", "pending", "done")}

    def delete(self, ids, where):
        """Cancel queued downloads (where "queue") or remove finished ones
        from the list (where "done"); files stay."""
        return self._json("POST", "delete", {"ids": list(ids), "where": where})
