"""Shared fixtures: the demo Navidrome stand-in, optionally behind mutual
TLS with certificates made by openssl for each test session
(phosh_toolkit.testing)."""
import os
import sys
from pathlib import Path

import pytest

# The shared package from the sibling checkout (CI checks it out at the
# commit the Flatpak manifest pins and sets PYTHONPATH).
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "phosh-toolkit" / "lib"))
os.environ["NAUTA_KEYRING"] = "memory"

from gi.repository import Gio  # noqa: E402
from phosh_toolkit.testing import P12_PASSWORD, make_pki, run_until  # noqa: E402,F401

from nauta.demo import DemoMeTube, DemoServer, DemoYouTubeMusic  # noqa: E402

DEMO = Path(__file__).resolve().parent / "data" / "demo"


@pytest.fixture(autouse=True)
def xdg(tmp_path, monkeypatch):
    for name in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME"):
        monkeypatch.setenv(name, str(tmp_path / name.lower()))
    from nauta import keyring
    keyring.KEYRING.forget_memory()
    keyring.DOWNLOADS.forget_memory()


@pytest.fixture
def demo():
    server = DemoServer(DEMO).start()
    yield server
    server.stop()


@pytest.fixture(scope="session")
def pki(tmp_path_factory):
    return make_pki(tmp_path_factory.mktemp("pki"))


@pytest.fixture
def mtls_demo(pki):
    server = DemoServer(DEMO, tls=(pki / "server.pem", pki / "server.key",
                                   pki / "ca.pem")).start()
    yield server
    server.stop()


@pytest.fixture
def trust(pki):
    """A Gio.TlsDatabase that trusts the test CA."""
    return Gio.TlsFileDatabase.new(str(pki / "ca.pem"))


@pytest.fixture
def metube():
    server = DemoMeTube(DEMO).start()
    yield server
    server.stop()


@pytest.fixture
def mtls_metube(pki):
    server = DemoMeTube(DEMO, tls=(pki / "server.pem", pki / "server.key",
                                   pki / "ca.pem")).start()
    yield server
    server.stop()


@pytest.fixture
def youtube_music():
    server = DemoYouTubeMusic(DEMO).start()
    yield server
    server.stop()


# --- UI tests (need a display) ------------------------------------------

@pytest.fixture(scope="session")
def app():
    """One application for all UI tests: a second one with the same id
    can't register on the session bus."""
    from gi.repository import Adw, Gtk

    from nauta.main import Application
    application = Application()
    application.register(None)
    Adw.init()
    # No animations: a spinner redrawing all the time keeps GTK's frame
    # source ready on slow software rendering (CI's xvfb), and the idle
    # callbacks that deliver worker results then never run.
    Gtk.Settings.get_default().props.gtk_enable_animations = False
    yield application


@pytest.fixture
def quiet(monkeypatch):
    """No sound card in CI: a clocked fakesink instead."""
    import gi
    gi.require_version("Gst", "1.0")
    from gi.repository import Gst
    from phosh_toolkit.media import Media

    from nauta import player

    def media(url, video=False):
        m = Media(url, video=False)
        sink = Gst.ElementFactory.make("fakesink", None)
        sink.props.sync = True
        m.pipeline.props.audio_sink = sink
        return m
    monkeypatch.setattr(player, "Media", media)


def visible(window):
    return window.nav.get_visible_page()
