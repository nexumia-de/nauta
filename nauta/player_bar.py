"""The bar at the bottom of the window while something plays: cover,
title, artist, play/pause, next and a thin progress line; tapping it
opens Now Playing (docs/playback.md)."""
from gi.repository import Gtk, Pango

from nauta import widgets

BAR_COVER = 40


def button(icon, tooltip, callback, css=("flat",)):
    button = Gtk.Button(icon_name=icon, tooltip_text=tooltip,
                        valign=Gtk.Align.CENTER)
    button.update_property([Gtk.AccessibleProperty.LABEL], [tooltip])
    for name in css:
        button.add_css_class(name)
    button.connect("clicked", lambda *_: callback())
    return button


def set_play_icon(button, playing):
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
        self.play = button("media-playback-start-symbolic", "Play", player.toggle)
        box.append(self.play)
        box.append(button("media-skip-forward-symbolic", "Next", player.next))
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
        set_play_icon(self.play, player.playing)
        duration = player.duration
        self.progress.set_fraction(min(1, player.position / duration) if duration else 0)
