"""Search YouTube Music for albums and playlists, from the phone
(docs/downloads.md, docs/decisions/youtube-music-search.md).

MeTube's /browse can't list them: yt-dlp's album and playlist search
results are links without a title, and MeTube opens the first of them
instead of listing them. So Nauta asks YouTube Music's web API itself,
only for this list. The songs of an album or playlist are then listed and
downloaded through MeTube as before.

Request facts from yt-dlp (yt_dlp/extractor/youtube/_base.py, client
"web_music", and _search.py, YoutubeMusicSearchURLIE._SECTIONS, at
412e7f0, 2026-11-04). No code from yt-dlp. This client never sends the
download server's certificate, cookies or proxy login: it has its own
HTTP client. Blocking calls meant for worker threads; no GTK."""
import json

from gi.repository import GLib
from phosh_toolkit.http import SERVER, Client, HttpError

from nauta import USER_AGENT

BASE_URL = "https://music.youtube.com"
CLIENT_NAME = "WEB_REMIX"
CLIENT_ID = "67"
CLIENT_VERSION = "1.20260707.12.00"

ALBUMS = "albums"
PLAYLISTS = "playlists"
# The "params" of a search, one per section of YouTube Music's results.
# Playlists: the featured ones (YouTube Music's own) first, then the
# community playlists.
SECTIONS = {
    ALBUMS: ("EgWKAQIYAWoKEAoQAxAEEAkQBQ==",),
    PLAYLISTS: ("EgeKAQQoADgBagwQAxAJEAQQDhAKEAU==",
                "EgeKAQQoAEABagoQChADEAQQCRAF"),
}
RESULTS = 20


def language():
    """"de" for a German system; YouTube Music answers in it (the
    "Album • Artist • 2019" line)."""
    for name in GLib.get_language_names():
        code = name.split(".")[0].split("_")[0]
        if code.isalpha() and len(code) == 2:
            return code
    return "en"


def _text(column):
    runs = (((column or {}).get("musicResponsiveListItemFlexColumnRenderer")
             or {}).get("text") or {}).get("runs") or []
    return "".join(r.get("text") or "" for r in runs if isinstance(r, dict)).strip()


def collection_url(browse_id):
    """The URL MeTube gets for a result: an album's browse page
    (yt-dlp resolves it to the album's playlist) or a playlist."""
    if browse_id.startswith("VL"):
        return f"{BASE_URL}/playlist?list={browse_id[2:]}"
    if browse_id.startswith("MPREb_"):
        return f"{BASE_URL}/browse/{browse_id}"
    return ""


def parse(answer, kind):
    """[{"url", "title", "subtitle", "kind"}] from a search answer:
    the list items of every music shelf that open an album or playlist."""
    tabs = (((answer or {}).get("contents") or {})
            .get("tabbedSearchResultsRenderer") or {}).get("tabs") or []
    results = []
    for tab in tabs[:1]:
        sections = ((((tab.get("tabRenderer") or {}).get("content") or {})
                     .get("sectionListRenderer") or {}).get("contents") or [])
        for section in sections:
            shelf = section.get("musicShelfRenderer") or {}
            for item in shelf.get("contents") or []:
                renderer = item.get("musicResponsiveListItemRenderer")
                if not renderer:
                    continue
                browse_id = (((renderer.get("navigationEndpoint") or {})
                              .get("browseEndpoint") or {}).get("browseId") or "")
                url = collection_url(browse_id)
                columns = renderer.get("flexColumns") or []
                title = _text(columns[0]) if columns else ""
                if not url or not title:
                    continue
                results.append({
                    "url": url, "title": title, "kind": kind,
                    "subtitle": _text(columns[1]) if len(columns) > 1 else ""})
    return results


class YouTubeMusic:
    def __init__(self, http=None, base_url=None):
        self.http = http or Client(USER_AGENT)
        self.base_url = base_url or BASE_URL

    def _search(self, query, params, timeout):
        body = {
            "context": {"client": {"clientName": CLIENT_NAME,
                                   "clientVersion": CLIENT_VERSION,
                                   "hl": language()}},
            "query": query, "params": params}
        response = self.http.request(
            "POST", f"{self.base_url}/youtubei/v1/search?prettyPrint=false",
            {"Accept": "application/json",
             "Origin": BASE_URL,
             "X-YouTube-Client-Name": CLIENT_ID,
             "X-YouTube-Client-Version": CLIENT_VERSION},
            body=json.dumps(body).encode(), content_type="application/json",
            timeout=timeout)
        try:
            return json.loads(response.body)
        except ValueError:
            raise HttpError(SERVER, "YouTube Music sent no search results") from None

    def search(self, query, kind=ALBUMS, count=RESULTS, timeout=30):
        """Albums or playlists for `query`, at most `count`."""
        query = " ".join(query.split())
        results, seen = [], set()
        for params in SECTIONS[kind]:
            for result in parse(self._search(query, params, timeout), kind):
                if result["url"] not in seen:
                    seen.add(result["url"])
                    results.append(result)
        return results[:count]
