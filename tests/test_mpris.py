"""The MPRIS interface on a private session bus, driven like Phosh's lock
screen does: properties, PlayPause, Next, Seek, Raise and Quit."""
import shutil
import subprocess

import pytest
from gi.repository import Gio, GLib
from phosh_toolkit import router
from phosh_toolkit.media import Media, init
from phosh_toolkit.proxy import MediaProxy

from conftest import run_until
from nauta import connection, mpris, settings
from nauta.demo import PASSWORD
from nauta.images import Covers
from nauta.player import Player

gi = pytest.importorskip("gi")
gi.require_version("Gst", "1.0")
from gi.repository import Gst  # noqa: E402

init()
pytestmark = pytest.mark.skipif(
    Gst.ElementFactory.find("wavparse") is None or not shutil.which("dbus-daemon"),
    reason="needs GStreamer's wavparse and dbus-daemon")


def media(url):
    m = Media(url, video=False)
    sink = Gst.ElementFactory.make("fakesink", None)
    sink.props.sync = True
    m.pipeline.props.audio_sink = sink
    return m


def _connect(address):
    return Gio.DBusConnection.new_for_address_sync(
        address, Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT
        | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION, None, None)


@pytest.fixture
def buses():
    """A private session bus with two connections: Nauta's and the lock
    screen's."""
    daemon = subprocess.Popen(["dbus-daemon", "--session", "--nofork",
                               "--print-address=1"],
                              stdout=subprocess.PIPE, text=True)
    address = daemon.stdout.readline().strip()
    service, client = (_connect(address) for _ in range(2))
    yield service, client
    for c in (service, client):
        c.close_sync(None)
    daemon.terminate()
    daemon.wait(10)


@pytest.fixture
def setup(demo, buses, monkeypatch):
    bus, client = buses
    monkeypatch.setattr(router.network, "current_ssids", lambda: None)
    store = settings.Store()
    account = store.load()
    account.remote_url, account.user_name = demo.url, "robin"
    store.save(account)
    conn = connection.Connection(store, watch=False)
    conn.api.user, conn.api.password = "robin", PASSWORD
    proxy = MediaProxy(conn.forward)
    player = Player(conn, proxy, make_media=media)
    calls = []
    exported = mpris.Mpris(player, Covers(conn), lambda: calls.append("raise"),
                           lambda: calls.append("quit"), bus=bus,
                           name="org.mpris.MediaPlayer2.NautaTest")
    yield player, client, calls
    exported.close()
    player.clear()
    proxy.stop()


def call(bus, interface, method, args=None):
    """Asynchronously, as the service answers on this main loop."""
    out = []
    bus.call("org.mpris.MediaPlayer2.NautaTest", mpris.PATH, interface, method,
             args, None, Gio.DBusCallFlags.NONE, 5000, None,
             lambda b, result: out.append(b.call_finish(result)))
    run_until(lambda: out)
    return out[0]


def prop(bus, name, interface=mpris.PLAYER):
    result = call(bus, "org.freedesktop.DBus.Properties", "Get",
                  GLib.Variant("(ss)", (interface, name)))
    return result.unpack()[0]


def test_lock_screen_controls(setup, demo):
    player, bus, calls = setup
    assert prop(bus, "PlaybackStatus") == "Stopped"
    assert prop(bus, "Identity", mpris.ROOT) == "Nauta"
    changes = []
    bus.signal_subscribe(None, "org.freedesktop.DBus.Properties", "PropertiesChanged",
                         mpris.PATH, None, Gio.DBusSignalFlags.NONE,
                         lambda *a: changes.append(a[5].unpack()[1]))
    album = demo.library["albums"][0]["id"]
    songs = [s for s in demo.library["songs"] if s["albumId"] == album]
    player.play(songs)
    run_until(lambda: player.position > 0.2, 15)
    meta = prop(bus, "Metadata")
    assert meta["xesam:title"] == songs[0]["title"]
    assert meta["xesam:artist"] == [songs[0]["artist"]]
    assert meta["mpris:trackid"] == mpris.track_id(songs[0])
    assert prop(bus, "PlaybackStatus") == "Playing" and prop(bus, "CanGoNext")
    # The cover arrives as a local file, never a server URL.
    run_until(lambda: "mpris:artUrl" in prop(bus, "Metadata"), 10)
    assert prop(bus, "Metadata")["mpris:artUrl"].startswith("file:///")
    run_until(lambda: any("PlaybackStatus" in c for c in changes))

    call(bus, mpris.PLAYER, "PlayPause")
    run_until(lambda: not player.playing, 5)
    assert prop(bus, "PlaybackStatus") == "Paused"
    call(bus, mpris.PLAYER, "Play")
    run_until(lambda: player.playing, 5)
    call(bus, mpris.PLAYER, "Seek", GLib.Variant("(x)", (5_000_000,)))
    assert player.position >= 5
    call(bus, mpris.PLAYER, "Next")
    assert player.index == 1
    assert prop(bus, "Metadata")["xesam:title"] == songs[1]["title"]
    call(bus, mpris.ROOT, "Raise")
    call(bus, mpris.ROOT, "Quit")
    assert calls == ["raise", "quit"]


def test_track_ids_are_object_paths():
    assert mpris.track_id({"id": "tr-ab/c:d"}) == "/de/nexumia/Nauta/Track/tr_ab_c_d"
    assert GLib.Variant.is_object_path(mpris.track_id({"id": "a"}))
