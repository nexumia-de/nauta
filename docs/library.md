---
type: Concept
title: Library features
description: Song and album menus, the swipe to queue, likes (stars) and Liked Songs, playlist editing, album orders, radio, popular songs and similar artists; what Navidrome's API allows and what it does not.
tags: [library, favourites, playlists, radio, gestures, spotify]
resource: ../nauta/actions.py
generated: { by: claude-code/2.1.317, at: 2026-11-04T20:30:00Z }
sources:
  - id: nd-pls
    resource: https://github.com/navidrome/navidrome/blob/7c1e68a1e4e68e7257affba4f25cd9cb545c7016/core/playlists/playlists.go
    title: Navidrome core/playlists/playlists.go (Create with a playlist id replaces the songs, Update removes by index)
  - id: nd-ann
    resource: https://github.com/navidrome/navidrome/blob/7c1e68a1e4e68e7257affba4f25cd9cb545c7016/server/subsonic/media_annotation.go
    title: Navidrome server/subsonic/media_annotation.go (star, unstar)
  - id: nd-browse
    resource: https://github.com/navidrome/navidrome/blob/7c1e68a1e4e68e7257affba4f25cd9cb545c7016/server/subsonic/browsing.go
    title: Navidrome server/subsonic/browsing.go (getTopSongs, getSimilarSongs2, getArtistInfo2)
  - id: nd-resp
    resource: https://github.com/navidrome/navidrome/blob/7c1e68a1e4e68e7257affba4f25cd9cb545c7016/server/subsonic/responses/responses.go
    title: Navidrome server/subsonic/responses (readonly playlists, starred)
---

# Why

The owner asked for the everyday features of Spotify that Navidrome
can serve (2026-11-04): queueing from any song, a menu on every
song, likes, playlist editing, radio. Issues #27–#33; what is left
over is in #34 (offline), #35 (crossfade, equalizer, speed), #36
(share links) and #8 (gapless).

# Song menu (`actions.py`)

Every song row (album, playlist, search, Liked Songs, Popular, queue)
has a "⋮" button; a long press or a right click opens the same menu as
a `GtkPopoverMenu`, built when it opens:

- **Play Next** (inserted after the current song) and **Add to Queue**
  (at the end), each with a toast;
- **Add to Liked Songs** / **Remove from Liked Songs**;
- **Add to Playlist…**: a dialog of the user's editable playlists and
  "New Playlist…";
- per list: **Remove from Playlist**, **Move Up**, **Move Down** (own
  playlists), **Remove from Queue**, **Move Up**, **Move Down** (queue);
- **Song Radio**, **Go to Album**, **Go to Artist**.

Album and playlist pages have the same queue and playlist entries for
all their songs in a "⋮" next to Play and Shuffle; albums also Radio
and Go to Artist, own playlists Rename… and Delete Playlist….

# Swipe (`swipe.py`)

Swiping a song row **from right to left** past a third of its width
adds the song to the queue (in the queue: removes it). The row's
content follows the finger and uncovers an icon on the accent colour.
Spotify swipes the other way, but left-to-right is libadwaita's swipe
back on every page (phosh-toolkit adaptive rule 9), so Nauta keeps that
direction free. The gesture takes the drag only when it is mostly
sideways, so scrolling is unaffected. Not yet tried on the phone's
touchscreen (#28).

# Likes (`favourites.py`)

Navidrome's "starred" songs, albums and artists[^nd-ann]. Nauta loads
the ids once with `getStarred2` after sign-in and keeps them current;
a change shows at once ("changed") and is undone if the server refuses.
The star sits on album and artist pages and on Now Playing.
**Liked Songs** is the first row of the Playlists view: liked songs
with Play and Shuffle, then liked albums and artists. It reloads after
the server has saved a change ("saved"), not before, or it would show
the old list.

# Playlists (`playlist_edit.py`)

- New: `createPlaylist` with `name` and `songId`s.
- Add: `updatePlaylist` `songIdToAdd` (at the end).
- Remove: `updatePlaylist` `songIndexToRemove` (0-based)[^nd-pls].
- Rename: `updatePlaylist` `name`.
- New order: `createPlaylist` with `playlistId` and all `songId`s, which
  **replaces** the songs[^nd-pls]; the Subsonic API has no move.
- Delete: `deletePlaylist`, after a confirmation.

Smart playlists and playlists of other users come with OpenSubsonic
`readonly: true` or another `owner`[^nd-resp]; they offer none of this
and are not listed in "Add to Playlist". Playlist folders, collaborative
playlists and cover uploads are not in the API.

# Album orders (`library.py`)

The sort button in the header (Albums view only): Recently Added,
Recently Played, Most Played, Name, Artist, Liked, Random
(`getAlbumList2` types). The choice is kept in `account.json`
(`album_sort`). Random loads one page only, as every page is new
random albums.

# Radio and discovery (`artist.py`, `actions.py`)

- **Song Radio**: the song, then `getSimilarSongs2` for it; **Radio**
  of an album and **Artist Radio** play `getSimilarSongs2` for the album
  or artist id.
- Artist page: **Popular** (`getTopSongs` with the artist's name, 5
  songs) and **Fans Also Like** (`getArtistInfo2` `similarArtist`).

Navidrome finds these through an agent such as Last.fm[^nd-browse];
without one the lists are empty: the sections are hidden and the radio
says "No similar songs". Not yet tried against the owner's server.

# Verified (2026-11-04, cloud container)

Against the demo server, which implements these calls like Navidrome
(likes and playlists change its state): `tests/test_library_api.py`
(repeated ids, playlist create / add / remove / reorder / rename /
delete, discovery, lyrics, album orders) and `tests/test_library_ui.py`
(menus and their actions, the swipe's thresholds, the album star,
playlist dialogs, Liked Songs, the artist page, the kept album order).
Screenshots at 360×720 and 1000×700.

[^nd-pls]: Navidrome core/playlists/playlists.go
[^nd-ann]: Navidrome server/subsonic/media_annotation.go
[^nd-browse]: Navidrome server/subsonic/browsing.go
[^nd-resp]: Navidrome server/subsonic/responses
