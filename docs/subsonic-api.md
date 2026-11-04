---
type: Reference
title: Subsonic API as Navidrome serves it
description: The Subsonic and OpenSubsonic calls Nauta uses, how authentication and errors work, read from Navidrome's source at a recorded commit.
tags: [api, subsonic, opensubsonic, navidrome, authentication]
resource: ../nauta/api.py
generated: { by: claude-code/2.1.317, at: 2026-11-04T14:00:00Z }
sources:
  - id: nd-api
    resource: https://github.com/navidrome/navidrome/blob/7c1e68a1e4e68e7257affba4f25cd9cb545c7016/server/subsonic/api.go
    title: Navidrome server/subsonic/api.go (routes, sendError)
  - id: nd-mw
    resource: https://github.com/navidrome/navidrome/blob/7c1e68a1e4e68e7257affba4f25cd9cb545c7016/server/subsonic/middlewares.go
    title: Navidrome server/subsonic/middlewares.go (postFormToQueryParams, checkRequiredParameters, authenticate, validateCredentials)
  - id: nd-os
    resource: https://github.com/navidrome/navidrome/blob/7c1e68a1e4e68e7257affba4f25cd9cb545c7016/server/subsonic/opensubsonic.go
    title: Navidrome server/subsonic/opensubsonic.go (extensions)
  - id: nd-resp
    resource: https://github.com/navidrome/navidrome/blob/7c1e68a1e4e68e7257affba4f25cd9cb545c7016/server/subsonic/responses/responses.go
    title: Navidrome server/subsonic/responses (JSON field names, error codes)
  - id: nd-stream
    resource: https://github.com/navidrome/navidrome/blob/7c1e68a1e4e68e7257affba4f25cd9cb545c7016/core/stream/media_streamer.go
    title: Navidrome core/stream/media_streamer.go (http.ServeContent)
---

# Source

Read from Navidrome's `main` at commit `7c1e68a` (2026-11-03, after
tag v0.64.2), cloned from GitHub. The public docs
(`www.navidrome.org`, `opensubsonic.netlify.app`, `www.subsonic.org`)
and the demo server are blocked in the cloud environment
([dev environment](dev-environment.md)). The owner confirmed on
2026-11-04 that browsing and playing work against their Navidrome, at
home and on mobile data (nexumia-de/nauta#6); the calls added for the
[library features](library.md) are not yet tried there.

# Requests

- Endpoint `<base>/rest/<method>`; `.view` suffixes are optional.
- **POST with a form body** works for every call: the middleware
  `postFormToQueryParams` merges the body into the query before
  anything else runs, and Navidrome lists the OpenSubsonic extension
  `formPost`[^nd-mw][^nd-os]. Nauta sends every call this way, so no
  credential is in a URL ([decision](decisions/form-post-credentials.md)).
- Required: `u` (user, unless `apiKey` or reverse-proxy auth), `v`
  (API version, Nauta sends 1.16.1), `c` (client name, "Nauta"); Nauta
  adds `f=json`.
- `getOpenSubsonicExtensions` is registered before the authentication
  middleware and answers **without credentials**[^nd-api]. Nauta uses it
  as the probe: `openSubsonic: true`, `type` ("navidrome"),
  `serverVersion` and the extension list. It has **no server id**.

# Authentication

`validateCredentials`[^nd-mw] accepts:

| Fields | Check |
|---|---|
| `u`, `t`, `s` | `t == md5(password + s)` in hex; Nauta's choice, a fresh salt per request |
| `u`, `p` | plain or `enc:`-hex password |
| `u`, `jwt` | Navidrome's own UI tokens |
| `apiKey` | OpenSubsonic `apiKeyAuthentication`; must not be combined with `u`, `p`, `t`, `s` (error 43) |

Navidrome also accepts reverse-proxy authentication (a user header from
a whitelisted proxy). Failed logins are rate-limited per IP and user.

# Errors

Failures come with **HTTP 200** and `{"subsonic-response": {"status":
"failed", "error": {"code": …, "message": …}}}`[^nd-api], except "too
many transcodes" (HTTP 429). Codes[^nd-resp]: 0 generic, 10 missing
parameter, 40 wrong user or password, 41 token auth not supported, 43
multiple auth mechanisms, 44 invalid API key, 50 not authorised, 70 not
found. Nauta treats 40, 41 and 44 as "signed out".

# Calls used

| Call | Parameters | Answer key |
|---|---|---|
| `getOpenSubsonicExtensions` | – | `openSubsonicExtensions` |
| `ping` | – | – |
| `getAlbumList2` | `type` (newest, …), `size`, `offset` | `albumList2.album[]` |
| `getArtists` | – | `artists.index[].artist[]` |
| `getArtist` | `id` | `artist` with `album[]` |
| `getAlbum` | `id` | `album` with `song[]` |
| `getPlaylists`, `getPlaylist` | `id` | `playlists.playlist[]`, `playlist` with `entry[]` |
| `search3` | `query`, `artistCount`, `albumCount`, `songCount` | `searchResult3` with `artist`, `album`, `song` |
| `getCoverArt` | `id`, `size` | image bytes |
| `stream` | `id`, `maxBitRate` (kbit/s) | audio bytes |
| `scrobble` | `id`, `submission` | – |
| `star`, `unstar` | `id`, `albumId`, `artistId` (each repeatable) | – |
| `getStarred2` | – | `starred2` with `artist`, `album`, `song` |
| `createPlaylist` | `name` or `playlistId` (replaces the songs), `songId` (repeatable) | `playlist` with `entry[]` |
| `updatePlaylist` | `playlistId`, `name`, `songIdToAdd`, `songIndexToRemove` (0-based; repeatable) | – |
| `deletePlaylist` | `id` | – |
| `getSimilarSongs2` | `id` (song, album or artist), `count` | `similarSongs2.song[]` |
| `getTopSongs` | `artist` (name), `count` | `topSongs.song[]` |
| `getArtistInfo2` | `id`, `count` | `artistInfo2` with `similarArtist[]` |
| `getLyricsBySongId` | `id` | `lyricsList.structuredLyrics[]` with `synced`, `offset`, `line[]` (`start` ms, `value`) |

`getAlbumList2` types: newest, recent, frequent, random,
alphabeticalByName, alphabeticalByArtist, starred, highest, byGenre,
byYear. Liked items carry `starred` (a time); playlists carry
OpenSubsonic `readonly` (smart playlists, others' playlists). Similar
songs, top songs and similar artists come from an agent (Last.fm and
others) and are empty without one ([library features](library.md)).

JSON field names (struct tags)[^nd-resp]: songs (`Child`) have `id`,
`title`, `album`, `artist`, `track`, `discNumber`, `year`,
`coverArt`, `duration` (s), `albumId`, `artistId`, `suffix`,
`bitRate`; albums (`AlbumID3`) `id`, `name`, `artist`,
`artistId`, `coverArt`, `songCount`, `duration`, `year`,
`created`; artists `id`, `name`, `coverArt`, `albumCount`.

`stream` serves files with Go's `http.ServeContent`[^nd-stream], so
`Range` works (for POST too); transcoded streams answer
`Accept-Ranges: none`.

[^nd-api]: Navidrome server/subsonic/api.go
[^nd-mw]: Navidrome server/subsonic/middlewares.go
[^nd-os]: Navidrome server/subsonic/opensubsonic.go
[^nd-resp]: Navidrome server/subsonic/responses
[^nd-stream]: Navidrome core/stream/media_streamer.go
