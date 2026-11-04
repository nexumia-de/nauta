"""The play queue and playback (docs/playback.md): songs play through the
local media proxy with phosh_toolkit's playbin player, one after the
other; the server learns what plays (scrobble). No widgets."""
import logging
import random

from gi.repository import GObject
from phosh_toolkit import route
from phosh_toolkit.media import Media

log = logging.getLogger("nauta.player")

# Seconds into a song after which "previous" restarts it instead.
RESTART_AFTER = 3
# A song counts as played after half of it or four minutes (the usual
# scrobbling rule).
PLAYED_AFTER = 240


class Player(GObject.Object):
    """Signals: "song-changed" (new song or empty queue), "state-changed"
    (playing, position, duration), "error" (message)."""
    __gsignals__ = {
        "song-changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "state-changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "error": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    def __init__(self, connection, proxy, make_media=None):
        super().__init__()
        self.connection = connection
        self.proxy = proxy
        # Tests replace the sink; see tests/test_player.py.
        self.make_media = make_media or (lambda url: Media(url, video=False))
        self.queue = []
        self.index = -1
        self.media = None
        self._scrobbled = False

    # --- state -------------------------------------------------------

    @property
    def song(self):
        return self.queue[self.index] if 0 <= self.index < len(self.queue) else None

    @property
    def playing(self):
        return bool(self.media and self.media.get_playing())

    @property
    def position(self):
        """Seconds."""
        return self.media.get_timestamp() / 1_000_000 if self.media else 0

    @property
    def duration(self):
        """Seconds: from the stream once known, else from the server."""
        if self.media and self.media.get_duration() > 0:
            return self.media.get_duration() / 1_000_000
        return (self.song or {}).get("duration") or 0

    def bitrate(self):
        """kbit/s for the current route; 0 is the original file."""
        account = self.connection.account
        return (account.quality_home if self.connection.state == route.LOCAL
                else account.quality_away)

    # --- control -----------------------------------------------------

    def play(self, songs, start=0, shuffle=False):
        songs = list(songs)
        if not songs:
            return
        if shuffle:
            first = songs.pop(start) if start else None
            random.shuffle(songs)
            if first is not None:
                songs.insert(0, first)
            start = 0
        self.queue = songs
        self._load(start)

    def play_index(self, index):
        if 0 <= index < len(self.queue):
            self._load(index)

    def toggle(self):
        if self.media is None:
            if self.song:
                self._load(self.index)
            return
        self.media.set_playing(not self.media.get_playing())

    def next(self):
        if self.index + 1 < len(self.queue):
            self._load(self.index + 1)
        else:
            self.stop()

    def previous(self):
        if self.position > RESTART_AFTER or self.index == 0:
            self.seek(0)
        else:
            self._load(self.index - 1)

    def seek(self, seconds):
        if self.media and self.media.is_seekable():
            self.media.seek(int(max(0, seconds) * 1_000_000))
            self.emit("state-changed")

    def stop(self):
        """Stop and keep the queue; play() or toggle() starts again."""
        self._release()
        self.emit("state-changed")

    def clear(self):
        self._release()
        self.queue, self.index = [], -1
        self.emit("song-changed")

    # --- internals ---------------------------------------------------

    def _release(self):
        if self.media is not None:
            self.media.stop()
            self.media = None

    def _load(self, index):
        self._release()
        self.index = index
        self._scrobbled = False
        if not self.connection.base_url:
            # Not connected yet (start-up, offline): find the route first.
            self.emit("song-changed")

            def resolved(error):
                if error is not None:
                    self.emit("error", str(error))
                elif self.index == index and self.media is None:
                    self._start()
            self.connection.resolve(resolved)
            return
        self._start()

    def _start(self):
        song = self.song
        url = self.proxy.url(self.connection.api.stream_path(song["id"], self.bitrate()))
        self.media = self.make_media(url)
        for prop in ("playing", "prepared", "ended", "timestamp", "duration", "error"):
            self.media.connect(f"notify::{prop}", self._on_media)
        self.media.play()
        self.emit("song-changed")
        self.emit("state-changed")
        self._scrobble(song, False)

    def _scrobble(self, song, submission):
        self.connection.call(self.connection.api.scrobble,
                             lambda r, e: e and log.info("scrobble: %s", e),
                             song["id"], submission)

    def _on_media(self, media, pspec):
        if media is not self.media:
            return
        name = pspec.name
        if name == "error" and media.get_error():
            message = media.get_error()
            self._release()
            self.emit("state-changed")
            self.emit("error", message)
            return
        if name == "timestamp" and not self._scrobbled and self.duration:
            if self.position >= min(self.duration / 2, PLAYED_AFTER):
                self._scrobbled = True
                self._scrobble(self.song, True)
        if name == "ended" and media.get_ended():
            if not self._scrobbled:
                self._scrobbled = True
                self._scrobble(self.song, True)
            self.next()
            return
        self.emit("state-changed")
