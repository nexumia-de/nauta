---
type: Concept
title: Playback
description: The play queue and its editing, repeat and shuffle, the queue kept across restarts, streaming through the local media proxy as POST, quality per route, volume normalisation, scrobbling, sleep timer, lyrics, and the player bar and Now Playing page.
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

- **Editing** while it plays: `play_next` inserts after the current
  song, `add` appends (both start playing when nothing is loaded),
  `remove` (removing the current song plays the next), `move`,
  `clear_upcoming`. The signal "queue-changed" tells the views.
- **Shuffle** as a toggle shuffles only what comes next, like Spotify;
  turning it off puts the queue back in its order, with songs added in
  between kept.
- **Repeat**: off → all (after the last song the first) → one (the song
  again at its end; Next still goes on).

# Kept across restarts (`resume.py`)

The queue, the current song, its position and repeat are saved in
`queue.json` in the data directory (half a second after a change, every
10 s of playing, at quit), as the songs' metadata: no URLs, no
credentials. At the next start they are set again, paused; Play
continues at the saved position (a seek once the stream is prepared;
streams the server converts can't seek, they start from the
beginning). Signing out clears the queue and so the file.

# Volume normalisation (`loudness.py`)

GStreamer's `rgvolume` as playbin's audio filter reads the ReplayGain
tags in the stream: Off, per song (default) or per album, in
Preferences → Playback; songs without tags play 6 dB lower, and the
headroom is 0 dB, so tagged loud songs are not clipped. It takes effect
with the next song. Whether Navidrome keeps the tags in converted
streams is not checked yet.

# Sleep timer (`sleep.py`)

From Now Playing's "⋮" → Sleep Timer: pause after 15, 30, 45 or 60
minutes or at the end of the song (the next one starts and is paused
at once); "Pauses in … min" shows under the controls.

# Lyrics (`lyrics.py`)

The Lyrics button on Now Playing opens a page with
`getLyricsBySongId` (OpenSubsonic `songLyrics`): synced lyrics before
unsynced ones; the current line is marked in the accent colour and
scrolled to a third of the height; tapping a line seeks there. The
lyric's `offset` (ms, positive = earlier) is applied. The page follows
the player to the next song; "No Lyrics" when the server has none.

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

# UI (`nowplaying.py`, `player_bar.py`)

- **Player bar** under every page except Now Playing: cover, title,
  artist, play/pause, next, and a thin progress line. Tapping it opens
  Now Playing.
- **Now Playing**: cover, title, artist and album with the like star,
  position slider with elapsed and remaining time, shuffle / previous /
  play / next / repeat, and **Next Up** (`queue_view.py`): the songs
  after the current one with their menu (remove, move up or down) and
  the swipe that removes, and "Clear". The header has Lyrics and the
  song's "⋮" menu with the sleep timer. It is a normal page: swipe back
  closes it.
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
- Confirmed by the owner on the phone (2026-11-04): music keeps playing
  with the screen off (nexumia-de/nauta#4).

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
- Confirmed by the owner on the phone (2026-11-04): Phosh's lock screen
  shows the song and its controls work (nexumia-de/nauta#5).

# Not yet

Gapless playback (#8) and crossfade (#35) need changes to
phosh-toolkit's `media.Media` (one pipeline per song today).

# Verified (2026-11-04, cloud container, GStreamer 1.24)

`tests/test_player.py`: WAV tones from the demo server through the
proxy with real GStreamer: play, pause, seek, next at the end, scrobbles,
restart vs. previous, shuffle keeps the tapped song first, a missing song
reports an error. `tests/test_mpris.py`: the interface on a private
dbus-daemon, driven like a lock screen (properties, change signals,
PlayPause, Play, Seek, Next, Raise, Quit, cover as a local file).
`tests/test_ui.py`: closing the window while playing hides it, holds
the app and inhibits suspend; pausing keeps it; stopping quits.
`tests/test_player.py` also: play next and add, remove and move with
the current song kept, shuffle on and off, repeat all and one, the
queue saved and resumed at its position, `rgvolume` in the pipeline
with sound going through, the sleep timer. `tests/test_library_ui.py`:
Next Up, repeat, shuffle, sleep timer and lyrics following the song.
