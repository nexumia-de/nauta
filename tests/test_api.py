"""The Subsonic client, the connection and the media proxy against the
demo server, also behind mutual TLS."""
import hashlib
import urllib.request

import pytest
from phosh_toolkit import router, tls
from phosh_toolkit.http import AUTH, CERTIFICATE_REQUIRED, SERVER, Client, HttpError
from phosh_toolkit.proxy import MediaProxy
from phosh_toolkit.route import LOCAL, REMOTE

from conftest import P12_PASSWORD, run_until
from nauta import USER_AGENT, connection, keyring, settings
from nauta.api import Subsonic, token
from nauta.demo import PASSWORD


def api_for(url, http=None, password=PASSWORD):
    api = Subsonic(http)
    api.base_url, api.user, api.password = url, "robin", password
    return api


def test_token_is_salted_md5():
    assert token("sesame", "c19b2d") == hashlib.md5(b"sesamec19b2d").hexdigest()


def test_credentials_only_in_the_body(demo):
    api_for(demo.url).ping()
    method, path, form = demo.requests[-1]
    assert (method, path) == ("POST", "/rest/ping")
    assert form["u"] == "robin" and form["c"] == "Nauta" and form["f"] == "json"
    assert form["t"] == token(PASSWORD, form["s"]) and "p" not in form
    # A fresh salt for every request.
    api_for(demo.url).ping()
    assert demo.requests[-1][2]["s"] != form["s"]


def test_probe_needs_no_credentials(demo):
    info = Subsonic().probe(demo.url)
    assert info["type"] == "navidrome" and info["openSubsonic"]
    assert "u" not in demo.requests[-1][2]


def test_probe_rejects_other_servers(demo, monkeypatch):
    monkeypatch.setattr("nauta.demo.EXTENSIONS", ("songLyrics",))
    with pytest.raises(HttpError) as e:
        Subsonic().probe(demo.url)
    assert e.value.kind == SERVER and "OpenSubsonic" in str(e.value)


def test_wrong_password_is_auth_error(demo):
    with pytest.raises(HttpError) as e:
        api_for(demo.url, password="nope").ping()
    assert e.value.kind == AUTH


def test_browse(demo):
    api = api_for(demo.url)
    newest = api.albums("newest", size=4)
    assert len(newest) == 4
    assert newest[0]["created"] >= newest[1]["created"]
    assert len(api.albums("alphabeticalByName", size=60)) == 10
    artists = api.artists()
    assert [a["name"] for a in artists][:2] == ["Ada Lindqvist Trio", "Harbour Lights"]
    artist = api.artist(artists[1]["id"])
    assert len(artist["album"]) == 3
    album = api.album(artist["album"][0]["id"])
    assert album["song"][0]["track"] == 1
    lists = api.playlists()
    assert [p["name"] for p in lists] == ["Commute", "Quiet Evening"]
    assert api.playlist(lists[0]["id"])["entry"]
    found = api.search("harbour")
    assert found["artist"][0]["name"] == "Harbour Lights"
    assert any(s["title"] == "Glass Harbour" for s in found["song"])
    assert api.cover(album["coverArt"], 64).startswith(b"\x89PNG")
    with pytest.raises(HttpError):
        api.album("missing")


def test_scrobble(demo):
    api = api_for(demo.url)
    api.scrobble("tr-1", False)
    api.scrobble("tr-1", True)
    assert demo.scrobbles == [("tr-1", False), ("tr-1", True)]


def test_mtls(mtls_demo, pki, trust):
    http = Client(USER_AGENT)
    http.tls_database = trust
    with pytest.raises(HttpError) as e:
        Subsonic(http).probe(mtls_demo.url)
    assert e.value.kind == CERTIFICATE_REQUIRED
    http.certificate = tls.load((pki / "client.p12").read_bytes(), P12_PASSWORD)
    assert api_for(mtls_demo.url, http).artists()


def _connection(local, remote, networks, ssids, monkeypatch):
    store = settings.Store()
    account = store.load()
    account.local_url, account.remote_url = local, remote
    account.home_networks = list(networks)
    store.save(account)
    monkeypatch.setattr(router.network, "current_ssids", lambda: ssids)
    return connection.Connection(store, watch=False)


