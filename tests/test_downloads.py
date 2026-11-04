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
from nauta.metube import YOUTUBE, YOUTUBE_MUSIC, MeTube, matches, search_url, video_id


def test_search_urls():
    assert search_url("  Harbour   Lights ") == \
        "https://music.youtube.com/search?q=Harbour+Lights#songs"
    assert search_url("a b", YOUTUBE, 5) == "ytsearch5:a b"
    assert video_id("https://music.youtube.com/watch?v=abc&list=x") == "abc"
    item = {"id": "abc", "url": "https://www.youtube.com/watch?v=abc"}
    assert matches(item, "https://music.youtube.com/watch?v=abc")


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
    dl.search("juniper", YOUTUBE_MUSIC, lambda r, e: done.append((r, e)))
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
