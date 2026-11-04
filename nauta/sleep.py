"""The sleep timer (docs/playback.md): pause after some minutes or at the
end of the current song. No widgets."""
import time

from gi.repository import GLib, GObject

# Minutes offered in the menu.
CHOICES = (15, 30, 45, 60)
END_OF_SONG = -1


class SleepTimer(GObject.Object):
    """Signals "changed" (set, cancelled or done)."""
    __gsignals__ = {"changed": (GObject.SignalFlags.RUN_FIRST, None, ())}

    def __init__(self, player, clock=time.monotonic):
        super().__init__()
        self.player = player
        self.clock = clock
        self.minutes = 0           # 0 off, END_OF_SONG, or minutes
        self._ends_at = 0
        self._source = 0
        self._song = None
        self._handler = player.connect("song-changed", self._on_song)

    @property
    def active(self):
        return self.minutes != 0

    def remaining(self):
        """Seconds left; None at the end of the song or when off."""
        if self.minutes > 0:
            return max(0, self._ends_at - self.clock())
        return None

    def start(self, minutes):
        """Minutes from now, or END_OF_SONG."""
        self.cancel(notify=False)
        self.minutes = minutes
        if minutes == END_OF_SONG:
            self._song = self.player.song
        else:
            self._ends_at = self.clock() + minutes * 60
            self._source = GLib.timeout_add_seconds(minutes * 60, self._done)
        self.emit("changed")

    def cancel(self, notify=True):
        if self._source:
            GLib.source_remove(self._source)
            self._source = 0
        self.minutes = 0
        self._song = None
        if notify:
            self.emit("changed")

    def close(self):
        self.cancel(notify=False)
        if self._handler:
            self.player.disconnect(self._handler)
            self._handler = 0

    def _done(self):
        self._source = 0
        self.player.pause()
        self.cancel()
        return GLib.SOURCE_REMOVE

    def _on_song(self, player):
        # The song it waited for is over: the next one starts paused.
        if self.minutes == END_OF_SONG and player.song is not self._song:
            self._done()
