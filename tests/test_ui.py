"""The whole flow through the real widgets against the demo server behind
mutual TLS: setup, sign in, albums, an album, playing, Now Playing,
artists, playlists, search and the preferences. Needs a display (CI runs
pytest under xvfb-run)."""
import os

import pytest

from conftest import P12_PASSWORD, run_until

if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
    pytest.skip("needs a display", allow_module_level=True)

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gst", "1.0")
from gi.repository import Adw, Gst  # noqa: E402
from phosh_toolkit import connection_form, router  # noqa: E402
from phosh_toolkit.http import Client  # noqa: E402
from phosh_toolkit.media import Media  # noqa: E402

from nauta import connection, keyring, player, settings, setup  # noqa: E402
from nauta.demo import PASSWORD  # noqa: E402


@pytest.fixture(scope="module")
def app():
    """One application for all tests: a second one with the same id can't
    register on the session bus."""
    from nauta.main import Application
    application = Application()
    application.register(None)
    Adw.init()
    yield application


@pytest.fixture(autouse=True)
def quiet(monkeypatch):
    """No sound card in CI: a clocked fakesink instead."""
    def media(url, video=False):
        m = Media(url, video=False)
        sink = Gst.ElementFactory.make("fakesink", None)
        sink.props.sync = True
        m.pipeline.props.audio_sink = sink
        return m
    monkeypatch.setattr(player, "Media", media)


def visible(window):
    return window.nav.get_visible_page()


def test_setup_sign_in_browse_and_play(app, mtls_demo, pki, trust, monkeypatch):
    from nauta.library import MainPage
    from nauta.nowplaying import NowPlayingPage
    from nauta.pages import AlbumPage, ArtistPage, PlaylistPage, SearchPage
    from nauta.preferences import PreferencesDialog
    from nauta.window import Window

    def trusting_client(user_agent):
        client = Client(user_agent)
        client.tls_database = trust
        return client
    monkeypatch.setattr(connection_form, "Client", trusting_client)
    monkeypatch.setattr(router.network, "current_ssids", lambda: {"Home"})
    monkeypatch.setattr(connection_form.network, "current_ssids", lambda: {"Home"})

    conn = connection.Connection(watch=False)
    conn.api.http.tls_database = trust
    window = Window(app, conn)
    window.present()
    page = visible(window)
    assert isinstance(page, setup.SetupPage)
    assert not window.bar.get_reveal_child()

    # Without the certificate the server refuses, and the row is marked.
    page.form.remote.set_text(mtls_demo.url)
    page.form.local.set_text("http://127.0.0.1:9")
    page.form._add("Home")
    toasts = []
    monkeypatch.setattr(window, "toast", toasts.append)
    page.form.toast = window.toast
    page.button.emit("clicked")
    run_until(lambda: page.button.get_sensitive())
    assert "client certificate" in toasts[-1]
    assert page.form.cert_row.has_css_class("error")

    page.form.choose_data((pki / "client.p12").read_bytes(), "client.p12")
    page.form.password.set_text(P12_PASSWORD)
    page.button.emit("clicked")
    run_until(lambda: isinstance(visible(window), setup.SignInPage))

    sign_in = visible(window)
    sign_in.user.set_text("robin")
    sign_in.password.set_text("wrong")
    sign_in.button.emit("clicked")
    run_until(lambda: sign_in.button.get_sensitive() and toasts[-1] != toasts[0])
    assert "Wrong" in toasts[-1]
    sign_in.password.set_text(PASSWORD)
    sign_in.button.emit("clicked")
    run_until(lambda: isinstance(visible(window), MainPage))

    account = settings.Store().load()
    assert account.signed_in and account.certificate
    assert account.home_networks == ["Home"]
    assert keyring.lookup(keyring.PASSWORD) == PASSWORD
    # At "home" the local address is down, so the remote one is used.
    run_until(lambda: conn.state == "remote")

    main = visible(window)
    albums = main.views["albums"]
    run_until(lambda: albums.get_visible_child_name() == "content")
    assert albums.store.get_n_items() == 10

    window.show_album(albums.store.get_item(0).data)
    album = visible(window)
    assert isinstance(album, AlbumPage)
    run_until(lambda: album.stack.get_visible_child_name() == "content")
    album.list.emit("row-activated", album.list.get_row_at_index(1))
    run_until(lambda: window.player.playing and window.player.position > 0.2, 15)
    assert window.player.index == 1 and window.bar.get_reveal_child()
    assert window.bar.title.get_label() == album.album["song"][1]["title"]

    window.show_now_playing()
    now = visible(window)
    assert isinstance(now, NowPlayingPage) and not window.bar.get_reveal_child()
    assert now.title.get_label() == album.album["song"][1]["title"]
    now.play.emit("clicked")
    run_until(lambda: not window.player.playing, 5)
    now.queue.emit("row-activated", now.queue.get_row_at_index(2))
    run_until(lambda: now.title.get_label() == album.album["song"][2]["title"])
    window.nav.pop()
    assert window.bar.get_reveal_child()

    window.show_artist({"id": album.album["artistId"], "name": album.album["artist"]})
    artist = visible(window)
    assert isinstance(artist, ArtistPage)
    run_until(lambda: artist.stack.get_visible_child_name() == "content")

    window.show_view(2)
    assert visible(window) is main
    playlists = main.views["playlists"]
    run_until(lambda: playlists.get_visible_child_name() == "content")
    window.show_playlist({"id": "pl-commute", "name": "Commute"})
    playlist = visible(window)
    assert isinstance(playlist, PlaylistPage)
    run_until(lambda: playlist.stack.get_visible_child_name() == "content")

    window.show_search()
    search = visible(window)
    assert isinstance(search, SearchPage)
    search.search("harbour")
    run_until(lambda: search.stack.get_visible_child_name() == "results")

    dialog = PreferencesDialog(window)
    dialog.present(window)
    assert dialog.form.remote.get_text() == mtls_demo.url
    manager = Adw.StyleManager.get_default()
    dialog.style_row.set_selected(2)
    assert manager.get_color_scheme() == Adw.ColorScheme.FORCE_DARK
    assert settings.Store().load().style == "dark"
    dialog.style_row.set_selected(0)
    dialog.quality_rows["quality_away"].set_selected(3)
    assert settings.Store().load().quality_away == 128
    dialog.close()
    window.player.clear()
    window.destroy()


