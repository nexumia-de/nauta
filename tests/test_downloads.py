"""The MeTube client and the download server's connection against the
MeTube stand-in (nauta.demo.DemoMeTube), also behind mutual TLS and a
proxy login (docs/downloads.md)."""
import pytest
from phosh_toolkit import router
from phosh_toolkit.http import CERTIFICATE_REQUIRED, PROXY_LOGIN, Client, HttpError, origin
from phosh_toolkit.proxy_login import CookieJar
from phosh_toolkit.route import LOCAL, REMOTE

from conftest import P12_PASSWORD, run_until
from nauta import USER_AGENT, downloads, keyring, settings
from nauta.metube import (SONGS, YOUTUBE, YOUTUBE_MUSIC, MeTube, collection_link, matches,
                          search_url, video_id)
from nauta.ytmusic import ALBUMS, PLAYLISTS, YouTubeMusic, collection_url, parse


def test_search_urls():
    assert search_url("  Harbour   Lights ") == \
        "https://music.youtube.com/search?q=Harbour+Lights#songs"
    assert search_url("a b", YOUTUBE, 5) == "ytsearch5:a b"
    assert video_id("https://music.youtube.com/watch?v=abc&list=x") == "abc"
    item = {"id": "abc", "url": "https://www.youtube.com/watch?v=abc"}
    assert matches(item, "https://music.youtube.com/watch?v=abc")


def test_collection_links():
    album = "https://music.youtube.com/browse/MPREb_abc"
    assert collection_link(f" {album} ") == album
    assert collection_link("https://music.youtube.com/playlist?list=OLAK5uy_x&si=y") == \
        "https://music.youtube.com/playlist?list=OLAK5uy_x"
    assert collection_link("https://youtube.com/watch?v=abc&list=PLx") == \
        "https://www.youtube.com/playlist?list=PLx"
    for text in ("harbour lights", "https://music.youtube.com/watch?v=abc",
                 "https://example.com/playlist?list=PLx", "ytsearch5:a"):
        assert collection_link(text) == ""
    assert collection_url("MPREb_abc") == album
    assert collection_url("VLPLx") == "https://music.youtube.com/playlist?list=PLx"
    assert collection_url("UCartist") == ""
    assert parse({}, ALBUMS) == [] and parse({"contents": None}, ALBUMS) == []


def test_youtube_music_search(youtube_music):
    api = YouTubeMusic(base_url=youtube_music.url)
    albums = api.search("  harbour   lights ", ALBUMS)
    assert albums == [{"url": "https://music.youtube.com/browse/MPREb_demoHarbour01",
                       "title": "Saltwater Letters", "kind": ALBUMS,
                       "subtitle": "Album • Harbour Lights • 2024"}]
    method, path, body = youtube_music.requests[-1]
    assert body["query"] == "harbour lights"
    assert body["context"]["client"]["clientName"] == "WEB_REMIX"
    playlists = api.search("harbour", PLAYLISTS)
    assert [p["title"] for p in playlists] == ["Coastal Evenings"]
    # Featured playlists first, then community playlists.
    assert len(youtube_music.requests) == 3
    assert api.search("nothing like this", ALBUMS) == []


def test_browse_and_add_an_album(metube):
    api = MeTube()
    api.base_url = metube.url
    url = "https://music.youtube.com/browse/MPREb_demoHarbour01"
    title, songs = api.browse(url)
    assert title == "Saltwater Letters"
    assert [s["title"] for s in songs] == ["Northern Tide", "Lanterns on the Pier",
                                           "Saltwater Letters"]
    assert metube.requests[-1][2]["playlist_item_limit"] == 200
    api.add(url)
    assert [i["title"] for i in api.history()["queue"]] == [s["title"] for s in songs]


