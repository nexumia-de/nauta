"""Pages pushed onto the navigation view: an album, a playlist and
search. Every one closes with the swipe back. The artist page is in
artist.py, Liked Songs in liked.py."""
from gi.repository import Adw, Gtk, Pango

from nauta import actions, favourites, playlist_edit, text, widgets

COVER = 200


def page(child):
    """A scrolled, clamped page body."""
    clamp = Adw.Clamp(child=child, maximum_size=900, margin_top=12,
                      margin_bottom=24, margin_start=12, margin_end=12)
    return Gtk.ScrolledWindow(child=clamp, hscrollbar_policy=Gtk.PolicyType.NEVER,
                              vexpand=True)


def label(value, css=(), wrap=True):
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


def header(window, cover_id, title, subtitle_widget, details, songs,
           start=None, end=None, icon="folder-music-symbolic"):
    """Cover, title, artist, details and Play / Shuffle buttons, with
    `start` and `end` widgets beside them (like button, "⋮" menu)."""
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    cover = widgets.Cover(size=COVER, icon=icon)
    cover.set_halign(Gtk.Align.CENTER)
    cover.show(window.covers, cover_id, COVER)
    box.append(cover)
    title_label = label(title, ("title-2",))
    title_label.set_margin_top(12)
    box.append(title_label)
    if subtitle_widget is not None:
        box.append(subtitle_widget)
    if details:
        box.append(label(details, ("caption", "dimmed", "dim-label")))
    buttons = Gtk.Box(spacing=8, halign=Gtk.Align.CENTER, margin_top=12)
    if start is not None:
        buttons.append(start)
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
    if end is not None:
        buttons.append(end)
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
        window = self.window
        self.menu = actions.menu_button(lambda: actions.collection_menu(
            window, songs, favourites.ALBUM, album))
        self.like = actions.like_button(window, favourites.ALBUM, album)
        self.header = header(window, album.get("coverArt"), album.get("name") or "",
                             artist, text.album_details(album), songs,
                             self.like, self.menu)
        body.append(self.header)
        if songs:
            self.list = widgets.song_list(
                songs, lambda i: window.player.play(songs, i), with_album=False,
                actions=actions.SongActions(window))
            body.append(self.list)
        return page(body)


class PlaylistPage(LoadingPage):
    def __init__(self, window, playlist):
        self.playlist = playlist
        super().__init__(window, playlist.get("name") or "Playlist", "playlist")

    def fetch(self):
        conn = self.window.connection
        conn.call(conn.api.playlist, self.loaded, self.playlist["id"])

    def build(self, playlist):
        self.playlist = playlist
        self.set_title(playlist.get("name") or "Playlist")
        window = self.window
        self.songs = songs = playlist.get("entry") or []
        details = f"{text.songs(len(songs))} · {text.total(playlist.get('duration'))}"
        if playlist.get("comment"):
            details = f"{playlist['comment']}\n{details}"
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        self.editable = playlist_edit.editable(window, playlist)
        extras = []
        if self.editable:
            extras = [("Rename…", lambda: playlist_edit.rename_playlist(
                          window, playlist, lambda name: self.reload())),
                      ("Delete Playlist…", lambda: playlist_edit.delete_playlist(
                          window, playlist, self._deleted))]
        self.menu = actions.menu_button(lambda: actions.collection_menu(
            window, songs, extras=extras))
        body.append(header(window, playlist.get("coverArt"),
                           playlist.get("name") or "", None, details, songs,
                           end=self.menu))
        if songs:
            song_extras = []
            if self.editable:
                song_extras = [("Remove from Playlist", self._remove),
                               ("Move Up", lambda i: self._move(i, i - 1)),
                               ("Move Down", lambda i: self._move(i, i + 1))]
            self.list = widgets.song_list(
                songs, lambda i: window.player.play(songs, i),
                covers=window.covers,
                actions=actions.SongActions(window, song_extras))
            body.append(self.list)
        else:
            body.append(Adw.StatusPage(
                icon_name="view-list-bullet-symbolic", title="No Songs",
                description="Add songs with “Add to Playlist…” in a song's menu"))
        return page(body)

    def _deleted(self):
        if self.get_parent() is not None:
            self.window.nav.pop_to_page(self.window.main)

    def _remove(self, index):
        conn = self.window.connection
        title = self.songs[index].get("title")

        def done(result, error):
            if error is not None:
                self.window.toast(f"Can't remove the song: {error}")
                return
            self.window.toast(f"Removed “{title}”")
            self.window.playlists_changed()
            self.reload()
        conn.call(lambda: conn.api.update_playlist(self.playlist["id"],
                                                   remove=[index]), done)

    def _move(self, index, to):
        if not 0 <= to < len(self.songs):
            return
        songs = list(self.songs)
        songs.insert(to, songs.pop(index))
        playlist_edit.save_order(self.window, self.playlist, songs, self.reload)


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
        # Not in the library: look for it with MeTube (docs/downloads.md).
        find = Gtk.Button(label="Find New Music", halign=Gtk.Align.CENTER)
        find.add_css_class("pill")
        find.connect("clicked", lambda *_: window.show_find_music(self._query))
        self.stack.add_named(Adw.StatusPage(
            icon_name="system-search-symbolic", title="No Results",
            description="Not in your library yet", child=find), "empty")
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
                covers=self.window.covers,
                actions=actions.SongActions(self.window))))
        self.stack.add_named(page(body), "results")
        self.stack.set_visible_child_name("results")

