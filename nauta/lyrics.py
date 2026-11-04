"""The lyrics of the song that plays (docs/playback.md), from
getLyricsBySongId (OpenSubsonic songLyrics). Synced lyrics mark the
current line and follow it; tapping a line seeks there. The page follows
the player to the next song."""
from gi.repository import Adw, GLib, Gtk, Pango

from nauta import widgets


def best(lyrics):
    """The structured lyric to show: synced before unsynced."""
    with_lines = [lyric for lyric in lyrics if lyric.get("line")]
    synced = [lyric for lyric in with_lines if lyric.get("synced")]
    return (synced or with_lines or [None])[0]


def current_line(lines, ms):
    """Index of the line that plays at `ms`, -1 before the first."""
    index = -1
    for i, line in enumerate(lines):
        if (line.get("start") or 0) <= ms:
            index = i
        else:
            break
    return index


class LyricsPage(Adw.NavigationPage):
    def __init__(self, window):
        super().__init__(title="Lyrics", tag="lyrics")
        self.window = window
        self.player = window.player
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        view = Adw.ToolbarView(content=self.stack)
        self.heading = Adw.WindowTitle(title="Lyrics")
        view.add_top_bar(Adw.HeaderBar(title_widget=self.heading))
        self.set_child(view)
        self.lines = []
        self.labels = []
        self.offset = 0
        self.current = -1
        self._song = None
        self._handlers = [self.player.connect("song-changed", self._on_song),
                          self.player.connect("state-changed", self._on_state)]
        self.connect("hidden", self._on_hidden)
        self._on_song(self.player)

    def _on_hidden(self, *_):
        if self.get_parent() is None:
            for handler in self._handlers:
                self.player.disconnect(handler)
            self._handlers = []

    def _on_song(self, player):
        song = player.song
        if song is self._song:
            return
        self._song = song
        for child in list(self.stack):
            self.stack.remove(child)
        self.lines, self.labels, self.current = [], [], -1
        if song is None:
            self._status("Nothing Playing", "")
            return
        self.heading.set_subtitle(song.get("title") or "")
        self.stack.add_named(widgets.loading_page(), "loading")
        self.stack.set_visible_child_name("loading")
        conn = self.window.connection
        conn.call(conn.api.lyrics, lambda r, e, s=song: self._on_lyrics(s, r, e),
                  song["id"])

    def _status(self, title, description, retry=None):
        if retry is not None:
            page = widgets.error_page(title, description, retry)
        else:
            page = Adw.StatusPage(icon_name="format-justify-left-symbolic",
                                  title=title, description=description)
        self.stack.add_named(page, "status")
        self.stack.set_visible_child_name("status")

    def _on_lyrics(self, song, lyrics, error):
        if song is not self._song:
            return
        if error is not None:
            def retry():
                self._song = None
                self._on_song(self.player)
            self._status("Can't Load the Lyrics", str(error), retry)
            return
        lyric = best(lyrics)
        if lyric is None:
            self._status("No Lyrics", "The server has no lyrics for this song")
            return
        self.synced = bool(lyric.get("synced"))
        self.offset = lyric.get("offset") or 0
        self.lines = lyric["line"]
        box = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        box.add_css_class("nauta-lyrics")
        for line in self.lines:
            label = Gtk.Label(label=line.get("value") or " ", wrap=True, xalign=0,
                              wrap_mode=Pango.WrapMode.WORD_CHAR,
                              margin_top=6, margin_bottom=6, margin_start=12,
                              margin_end=12)
            label.add_css_class("title-4")
            if self.synced:
                label.add_css_class("dimmed")
                label.add_css_class("dim-label")
            row = Gtk.ListBoxRow(child=label, activatable=self.synced)
            box.append(row)
            self.labels.append(label)
        box.connect("row-activated", self._on_line)
        clamp = Adw.Clamp(child=box, maximum_size=700, margin_top=12,
                          margin_bottom=24, margin_start=6, margin_end=6)
        self.scroller = Gtk.ScrolledWindow(
            child=clamp, hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True)
        self.list = box
        self.stack.add_named(self.scroller, "lyrics")
        self.stack.set_visible_child_name("lyrics")
        self._on_state(self.player)

    def _on_line(self, box, row):
        start = self.lines[row.get_index()].get("start")
        if start is not None:
            self.player.seek(max(0, (start - self.offset) / 1000))

    def _on_state(self, player):
        if not self.lines or not self.synced:
            return
        index = current_line(self.lines, player.position * 1000 + self.offset)
        if index == self.current:
            return
        for i in (self.current, index):
            if 0 <= i < len(self.labels):
                on = i == index
                for css in ("dimmed", "dim-label"):
                    (self.labels[i].remove_css_class if on
                     else self.labels[i].add_css_class)(css)
                (self.labels[i].add_css_class if on
                 else self.labels[i].remove_css_class)("accent")
        self.current = index
        if index >= 0:
            GLib.idle_add(self._scroll_to, index)

    def _scroll_to(self, index):
        row = self.list.get_row_at_index(index)
        if row is None:
            return GLib.SOURCE_REMOVE
        ok, bounds = row.compute_bounds(self.list)
        adjustment = self.scroller.get_vadjustment()
        if ok:
            target = bounds.get_y() - adjustment.get_page_size() / 3
            adjustment.set_value(max(0, min(target, adjustment.get_upper()
                                            - adjustment.get_page_size())))
        return GLib.SOURCE_REMOVE