def test_probe_search_and_add(metube):
    api = MeTube()
    assert api.probe(metube.url)["yt-dlp"]
    api.base_url = metube.url
    found = api.search("harbour lights")
    assert found and all(set(r) == {"url", "title", "duration"} for r in found)
    method, path, body = metube.requests[-1]
    assert (method, path) == ("POST", "browse")
    assert body["url"].startswith("https://music.youtube.com/search?q=harbour+lights")
    assert api.search("harbour", YOUTUBE)[0]["duration"]
    assert api.search("nothing like this") == []
    api.add(found[0]["url"], "opus")
    body = metube.requests[-1][2]
    assert body["download_type"] == "audio" and body["format"] == "opus"
    assert body["audio_tags"] == "with_cover" and body["auto_start"] is True
    assert api.history()["queue"][0]["title"] == found[0]["title"]


def test_probe_rejects_other_servers(demo):
    with pytest.raises(HttpError):
        MeTube().probe(demo.url)


def _downloads(local, remote, networks, ssids, monkeypatch):
    store = settings.DownloadStore()
    account = store.load()
    account.local_url, account.remote_url = local, remote
    account.home_networks = list(networks)
    store.save(account)
    monkeypatch.setattr(router.network, "current_ssids", lambda: ssids)
    return downloads.Downloads(store, watch=False)


def _resolve(dl):
    done = []
    dl.resolve(lambda e: done.append(e))
    run_until(lambda: done)
    return done[0]


def test_route_like_the_music_server(metube, monkeypatch):
    dl = _downloads(metube.url, "http://127.0.0.1:9", ["Home"], {"Home"}, monkeypatch)
    assert _resolve(dl) is None and dl.state == LOCAL
    # Away, or without NetworkManager: only the remote address.
    dl = _downloads(metube.url, "", ["Home"], None, monkeypatch)
    assert isinstance(_resolve(dl), HttpError)
    dl = _downloads("http://127.0.0.1:9", metube.url, ["Home"], {"Café"}, monkeypatch)
    assert _resolve(dl) is None and dl.state == REMOTE


def test_not_configured(monkeypatch):
    dl = downloads.Downloads(settings.DownloadStore(), watch=False)
    assert not dl.configured
    assert isinstance(_resolve(dl), HttpError)


def test_finished_and_failed_downloads_are_reported(metube, monkeypatch):
    dl = _downloads("", metube.url, [], None, monkeypatch)
    monkeypatch.setattr(downloads, "POLL", 1)
    found = metube.data["results"]["youtube-music"]
    events = []
    dl.connect("finished", lambda d, title: events.append(("finished", title)))
    dl.connect("failed", lambda d, title, msg: events.append(("failed", title, msg)))
    added = []
    for entry in (found[0], found[-1]):     # the last one is "unavailable"
        dl.add(entry["url"], entry["title"], lambda a, e: added.append(e))
    run_until(lambda: len(added) == 2)
    assert added == [None, None]
    run_until(lambda: len(events) == 2, timeout=20)
    assert ("finished", found[0]["title"]) in events
    assert ("failed", found[-1]["title"], "Video unavailable") in events
    assert not dl._mine
    # Downloading the same song again is a new download, not the old one.
    dl.add(found[0]["url"], found[0]["title"], lambda a, e: added.append(e))
    run_until(lambda: len(added) == 3)
    assert len(dl._mine) == 1
    run_until(lambda: len(events) == 3, timeout=20)


def test_whole_album_and_playlist_reported_once(metube, monkeypatch):
    dl = _downloads("", metube.url, [], None, monkeypatch)
    monkeypatch.setattr(downloads, "POLL", 1)
    events = []
    dl.connect("finished", lambda d, title: events.append(("finished", title)))
    dl.connect("failed", lambda d, title, msg: events.append(("failed", title, msg)))
    added = []
    for url in ("https://music.youtube.com/browse/MPREb_demoHarbour01",
                "https://music.youtube.com/playlist?list=PLdemoCoastal00001"):
        listed = []
        dl.browse(url, lambda r, e: listed.append(r))
        run_until(lambda: listed)
        title, songs = listed[0]
        dl.add(url, title, lambda a, e: added.append(e), songs)
    run_until(lambda: len(added) == 2)
    assert added == [None, None]
    # "Lanterns on the Pier" is on the album and in the playlist.
    assert len(dl._mine) == 8 and sum(len(j) for j in dl._mine.values()) == 9
    run_until(lambda: len(events) == 2, timeout=20)
    assert ("finished", "Saltwater Letters") in events
    # The playlist's "Unavailable Session" failed, the other five not.
    assert ("failed", "Coastal Evenings", "1 of 6 songs failed (Video unavailable)") in events
    assert not dl._mine


