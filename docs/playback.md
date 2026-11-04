---
type: Concept
title: Playback
description: The play queue, streaming through the local media proxy as POST, streaming quality per route, scrobbling, and the player bar and Now Playing page.
tags: [playback, gstreamer, queue, proxy, scrobble]
resource: ../nauta/player.py
generated: { by: claude-code/2.1.317, at: 2026-11-04T14:00:00Z }
---

# Queue (`player.py`)

`Player` holds the queue (a list of songs) and the current index.
Playing an album, a playlist or a search result replaces the queue and
starts at the tapped song; "Shuffle" shuffles it. At the end of a song
the next one starts; "Previous" restarts the song after 3 s, else goes
back. After the last song playback stops and the queue stays.

# Streaming

- The player opens `http://127.0.0.1:<port>/<secret>/rest/stream?id=…&maxBitRate=…`
  on phosh-toolkit's media proxy; `Connection.forward` sends it up as
  **POST** to the current route with the credentials in the form body
  and the client certificate ([connection](connection.md)). `Range`
  passes through, so seeking works on files the server doesn't convert.
- `phosh_toolkit.media.Media` plays it with `playbin3`, sound only.
- **Quality**: `maxBitRate` from the preferences, "At Home" (default
  Original) on the local route and "Away" (default 192 kbit/s)
  otherwise. Above it Navidrome converts to its default format.
- When the route is not known yet (start, offline), the player resolves
  it first.

# Scrobbling

`scrobble` with `submission=false` when a song starts ("now playing"
on the server), `submission=true` once half of it or four minutes have
played, or at its end.

# UI (`nowplaying.py`)

- **Player bar** under every page except Now Playing: cover, title,
  artist, play/pause, next, and a thin progress line. Tapping it opens
  Now Playing.
- **Now Playing**: cover, title, artist and album, position slider with
  elapsed and remaining time, previous / play / next, and the queue
  (tap a song to jump). It is a normal page: swipe back closes it.
- Playback errors show as a toast ("Can't play this song: …").

# With the window closed (`window.py`)

- Closing the window while a song is loaded (playing or paused) only
  hides it; the application is held (`Gio.Application.hold`), so music
  goes on. Opening Nauta again shows the same window. When nothing is
  left to play (stopped, last song ended, error) a hidden Nauta quits.
  "Quit" in the main menu (Ctrl+Q) and the media controls' Quit end both.
- While music plays, suspend is inhibited (`Gtk.Application.inhibit`
  with `SUSPEND`, released on pause), so Phosh does not suspend the
  phone with the screen off. Without a session manager the call returns
  0 and nothing is inhibited.
- Not yet checked on the phone (nexumia-de/nauta#4).

# Media controls (`mpris.py`)

MPRIS 2 on the session bus as `org.mpris.MediaPlayer2.Nauta`
(`….Nauta.Devel` for the nightly app; the manifest has `--own-name` for
both): Phosh's lock screen and quick settings show title, artist, album,
length and cover, with play/pause, previous, next and seeking.

- Root: `Raise` (shows the window), `Quit`, `Identity` "Nauta",
  `DesktopEntry` the app id; no track list.
- Player: `PlaybackStatus` (Playing / Paused / Stopped), `Metadata`
  (`mpris:trackid` an object path made from the song id, `mpris:length`,
  `xesam:title`, `xesam:artist`, `xesam:album`, `xesam:trackNumber`,
  `mpris:artUrl`), `Position`, `CanGoNext`/`Previous`/`Play`/`Pause`/
  `Seek`; `Seek` past the end goes to the next song; `Seeked` after
  seeks; `PropertiesChanged` when a watched property changes.
- The cover is a `file://` URI of the cached cover (300 px), never a
  server URL: those would need credentials.
- Not yet checked on the phone's lock screen (nexumia-de/nauta#5).

# Not yet

Gapless playback and a queue kept across restarts (M2).

# Verified (2026-11-04, cloud container, GStreamer 1.24)

`tests/test_player.py`: WAV tones from the demo server through the
proxy with real GStreamer: play, pause, seek, next at the end, scrobbles,
restart vs. previous, shuffle keeps the tapped song first, a missing song
reports an error. `tests/test_mpris.py`: the interface on a private
dbus-daemon, driven like a lock screen (properties, change signals,
PlayPause, Play, Seek, Next, Raise, Quit, cover as a local file).
`tests/test_ui.py`: closing the window while playing hides it, holds
the app and inhibits suspend; pausing keeps it; stopping quits.
