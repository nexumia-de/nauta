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
import re
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
# YouTube's short links (the Share button): youtu.be/<video id>.
SHORT_HOST = "youtu.be"
# A YouTube video id: 11 characters of the URL-safe base64 alphabet.
VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}")
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


def _youtube_link(text):
    """(site, path, query, short) of a pasted YouTube (Music) link, site being
    "https://music.youtube.com" or "https://www.youtube.com", short true
    for youtu.be; None for anything else."""
    text = text.strip()
    if " " in text or "://" not in text:
        return None
    parts = urlsplit(text)
    if parts.scheme not in ("http", "https") or \
            parts.hostname not in YOUTUBE_HOSTS + (SHORT_HOST,):
        return None
    site = "https://music.youtube.com" if parts.hostname == "music.youtube.com" \
        else "https://www.youtube.com"
    return site, parts.path, parse_qs(parts.query), parts.hostname == SHORT_HOST


def _is_mix(playlist):
    """YouTube's endless radio mixes (list=RD…), which a watch link of a
    song played from a radio carries; the song is meant, not the mix."""
    return playlist.startswith("RD")


def collection_link(text):
    """The album or playlist a pasted YouTube (Music) link points to, as a
    URL for /browse and /add; "" for anything else."""
    link = _youtube_link(text)
    if link is None:
        return ""
    site, path, query, short = link
    playlist = (query.get("list") or [""])[0]
    if playlist and not _is_mix(playlist) and (short or path in ("/playlist", "/watch")):
        return f"{site}/playlist?list={quote_plus(playlist)}"
    if not short and path.startswith("/browse/MPREb_"):
        return f"{site}{path}"
    return ""


def song_link(text):
    """The single song or video a pasted link points to, as a watch URL for
    /add (youtu.be/<id>, …/watch?v=<id>, …/shorts/<id>, share parameters
    dropped); "" for anything else, collections included."""
    link = _youtube_link(text)
    if link is None or collection_link(text):
        return ""
    site, path, query, short = link
    if short:
        vid = path.strip("/")
    elif path == "/watch":
        vid = (query.get("v") or [""])[0]
    elif path.startswith("/shorts/"):
        vid = path.removeprefix("/shorts/").strip("/")
    else:
        return ""
    if not VIDEO_ID.fullmatch(vid):
        return ""
    return f"{site}/watch?v={vid}"


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
