"""The background notification on a private session bus, against a
stand-in notification server that answers and signals like Phosh's:
swiped away (reason 3) or "Clear all" (2) quits, Quit quits, tapping
opens, withdrawing does not quit."""
import shutil
import subprocess

import pytest
from conftest import run_until
from gi.repository import Gio, GLib

from nauta import background

pytestmark = pytest.mark.skipif(not shutil.which("dbus-daemon"),
                                reason="needs dbus-daemon")

XML = """
<node>
  <interface name="org.freedesktop.Notifications">
    <method name="Notify">
      <arg direction="in" type="s"/><arg direction="in" type="u"/>
      <arg direction="in" type="s"/><arg direction="in" type="s"/>
      <arg direction="in" type="s"/><arg direction="in" type="as"/>
      <arg direction="in" type="a{sv}"/><arg direction="in" type="i"/>
      <arg direction="out" type="u"/>
    </method>
    <method name="CloseNotification"><arg direction="in" type="u"/></method>
    <signal name="NotificationClosed"><arg type="u"/><arg type="u"/></signal>
    <signal name="ActionInvoked"><arg type="u"/><arg type="s"/></signal>
  </interface>
</node>
"""


def _connect(address):
    return Gio.DBusConnection.new_for_address_sync(
        address, Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT
        | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION, None, None)


class FakeServer:
    """Records notifications; `swipe`, `clear_all` and `invoke` act like
    the user in Phosh."""

    def __init__(self, bus):
        self.bus = bus
        self.shown = {}         # id -> (summary, actions, hints, timeout)
        self.closed = []
        self._next = 1
        info = Gio.DBusNodeInfo.new_for_xml(XML)
        self._registration = bus.register_object(
            background.PATH, info.interfaces[0], self._on_call, None, None)
        self._owned = []
        self._owner = Gio.bus_own_name_on_connection(
            bus, background.SERVICE, Gio.BusNameOwnerFlags.NONE,
            lambda *a: self._owned.append(1), None)
        run_until(lambda: self._owned)

    def _on_call(self, connection, sender, path, interface, method, params,
                 invocation):
        if method == "Notify":
            _, replaces, _, summary, _, actions, hints, timeout = params.unpack()
            nid = replaces or self._next
            self._next += 1
            self.shown[nid] = (summary, actions, hints, timeout)
            invocation.return_value(GLib.Variant("(u)", (nid,)))
        else:
            nid = params.unpack()[0]
            self.closed.append(nid)
            self.shown.pop(nid, None)
            invocation.return_value(None)
            self._emit("NotificationClosed", "(uu)", (nid, 3))

    def _emit(self, name, signature, values):
        self.bus.emit_signal(None, background.PATH, background.SERVICE, name,
                             GLib.Variant(signature, values))

    def swipe(self, nid, reason=3):
        self.shown.pop(nid)
        self._emit("NotificationClosed", "(uu)", (nid, reason))

    def invoke(self, nid, action):
        self._emit("ActionInvoked", "(us)", (nid, action))

    def stop(self):
        Gio.bus_unown_name(self._owner)
        self.bus.unregister_object(self._registration)


@pytest.fixture
def setup():
    daemon = subprocess.Popen(["dbus-daemon", "--session", "--nofork",
                               "--print-address=1"],
                              stdout=subprocess.PIPE, text=True)
    address = daemon.stdout.readline().strip()
    app_bus, server_bus = (_connect(address) for _ in range(2))
    server = FakeServer(server_bus)
    calls = []
    notice = background.BackgroundNotice(lambda: calls.append("open"),
                                         lambda: calls.append("quit"),
                                         bus=app_bus)
    yield notice, server, calls
    notice.close()
    server.stop()
    for c in (app_bus, server_bus):
        c.close_sync(None)
    daemon.terminate()
    daemon.wait(10)


def shown(notice, server):
    notice.show()
    run_until(lambda: notice._id and server.shown)
    return notice._id


def test_swiping_it_away_quits(setup):
    notice, server, calls = setup
    nid = shown(notice, server)
    summary, actions, hints, timeout = server.shown[nid]
    assert summary == background.SUMMARY
    assert actions == ["default", "Open", "quit", "Quit"]
    assert hints["desktop-entry"] == "de.nexumia.Nauta" and hints["resident"]
    # Phosh's banner goes after its own timeout; the entry stays.
    assert timeout == -1
    notice.show()                       # once only
    server.swipe(nid)
    run_until(lambda: calls)
    assert calls == ["quit"] and not notice.shown


def test_clear_all_quits_and_expiry_does_not(setup):
    notice, server, calls = setup
    server.swipe(shown(notice, server), reason=1)
    run_until(lambda: not notice.shown)
    assert calls == []
    server.swipe(shown(notice, server), reason=2)
    run_until(lambda: calls)
    assert calls == ["quit"]


def test_actions_open_and_quit(setup):
    notice, server, calls = setup
    nid = shown(notice, server)
    server.invoke(nid, "default")
    run_until(lambda: calls)
    server.invoke(nid, "quit")
    run_until(lambda: len(calls) == 2)
    assert calls == ["open", "quit"]
    server.invoke(nid + 1, "quit")      # not ours
    GLib.MainContext.default().iteration(False)
    assert len(calls) == 2


def test_withdrawing_does_not_quit(setup):
    notice, server, calls = setup
    nid = shown(notice, server)
    notice.withdraw()
    run_until(lambda: server.closed == [nid])
    # The server's NotificationClosed for our own close is ignored.
    ctx = GLib.MainContext.default()
    for _ in range(50):
        ctx.iteration(False)
    assert calls == [] and not server.shown
    # Withdrawn while Notify is still on its way: closed on arrival.
    notice.show()
    notice.withdraw()
    run_until(lambda: len(server.closed) == 2)
    assert calls == [] and not server.shown
