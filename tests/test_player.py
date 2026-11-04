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


# --- editing the queue, repeat, shuffle (docs/playback.md) -------------

def ids(songs):
    return [s["id"] for s in songs]


def test_play_next_and_add_to_the_end(player, demo):
    songs = album(demo)
    other = demo.library["songs"][-2:]
    player.play(songs[:3], 0)
    changes = []
    player.connect("queue-changed", lambda p: changes.append(1))
    player.play_next([other[0]])
    player.add([other[1]])
    assert ids(player.queue) == ids([songs[0], other[0], songs[1], songs[2], other[1]])
    assert player.index == 0 and len(changes) == 2
    # With nothing loaded, both start playing.
    player.clear()
    player.add(songs[:2])
    assert player.song is songs[0]


def test_remove_and_move_keep_the_current_song(player, demo):
    songs = album(demo)[:5]
    player.play(songs, 2)
    player.remove(0)
    assert player.song is songs[2] and player.index == 1
    player.move(3, 0)
    assert ids(player.queue) == ids([songs[4], songs[1], songs[2], songs[3]])
    assert player.song is songs[2] and player.index == 2
    player.remove(2)               # the current one: the next one plays
    assert player.song is songs[3]
    run_until(lambda: player.position > 0.1, 15)
    player.clear_upcoming()
    assert player.queue[-1] is songs[3] and player.upcoming == []


def test_shuffle_toggle_restores_the_order(player, demo):
    songs = album(demo)
    player.play(songs, 2)
    player.set_shuffle(True)
    assert player.shuffled and player.song is songs[2]
    # Only what comes next is shuffled.
    assert ids(player.queue[:3]) == ids(songs[:3])
    assert sorted(ids(player.upcoming)) == sorted(ids(songs[3:]))
    extra = demo.library["songs"][-1]
    player.add([extra])
    player.set_shuffle(False)
    assert ids(player.queue) == ids(songs + [extra])
    assert player.index == 2


def test_repeat(player, demo):
    songs = album(demo)[:2]
    player.play(songs, 1)
    player.cycle_repeat()
    assert player.repeat == "all"
    player.next()                         # past the end: back to the first
    assert player.index == 0
    player.cycle_repeat()
    assert player.repeat == "one"
    run_until(lambda: player.position > 0.2, 15)
    player.seek(19.6)
    run_until(lambda: player.position < 5 and player.playing, 15)
    assert player.index == 0              # the same song again


def test_queue_kept_across_restarts(player, demo, tmp_path):
    from nauta.resume import QueueMemory
    songs = album(demo)
    memory = QueueMemory(player, tmp_path / "queue.json")
    player.play(songs, 1)
    run_until(lambda: player.position > 0.2, 15)
    player.seek(7)
    run_until(lambda: player.position >= 7, 15)
    player.set_repeat("all")
    memory.close()
    player.clear()

    again = QueueMemory(player, tmp_path / "queue.json")
    again.restore()
    assert ids(player.queue) == ids(songs) and player.index == 1
    assert player.media is None and player.repeat == "all"
    player.toggle()
    run_until(lambda: player.playing and player.position >= 6.5, 15)
    again.close()


def test_volume_normalisation(player, demo):
    from nauta import loudness
    player.make_media = player._make_media
    player.connection.account.replay_gain = loudness.ALBUM
    player.play(album(demo)[:1])
    run_until(lambda: player.media is not None, 15)
    element = player.media.pipeline.props.audio_filter
    assert element.get_factory().get_name() == "rgvolume" and element.props.album_mode
    run_until(lambda: player.position > 0.3, 15)     # sound goes through it
    player.clear()
    player.connection.account.replay_gain = loudness.OFF
    player.play(album(demo)[:1])
    run_until(lambda: player.media is not None, 15)
    assert player.media.pipeline.props.audio_filter is None


def test_sleep_timer(player, demo):
    from nauta.sleep import END_OF_SONG, SleepTimer
    now = [100.0]
    timer = SleepTimer(player, clock=lambda: now[0])
    songs = album(demo)
    player.play(songs, 0)
    timer.start(15)
    now[0] += 60
    assert timer.active and timer.remaining() == 14 * 60
    timer._done()                       # the 15 minutes are over
    run_until(lambda: not player.playing, 5)
    assert not timer.active
    player.toggle()
    timer.start(END_OF_SONG)
    assert timer.remaining() is None
    player.next()
    run_until(lambda: not player.playing, 5)
    assert player.index == 1 and not timer.active
    timer.close()
