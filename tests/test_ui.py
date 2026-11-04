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
from gi.repository import Adw, Gst, Gtk  # noqa: E402
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
    monkeypatch.setattr(proxy_login, "sign_in", lambda *a, **kw: calls.append((a, kw)))
    window = Window(app, conn)
    conn.emit("proxy-login", demo.url + "/login")
    assert calls and calls[0][0][0] is window.nav
    assert calls[0][0][5] == demo.url + "/login"
    # A proxy that wants HTTP Basic auth points to the preferences.
    toasts = []
    monkeypatch.setattr(window, "toast", toasts.append)
    calls[0][1]["on_basic"]()
    assert "Proxy Login" in toasts[-1]
    window.player.clear()
    window.destroy()


def test_music_goes_on_with_the_window_closed(app, demo, monkeypatch):
    from nauta.window import Window
    monkeypatch.setattr(router.network, "current_ssids", lambda: None)
    store = settings.Store()
    account = store.load()
    account.remote_url, account.user_name = demo.url, "robin"
    store.save(account)
    keyring.store(keyring.PASSWORD, PASSWORD)
    conn = connection.Connection(store, watch=False)
    window = Window(app, conn)
    window.present()
    quits = []
    monkeypatch.setattr(window, "quit_app", lambda: quits.append(1))
    album = demo.library["albums"][0]["id"]
    window.player.play([s for s in demo.library["songs"] if s["albumId"] == album])
    run_until(lambda: window.player.playing and window._inhibiting, 15)
    # Closing hides the window and holds the app; the music plays on.
    assert window.emit("close-request") is True
    assert not window.get_visible() and window._held and window.player.playing
    window.player.toggle()
    run_until(lambda: not window._inhibiting, 5)
    assert not quits                       # paused: still there
    window.player.stop()
    assert quits == [1]                    # nothing left: quit
    window._held = False
    app.release()
    window.player.clear()
    window.destroy()


def test_find_and_download_new_music(app, demo, mtls_metube, pki, trust, monkeypatch):
    """From a search without results to MeTube's setup behind mutual TLS,
    a search, a download and its end, the list of downloads and the
    preferences (docs/downloads.md)."""
    from nauta import downloads, find
    from nauta.pages import SearchPage
    from nauta.preferences import PreferencesDialog
    from nauta.window import Window

    def trusting_client(user_agent):
        client = Client(user_agent)
        client.tls_database = trust
        return client
    monkeypatch.setattr(connection_form, "Client", trusting_client)
    monkeypatch.setattr(router.network, "current_ssids", lambda: None)
    monkeypatch.setattr(downloads, "POLL", 1)
    store = settings.Store()
    account = store.load()
    account.remote_url = demo.url
    account.user_name = "robin"
    store.save(account)
    keyring.store(keyring.PASSWORD, PASSWORD)
    conn = connection.Connection(store, watch=False)
    dl = downloads.Downloads(watch=False)
    dl.api.http.tls_database = trust
    window = Window(app, conn, dl)
    window.present()
    toasts = []
    monkeypatch.setattr(window, "toast", toasts.append)

    window.show_search()
    search = visible(window)
    assert isinstance(search, SearchPage)
    search.search("pine smoke")
    run_until(lambda: search.stack.get_visible_child_name() == "empty")
    search.stack.get_child_by_name("empty").get_child().emit("clicked")
    setup_page = visible(window)
    assert isinstance(setup_page, find.DownloadSetupPage)

    setup_page.form.toast = window.toast
    setup_page.form.remote.set_text(mtls_metube.url)
    setup_page.form.choose_data((pki / "client.p12").read_bytes(), "client.p12")
    setup_page.form.password.set_text(P12_PASSWORD)
    setup_page.button.emit("clicked")
    run_until(lambda: isinstance(visible(window), find.FindMusicPage))
    page = visible(window)
    # The setup page made way: swiping back returns to the library search.
    assert window.nav.get_previous_page(page) is search
    assert settings.DownloadStore().load().certificate
    # The query from the library search was taken along.
    assert page.entry.get_text() == "pine smoke"
    run_until(lambda: page.stack.get_visible_child_name() == "results")
    results = page.stack.get_child_by_name("results")
    box = results.get_child().get_child().get_child()
    row = box.get_row_at_index(0)
    assert row.get_title() == "Pine Smoke"

    page.source_buttons["youtube"].set_active(True)
    assert settings.DownloadStore().load().source == "youtube"
    run_until(lambda: page.stack.get_visible_child_name() == "results"
              and page.stack.get_child_by_name("results") is not results)
    box = page.stack.get_child_by_name("results").get_child().get_child().get_child()
    row = box.get_row_at_index(0)
    assert row.get_title().startswith("Juniper Vale - Pine Smoke")
    row.download.emit("clicked")
    run_until(lambda: any("Downloaded" in t for t in toasts), 20)
    assert row.download.get_icon_name() == "object-select-symbolic"
    added = [b for m, p, b in mtls_metube.requests if p == "add"]
    assert added[0]["format"] == "m4a"

    page.search("nothing like this")
    run_until(lambda: page.stack.get_visible_child_name() == "empty")

    window.nav.push(find.DownloadsPage(window))
    downloads_page = visible(window)
    run_until(lambda: downloads_page.stack.get_visible_child_name() == "list")
    window.nav.pop()
    run_until(lambda: dl._watchers == 0)

    dialog = PreferencesDialog(window)
    dialog.present(window)
    assert dialog.download_form.remote.get_text() == mtls_metube.url
    assert dialog.download_remove.get_visible()
    dialog._on_download_remove_response(None, "remove")
    assert not dl.configured and not settings.DownloadStore().load().remote_url
    assert not dialog.download_remove.get_visible()
    dialog.close()
    window.destroy()