def test_search_kinds(metube, youtube_music, monkeypatch):
    """Songs and videos through MeTube, albums and playlists straight from
    YouTube Music, without the download server's proxy login."""
    metube.proxy_basic = "phone:s3cret"
    from phosh_toolkit.proxy_login import ProxyCredentials
    ProxyCredentials(keyring.DOWNLOADS).set(metube.url, "phone", "s3cret")
    dl = _downloads("", metube.url, [], None, monkeypatch)
    dl.youtube_music.base_url = youtube_music.url
    done = []
    dl.search("harbour", YOUTUBE_MUSIC, ALBUMS, lambda r, e: done.append((r, e)))
    run_until(lambda: done)
    assert done[0][1] is None and done[0][0][0]["title"] == "Saltwater Letters"
    assert not [r for r in metube.requests if r[1] == "browse"]
    headers = youtube_music.headers[-1]
    assert "Authorization" not in headers and "Cookie" not in headers
    assert headers["User-Agent"].startswith("Nauta/")
    done.clear()
    dl.search("harbour", YOUTUBE, ALBUMS, lambda r, e: done.append((r, e)))
    run_until(lambda: done)
    assert done[0][1] is None and done[0][0][0]["duration"]


def test_mtls(mtls_metube, pki, trust, monkeypatch):
    http = Client(USER_AGENT)
    http.tls_database = trust
    with pytest.raises(HttpError) as e:
        MeTube(http).probe(mtls_metube.url)
    assert e.value.kind == CERTIFICATE_REQUIRED
    store = settings.DownloadStore()
    account = store.load()
    account.remote_url = mtls_metube.url
    account.certificate = True
    store.save(account)
    settings.download_certificates().save((pki / "client.p12").read_bytes(), P12_PASSWORD)
    monkeypatch.setattr(router.network, "current_ssids", lambda: None)
    dl = downloads.Downloads(store, watch=False)
    dl.api.http.tls_database = trust
    assert dl.certificate_error is None
    assert _resolve(dl) is None
    done = []
    dl.search("juniper", YOUTUBE_MUSIC, SONGS, lambda r, e: done.append((r, e)))
    run_until(lambda: done)
    assert done[0][1] is None and done[0][0][0]["title"] == "Pine Smoke"
    # Its certificate password lives apart from the music server's.
    assert keyring.lookup(keyring.CERTIFICATE_PASSWORD) is None


def test_proxy_login(metube, monkeypatch):
    metube.proxy_cookie = "session=ok"
    dl = _downloads("", metube.url, [], None, monkeypatch)
    signals = []
    dl.connect("proxy-login", lambda d, url: signals.append(url))
    error = _resolve(dl)
    assert error.kind == PROXY_LOGIN and signals == [metube.url]
    # The cookies of a login (phosh_toolkit.proxy_login) are loaded at start.
    CookieJar(keyring.DOWNLOADS).save({origin(metube.url): "session=ok"})
    assert CookieJar(keyring.KEYRING).load() == {}
    dl = downloads.Downloads(dl.store, watch=False)
    assert _resolve(dl) is None


def test_proxy_basic_auth(metube, monkeypatch):
    """Pangolin's header authentication in front of MeTube: user name and
    password from the keyring, sent only to MeTube's address."""
    from phosh_toolkit.proxy_login import ProxyCredentials
    metube.proxy_basic = "phone:s3cret"
    dl = _downloads("", metube.url, [], None, monkeypatch)
    error = _resolve(dl)
    assert error.kind == PROXY_LOGIN and error.wants_basic
    assert dl.proxy_error is error
    ProxyCredentials(keyring.DOWNLOADS).set(metube.url, "phone", "s3cret")
    assert ProxyCredentials(keyring.KEYRING).load() == {}
    dl.reconnect()
    run_until(lambda: dl.state == REMOTE)
    assert metube.requests[-1][1] == "version"
    dl.forget()
    assert ProxyCredentials(keyring.DOWNLOADS).load() == {}
