"""The play queue and playback (docs/playback.md): songs play through the
local media proxy with phosh_toolkit's playbin player, one after the
other; the server learns what plays (scrobble). The queue can be edited
while it plays; repeat and shuffle. No widgets."""
import logging
import random

from gi.repository import GObject
from phosh_toolkit import route
from phosh_toolkit.media import Media

from nauta import loudness

log = logging.getLogger("nauta.player")

# Seconds into a song after which "previous" restarts it instead.
RESTART_AFTER = 3
# A song counts as played after half of it or four minutes (the usual
# scrobbling rule).
PLAYED_AFTER = 240
# Repeat modes.
REPEAT_OFF, REPEAT_ALL, REPEAT_ONE = "off", "all", "one"
REPEAT_MODES = (REPEAT_OFF, REPEAT_ALL, REPEAT_ONE)


class Player(GObject.Object):
    """Signals: "song-changed" (new song or empty queue), "queue-changed"
    (songs added, removed or moved; repeat or shuffle), "state-changed"
    (playing, position, duration), "error" (message)."""
    __gsignals__ = {
        "song-changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "queue-changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "state-changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "error": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    def __init__(self, connection, proxy, make_media=None):
        super().__init__()
        self.connection = connection
        self.proxy = proxy
        # Tests replace the sink; see tests/test_player.py.
        self.make_media = make_media or self._make_media
        self.queue = []
        self.index = -1
        self.media = None
        self.repeat = REPEAT_OFF
        self.shuffled = False
        # The queue in its order before shuffling; None when not shuffled.
        self._unshuffled = None
        # Seconds to seek to once a restored song is loaded (resume.py).
        self.resume_at = 0
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

    @property
    def upcoming(self):
        """The songs after the current one."""
        return self.queue[self.index + 1:]

    # --- control -----------------------------------------------------

    def play(self, songs, start=0, shuffle=False):
        songs = list(songs)
        if not songs:
            return
        self._unshuffled = list(songs) if shuffle else None
        self.shuffled = shuffle
        if shuffle:
            first = songs.pop(start) if start else None
            random.shuffle(songs)
            if first is not None:
                songs.insert(0, first)
            start = 0
        self.queue = songs
        self.emit("queue-changed")
        self._load(start)

    def restore(self, songs, index, position=0):
        """Set the queue saved at the last run without playing; play or
        toggle starts at `position` seconds (docs/playback.md)."""
        songs = list(songs)
        if not songs or not 0 <= index < len(songs):
            return
        self.queue, self.index = songs, index
        self.resume_at = position
        self.emit("queue-changed")
        self.emit("song-changed")

    # --- editing the queue ------------------------------------------

    def play_next(self, songs):
        """Insert songs right after the current one."""
        songs = list(songs)
        if not songs:
            return
        if self.song is None:
            self.play(songs)
            return
        at = self.index + 1
        self.queue[at:at] = songs
        if self._unshuffled is not None:
            at = self._position_in_unshuffled() + 1
            self._unshuffled[at:at] = songs
        self.emit("queue-changed")

    def add(self, songs):
        """Add songs at the end of the queue."""
        songs = list(songs)
        if not songs:
            return
        if self.song is None:
            self.play(songs)
            return
        self.queue += songs
        if self._unshuffled is not None:
            self._unshuffled += songs
        self.emit("queue-changed")

    def remove(self, index):
        """Remove a song; removing the current one plays the next."""
        if not 0 <= index < len(self.queue):
            return
        song = self.queue.pop(index)
        if self._unshuffled is not None:
            self._unshuffled = [s for s in self._unshuffled if s is not song]
        if index < self.index:
            self.index -= 1
        elif index == self.index:
            if not self.queue:
                self.clear()
                return
            was_playing = self.media is not None
            if self.index >= len(self.queue):
                self.index = len(self.queue) - 1
                self._release()
                self.emit("song-changed")
                self.emit("state-changed")
            elif was_playing:
                self._load(self.index)
            else:
                self.emit("song-changed")
        self.emit("queue-changed")

    def move(self, index, to):
        """Move a song to another place; the current song keeps playing."""
        if not (0 <= index < len(self.queue) and 0 <= to < len(self.queue)) \
                or index == to:
            return
        current = self.song
        song = self.queue.pop(index)
        self.queue.insert(to, song)
        self.index = next(i for i, s in enumerate(self.queue) if s is current)
        self.emit("queue-changed")

    def clear_upcoming(self):
        """Remove every song after the current one."""
        if self.upcoming:
            kept = self.queue[:self.index + 1]
            if self._unshuffled is not None:
                self._unshuffled = [s for s in self._unshuffled
                                    if any(s is k for k in kept)]
            self.queue = kept
            self.emit("queue-changed")

    def set_shuffle(self, shuffle):
        """Shuffle the songs after the current one, or put the queue back
        in its order (songs added since then stay where they were put)."""
        if shuffle == self.shuffled:
            return
        self.shuffled = shuffle
        if shuffle:
            self._unshuffled = list(self.queue)
            rest = self.upcoming
            random.shuffle(rest)
            self.queue = self.queue[:self.index + 1] + rest
        elif self._unshuffled is not None:
            current = self.song
            self.queue = self._unshuffled
            self._unshuffled = None
            self.index = next((i for i, s in enumerate(self.queue) if s is current),
                              self.index)
        else:
            self._unshuffled = None
        self.emit("queue-changed")

    def set_repeat(self, mode):
        if mode in REPEAT_MODES and mode != self.repeat:
            self.repeat = mode
            self.emit("queue-changed")

    def cycle_repeat(self):
        """Off → all → one → off."""
        self.set_repeat(REPEAT_MODES[(REPEAT_MODES.index(self.repeat) + 1)
                                     % len(REPEAT_MODES)])

    def play_index(self, index):
        if 0 <= index < len(self.queue):
            self._load(index)

    def toggle(self):
        if self.media is None:
            if self.song:
                self._load(self.index)
            return
        self.media.set_playing(not self.media.get_playing())

    def pause(self):
        if self.media is not None:
            self.media.set_playing(False)

    def next(self):
        if self.index + 1 < len(self.queue):
            self._load(self.index + 1)
        elif self.repeat != REPEAT_OFF and self.queue:
            self._load(0)
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
        self._unshuffled = None
        self.shuffled = False
        self.emit("queue-changed")
        self.emit("song-changed")

    # --- internals ---------------------------------------------------

    def _make_media(self, url):
        media = Media(url, video=False)
        loudness.apply(media, self.connection.account.replay_gain)
        return media

    def _position_in_unshuffled(self):
        current = self.song
        return next((i for i, s in enumerate(self._unshuffled) if s is current),
                    len(self._unshuffled) - 1)

    def _release(self):
        if self.media is not None:
            self.media.stop()
            self.media = None

    def _load(self, index):
        self._release()
        if index != self.index:
            self.resume_at = 0
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
        if name == "prepared" and media.is_prepared() and self.resume_at:
            at, self.resume_at = self.resume_at, 0
            self.seek(at)
        if name == "ended" and media.get_ended():
            if not self._scrobbled:
                self._scrobbled = True
                self._scrobble(self.song, True)
            if self.repeat == REPEAT_ONE:
                self._load(self.index)
            else:
                self.next()
            return
        self.emit("state-changed")