def test_setup_with_the_proxy_basic_auth(app, demo, monkeypatch):
    """The setup form asks for the proxy's user name and password when the
    proxy challenges, and keeps them for later starts."""
    from phosh_toolkit.http import origin
    from phosh_toolkit.proxy_login import ProxyCredentials

    from nauta.window import Window
    monkeypatch.setattr(router.network, "current_ssids", lambda: None)
    monkeypatch.setattr(connection_form.network, "current_ssids", lambda: None)
    demo.proxy_basic = "phone:s3cret"
    conn = connection.Connection(watch=False)
    window = Window(app, conn)
    toasts = []
    monkeypatch.setattr(window, "toast", toasts.append)
    page = visible(window)
    page.form.toast = window.toast
    page.form.remote.set_text(demo.url)
    page.button.emit("clicked")
    run_until(lambda: page.button.get_sensitive() and toasts)
    assert "Proxy Login" in toasts[-1] and page.form.proxy.get_expanded()
    page.form.proxy_user.set_text("phone")
    page.form.proxy_password.set_text("s3cret")
    page.button.emit("clicked")
    run_until(lambda: isinstance(visible(window), setup.SignInPage))
    sign_in = visible(window)
    sign_in.user.set_text("robin")
    sign_in.password.set_text(PASSWORD)
    sign_in.button.emit("clicked")
    run_until(lambda: window.main is not None)
    assert ProxyCredentials(keyring.KEYRING).get(demo.url) == ("phone", "s3cret")
    again = connection.Connection(watch=False)
    assert origin(demo.url) in again.api.http.proxy_auth
    window.destroy()


def test_playing_song_follows_the_route(app, demo, monkeypatch):
    """When the route changes (Wi-Fi gone), the media proxy cuts the
    running stream so the player reconnects through the new address."""
    from nauta.window import Window
    monkeypatch.setattr(router.network, "current_ssids", lambda: None)
    store = settings.Store()
    account = store.load()
    account.remote_url = demo.url
    account.user_name = "robin"
    store.save(account)
    keyring.store(keyring.PASSWORD, PASSWORD)
    conn = connection.Connection(store, watch=False)
    window = Window(app, conn)
    calls = []
    monkeypatch.setattr(window.proxy, "reroute", lambda: calls.append(1))
    run_until(lambda: conn.base_url == demo.url)
    assert calls == []          # the first route is no change
    conn.base_url = "http://127.0.0.1:9"
    conn.emit("state-changed")
    assert calls == [1]
    window.player.clear()
    window.destroy()


def _rows(page, name):
    """The rows of a list page's scrolled list (results or songs)."""
    child = page.stack.get_child_by_name(name).get_child().get_child()
    box = child if isinstance(child, Gtk.ListBox) else child.get_last_child()
    rows, row = [], box.get_first_child()
    while row is not None:
        rows.append(row)
        row = row.get_next_sibling()
    return rows


