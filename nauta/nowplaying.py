"""What plays: the bar at the bottom of the window and the Now Playing page
with the controls and the queue."""
from gi.repository import Adw, Gtk, Pango

from nauta import text, widgets

BAR_COVER = 40
PAGE_COVER = 320


def _button(icon, tooltip, callback, css=("flat",)):
    button = Gtk.Button(icon_name=icon, tooltip_text=tooltip,
                        valign=Gtk.Align.CENTER)
    button.update_property([Gtk.AccessibleProperty.LABEL], [tooltip])
    for name in css:
        button.add_css_class(name)
    button.connect("clicked", lambda *_: callback())
    return button


def _set_play_icon(button, playing):
    label = "Pause" if playing else "Play"
    button.set_icon_name("media-playback-pause-symbolic" if playing
                         else "media-playback-start-symbolic")
    button.set_tooltip_text(label)
    button.update_property([Gtk.AccessibleProperty.LABEL], [label])


class PlayerBar(Gtk.Revealer):
    """Cover, title and artist, play/pause and next. Tapping it opens Now
    Playing. Hidden while the queue is empty."""

    def __init__(self, window):
        super().__init__(transition_type=Gtk.RevealerTransitionType.SLIDE_UP)
        self.window = window
        player = window.player
        box = Gtk.Box(spacing=12, margin_start=12, margin_end=6, margin_top=6,
                      margin_bottom=6)
        self.cover = widgets.Cover(size=BAR_COVER)
        box.append(self.cover)
        labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True,
                         valign=Gtk.Align.CENTER)
        self.title = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END,
                               max_width_chars=1)
        self.title.add_css_class("heading")
        self.artist = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END,
                                max_width_chars=1)
        self.artist.add_css_class("caption")
        labels.append(self.title)
        labels.append(self.artist)
        box.append(labels)
        self.play = _button("media-playback-start-symbolic", "Play", player.toggle)
        box.append(self.play)
        box.append(_button("media-skip-forward-symbolic", "Next", player.next))
        self.progress = Gtk.ProgressBar()
        self.progress.add_css_class("nauta-bar-progress")
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        outer.append(self.progress)
        outer.append(box)
        click = Gtk.GestureClick()
        click.connect("released", lambda *_: window.show_now_playing())
        labels.add_controller(click)
        cover_click = Gtk.GestureClick()
        cover_click.connect("released", lambda *_: window.show_now_playing())
        self.cover.add_controller(cover_click)
        outer.add_css_class("toolbar")
        self.set_child(outer)
        player.connect("song-changed", self._on_song)
        player.connect("state-changed", self._on_state)
        self._on_song(player)

    def _on_song(self, player):
        song = player.song
        self.set_reveal_child(song is not None and not self.window.now_playing_shown())
        if song is None:
            return
        self.title.set_label(song.get("title") or "")
        self.artist.set_label(song.get("artist") or "")
        self.cover.show(self.window.covers, song.get("coverArt"), BAR_COVER)
        self._on_state(player)

    def _on_state(self, player):
        _set_play_icon(self.play, player.playing)
        duration = player.duration
        self.progress.set_fraction(min(1, player.position / duration) if duration else 0)


