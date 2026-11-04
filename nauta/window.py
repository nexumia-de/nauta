import logging

from gi.repository import Adw, GLib, Gtk
from phosh_toolkit import proxy_login
from phosh_toolkit.proxy import MediaProxy

from nauta import NAME
from nauta import connection as connection_module
from nauta import downloads as downloads_module
from nauta.images import Covers
from nauta.library import MainPage
from nauta.nowplaying import NowPlayingPage, PlayerBar
from nauta.pages import AlbumPage, ArtistPage, PlaylistPage, SearchPage
from nauta.player import Player
from nauta.setup import SetupPage

log = logging.getLogger("nauta.window")


class Window(Adw.ApplicationWindow):
    def __init__(self, app, connection, downloads=None):
        super().__init__(application=app, default_width=1000,
                         default_height=700, title=NAME)
        # Breakpoints need a minimum size (phosh-toolkit adaptive rules).
        self.set_size_request(360, 294)
        self.app_name = NAME
        self.app_icon = app.get_application_id()
        self.connection = connection
        # The download server for new music (docs/downloads.md).
        self.downloads = downloads or downloads_module.Downloads(
            watch=connection.watcher is not None)
        self.covers = Covers(connection)
        self.proxy = MediaProxy(connection.forward)
        self.player = Player(connection, self.proxy)
        self.player.connect("error", lambda p, message: self.toast(
            f"Can't play this song: {message}"))
        # Music goes on with the window closed and the screen off
        # (docs/playback.md): the app is held while something is loaded,
        # suspend is inhibited while it plays.
        self._held = False
        self._inhibiting = False
        self._inhibit = 0       # 0 when no session manager answers
        self.player.connect("state-changed", self._on_player_state)
        self.mpris = None
        try:
            from nauta.mpris import Mpris
            self.mpris = Mpris(self.player, self.covers, self.present,
                               self.quit_app)
        except GLib.Error as e:
            log.info("no media controls: %s", e.message)
        self.connect("destroy", self._on_destroy)
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
        connection.connect("proxy-login", self._on_proxy_login)
        self.downloads.connect("proxy-login", self._on_downloads_proxy_login)
        self.downloads.connect("finished", lambda d, title: self.toast(
            f"Downloaded “{title}”. Navidrome adds it at its next scan."))
        self.downloads.connect("failed", lambda d, title, message: self.toast(
            f"Can't download “{title}”: {message}"))
        self.connect("close-request", self._on_close)
        if connection.signed_in:
            self.show_library()
            connection.resolve()
            self.downloads.resolve()
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

    def show_find_music(self, query=""):
        """Search for new music through MeTube, or set it up first."""
        if self.main is None:
            return
        from nauta.find import DownloadSetupPage, FindMusicPage
        visible = self.nav.get_visible_page()
        if isinstance(visible, FindMusicPage):
            if query:
                visible.search(query)
            visible.entry.grab_focus()
            return
        if self.downloads.configured:
            self.nav.push(FindMusicPage(self, query))
        else:
            self.nav.push(DownloadSetupPage(self, query))

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

    def _on_proxy_login(self, connection, url):
        """The reverse proxy in front of the server wants its own login
        (again): show its page (docs/connection.md)."""
        if connection.signed_in:
            proxy_login.sign_in(self.nav, connection, connection.api.http,
                                connection.proxy_cookies,
                                connection_module.probe_through, url)

    def _on_downloads_proxy_login(self, downloads, url):
        """The proxy in front of MeTube wants its login (again)."""
        if downloads.configured and self.main is not None:
            proxy_login.sign_in(self.nav, downloads, downloads.api.http,
                                downloads.proxy_cookies,
                                downloads_module.probe_through, url)

    def _on_signed_out(self, *_):
        self.player.clear()
        self.toast("The server didn't accept the password. Sign in again.")
        self.show_setup()

    def _on_close(self, *_):
        if self.player.media is not None:
            # Playing or paused: hide and keep the app; the media controls
            # and opening Nauta again bring the window back.
            self.set_visible(False)
            if not self._held:
                self.get_application().hold()
                self._held = True
            return True
        self._shut_down()
        return False

    def _on_player_state(self, player):
        app = self.get_application()
        if player.playing and not self._inhibiting and app is not None:
            self._inhibiting = True
            self._inhibit = app.inhibit(self, Gtk.ApplicationInhibitFlags.SUSPEND,
                                        "Playing music")
        elif not player.playing and self._inhibiting:
            self._release_inhibit()
        if player.media is None and self._held and not self.get_visible():
            # Hidden and nothing left to play: quit.
            self.quit_app()

    def _on_destroy(self, *_):
        if self.mpris is not None:
            self.mpris.close()
            self.mpris = None

    def quit_app(self):
        """Stop playing and quit (menu, media controls)."""
        self._shut_down()
        app = self.get_application()
        if self._held:
            self._held = False
            app.release()
        self.destroy()
        app.quit()

    def _release_inhibit(self):
        self._inhibiting = False
        if self._inhibit:
            self.get_application().uninhibit(self._inhibit)
            self._inhibit = 0

    def _shut_down(self):
        if self._inhibiting:
            self._release_inhibit()
        if self.mpris is not None:
            self.mpris.close()
            self.mpris = None
        self.player.clear()
        self.proxy.stop()
