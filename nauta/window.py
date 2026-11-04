from gi.repository import Adw, GLib, Gtk
from phosh_toolkit.proxy import MediaProxy

from nauta import NAME
from nauta.images import Covers
from nauta.library import MainPage
from nauta.nowplaying import NowPlayingPage, PlayerBar
from nauta.pages import AlbumPage, ArtistPage, PlaylistPage, SearchPage
from nauta.player import Player
from nauta.setup import SetupPage


class Window(Adw.ApplicationWindow):
    def __init__(self, app, connection):
        super().__init__(application=app, default_width=1000,
                         default_height=700, title=NAME)
        # Breakpoints need a minimum size (phosh-toolkit adaptive rules).
        self.set_size_request(360, 294)
        self.app_name = NAME
        self.app_icon = app.get_application_id()
        self.connection = connection
        self.covers = Covers(connection)
        self.proxy = MediaProxy(connection.forward)
        self.player = Player(connection, self.proxy)
        self.player.connect("error", lambda p, message: self.toast(
            f"Can't play this song: {message}"))
        self.main = None
        self.nav = Adw.NavigationView()
        self.nav.connect("notify::visible-page", self._on_page)
        # The player bar stays below every page except Now Playing.
        self.bar = PlayerBar(self)
        toolbar = Adw.ToolbarView(content=self.nav)
        toolbar.add_bottom_bar(self.bar)
        self.toasts = Adw.ToastOverlay(child=toolbar)
        self.set_content(self.toasts)

        breakpoint = Adw.Breakpoint.new(
            Adw.BreakpointCondition.parse("max-width: 600sp"))
        breakpoint.connect("apply", lambda *_: self._set_wide(False))
        breakpoint.connect("unapply", lambda *_: self._set_wide(True))
        self.add_breakpoint(breakpoint)
        self._wide = True

        connection.connect("signed-out", self._on_signed_out)
        self.connect("close-request", self._on_close)
        if connection.signed_in:
            self.show_library()
            connection.resolve()
        else:
            self.show_setup()

    # --- pages ---------------------------------------------------------

    def show_setup(self):
        self.main = None
        self.nav.replace([SetupPage(self)])

    def show_library(self):
        self.main = MainPage(self)
        self.main.set_wide(self._wide)
        self.nav.replace([self.main])

    def show_view(self, index):
        if self.main is not None:
            self.nav.pop_to_page(self.main)
            self.main.show_view(index)

    def show_album(self, album):
        self.nav.push(AlbumPage(self, album))

    def show_artist(self, artist):
        self.nav.push(ArtistPage(self, artist))

    def show_playlist(self, playlist):
        self.nav.push(PlaylistPage(self, playlist))

    def show_search(self):
        if self.main is None:
            return
        visible = self.nav.get_visible_page()
        if isinstance(visible, SearchPage):
            visible.entry.grab_focus()
            return
        self.nav.push(SearchPage(self))

    def show_now_playing(self):
        if self.player.song is not None and not self.now_playing_shown():
            self.nav.push(NowPlayingPage(self))

    def now_playing_shown(self):
        return isinstance(self.nav.get_visible_page(), NowPlayingPage)

    # --- events --------------------------------------------------------

    def toast(self, message):
        self.toasts.add_toast(Adw.Toast(title=GLib.markup_escape_text(message)))

    def _set_wide(self, wide):
        self._wide = wide
        if self.main is not None:
            self.main.set_wide(wide)

    def _on_page(self, *_):
        self.bar.set_reveal_child(self.player.song is not None
                                  and self.main is not None
                                  and not self.now_playing_shown())

    def _on_signed_out(self, *_):
        self.player.clear()
        self.toast("The server didn't accept the password. Sign in again.")
        self.show_setup()

    def _on_close(self, *_):
        self.player.clear()
        self.proxy.stop()
        return False
