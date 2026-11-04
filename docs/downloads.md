---
type: Concept
title: Finding and downloading new music with MeTube
description: How Nauta searches YouTube Music or YouTube through the user's own MeTube server, downloads songs into the Navidrome library, and reaches MeTube with the same home/remote route, client certificate and proxy login as the music server.
tags: [downloads, metube, yt-dlp, search, connection, mtls, proxy-login]
resource: ../nauta/downloads.py
generated: { by: claude-code/2.1.318, at: 2026-11-04T09:30:00Z }
sources:
  - id: metube
    resource: https://github.com/alexta69/metube/tree/7e73766238f3fc491b2aeba0c3c8b415c408eaaa/app
    title: MeTube source, app/main.py, app/ytdl.py, app/subscriptions.py, app/format_catalog.py, app/url_guard.py (commit 7e73766, 2026-11-01)
  - id: yt-dlp
    resource: https://github.com/yt-dlp/yt-dlp/blob/412e7f0/yt_dlp/extractor/youtube/_search.py
    title: yt-dlp, YoutubeMusicSearchURLIE and YoutubeSearchIE (commit 412e7f0, 2026-11-04)
---

# What it is

"Find New Music" (main menu, `Ctrl+D`, and the button on an empty
library search) searches for songs that are not in the library yet and
downloads them on the server, where Navidrome picks them up. Nauta
does not download anything itself: the work is done by
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

MeTube has no search call. `/browse` "flat-probes a playlist/channel URL
and lists its entries; queues nothing", and MeTube's URL guard lets
yt-dlp's search prefixes through unchanged ("Inputs without a `://` …
`ytsearch:` … are allowed")[^metube]. A yt-dlp search is a playlist, so:

- **YouTube Music** (default): `https://music.youtube.com/search?q=<query>#songs`,
  yt-dlp's `youtube:music:search_url` with the "songs" section[^yt-dlp].
  Flat entries carry only the song title (no artist, no duration), so
  rows show the title only.
- **YouTube**: `ytsearch20:<query>`, entries with the video title
  (usually "Artist - Song (…)") and duration.

The source is a toggle on the search page and kept in `downloads.json`.
Searching runs yt-dlp on the server and takes a few seconds, so Nauta
searches on Enter, not on every key, with a 90 s timeout. "No entries
found at this URL." is an empty result, not an error.

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

The Downloads page lists MeTube's queue and done list (all of MeTube's
downloads, also those started in its web UI) with cancel and "remove
from the list".

# Not covered yet

- Asking Navidrome to scan right away (`startScan` needs an admin user).
- Artist and album in YouTube Music results: yt-dlp's flat search
  entries have the title only; full extraction per result would be
  much slower.
- MeTube's Socket.IO events instead of polling.

# Verified (2026-11-04, cloud container)

`tests/test_downloads.py` and `tests/test_ui.py::test_find_and_download_new_music`
against the MeTube stand-in `nauta.demo.DemoMeTube` (answers shaped as
above): search on both sources, add with the chosen format, finished and
failed downloads reported, a repeated download not mistaken for the old
one, the strict route at home and away, mutual TLS with an
`openssl`-made certificate in its own keyring schema, and the proxy
login (401 without the cookie). Screenshots at 360×720 and 1000×700.
Not yet against a real MeTube: YouTube and a running MeTube are not
available in the cloud container, so whether yt-dlp's YouTube Music
search still returns songs today is unchecked (M2 exit criterion).