def test_server_rejecting_the_password_shows_setup(app, demo, monkeypatch):
    from nauta.window import Window
    monkeypatch.setattr(router.network, "current_ssids", lambda: None)
    store = settings.Store()
    account = store.load()
    account.remote_url = demo.url
    account.user_name = "robin"
    store.save(account)
    keyring.store(keyring.PASSWORD, "changed on the server")
    conn = connection.Connection(store, watch=False)
    window = Window(app, conn)
    window.present()
    run_until(lambda: isinstance(visible(window), setup.SetupPage))
    assert not conn.signed_in
    window.destroy()


def test_proxy_login_opens_the_login_page(app, demo, monkeypatch):
    """The router's "proxy-login" signal (the proxy's session ran out)
    opens the toolkit's login page; its cookies are loaded at start."""
    from phosh_toolkit import proxy_login
    from phosh_toolkit.http import origin

    from nauta.window import Window
    monkeypatch.setattr(router.network, "current_ssids", lambda: None)
    proxy_login.CookieJar(keyring.KEYRING).save({origin(demo.url): "s=1"})
    store = settings.Store()
    account = store.load()
    account.remote_url = demo.url
    account.user_name = "robin"
    store.save(account)
    keyring.store(keyring.PASSWORD, PASSWORD)
    conn = connection.Connection(store, watch=False)
    assert conn.api.http.cookies == {origin(demo.url): "s=1"}
    calls = []
    monkeypatch.setattr(proxy_login, "sign_in", lambda *a: calls.append(a))
    window = Window(app, conn)
    conn.emit("proxy-login", demo.url + "/login")
    assert calls and calls[0][0] is window.nav and calls[0][5] == demo.url + "/login"
    window.player.clear()
    window.destroy()
