"""The main page: Albums, Artists and Playlists in a view stack, with the
view switcher in the header on wide windows and at the bottom on phones."""
from gi.repository import Adw, Gio, GLib, Gtk
from phosh_toolkit import route
from phosh_toolkit.router import CONNECTING, OFFLINE

from nauta import NAME, playlist_edit, text, widgets

# Albums are loaded in pages of this size, up to MAX_ALBUMS.
PAGE = 100
MAX_ALBUMS = 2000

# Orders of the Albums view: (getAlbumList2 type, name in the menu).
SORTS = (("newest", "Recently Added"),
         ("recent", "Recently Played"),
         ("frequent", "Most Played"),
         ("alphabeticalByName", "Name"),
         ("alphabeticalByArtist", "Artist"),
         ("starred", "Liked"),
         ("random", "Random"))

VIEWS = (("albums", "Albums", "media-optical-cd-audio-symbolic"),
         ("artists", "Artists", "system-users-symbolic"),
         ("playlists", "Playlists", "view-list-bullet-symbolic"))


def route_label(conn):
    return {route.LOCAL: "Home network", route.REMOTE: "Remote",
            CONNECTING: "Connecting…", OFFLINE: "Offline"}.get(conn.state, "")


class View(Gtk.Stack):
    """Loading, error or content of one view; loaded on first show."""

    def __init__(self, window):
        super().__init__(transition_type=Gtk.StackTransitionType.CROSSFADE)
        self.window = window
        self.loaded = False

    def load(self):
        self.loaded = True
        for child in list(self):
            self.remove(child)
        self.add_named(widgets.loading_page(), "loading")
        self.set_visible_child_name("loading")
        self.fetch()

    def failed(self, title, error):
        self.add_named(widgets.error_page(title, str(error), self.load), "error")
        self.set_visible_child_name("error")

    def show_content(self, child):
        self.add_named(child, "content")
        self.set_visible_child_name("content")


class AlbumsView(View):
    @property
    def sort(self):
        sort = self.window.connection.account.album_sort
        return sort if sort in dict(SORTS) else SORTS[0][0]

    def set_sort(self, sort):
        """Change and keep the order, and load again."""
        account = self.window.connection.account
        if sort == account.album_sort or sort not in dict(SORTS):
            return
        account.album_sort = sort
        self.window.connection.save()
        self.load()

    def fetch(self):
        self.store = Gio.ListStore.new(widgets.Entry)
        self._offset = 0
        self._generation = getattr(self, "_generation", 0) + 1
        self._next_page()

    def _next_page(self):
        conn = self.window.connection
        generation = self._generation
        # Random answers different albums on every page: one page only.
        conn.call(conn.api.albums,
                  lambda r, e: generation == self._generation and self._on_page(r, e),
                  self.sort, PAGE, self._offset)

    def _on_page(self, albums, error):
        if error is not None:
            if self._offset == 0:
                self.failed("Can't Load Albums", error)
            return
        for album in albums:
            self.store.append(widgets.Entry(album))
        if self._offset == 0:
            if not albums:
                empty = {"starred": ("No Liked Albums", "Like albums with the star "
                                     "on their page"),
                         "recent": ("Nothing Played Yet", "")}.get(
                    self.sort, ("No Albums", "The server's library is empty"))
                self.show_content(Adw.StatusPage(
                    icon_name="media-optical-cd-audio-symbolic",
                    title=empty[0], description=empty[1]))
                return
            grid = widgets.AlbumGrid(self.window.covers, self.store,
                                     self.window.show_album)
            self.show_content(Gtk.ScrolledWindow(
                child=grid, hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True))
        self._offset += len(albums)
        if len(albums) == PAGE and self._offset < MAX_ALBUMS and \
                self.sort != "random":
            self._next_page()


