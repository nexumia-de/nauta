---
type: Concept
title: Finding and downloading new music with MeTube
description: How Nauta searches YouTube Music or YouTube for songs, albums and playlists, downloads them into the Navidrome library through the user's own MeTube server, and reaches MeTube with the same home/remote route, client certificate and proxy login as the music server.
tags: [downloads, metube, yt-dlp, search, albums, playlists, youtube-music, connection, mtls, proxy-login]
resource: ../nauta/downloads.py
generated: { by: claude-code/2.1.318, at: 2026-11-04T16:00:00Z }
sources:
  - id: metube
    resource: https://github.com/alexta69/metube/tree/7e73766238f3fc491b2aeba0c3c8b415c408eaaa/app
    title: MeTube source, app/main.py, app/ytdl.py, app/subscriptions.py, app/format_catalog.py, app/url_guard.py (commit 7e73766, 2026-11-01)
  - id: yt-dlp
    resource: https://github.com/yt-dlp/yt-dlp/blob/412e7f0/yt_dlp/extractor/youtube/_search.py
    title: yt-dlp, YoutubeMusicSearchURLIE and YoutubeSearchIE (commit 412e7f0, 2026-11-04)
  - id: ytmusicapi
    resource: https://github.com/sigma67/ytmusicapi/blob/488dbf3/ytmusicapi/parsers/search.py
    title: ytmusicapi, parsers/search.py (album results, playlist id under the play button, "Single", "EP") and navigation.py (commit 488dbf3, 2026-11-04)
  - id: yt-dlp-flat
    resource: https://github.com/yt-dlp/yt-dlp/blob/412e7f0/yt_dlp/YoutubeDL.py
    title: yt-dlp, YoutubeDL.process_ie_result, extract_flat True keeps a "url" result unresolved (commit 412e7f0, 2026-11-04)
  - id: yt-dlp-api
    resource: https://github.com/yt-dlp/yt-dlp/tree/412e7f0/yt_dlp/extractor/youtube
    title: yt-dlp, _base.py (client "web_music", _call_api, generate_api_headers) and _tab.py (_music_reponsive_list_entry, MPREb_ album URLs) (commit 412e7f0, 2026-11-04)
---

# What it is

