"""The play queue kept across restarts (docs/playback.md): the songs, the
current one and its position are saved in the data directory and set
again, paused, at the next start. No widgets."""
from dataclasses import dataclass, field

from gi.repository import GLib
from phosh_toolkit.settings import JsonStore

from nauta import settings

VERSION = 1
# Save the position at most this often while playing (seconds).
POSITION_EVERY = 10
# Wait this long after a change before writing (ms), so a burst of edits
# writes once.
DELAY = 500


@dataclass
class SavedQueue:
    songs: list = field(default_factory=list)
    index: int = -1
    position: float = 0
    repeat: str = "off"


class QueueMemory:
    """Watches a Player and keeps its queue in `queue.json`."""

    def __init__(self, player, path=None):
        self.player = player
        self.store = JsonStore(path or settings.data_dir() / "queue.json",
                               SavedQueue, VERSION)
        self._pending = 0
        self._saved_position = 0
        self._handlers = [
            player.connect("queue-changed", self._later),
            player.connect("song-changed", self._later),
            player.connect("state-changed", self._on_state),
        ]

    def restore(self):
        """Set the saved queue on the player (not playing)."""
        saved = self.store.load()
        self.player.set_repeat(saved.repeat)
        self.player.restore(saved.songs, saved.index, saved.position)

    def save(self):
        if self._pending:
            GLib.source_remove(self._pending)
            self._pending = 0
        player = self.player
        position = player.position if player.media is not None else \
            player.resume_at
        self._saved_position = position
        self.store.save(SavedQueue(list(player.queue), player.index,
                                   round(position, 1), player.repeat))
        return GLib.SOURCE_REMOVE

    def close(self):
        """Save now and stop watching."""
        self.save()
        for handler in self._handlers:
            self.player.disconnect(handler)
        self._handlers = []

    def _later(self, *_):
        if not self._pending:
            self._pending = GLib.timeout_add(DELAY, self._save_later)

    def _save_later(self):
        self._pending = 0
        return self.save()

    def _on_state(self, player):
        if player.media is not None and \
                abs(player.position - self._saved_position) >= POSITION_EVERY:
            self._later()
