"""Liked Songs: the songs, albums and artists the user liked (starred),
from getStarred2 (docs/library.md)."""
from gi.repository import Adw, Gtk

from nauta import actions, text, widgets
from nauta.pages import LoadingPage, header, page


class LikedPage(LoadingPage):
    def __init__(self, window):
        super().__init__(window, "Liked Songs", "liked")
        self._handler = window.favourites.connect("saved", self._on_changed)
        self.connect("hidden", self._on_hidden)
        self.connect("shown", self._on_shown)
        self._stale = False

    def fetch(self):
        self.window.favourites.load(self.loaded)

    def build(self, found):
        window = self.window
        self._stale = False
        self.songs = songs = found["song"]
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        total = sum(s.get("duration") or 0 for s in songs)
        body.append(header(window, None, "Liked Songs", None,
                           f"{text.songs(len(songs))} · {text.total(total)}", songs,
                           icon="starred-symbolic"))
        if songs:
            self.list = widgets.song_list(
                songs, lambda i: window.player.play(songs, i), covers=window.covers,
                actions=actions.SongActions(window))
            body.append(self.list)
        if found["album"]:
            body.append(widgets.section("Albums", widgets.album_box(
                window.covers, found["album"], window.show_album)))
        if found["artist"]:
            box = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
            box.add_css_class("boxed-list")
            for artist in found["artist"]:
                row = widgets.nav_row(artist.get("name"),
                                      text.albums(artist.get("albumCount")),
                                      covers=window.covers,
                                      cover_id=artist.get("coverArt"),
                                      icon="avatar-default-symbolic")
                row.connect("activated", lambda r, a=artist: window.show_artist(a))
                box.append(row)
            body.append(widgets.section("Artists", box))
        if not any(found.values()):
            body.append(Adw.StatusPage(
                icon_name="non-starred-symbolic", title="Nothing Liked Yet",
                description="Like songs, albums and artists with the star "
                            "or in a song's menu"))
        return page(body)

    def _on_changed(self, favourites, item_id):
        # Reload when visible, else when shown again.
        if self.window.nav.get_visible_page() is self:
            self.reload()
        else:
            self._stale = True

    def _on_shown(self, *_):
        if self._stale:
            self.reload()

    def _on_hidden(self, *_):
        if self.get_parent() is None and self._handler:
            self.window.favourites.disconnect(self._handler)
            self._handler = 0