"Find New Music" (main menu, `Ctrl+D`, and the button on an empty
library search) searches for songs, albums and playlists that are not
in the library yet. It downloads them on the server, where Navidrome
picks them up. Nauta does not download anything itself: the work is done by
[MeTube](https://github.com/alexta69/metube), a web front end for
yt-dlp that **the user runs next to Navidrome**
([decision](decisions/metube-downloads.md)).

# What the user sets up on the server

- MeTube, reachable like Navidrome: a local address at home, a public
  one behind the reverse proxy (client certificate, optionally the
  proxy's own login).
- MeTube's `AUDIO_DOWNLOAD_DIR` (or `DOWNLOAD_DIR`) **inside Navidrome's
  music folder**, e.g. `/music/Downloads`. Navidrome adds the files at
  its next scan; with its file watcher on (the default since 0.55) that
  happens within a minute.
- Nothing in MeTube's own configuration is needed for Nauta; no
  `CUSTOM_DIRS`, no option overrides.

In Nauta: preferences → Downloads, or the setup page that "Find New
Music" shows first. It is the toolkit's connection form (server
address, client certificate, home Wi-Fi), so the rules of
[connection](connection.md) apply unchanged:

| | Music server | Download server |
|---|---|---|
| Account file | `account.json` | `downloads.json` (`settings.DownloadServer`) |
| Keyring schema | `de.nexumia.Nauta` | `de.nexumia.Nauta.Downloads` (`keyring.DOWNLOADS`) |
| Client certificate | `client-certificate` | `download-certificate`, own password |
| Proxy login cookies | kind `proxy-cookies` | kind `proxy-cookies` in its own schema |
| Proxy user name and password (HTTP Basic) | kind `proxy-credentials` | kind `proxy-credentials` in its own schema |
| Probe | `getOpenSubsonicExtensions` | `GET /version` (needs `yt-dlp` in the answer) |
| Local address | only on a listed home Wi-Fi (`strict_local`) | the same: MeTube has no server id |

The download server is optional; without it the rest of Nauta is
unchanged. "Remove Download Server" forgets addresses, certificate and
proxy login; downloaded songs stay on the server.

# MeTube's API, as Nauta uses it

Read from MeTube's source at commit `7e73766`[^metube]. MeTube has **no
login of its own**; access control is the reverse proxy's job. Every
call sends `Accept: application/json`, so a proxy's login page (HTML)
is recognised as a proxy login (`phosh_toolkit.http`). MeTube answers
most calls as `text/plain` with a JSON body.

| Call | Body | Answer |
|---|---|---|
| `GET /version` | – | `{"yt-dlp": "…", "version": "…"}` |
| `POST /browse` | `{"url", "playlist_item_limit"}` | `{"status": "ok", "title", "entries": [{"url", "title", "duration"}]}`, or `{"status": "error", "msg"}` |
| `POST /add` | `{"url", "download_type": "audio", "codec": "auto", "format", "quality": "best", "audio_tags": "with_cover", "auto_start": true}` | `{"status": "ok"}` (maybe with `msg` "Already in queue: …") or `{"status": "error", "msg"}` |
| `GET /history` | – | `{"queue", "pending", "done"}`: items with `id` (video id), `title`, `url` (webpage URL, the key), `status`, `percent`, `msg`, `timestamp` |
| `POST /delete` | `{"ids": [url, …], "where": "queue" or "done"}` | cancels, or removes from the list (files stay: `delete_files` false) |

A URL prefix (`URL_PREFIX`) is simply part of the server address. Live
updates come over Socket.IO in MeTube's web UI; Nauta polls
`/history` every 2 s instead, only while the Downloads page is shown or
a download it started is running (`Downloads.watch()`).

# Search

Two rows of linked buttons sit under the search entry. The first picks
the source: **YouTube Music** or **YouTube**. With YouTube Music a
second row picks what to search: **Songs**, **Albums** or **Playlists**.
YouTube searches videos only, so the second row is hidden there. Both
choices are kept in `downloads.json` (`source`, `kind`).

Searching runs yt-dlp on the server and takes a few seconds, so Nauta
searches on Enter, not on every key, with a 90 s timeout.

## Songs and videos: MeTube's `/browse`

MeTube has no search call. `/browse` "flat-probes a playlist/channel URL
and lists its entries; queues nothing", and MeTube's URL guard lets
yt-dlp's search prefixes through unchanged ("Inputs without a `://` …
`ytsearch:` … are allowed")[^metube]. A yt-dlp search is a playlist, so:

- **YouTube Music, Songs** (default): `https://music.youtube.com/search?q=<query>#songs`,
  yt-dlp's `youtube:music:search_url` with the "songs" section[^yt-dlp].
  Flat entries carry only the song title (no artist, no duration), so
  rows show the title only.
- **YouTube**: `ytsearch20:<query>`, entries with the video title
  (usually "Artist - Song (…)") and duration.

"No entries found at this URL." is an empty result, not an error.

## Albums and playlists: from the phone

`/browse` can't list albums or playlists. yt-dlp's results for those
sections are links without titles. MeTube doesn't treat them as entries
and answers with the songs of the first album instead
([decision](decisions/youtube-music-search.md)). So Nauta asks YouTube
Music's web API itself (`nauta/ytmusic.py`), with request facts from
yt-dlp[^yt-dlp-api]:

| | |
|---|---|
| Request | `POST https://music.youtube.com/youtubei/v1/search?prettyPrint=false`, JSON `{"context": {"client": {"clientName": "WEB_REMIX", "clientVersion": "1.20260707.12.00", "hl": <system language>}}, "query", "params"}` |
| Headers | `X-YouTube-Client-Name: 67`, `X-YouTube-Client-Version`, `Origin: https://music.youtube.com`, Nauta's `User-Agent`; no key, no cookies |
| `params` Albums | `EgWKAQIYAWoKEAoQAxAEEAkQBQ==`. Gives albums, singles and EPs, as YouTube Music's own "Albums" filter does: the line under the title starts with "Album", "Single" or "EP"[^ytmusicapi] |
| `params` Playlists | featured `EgeKAQQoADgBagwQAxAJEAQQDhAKEAU==`, then community `EgeKAQQoAEABagoQChADEAQQCRAF` (two requests, merged) |
| Answer read | `contents.tabbedSearchResultsRenderer.tabs[0]…sectionListRenderer.contents[].musicShelfRenderer.contents[].musicResponsiveListItemRenderer`: title = text runs of `flexColumns[0]`, the line under it = runs of `flexColumns[1]` ("Album • Artist • 2024"), link = `navigationEndpoint.browseEndpoint.browseId` |
| Link for MeTube | Album: its playlist `https://music.youtube.com/playlist?list=OLAK5uy_…`, from the play button (`overlay.musicItemThumbnailOverlayRenderer.content.musicPlayButtonRenderer.playNavigationEndpoint.watchPlaylistEndpoint.playlistId`, or `watchEndpoint.playlistId`)[^ytmusicapi]. Playlist: `VL<id>` → `https://music.youtube.com/playlist?list=<id>` |
| Album without a play button, or a pasted album page link | `POST /youtubei/v1/browse` `{"browseId": "MPREb_…"}` → `microformat.microformatDataRenderer.urlCanonical`, the album's playlist, as yt-dlp resolves albums[^yt-dlp-api] |

**MeTube never gets an album page link (`…/browse/MPREb_…`).** yt-dlp
answers such a link only with a pointer to the album's playlist. MeTube's
`/browse` runs yt-dlp with `extract_flat: True`, which leaves that pointer
unfollowed[^yt-dlp-flat]. So MeTube answers "This URL points to a single
video, not a channel or playlist" (found by the owner on the phone;
`/add` would follow it). The stand-in `DemoMeTube` answers the same.