def _resolve(conn):
    done = []
    conn.resolve(lambda e: done.append(e))
    run_until(lambda: done)
    return done[0]


def test_local_only_on_a_listed_home_network(demo, monkeypatch):
    conn = _connection(demo.url, "http://127.0.0.1:9", ["Home"], {"Home"}, monkeypatch)
    assert _resolve(conn) is None and conn.state == LOCAL
    assert conn.api.base_url == demo.url
    # Without NetworkManager or without a list the local address is not
    # tried: no server id protects the password there.
    conn = _connection(demo.url, "", ["Home"], None, monkeypatch)
    assert isinstance(_resolve(conn), HttpError)
    conn = _connection(demo.url, "", [], {"Home"}, monkeypatch)
    assert isinstance(_resolve(conn), HttpError)


def test_away_uses_remote(demo, monkeypatch):
    conn = _connection("http://127.0.0.1:9", demo.url, ["Home"], {"Café"}, monkeypatch)
    assert _resolve(conn) is None and conn.state == REMOTE


def test_sign_in_keeps_the_password_in_the_keyring(demo, monkeypatch):
    conn = _connection("", demo.url, [], None, monkeypatch)
    done = []
    connection.sign_in(conn, demo.url, "robin", PASSWORD, lambda r, e: done.append(e))
    run_until(lambda: done)
    assert done[0] is None and conn.signed_in
    assert keyring.lookup(keyring.PASSWORD) == PASSWORD
    assert f'"{PASSWORD}"' not in conn.store.path.read_text()
    again = connection.Connection(conn.store, watch=False)
    assert again.signed_in and again.account.server_type == "navidrome"


def test_rejected_password_signs_out(demo, monkeypatch):
    conn = _connection("", demo.url, [], None, monkeypatch)
    conn.account.user_name = "robin"
    conn.api.user, conn.api.password = "robin", "changed"
    signals = []
    conn.connect("signed-out", lambda *_: signals.append(1))
    done = []
    conn.call(conn.api.artists, lambda r, e: done.append(e))
    run_until(lambda: done)
    assert done[0].kind == AUTH and signals == [1] and not conn.signed_in


def test_proxy_streams_without_credentials_in_the_url(mtls_demo, pki, trust, monkeypatch):
    conn = _connection("", mtls_demo.url, [], None, monkeypatch)
    conn.api.http.tls_database = trust
    conn.api.http.certificate = tls.load((pki / "client.p12").read_bytes(), P12_PASSWORD)
    conn.api.user, conn.api.password = "robin", PASSWORD
    assert _resolve(conn) is None
    song = mtls_demo.library["songs"][0]
    proxy = MediaProxy(conn.forward)
    try:
        url = proxy.url(conn.api.stream_path(song["id"], 192))
        request = urllib.request.Request(url, headers={"Range": "bytes=0-43"})
        with urllib.request.urlopen(request, timeout=10) as response:
            assert response.status == 206 and response.read().startswith(b"RIFF")
    finally:
        proxy.stop()
    method, path, form = mtls_demo.requests[-1]
    assert method == "POST" and path == f"/rest/stream?id={song['id']}&maxBitRate=192"
    assert form["t"] == token(PASSWORD, form["s"])


def test_proxy_basic_auth_reaches_navidrome(demo, monkeypatch):
    """The proxy's Basic auth goes along with every call and stream, the
    Subsonic credentials stay in the body."""
    from phosh_toolkit.proxy_login import ProxyCredentials
    demo.proxy_basic = "phone:s3cret"
    conn = _connection("", demo.url, [], None, monkeypatch)
    conn.api.user, conn.api.password = "robin", PASSWORD
    error = _resolve(conn)
    assert error.kind == "proxy-login" and error.wants_basic
    ProxyCredentials(keyring.KEYRING).set(demo.url, "phone", "s3cret")
    conn.load_proxy_login()
    assert _resolve(conn) is None
    assert conn.api.artists()
    song = demo.library["songs"][0]
    proxy = MediaProxy(conn.forward)
    try:
        with urllib.request.urlopen(proxy.url(conn.api.stream_path(song["id"])),
                                    timeout=10) as response:
            assert response.status == 200
    finally:
        proxy.stop()
