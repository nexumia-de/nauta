"""Pages pushed onto the navigation view: an album, an artist, a playlist
and search. Every one closes with the swipe back."""
from gi.repository import Adw, Gtk, Pango

from nauta import text, widgets

COVER = 200


def _page(child):
    """A scrolled, clamped page body."""
    clamp = Adw.Clamp(child=child, maximum_size=900, margin_top=12,
                      margin_bottom=24, margin_start=12, margin_end=12)
    return Gtk.ScrolledWindow(child=clamp, hscrollbar_policy=Gtk.PolicyType.NEVER,
                              vexpand=True)


def _label(value, css=(), wrap=True):
    label = Gtk.Label(label=value, wrap=wrap, xalign=0.5,
                      justify=Gtk.Justification.CENTER,
                      wrap_mode=Pango.WrapMode.WORD_CHAR)
    for name in css:
        label.add_css_class(name)
    return label


class LoadingPage(Adw.NavigationPage):
    """A page that loads its content through the connection."""

    def __init__(self, window, title, tag):
        super().__init__(title=title, tag=tag)
        self.window = window
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        view = Adw.ToolbarView(content=self.stack)
        view.add_top_bar(Adw.HeaderBar())
        self.set_child(view)
        self.reload()

    def reload(self):
        for child in list(self.stack):
            self.stack.remove(child)
        self.stack.add_named(widgets.loading_page(), "loading")
        self.stack.set_visible_child_name("loading")
        self.fetch()

    def loaded(self, result, error):
        if error is not None:
            self.stack.add_named(widgets.error_page(
                "Can't Load This", str(error), self.reload), "error")
            self.stack.set_visible_child_name("error")
            return
        self.stack.add_named(self.build(result), "content")
        self.stack.set_visible_child_name("content")


def _header(window, cover_id, title, subtitle_widget, details, songs):
    """Cover, title, artist, details and Play / Shuffle buttons."""
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    cover = widgets.Cover(size=COVER, icon="folder-music-symbolic")
    cover.set_halign(Gtk.Align.CENTER)
    cover.show(window.covers, cover_id, COVER)
    box.append(cover)
    title_label = _label(title, ("title-2",))
    title_label.set_margin_top(12)
    box.append(title_label)
    if subtitle_widget is not None:
        box.append(subtitle_widget)
    if details:
        box.append(_label(details, ("caption", "dimmed", "dim-label")))
    buttons = Gtk.Box(spacing=12, halign=Gtk.Align.CENTER, margin_top=12,
                      homogeneous=True)
    play = Gtk.Button(child=Adw.ButtonContent(icon_name="media-playback-start-symbolic",
                                              label="Play"))
    play.add_css_class("pill")
    play.add_css_class("suggested-action")
    play.connect("clicked", lambda *_: window.player.play(songs))
    shuffle = Gtk.Button(child=Adw.ButtonContent(
        icon_name="media-playlist-shuffle-symbolic", label="Shuffle"))
    shuffle.add_css_class("pill")
    shuffle.connect("clicked", lambda *_: window.player.play(songs, shuffle=True))
    for button in (play, shuffle):
        button.set_sensitive(bool(songs))
        buttons.append(button)
    box.append(buttons)
    box.play_button = play
    return box


class AlbumPage(LoadingPage):
    def __init__(self, window, album):
        self.album = album
        super().__init__(window, album.get("name") or "Album", "album")

    def fetch(self):
        conn = self.window.connection
        conn.call(conn.api.album, self.loaded, self.album["id"])

    def build(self, album):
        self.album = album
        self.set_title(album.get("name") or "Album")
        songs = album.get("song") or []
        artist = Gtk.Button(label=album.get("artist") or "Unknown Artist",
                            halign=Gtk.Align.CENTER)
        artist.add_css_class("flat")
        artist.get_child().set_ellipsize(Pango.EllipsizeMode.END)
        if album.get("artistId"):
            artist.connect("clicked", lambda *_: self.window.show_artist(
                {"id": album["artistId"], "name": album.get("artist")}))
        else:
            artist.set_sensitive(False)
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        self.header = _header(self.window, album.get("coverArt"), album.get("name") or "",
                              artist, text.album_details(album), songs)
        body.append(self.header)
        if songs:
            self.list = widgets.song_list(
                songs, lambda i: self.window.player.play(songs, i), with_album=False)
            body.append(self.list)
        return _page(body)


