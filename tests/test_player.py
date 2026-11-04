"""The play queue through the demo server and the media proxy with real
GStreamer (WAV tones); sound goes to a clocked fakesink."""
import pytest
from phosh_toolkit import router
from phosh_toolkit.media import Media, init
from phosh_toolkit.proxy import MediaProxy

from conftest import run_until
from nauta import connection, settings
from nauta.demo import PASSWORD
from nauta.player import Player

gi = pytest.importorskip("gi")
gi.require_version("Gst", "1.0")
from gi.repository import Gst  # noqa: E402

init()
missing = [e for e in ("playbin3", "wavparse", "souphttpsrc")
           if Gst.ElementFactory.find(e) is None]
pytestmark = pytest.mark.skipif(bool(missing), reason=f"GStreamer lacks {missing}")


def media(url):
    m = Media(url, video=False)
    sink = Gst.ElementFactory.make("fakesink", None)
    sink.props.sync = True
    m.pipeline.props.audio_sink = sink
    return m


@pytest.fixture
def player(demo, monkeypatch):
    monkeypatch.setattr(router.network, "current_ssids", lambda: None)
    store = settings.Store()
    account = store.load()
    account.remote_url, account.user_name = demo.url, "robin"
    store.save(account)
    conn = connection.Connection(store, watch=False)
    conn.api.user, conn.api.password = "robin", PASSWORD
    proxy = MediaProxy(conn.forward)
    p = Player(conn, proxy, make_media=media)
    yield p
    p.clear()
    proxy.stop()


def album(demo):
    first = demo.library["albums"][0]["id"]
    return [s for s in demo.library["songs"] if s["albumId"] == first]


def test_plays_and_reports(player, demo):
    songs = album(demo)
    changes = []
    player.connect("song-changed", lambda *_: changes.append(player.index))
    player.play(songs, 1)
    run_until(lambda: player.position > 0.3, 15)
    assert player.playing and player.song is songs[1]
    assert 19 < player.duration < 21          # the demo's 20 s tone
    assert player.bitrate() == 192             # away: the default
    method, path, form = [r for r in demo.requests if "stream" in r[1]][-1]
    assert path.endswith("maxBitRate=192") and "t" in form
    run_until(lambda: (songs[1]["id"], False) in demo.scrobbles)
    player.toggle()
    run_until(lambda: not player.playing, 5)
    # Near the end: the song counts as played, the next one starts.
    player.toggle()
    player.seek(19.5)
    run_until(lambda: player.index == 2, 15)
    assert (songs[1]["id"], True) in demo.scrobbles
    assert changes[0] == 1 and changes[-1] == 2


def test_previous_restarts_then_goes_back(player, demo):
    songs = album(demo)
    player.play(songs, 1)
    run_until(lambda: player.position > 0.2, 15)
    player.previous()
    assert player.index == 0


def test_last_song_ends_and_shuffle_keeps_the_chosen_first(player, demo):
    songs = album(demo)
    player.play(songs, 3, shuffle=True)
    assert player.song is songs[3] and len(player.queue) == len(songs)
    player.play(songs[-1:])
    run_until(lambda: player.position > 0.2, 15)
    player.seek(19.6)
    run_until(lambda: player.media is None, 15)
    assert player.song is songs[-1] and not player.playing


def test_error_is_reported(player, demo):
    errors = []
    player.connect("error", lambda p, m: errors.append(m))
    player.play([{"id": "missing", "title": "Gone", "duration": 10}])
    run_until(lambda: errors, 15)
    assert player.media is None