class ArtistsView(View):
    def fetch(self):
        conn = self.window.connection
        conn.call(conn.api.artists, self._on_artists)

    def _on_artists(self, artists, error):
        if error is not None:
            self.failed("Can't Load Artists", error)
            return
        if not artists:
            self.show_content(Adw.StatusPage(
                icon_name="system-users-symbolic", title="No Artists"))
            return
        store = Gio.ListStore.new(widgets.Entry)
        for artist in artists:
            store.append(widgets.Entry(artist))
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._setup)
        factory.connect("bind", self._bind)
        view = Gtk.ListView(model=Gtk.NoSelection(model=store), factory=factory,
                            single_click_activate=True)
        view.add_css_class("navigation-sidebar")
        view.connect("activate", lambda v, pos: self.window.show_artist(
            store.get_item(pos).data))
        clamp = Adw.ClampScrollable(child=view, maximum_size=800)
        self.show_content(Gtk.ScrolledWindow(
            child=clamp, hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True))

    def _setup(self, factory, item):
        box = Gtk.Box(spacing=12, margin_top=6, margin_bottom=6)
        box.cover = widgets.Cover(size=48, icon="avatar-default-symbolic")
        box.append(box.cover)
        labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                         valign=Gtk.Align.CENTER, hexpand=True)
        box.name = Gtk.Label(xalign=0, ellipsize=3, max_width_chars=1)
        box.count = Gtk.Label(xalign=0, ellipsize=3, max_width_chars=1)
        box.count.add_css_class("caption")
        box.count.add_css_class("dimmed")
        box.count.add_css_class("dim-label")
        labels.append(box.name)
        labels.append(box.count)
        box.append(labels)
        item.set_child(box)

    def _bind(self, factory, item):
        artist = item.get_item().data
        box = item.get_child()
        box.name.set_label(artist.get("name") or "")
        box.count.set_label(text.albums(artist.get("albumCount")))
        box.cover.show(self.window.covers, artist.get("coverArt"), 48,
                       "avatar-default-symbolic")


class PlaylistsView(View):
    def fetch(self):
        conn = self.window.connection
        conn.call(conn.api.playlists, self._on_playlists)

    def _on_playlists(self, playlists, error):
        if error is not None:
            self.failed("Can't Load Playlists", error)
            return
        window = self.window
        top = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        top.add_css_class("boxed-list")
        liked = widgets.nav_row("Liked Songs", "Songs, albums and artists you liked",
                                icon="starred-symbolic")
        liked.connect("activated", lambda r: window.show_liked())
        top.append(liked)
        new = widgets.nav_row("New Playlist", icon="list-add-symbolic")
        new.connect("activated", lambda r: playlist_edit.new_playlist(
            window, done=window.show_playlist))
        top.append(new)
        self.top = top
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        content.append(top)
        if not playlists:
            content.append(Adw.StatusPage(
                icon_name="view-list-bullet-symbolic", title="No Playlists",
                description="Make one here, or add songs to a new playlist from "
                            "a song's menu"))
            self._show(content)
            return
        box = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        box.add_css_class("boxed-list")
        content.append(box)
        for playlist in playlists:
            row = widgets.nav_row(
                playlist.get("name"),
                f"{text.songs(playlist.get('songCount'))} · "
                f"{text.total(playlist.get('duration'))}",
                covers=self.window.covers, cover_id=playlist.get("coverArt"),
                icon="view-list-bullet-symbolic")
            row.connect("activated", lambda r, p=playlist: self.window.show_playlist(p))
            box.append(row)
        self._show(content)

    def _show(self, content):
        page = Adw.Clamp(child=content, maximum_size=800, margin_top=12,
                         margin_bottom=24, margin_start=12, margin_end=12)
        self.show_content(Gtk.ScrolledWindow(
            child=page, hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True))


