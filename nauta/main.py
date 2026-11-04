import logging
import os
import tempfile
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

from nauta import (APP_ID, NAME, NIGHTLY, REPO_URL, SUPPORT_URL,  # noqa: E402
                   VERSION_LABEL)

log = logging.getLogger("nauta")


def demo_connection():
    """NAUTA_DEMO=<dir>: signed in to the recorded demo library served by
    nauta.demo, with nothing stored on disk or in the keyring (store
    screenshots, docs/release-channels.md)."""
    os.environ["NAUTA_KEYRING"] = "memory"
    from nauta import connection, keyring, settings
    from nauta.demo import PASSWORD, DemoServer
    server = DemoServer(os.environ["NAUTA_DEMO"]).start()
    store = settings.Store(Path(tempfile.mkdtemp(prefix="nauta-demo-")) / "account.json")
    account = store.load()
    account.remote_url = server.url
    account.user_name = server.library["user"]
    account.server_type = server.library["server"]["type"]
    account.server_version = server.library["server"]["serverVersion"]
    store.save(account)
    keyring.store(keyring.PASSWORD, PASSWORD)
    conn = connection.Connection(store, watch=False)
    conn.demo_server = server
    return conn


class Application(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID,
                         flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.connection = None
        for name, callback in (("about", self._on_about),
                               ("preferences", self._on_preferences),
                               ("search", self._on_search),
                               ("play-pause", self._on_play_pause),
                               ("now-playing", self._on_now_playing),
                               ("quit", lambda *_: self.quit())):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)
        # App actions with parameters, so screenshots can open states over
        # D-Bus (release.toml): show-view(n) for Albums (0), Artists (1)
        # and Playlists (2); show-album and play-album take an album id.
        for name, kind, callback in (("show-view", "i", self._on_show_view),
                                     ("show-album", "s", self._on_show_album),
                                     ("play-album", "s", self._on_play_album)):
            action = Gio.SimpleAction.new(name, GLib.VariantType(kind))
            action.connect("activate", callback)
            self.add_action(action)
        self.set_accels_for_action("app.quit", ["<Control>q"])
        self.set_accels_for_action("app.preferences", ["<Control>comma"])
        self.set_accels_for_action("app.search", ["<Control>f"])
        for n in range(3):
            self.set_accels_for_action(f"app.show-view({n})", [f"<Control>{n + 1}"])

    def do_startup(self):
        Adw.Application.do_startup(self)
        css = Gtk.CssProvider()
        css.load_from_path(str(Path(__file__).with_name("style.css")))
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        # Running from the source tree: the app icon is not installed.
        icons = Path(__file__).resolve().parent.parent / "data" / "icons"
        if icons.is_dir():
            Gtk.IconTheme.get_for_display(Gdk.Display.get_default()) \
                .add_search_path(str(icons))
        if os.environ.get("NAUTA_DEMO"):
            self.connection = demo_connection()
        else:
            from nauta.connection import Connection
            self.connection = Connection()
        from phosh_toolkit import style
        style.apply(self.connection.account.style)

    def do_activate(self):
        from nauta.window import Window
        window = self.props.active_window
        if window is None:
            window = Window(self, self.connection)
            if os.environ.get("NAUTA_DEMO"):
                window.maximize()
            if NIGHTLY:
                # libadwaita's striped header bar for development builds.
                window.add_css_class("devel")
        window.present()

    def _window(self):
        return self.props.active_window

    def _on_show_view(self, action, index):
        if self._window():
            self._window().show_view(index.unpack())

    def _on_show_album(self, action, album_id):
        if self._window() and self._window().main is not None:
            self._window().show_album({"id": album_id.unpack()})

    def _on_play_album(self, action, album_id):
        window = self._window()
        if window is None or window.main is None:
            return

        def done(album, error):
            if error is None and album.get("song"):
                window.player.play(album["song"])
                window.show_now_playing()
        self.connection.call(self.connection.api.album, done, album_id.unpack())

    def _on_play_pause(self, *_):
        if self._window():
            self._window().player.toggle()

    def _on_now_playing(self, *_):
        if self._window():
            self._window().show_now_playing()

    def _on_search(self, *_):
        if self._window():
            self._window().show_search()

    def _on_preferences(self, *_):
        window = self._window()
        if window and window.connection.signed_in:
            from nauta.preferences import PreferencesDialog
            PreferencesDialog(window).present(window)

    def _on_about(self, *_):
        dialog = Adw.AboutDialog(
            application_name=NAME,
            application_icon=APP_ID,
            version=VERSION_LABEL,
            developer_name="suitably",
            website=REPO_URL,
            issue_url=f"{REPO_URL}/issues",
            license_type=Gtk.License.AGPL_3_0,
            comments="Listen to your Navidrome library on a Phosh phone. Not "
                     "affiliated with the Navidrome project.",
        )
        dialog.add_link("Support Development", SUPPORT_URL)
        dialog.present(self._window())


def main(argv):
    # NAUTA_DEBUG=1 logs routes, requests and playback.
    logging.basicConfig(format="nauta: %(name)s: %(message)s")
    if os.environ.get("NAUTA_DEBUG"):
        logging.getLogger("nauta").setLevel(logging.DEBUG)
        logging.getLogger("phosh_toolkit").setLevel(logging.DEBUG)
    return Application().run(argv)
