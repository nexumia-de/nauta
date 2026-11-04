---
type: Decision Record
title: New music through the user's own MeTube
description: Nauta finds and downloads new songs through a MeTube server the user runs next to Navidrome, searching YouTube Music through MeTube's /browse, instead of downloading on the phone or talking to YouTube directly.
tags: [decision, downloads, metube, yt-dlp, search]
generated: { by: claude-code/2.1.318, at: 2026-11-04T09:30:00Z }
---

# Status

Accepted (2026-11-04), at the owner's request, in milestone M2.
Amended the same day: albums and playlists are searched from the phone
([decision](youtube-music-search.md)).

# Context

The owner wants to search for new songs in Nauta and download them into
the library. [MeTube](https://github.com/alexta69/metube) (AGPL-3.0)
is a self-hosted web front end for yt-dlp; it writes the files on the
server, where Navidrome can scan them. It has no search call and no
login of its own.

# Decision

- **The download runs on the server, in the user's MeTube.** Nauta only
  sends MeTube the URL; the files land in Navidrome's music folder,
  which the user points MeTube at. The phone stores nothing.
- **MeTube is reached like Navidrome**: its own address pair, home Wi-Fi
  list, client certificate and proxy login through phosh-toolkit's
  router and connection form, kept apart from the music server's
  (own account file and keyring schema). Strict local route: MeTube has
  no server id. Optional: without it Nauta is unchanged.
- **Search goes through MeTube too**, with `/browse` on a YouTube Music
  search URL ("songs" section, default) or `ytsearch20:` (YouTube). The
  phone never talks to YouTube, so the same mutual TLS and proxy login
  cover search, and no YouTube API key or extra host is needed.
- **No code from MeTube or yt-dlp** in Nauta; only API facts read from
  their source ([downloads](../downloads.md)).

# Alternatives

- **yt-dlp in the Flatpak** to search or download on the phone: a large
  module that YouTube changes break every few weeks, downloads over
  mobile data, and the files would still have to reach the server.
- **YouTube Data API or an Invidious instance for search**: an API key
  or a third-party host, outside the proxy, with their own terms.
- **Paste or share a link only**: simplest, but no search, which is
  what the owner asked for.
- **Only `ytsearch:`**: more robust (video titles include the artist,
  durations), but noisier results (videos, covers, live versions); kept
  as the second source.

# Consequences

- Results from YouTube Music show the title only (yt-dlp's flat search
  entries).
- Whether downloading is allowed depends on the source, the content and
  the user's country; Nauta leaves that to the user, who runs the
  server.