def test_find_albums_and_playlists(app, demo, metube, youtube_music, monkeypatch):
    """The Songs, Albums and Playlists filters, an album downloaded as a
    whole, one song of a playlist, and a pasted link (docs/downloads.md)."""
    from nauta import downloads, find
    from nauta.window import Window
    monkeypatch.setattr(router.network, "current_ssids", lambda: None)
    monkeypatch.setattr(downloads, "POLL", 1)
    store = settings.Store()
    account = store.load()
    account.remote_url = demo.url
    account.user_name = "robin"
    store.save(account)
    keyring.store(keyring.PASSWORD, PASSWORD)
    dl_store = settings.DownloadStore()
    dl_account = dl_store.load()
    dl_account.remote_url = metube.url
    dl_store.save(dl_account)
    dl = downloads.Downloads(dl_store, watch=False)
    dl.youtube_music.base_url = youtube_music.url
    window = Window(app, connection.Connection(store, watch=False), dl)
    window.present()
    toasts = []
    monkeypatch.setattr(window, "toast", toasts.append)

    window.show_find_music("harbour")
    page = visible(window)
    assert isinstance(page, find.FindMusicPage)
    assert page.kinds.get_reveal_child()
    run_until(lambda: page.stack.get_visible_child_name() == "results")
    assert _rows(page, "results")[0].get_title() == "Northern Tide"

    page.kind_buttons["albums"].set_active(True)
    assert settings.DownloadStore().load().kind == "albums"
    run_until(lambda: page.stack.get_visible_child_name() == "results"
              and _rows(page, "results")[0].get_title() == "Saltwater Letters")
    album = _rows(page, "results")[0]
    assert album.get_subtitle() == "Album • Harbour Lights • 2024"
    album.emit("activated")
    collection = visible(window)
    assert isinstance(collection, find.CollectionPage)
    assert window.nav.get_previous_page(collection) is page
    run_until(lambda: collection.stack.get_visible_child_name() == "songs")
    assert [r.get_title() for r in collection.rows] == [
        "Northern Tide", "Lanterns on the Pier", "Saltwater Letters"]
    collection.download_all.emit("clicked")
    run_until(lambda: any("Downloaded “Saltwater Letters”" in t for t in toasts), 20)
    added = [b for m, p, b in metube.requests if p == "add"]
    assert [b["url"] for b in added] == [
        "https://music.youtube.com/playlist?list=OLAK5uy_demoHarbour01"]
    assert not collection.download_all.get_sensitive()
    assert all(not r.download.get_sensitive() for r in collection.rows)
    window.nav.pop()

    # An album whose search result has no playlist id: its album page is
    # resolved on YouTube Music, MeTube only ever gets the playlist.
    page.search("okafor")
    run_until(lambda: page.stack.get_visible_child_name() == "results"
              and _rows(page, "results")[0].get_title() == "Glass Orchard")
    _rows(page, "results")[0].emit("activated")
    collection = visible(window)
    run_until(lambda: collection.stack.get_visible_child_name() == "songs")
    assert [r.get_title() for r in collection.rows] == ["Glass Orchard", "Slow Satellite"]
    collection.download_all.emit("clicked")
    run_until(lambda: any("Downloaded “Glass Orchard”" in t for t in toasts), 20)
    playlist = "https://music.youtube.com/playlist?list=OLAK5uy_demoOkafor001"
    assert [b["url"] for m, p, b in metube.requests if p in ("browse", "add")][-2:] == \
        [playlist, playlist]
    assert not [b for m, p, b in metube.requests if "MPREb_" in str(b.get("url"))]
    window.nav.pop()

    page.entry.set_text("harbour")
    page.kind_buttons["playlists"].set_active(True)
    run_until(lambda: page.stack.get_visible_child_name() == "results"
              and _rows(page, "results")[0].get_title() == "Coastal Evenings")
    _rows(page, "results")[0].emit("activated")
    collection = visible(window)
    run_until(lambda: collection.stack.get_visible_child_name() == "songs")
    collection.rows[1].download.emit("clicked")
    run_until(lambda: any("Downloaded “Pine Smoke”" in t for t in toasts), 20)
    added = [b for m, p, b in metube.requests if p == "add"]
    assert added[-1]["url"] == "https://music.youtube.com/watch?v=demo0000005"
    assert collection.download_all.get_sensitive()
    window.nav.pop()

    # YouTube searches videos only: no filters there.
    page.source_buttons["youtube"].set_active(True)
    assert not page.kinds.get_reveal_child() and page.kind == "songs"
    page.source_buttons["youtube-music"].set_active(True)

    # A pasted link opens its album or playlist.
    page.search("https://music.youtube.com/playlist?list=PLdemoCoastal00001&si=x")
    collection = visible(window)
    assert isinstance(collection, find.CollectionPage)
    run_until(lambda: collection.get_title() == "Coastal Evenings")
    assert len(collection.rows) == 6
    window.nav.pop()
    page.search("https://music.youtube.com/browse/MPREb_demoHarbour01")
    collection = visible(window)
    run_until(lambda: collection.stack.get_visible_child_name() == "songs")
    assert collection.get_title() == "Saltwater Letters"
    assert collection.url == "https://music.youtube.com/playlist?list=OLAK5uy_demoHarbour01"
    window.destroy()