This client has its own HTTP connection: none of the download
server's certificate, cookies or proxy login go to YouTube. The answer's
layout is not official and not verified against the live service yet.
The parser skips anything it doesn't recognise, so a change on
YouTube's side gives no results rather than a crash.

## An album or a playlist

Tapping an album or playlist opens its page (pushed on the navigation
view, swipe back closes it). It lists the songs through `/browse` on
the link, at most 200 (`playlist_item_limit`). From there you can:

- **Download All**: sends the album or playlist link itself to `/add`.
  MeTube queues each song before it answers (up to 120 s). It writes
  the track number from the playlist position (`MusicMetadataPreProcessor`)
  and applies its playlist folder template (`OUTPUT_TEMPLATE_PLAYLIST`)[^metube].
- **A single song**: its own download button, as in the search results.

Pasting a link to an album or playlist into the search field
(`music.youtube.com/browse/MPREb_…`, `…/playlist?list=…`, or a
`watch?…&list=…` link) opens its page directly
(`metube.collection_link`).

# Downloading

The download button sends the result's URL to `/add` as audio in the
chosen format (M4A (default, MeTube's own default), Opus or MP3, best
quality) with tags and the cover written by MeTube (`audio_tags`
`with_cover`; MeTube only uses metadata yt-dlp supplies). Nauta then
watches `/history` until an item with the same video id (or URL) and a
new timestamp is in `done`: "finished" shows the toast "Downloaded …
Navidrome adds it at its next scan.", "error" shows MeTube's message.
An older download of the same song in the list is told apart by its
timestamp, taken just before `/add`.

A whole album or playlist is followed through the songs `/browse`
listed. It is reported once, when the last of them is done:
"Downloaded “Album”", or "Can't download “Album”: 2 of 12 songs failed
(…)". A song in two albums being downloaded counts for both. A song
that never appears in MeTube's list counts as done.

The Downloads page lists MeTube's queue and done list (all of MeTube's
downloads, also those started in its web UI) with cancel and "remove
from the list".

# Duplicates

Facts as of MeTube `7e73766`[^metube]:

- **MeTube's queue**: adding a URL that is already queued or pending
  answers `{"status": "ok", "msg": "Already in queue: …"}`. Nauta shows
  that message as a toast.
- **yt-dlp's download archive** (off by default): once MeTube's
  operator sets `"download_archive": "<file>"` in `YTDL_OPTIONS`, yt-dlp
  records the id of every finished download. It then skips that id
  again, also when it comes from the web UI or another device. For a
  single URL, `/add` answers with an error: "Already recorded in the
  download archive, so yt-dlp skipped it. …". Inside an album or
  playlist, yt-dlp leaves archived songs out without a message. Nauta
  counts those as done.
- The archive matches **video ids only**. The same song from another
  upload (a music video instead of the "Topic" track, another album) is
  not a duplicate to it.
- Nothing checks the Navidrome library: a song already there from
  another source is downloaded again.

# Not covered yet

- Asking Navidrome to scan right away (`startScan` needs an admin user).
- Artist and album in YouTube Music song results: yt-dlp's flat search
  entries have the title only; full extraction per result would be
  much slower.
- Searching artists, and YouTube's own playlists (not YouTube Music's):
  same `/browse` limit as albums, not built yet.
- Covers of albums and playlists in the results (more image hosts).
- Playlists with more than 200 songs: the page lists the first 200;
  "Download All" still gets all of them.
- MeTube's Socket.IO events instead of polling.

# Verified (2026-11-04, cloud container)

`tests/test_downloads.py`, `tests/test_ui.py::test_find_and_download_new_music`
and `tests/test_ui.py::test_find_albums_and_playlists`. They run against
the MeTube stand-in `nauta.demo.DemoMeTube` (answers shaped as above) and
the YouTube Music stand-in `nauta.demo.DemoYouTubeMusic`. Covered:

- search on both sources and with every filter
- albums and playlists listed without a request to MeTube, and without
  the download server's proxy login in the request to YouTube Music
- an album downloaded whole (one `/add` of its link) and reported once
- a playlist with one failing song reported as "1 of 6 songs failed"
- a song in both an album and a playlist
- a single song from a playlist
- a pasted playlist link, and a pasted album page link resolved to its
  playlist
- an album result with and without a playlist id under its play button;
  MeTube never gets an album page link, which it answers with "single
  video", like the real MeTube
- add with the chosen format, finished and failed downloads reported, a
  repeated download not mistaken for the old one
- the strict route at home and away, mutual TLS with an
  `openssl`-made certificate in its own keyring schema, and the proxy
  login (401 without the cookie)

Screenshots at 360×720 and 1000×700.

Not yet checked against a real MeTube or the real YouTube Music:
`music.youtube.com`, `www.youtube.com` and a running MeTube are not
available in the cloud container. So it is unchecked whether yt-dlp's
YouTube Music song search still returns songs today, and whether the
search API answers as described (M2 exit criterion).
