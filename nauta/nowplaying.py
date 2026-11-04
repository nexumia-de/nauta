"""The Now Playing page: the song with its controls, the song's menu
(sleep timer, radio, playlists) and the queue (queue_view.py). The bar
at the bottom of the window is in player_bar.py."""
from gi.repository import Adw, Gio, GLib, Gtk, Pango

from nauta import actions, favourites, sleep, text, widgets
from nauta import player as player_module
from nauta.player_bar import button as _button
from nauta.player_bar import set_play_icon as _set_play_icon
from nauta.queue_view import QueueView

PAGE_COVER = 320


REPEAT = {player_module.REPEAT_OFF: ("media-playlist-repeat-symbolic", "Repeat"),
          player_module.REPEAT_ALL: ("media-playlist-repeat-symbolic",
                                     "Repeat All"),
          player_module.REPEAT_ONE: ("media-playlist-repeat-song-symbolic",
                                     "Repeat This Song")}


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

        about = Gtk.Box(spacing=6, margin_top=12)
        labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True,
                         valign=Gtk.Align.CENTER)
        self.title = Gtk.Label(wrap=True, xalign=0,
                               wrap_mode=Pango.WrapMode.WORD_CHAR)
        self.title.add_css_class("title-2")
        self.artist = Gtk.Label(wrap=True, xalign=0,
                                wrap_mode=Pango.WrapMode.WORD_CHAR)
        self.artist.add_css_class("dimmed")
        self.artist.add_css_class("dim-label")
        labels.append(self.title)
        labels.append(self.artist)
        about.append(labels)
        self.like = _button("non-starred-symbolic", "Like", self._on_like,
                            ("flat", "circular"))
        about.append(self.like)
        body.append(about)

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

        controls = Gtk.Box(spacing=16, halign=Gtk.Align.CENTER, margin_top=6)
        self.shuffle = Gtk.ToggleButton(icon_name="media-playlist-shuffle-symbolic",
                                        tooltip_text="Shuffle",
                                        valign=Gtk.Align.CENTER)
        self.shuffle.update_property([Gtk.AccessibleProperty.LABEL], ["Shuffle"])
        self.shuffle.add_css_class("flat")
        self.shuffle.add_css_class("circular")
        self.shuffle.connect("toggled", lambda b: player.set_shuffle(b.get_active()))
        controls.append(self.shuffle)
        controls.append(_button("media-skip-backward-symbolic", "Previous",
                                player.previous, ("circular", "flat")))
        self.play = _button("media-playback-start-symbolic", "Play", player.toggle,
                            ("circular", "suggested-action", "nauta-play"))
        controls.append(self.play)
        controls.append(_button("media-skip-forward-symbolic", "Next",
                                player.next, ("circular", "flat")))
        self.repeat = _button("media-playlist-repeat-symbolic", "Repeat",
                              player.cycle_repeat, ("circular", "flat"))
        controls.append(self.repeat)
        body.append(controls)
        self.sleep_label = Gtk.Label(margin_top=6)
        self.sleep_label.add_css_class("caption")
        self.sleep_label.add_css_class("accent")
        body.append(self.sleep_label)

        self.queue = QueueView(window)
        body.append(self.queue)

        clamp = Adw.Clamp(child=body, maximum_size=600, margin_top=12,
                          margin_bottom=24, margin_start=12, margin_end=12)
        view = Adw.ToolbarView(content=Gtk.ScrolledWindow(
            child=clamp, hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True))
        header = Adw.HeaderBar()
        self.lyrics = _button("format-justify-left-symbolic", "Lyrics",
                              window.show_lyrics)
        self.menu = actions.menu_button(self._menu, "More")
        header.pack_end(self.menu)
        header.pack_end(self.lyrics)
        view.add_top_bar(header)
        self.set_child(view)
        timer = window.sleep_timer
        self._handlers = [(player, player.connect("song-changed", self._on_song)),
                          (player, player.connect("state-changed", self._on_state)),
                          (player, player.connect("queue-changed", self._on_queue)),
                          (window.favourites, window.favourites.connect(
                              "changed", self._on_like_changed)),
                          (window.favourites, window.favourites.connect(
                              "loaded", lambda *_: self._show_like())),
                          (timer, timer.connect("changed", self._on_sleep))]
        self._tick = GLib.timeout_add_seconds(30, self._on_sleep_tick)
        self.connect("hidden", self._on_hidden)
        self._on_song(player)
        self._on_queue(player)
        self._on_sleep(timer)

    def _on_hidden(self, *_):
        # Popped (swipe back): stop listening; a new page is made next time.
        if self.get_parent() is None:
            for source, handler in self._handlers:
                source.disconnect(handler)
            self._handlers = []
            if self._tick:
                GLib.source_remove(self._tick)
                self._tick = 0

    # --- the song -------------------------------------------------------

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
        for widget in (self.like, self.menu, self.lyrics):
            widget.set_sensitive(song is not None)
        self._show_like()
        self.queue.fill()
        self._on_state(player)

    def _show_like(self):
        song = self.player.song
        liked = song is not None and self.window.favourites.liked(song)
        label = "Remove from Liked Songs" if liked else "Add to Liked Songs"
        self.like.set_icon_name("starred-symbolic" if liked else "non-starred-symbolic")
        self.like.set_tooltip_text(label)
        self.like.update_property([Gtk.AccessibleProperty.LABEL], [label])
        if liked:
            self.like.add_css_class("accent")
        else:
            self.like.remove_css_class("accent")

    def _on_like(self):
        if self.player.song is not None:
            actions.SongActions(self.window).toggle_like(favourites.SONG,
                                                         self.player.song)

    def _on_like_changed(self, favs, item_id):
        if self.player.song is not None and self.player.song.get("id") == item_id:
            self._show_like()

    def _menu(self):
        """The current song's menu plus the sleep timer."""
        song = self.player.song or {}
        menu, group = actions.SongActions(self.window, show_queue=False) \
            .song_menu(song, self.player.index)
        timer = Gio.Menu()
        for minutes in sleep.CHOICES:
            timer.append(f"{minutes} Minutes", f"item.sleep-{minutes}")
        timer.append("End of Song", "item.sleep-end")
        if self.window.sleep_timer.active:
            timer.append("Turn Off", "item.sleep-off")
        menu.append_submenu("Sleep Timer", timer)
        start = self.window.sleep_timer.start
        for name, callback in (
                [(f"sleep-{m}", lambda m=m: start(m)) for m in sleep.CHOICES]
                + [("sleep-end", lambda: start(sleep.END_OF_SONG)),
                   ("sleep-off", self.window.sleep_timer.cancel)]):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", lambda a, p, cb=callback: cb())
            group.add_action(action)
        return menu, group

    # --- queue, repeat, shuffle, sleep ---------------------------------

    def _on_queue(self, player):
        self.queue.fill()
        if self.shuffle.get_active() != player.shuffled:
            self.shuffle.set_active(player.shuffled)
        icon, label = REPEAT[player.repeat]
        self.repeat.set_icon_name(icon)
        self.repeat.set_tooltip_text(label)
        self.repeat.update_property([Gtk.AccessibleProperty.LABEL], [label])
        if player.repeat == player_module.REPEAT_OFF:
            self.repeat.remove_css_class("accent")
        else:
            self.repeat.add_css_class("accent")

    def _on_sleep(self, timer):
        remaining = timer.remaining()
        if not timer.active:
            text_ = ""
        elif remaining is None:
            text_ = "Pauses at the end of this song"
        else:
            text_ = f"Pauses in {max(1, round(remaining / 60))} min"
        self.sleep_label.set_label(text_)
        self.sleep_label.set_visible(bool(text_))

    def _on_sleep_tick(self):
        self._on_sleep(self.window.sleep_timer)
        return GLib.SOURCE_CONTINUE

    # --- position -------------------------------------------------------

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
