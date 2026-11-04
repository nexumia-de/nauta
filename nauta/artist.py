"""The artist page: popular songs, artist radio, albums and similar
artists in the library (docs/library.md)."""
from gi.repository import Adw, Gtk

from nauta import actions, favourites, text, widgets
from nauta.pages import LoadingPage, label, page

# Popular songs shown.
TOP = 5


class ArtistPage(LoadingPage):
    def __init__(self, window, artist):
        self.artist = artist
        super().__init__(window, artist.get("name") or "Artist", "artist")

    def fetch(self):
        conn = self.window.connection
        conn.call(conn.api.artist, self._on_artist, self.artist["id"])

    def _on_artist(self, artist, error):
        """Then the popular songs and similar artists; a server without
        an agent answers those with errors or nothing, which only hides
        the sections."""
        if error is not None:
            self.loaded(None, error)
            return
        conn = self.window.connection
        extra = {}

        def got(key, result, error):
            extra[key] = result if error is None else []
            if len(extra) == 2:
                self.loaded((artist, extra["top"], extra["info"]), None)
        conn.call(conn.api.top_songs, lambda r, e: got("top", r, e),
                  artist.get("name") or "", TOP)
        conn.call(conn.api.artist_info, lambda r, e: got("info", r, e),
                  artist["id"])

    def build(self, result):
        artist, top, info = result
        self.artist = artist
        self.set_title(artist.get("name") or "Artist")
        window = self.window
        albums = sorted(artist.get("album") or [],
                        key=lambda a: a.get("year") or 0, reverse=True)
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        body.append(label(artist.get("name") or "", ("title-1",)))
        body.append(label(text.albums(len(albums)), ("dimmed", "dim-label")))
        buttons = Gtk.Box(spacing=8, halign=Gtk.Align.CENTER)
        self.like = actions.like_button(window, favourites.ARTIST, artist)
        buttons.append(self.like)
        self.radio = Gtk.Button(child=Adw.ButtonContent(
            icon_name="media-playlist-shuffle-symbolic", label="Artist Radio"))
        self.radio.add_css_class("pill")
        self.radio.add_css_class("suggested-action")
        self.radio.connect("clicked", lambda b: actions.start_radio(
            window, artist["id"]))
        buttons.append(self.radio)
        body.append(buttons)
        self.top = top
        if top:
            body.append(widgets.section("Popular", widgets.song_list(
                top, lambda i: window.player.play(top, i), covers=window.covers,
                actions=actions.SongActions(window))))
        if albums:
            body.append(widgets.section("Albums", widgets.album_box(
                window.covers, albums, window.show_album,
                subtitle=lambda a: str(a.get("year") or ""))))
        similar = (info or {}).get("similarArtist") or []
        self.similar = similar
        if similar:
            box = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
            box.add_css_class("boxed-list")
            for other in similar:
                row = widgets.nav_row(other.get("name"),
                                      text.albums(other.get("albumCount")),
                                      covers=window.covers,
                                      cover_id=other.get("coverArt"),
                                      icon="avatar-default-symbolic")
                row.connect("activated", lambda r, a=other: window.show_artist(a))
                box.append(row)
            body.append(widgets.section("Fans Also Like", box))
        return page(body)
