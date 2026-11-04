"""The queue on Now Playing (docs/playback.md): what comes next, with
each song's menu (remove, move up or down) and the swipe that removes
it; "Clear" empties what comes next."""
from gi.repository import Gtk, Pango

from nauta import actions, widgets


class QueueView(Gtk.Box):
    def __init__(self, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                         margin_top=24)
        self.window = window
        self.player = player = window.player
        head = Gtk.Box(spacing=6)
        self.title = Gtk.Label(label="Next Up", xalign=0, hexpand=True,
                               ellipsize=Pango.EllipsizeMode.END)
        self.title.add_css_class("title-4")
        head.append(self.title)
        self.clear = Gtk.Button(label="Clear", valign=Gtk.Align.CENTER,
                                tooltip_text="Remove the songs that come next")
        self.clear.add_css_class("flat")
        self.clear.connect("clicked", lambda b: player.clear_upcoming())
        head.append(self.clear)
        self.append(head)
        self.list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.list.add_css_class("boxed-list")
        self.list.connect("row-activated", lambda b, row: player.play_index(
            self.player.index + 1 + row.get_index()))
        self.append(self.list)
        self.actions = actions.SongActions(
            window,
            extras=[("Remove from Queue", self._remove),
                    ("Move Up", lambda i: self._move(i, -1)),
                    ("Move Down", lambda i: self._move(i, 1))],
            swipe=("list-remove-symbolic", "Remove from Queue",
                   lambda song, i: self._remove(i)),
            show_queue=False)
        self.fill()

    def fill(self):
        """Rebuild the rows from the player's queue."""
        while (row := self.list.get_row_at_index(0)) is not None:
            self.list.remove(row)
        upcoming = self.player.upcoming
        for i, song in enumerate(upcoming):
            self.list.append(widgets.song_row(
                song, str(i + 1), covers=self.window.covers, actions=self.actions,
                index=i))
        self.set_visible(bool(upcoming))

    def _queue_index(self, i):
        return self.player.index + 1 + i

    def _remove(self, i):
        self.player.remove(self._queue_index(i))

    def _move(self, i, step):
        to = i + step
        if 0 <= to < len(self.player.upcoming):
            self.player.move(self._queue_index(i), self._queue_index(to))