class MainPage(Adw.NavigationPage):
    def __init__(self, window):
        super().__init__(title=window.app_name, tag="main")
        self.window = window
        self.stack = Adw.ViewStack(vexpand=True)
        self.views = {}
        for name, title, icon, cls in zip(
                [v[0] for v in VIEWS], [v[1] for v in VIEWS],
                [v[2] for v in VIEWS], (AlbumsView, ArtistsView, PlaylistsView)):
            view = cls(window)
            self.views[name] = view
            self.stack.add_titled_with_icon(view, name, title, icon)
        self.stack.connect("notify::visible-child", self._on_view)

        header = Adw.HeaderBar()
        self.switcher = Adw.ViewSwitcher(stack=self.stack,
                                         policy=Adw.ViewSwitcherPolicy.WIDE)
        self.title = Adw.WindowTitle(title=window.app_name)
        header.set_title_widget(self.title)
        search = Gtk.Button(icon_name="system-search-symbolic",
                            tooltip_text="Search")
        search.update_property([Gtk.AccessibleProperty.LABEL], ["Search"])
        search.set_action_name("app.search")
        header.pack_start(search)
        menu = Gio.Menu()
        menu.append("Find New Music", "app.find-music")
        menu.append("Preferences", "app.preferences")
        menu.append(f"About {NAME}", "app.about")
        # Closing the window keeps the music playing; this ends both.
        menu.append("Quit", "app.quit")
        header.pack_end(Gtk.MenuButton(icon_name="open-menu-symbolic",
                                       menu_model=menu, tooltip_text="Main Menu",
                                       primary=True))
        # The Albums view's order, shown with that view only.
        self.sort_action = Gio.SimpleAction.new_stateful(
            "album-sort", GLib.VariantType("s"),
            GLib.Variant("s", self.views["albums"].sort))
        self.sort_action.connect("change-state", self._on_sort)
        group = Gio.SimpleActionGroup()
        group.add_action(self.sort_action)
        self.insert_action_group("library", group)
        sorts = Gio.Menu()
        for value, name in SORTS:
            sorts.append(name, f"library.album-sort::{value}")
        self.sort_button = Gtk.MenuButton(icon_name="view-sort-descending-symbolic",
                                          menu_model=sorts, tooltip_text="Sort Albums")
        self.sort_button.update_property([Gtk.AccessibleProperty.LABEL],
                                         ["Sort Albums"])
        header.pack_end(self.sort_button)
        self.banner = Adw.Banner(button_label="Retry")
        self.banner.connect("button-clicked", lambda *_: window.connection.resolve())
        self.bar = Adw.ViewSwitcherBar(stack=self.stack, reveal=True)

        toolbar = Adw.ToolbarView(content=self.stack)
        toolbar.add_top_bar(header)
        toolbar.add_top_bar(self.banner)
        toolbar.add_bottom_bar(self.bar)
        self.set_child(toolbar)
        self.header = header
        window.connection.connect("state-changed", self._on_state)
        self._on_state(window.connection)
        self._on_view()

    def set_wide(self, wide):
        """Switcher in the header on wide windows, at the bottom on phones."""
        self.header.set_title_widget(self.switcher if wide else self.title)
        self.bar.set_reveal(not wide)

    def show_view(self, index):
        if 0 <= index < len(VIEWS):
            self.stack.set_visible_child_name(VIEWS[index][0])

    def _on_view(self, *_):
        view = self.stack.get_visible_child()
        if view is not None and not view.loaded:
            view.load()
        self.sort_button.set_visible(view is self.views["albums"])

    def _on_sort(self, action, value):
        action.set_state(value)
        self.views["albums"].set_sort(value.unpack())

    def playlists_changed(self):
        """Load the playlists again (one was made, changed or deleted)."""
        view = self.views["playlists"]
        if view.loaded:
            view.load()

    def _on_state(self, conn, *_):
        self.title.set_subtitle(route_label(conn))
        offline = conn.state == OFFLINE
        if offline:
            self.banner.set_title(str(conn.error or "Can't reach the server"))
        self.banner.set_revealed(offline)
        if not offline and conn.state != CONNECTING:
            for view in self.views.values():
                if view.loaded and view.get_visible_child_name() == "error":
                    view.load()