class NowPlayingPage(Adw.NavigationPage):
    def __init__(self, window):
        super().__init__(title="Now Playing", tag="now-playing")
        self.window = window
        player = window.player
        self.player = player
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.cover = widgets.Cover(max_height=PAGE_COVER, natural_width=PAGE_COVER)
        self.cover.set_halign(Gtk.Align.CENTER)
        self.cover.set_size_request(min(PAGE_COVER, 240), -1)
        body.append(self.cover)
        self.title = Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER,
                               wrap_mode=Pango.WrapMode.WORD_CHAR, margin_top=12)
        self.title.add_css_class("title-2")
        self.artist = Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER,
                                wrap_mode=Pango.WrapMode.WORD_CHAR)
        self.artist.add_css_class("dimmed")
        self.artist.add_css_class("dim-label")
        body.append(self.title)
        body.append(self.artist)

        self.scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL,
                               draw_value=False, hexpand=True, margin_top=12)
        self.scale.set_range(0, 1)
        self.scale.update_property([Gtk.AccessibleProperty.LABEL], ["Position"])
        self.scale.connect("change-value", self._on_seek)
        body.append(self.scale)
        times = Gtk.Box()
        self.elapsed = Gtk.Label(xalign=0, hexpand=True)
        self.remaining = Gtk.Label(xalign=1)
        for label in (self.elapsed, self.remaining):
            label.add_css_class("caption")
            label.add_css_class("numeric")
            times.append(label)
        body.append(times)

        controls = Gtk.Box(spacing=24, halign=Gtk.Align.CENTER, margin_top=6)
        controls.append(_button("media-skip-backward-symbolic", "Previous",
                                player.previous, ("circular", "flat")))
        self.play = _button("media-playback-start-symbolic", "Play", player.toggle,
                            ("circular", "suggested-action", "nauta-play"))
        controls.append(self.play)
        controls.append(_button("media-skip-forward-symbolic", "Next",
                                player.next, ("circular", "flat")))
        body.append(controls)

        self.queue_title = Gtk.Label(label="Queue", xalign=0, margin_top=24)
        self.queue_title.add_css_class("title-4")
        body.append(self.queue_title)
        self.queue = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.queue.add_css_class("boxed-list")
        self.queue.connect("row-activated", lambda b, row: player.play_index(row.get_index()))
        body.append(self.queue)

        clamp = Adw.Clamp(child=body, maximum_size=600, margin_top=12,
                          margin_bottom=24, margin_start=12, margin_end=12)
        view = Adw.ToolbarView(content=Gtk.ScrolledWindow(
            child=clamp, hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True))
        view.add_top_bar(Adw.HeaderBar())
        self.set_child(view)
        self._handlers = [player.connect("song-changed", self._on_song),
                          player.connect("state-changed", self._on_state)]
        self.connect("hidden", self._on_hidden)
        self._queue_of = None
        self._on_song(player)

    def _on_hidden(self, *_):
        # Popped (swipe back): stop listening; a new page is made next time.
        if self.get_parent() is None:
            for handler in self._handlers:
                self.player.disconnect(handler)
            self._handlers = []

    def _on_song(self, player):
        song = player.song
        if song is None:
            self.title.set_label("Nothing Playing")
            self.artist.set_label("")
            self.cover.show(self.window.covers, None)
        else:
            self.title.set_label(song.get("title") or "")
            self.artist.set_label(text.song_subtitle(song))
            self.cover.show(self.window.covers, song.get("coverArt"), PAGE_COVER)
        self._fill_queue(player)
        self._on_state(player)

    def _fill_queue(self, player):
        if self._queue_of is not player.queue:
            self._queue_of = player.queue
            while (row := self.queue.get_row_at_index(0)) is not None:
                self.queue.remove(row)
            for i, song in enumerate(player.queue):
                self.queue.append(widgets.song_row(song, str(i + 1)))
        for i, song in enumerate(player.queue):
            row = self.queue.get_row_at_index(i)
            if i == player.index:
                row.title_label.add_css_class("accent")
                row.title_label.add_css_class("heading")
            else:
                row.title_label.remove_css_class("accent")
                row.title_label.remove_css_class("heading")
        self.queue_title.set_visible(len(player.queue) > 1)
        self.queue.set_visible(len(player.queue) > 1)

    def _on_state(self, player):
        _set_play_icon(self.play, player.playing)
        duration = player.duration
        position = min(player.position, duration) if duration else 0
        self.scale.set_range(0, max(duration, 1))
        self.scale.set_value(position)
        self.elapsed.set_label(text.duration(position))
        self.remaining.set_label("-" + text.duration(max(0, duration - position)))

    def _on_seek(self, scale, scroll, value):
        self.player.seek(value)
        return False

