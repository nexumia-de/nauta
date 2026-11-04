---
type: Plan
title: Roadmap
description: Goals and exit criteria of Nauta's milestones; the work items are GitHub issues in those milestones.
tags: [plan, roadmap, milestones]
generated: { by: claude-code/2.1.317, at: 2026-11-04T20:30:00Z }
---

# How the plan is tracked

Work items are [issues](https://github.com/nexumia-de/nauta/issues),
grouped by [milestones](https://github.com/nexumia-de/nauta/milestones)
and `area: …` labels; issues without a milestone are the backlog. This
file keeps only the goals. Workflow: the toolkit's
[planning with issues and milestones](../../phosh-toolkit/docs/planning.md).

# M0 – Scaffold, connection and playback (done in the first pull request)

App skeleton with metadata, Flatpak manifest, CI and tests; sign-in
with the home/remote route and client certificates
([connection](connection.md)); albums, artists, playlists, search,
album, artist and playlist pages, play queue, player bar and Now
Playing ([playback](playback.md)).

# M1 – On the phone

**Goal**: Nauta is the owner's daily music player on the phone.

**Exit criteria**: first release installed from the shared repository;
home/remote switching and the client certificate work against the
owner's Navidrome; music keeps playing with the screen off and is
controlled from Phosh's lock screen and media controls (MPRIS);
battery use while streaming measured.

# M2 – Listening comfort

**Goal**: what a daily music player needs beyond playing.

**Exit criteria**: gapless playback, favourites (star) and a favourites
view, sort orders for albums, the queue kept across restarts, sign-in
with an API key, servers with a private CA; finding and downloading new
songs through the user's own MeTube ([downloads](downloads.md)) works
against the owner's MeTube behind the proxy.

# M3 – Like Spotify

**Goal**: the everyday features of Spotify that Navidrome can serve
([library features](library.md)), at the owner's request.

**Exit criteria**: a menu on every song (play next, add to queue, like,
add to playlist, radio, go to album or artist); swipe to queue; Liked
Songs; playlists made, renamed, reordered and deleted in the app; the
queue edited on Now Playing with repeat, shuffle and a sleep timer;
radio, popular songs and similar artists; synced lyrics; volume
normalisation; checked on the phone against the owner's Navidrome.
Later: offline albums, crossfade and equalizer, share links.

# Risks

- **Background playback**: Phosh may suspend the phone with the screen
  off; playback then needs an inhibitor or the app keeps the session
  awake (M1).
- **No server id** in the Subsonic API: the local address is only used on
  listed home Wi-Fi networks ([connection](connection.md)).
- **NetworkManager access** from the Flatpak (`--system-talk-name`)
  is a permission Flathub would question; without it Nauta always uses
  the remote address.
