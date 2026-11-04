---
type: Decision Record
title: Albums and playlists are searched from the phone
description: Nauta searches YouTube Music's albums and playlists directly from the phone through YouTube Music's web API, because MeTube's /browse can't list them; their songs are still listed and downloaded through MeTube.
tags: [decision, downloads, search, youtube-music, metube]
generated: { by: claude-code/2.1.318, at: 2026-11-04T16:00:00Z }
sources:
  - id: metube
    resource: https://github.com/alexta69/metube/blob/7e73766238f3fc491b2aeba0c3c8b415c408eaaa/app/subscriptions.py
    title: MeTube, app/subscriptions.py, extract_flat_playlist, _is_media_entry and browse_playlist (commit 7e73766, 2026-11-01)
  - id: yt-dlp
    resource: https://github.com/yt-dlp/yt-dlp/tree/412e7f0/yt_dlp/extractor/youtube
    title: yt-dlp, _search.py (YoutubeMusicSearchURLIE._SECTIONS), _tab.py (_music_reponsive_list_entry, _search_results), _base.py (client "web_music") (commit 412e7f0, 2026-11-04)
---

# Status

Accepted (2026-11-04), chosen by the owner. It amends
[new music through MeTube](metube-downloads.md): in that decision the phone
never talked to YouTube. Now it does for this one search.

# Context

The owner wants search filters for albums and playlists, and wants to
download a whole album or playlist, or only some of its songs.

MeTube's `/browse` can't list albums or playlists:

- In yt-dlp's YouTube Music search, album and playlist results are bare
  links (`music.youtube.com/browse/MPREb_…`, `…/playlist?list=…`) with
  no title[^yt-dlp].
- MeTube's `extract_flat_playlist` keeps only entries that look like
  media. A playlist link without a duration or similar field is not
  one. When no entry is, MeTube opens the first five entries and
  answers with the songs of the first that has any[^metube]. So an album
  search answers with the songs of the first album found.
- The same happens with a YouTube playlist search (`sp=EgIQAw==`).

Once Nauta has the link of an album or playlist, `/browse` lists its
songs and `/add` downloads all of them.

The owner chose this option over two others: only accepting pasted
links, and waiting for a MeTube change upstream.

# Decision

- **The list of albums and playlists comes from YouTube Music's web
  API, asked by the phone** (`POST music.youtube.com/youtubei/v1/search`,
  client `WEB_REMIX`, the section's `params` from yt-dlp's
  `_SECTIONS`[^yt-dlp]; `nauta/ytmusic.py`). No API key, no account, no
  cookies.
- **This client is separate**: its own HTTP client, so the download
  server's client certificate, proxy cookies and proxy login are never
  sent to YouTube. It sends Nauta's User-Agent.
- **Albums reach MeTube as their playlist** (`…/playlist?list=OLAK5uy_…`),
  never as their album page (`…/browse/MPREb_…`), which MeTube's
  `/browse` can't list ([details](../downloads.md#albums-and-playlists-from-the-phone)).
  When the search result doesn't name the playlist, the phone reads it
  from the album page on YouTube Music.
- **Everything else stays with MeTube**: songs and videos are still
  searched through `/browse`; the songs of an album or playlist are
  listed through `/browse`; downloads go through `/add`.
- **Whole albums and playlists are sent to MeTube as one link.** MeTube
  then numbers the tracks from the playlist and uses its playlist
  folder template. Single songs are sent one by one.
- **No code from yt-dlp**, only the request facts.

# Alternatives

- **Paste a link only**: no new host and nothing that can break on
  YouTube's side. But there is no album search, which is what the owner
  asked for. Pasting a link is still supported.
- **A MeTube change upstream** (a flag for `/browse` that lists
  playlist results): the cleanest option, but outside Nauta's control,
  and it would need a newer MeTube.
- **Full extraction of each search result in MeTube**: one yt-dlp run per
  album, too slow for a search.

# Consequences

- The phone talks to `music.youtube.com` when you search albums or
  playlists. It does so directly, not through the user's reverse
  proxy.
- The web API is not official. When YouTube changes it, album and
  playlist search breaks, while songs, videos and pasted links keep
  working. The client version is copied from yt-dlp and has to be updated by hand.
- `music.youtube.com` is blocked in the cloud environment, so this search
  is tested only against the stand-in `nauta.demo.DemoYouTubeMusic`.
  It has not been checked against the live service yet.