class PlaylistPage(LoadingPage):
    def __init__(self, window, playlist):
        self.playlist = playlist
        super().__init__(window, playlist.get("name") or "Playlist", "playlist")

    def fetch(self):
        conn = self.window.connection
        conn.call(conn.api.playlist, self.loaded, self.playlist["id"])

    def build(self, playlist):
        songs = playlist.get("entry") or []
        details = f"{text.songs(len(songs))} · {text.total(playlist.get('duration'))}"
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        body.append(_header(self.window, playlist.get("coverArt"),
                            playlist.get("name") or "", None, details, songs))
        if songs:
            body.append(widgets.song_list(
                songs, lambda i: self.window.player.play(songs, i),
                covers=self.window.covers))
        return _page(body)


class ArtistPage(LoadingPage):
    def __init__(self, window, artist):
        self.artist = artist
        super().__init__(window, artist.get("name") or "Artist", "artist")

    def fetch(self):
        conn = self.window.connection
        conn.call(conn.api.artist, self.loaded, self.artist["id"])

    def build(self, artist):
        albums = sorted(artist.get("album") or [],
                        key=lambda a: a.get("year") or 0, reverse=True)
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        name = _label(artist.get("name") or "", ("title-1",))
        body.append(name)
        body.append(_label(text.albums(len(albums)), ("dimmed", "dim-label")))
        body.append(widgets.album_box(
            self.window.covers, albums, self.window.show_album,
            subtitle=lambda a: str(a.get("year") or "")))
        return _page(body)


class SearchPage(Adw.NavigationPage):
    def __init__(self, window):
        super().__init__(title="Search", tag="search")
        self.window = window
        self.entry = Gtk.SearchEntry(placeholder_text="Artists, albums, songs",
                                     hexpand=True)
        self.entry.connect("search-changed", self._on_changed)
        header = Adw.HeaderBar(title_widget=Adw.Clamp(child=self.entry,
                                                      maximum_size=500))
        self.stack = Gtk.Stack()
        self.stack.add_named(Adw.StatusPage(
            icon_name="system-search-symbolic", title="Search the Library",
            description="Find artists, albums and songs"), "start")
        self.stack.add_named(widgets.loading_page(), "loading")
        self.stack.add_named(Adw.StatusPage(
            icon_name="system-search-symbolic", title="No Results"), "empty")
        view = Adw.ToolbarView(content=self.stack)
        view.add_top_bar(header)
        self.set_child(view)
        self._query = ""
        self.connect("shown", lambda *_: self.entry.grab_focus())

    def search(self, query):
        self.entry.set_text(query)
        self._on_changed(self.entry)

    def _on_changed(self, entry):
        query = entry.get_text().strip()
        self._query = query
        if not query:
            self.stack.set_visible_child_name("start")
            return
        self.stack.set_visible_child_name("loading")
        conn = self.window.connection
        conn.call(conn.api.search, lambda r, e, q=query: self._on_results(q, r, e),
                  query)

    def _on_results(self, query, found, error):
        if query != self._query:
            return   # an older search
        old = self.stack.get_child_by_name("results")
        if old is not None:
            self.stack.remove(old)
        if error is not None:
            self.stack.add_named(widgets.error_page(
                "Can't Search", str(error), lambda: self.search(query)), "results")
            self.stack.set_visible_child_name("results")
            return
        if not any(found.values()):
            self.stack.set_visible_child_name("empty")
            return
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        if found["artist"]:
            box = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
            box.add_css_class("boxed-list")
            for artist in found["artist"]:
                row = widgets.nav_row(artist.get("name"),
                                      text.albums(artist.get("albumCount")),
                                      covers=self.window.covers,
                                      cover_id=artist.get("coverArt"),
                                      icon="avatar-default-symbolic")
                row.connect("activated", lambda r, a=artist: self.window.show_artist(a))
                box.append(row)
            body.append(widgets.section("Artists", box))
        if found["album"]:
            body.append(widgets.section("Albums", widgets.album_box(
                self.window.covers, found["album"], self.window.show_album)))
        if found["song"]:
            songs = found["song"]
            body.append(widgets.section("Songs", widgets.song_list(
                songs, lambda i: self.window.player.play(songs, i),
                covers=self.window.covers)))
        self.stack.add_named(_page(body), "results")
        self.stack.set_visible_child_name("results")

