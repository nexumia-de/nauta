"""The notification shown while Nauta plays with its window closed
(docs/playback.md): swiping it away or its "Quit" button quits Nauta,
tapping it opens the window. Phosh's media widget can't be dismissed, so
this is the handle for ending background playback. Talks to the
notification server (org.freedesktop.Notifications) directly: the
portal does not say when a notification is swiped away."""
import logging

from gi.repository import Gio, GLib

from nauta import APP_ID, NAME

log = logging.getLogger("nauta.background")

SERVICE = "org.freedesktop.Notifications"
PATH = "/org/freedesktop/Notifications"
# NotificationClosed reasons: 1 expired, 2 dismissed by the user
# (Phosh: "Clear all"), 3 closed (Phosh: swiped away; also our own
# CloseNotification), 4 undefined.
EXPIRED = 1

SUMMARY = f"{NAME} plays in the background"
BODY = "Swipe away to quit, or tap to open."


class BackgroundNotice:
    """`open_window()` and `quit()` are the window's."""

    def __init__(self, open_window, quit, bus=None):
        self.open_window = open_window
        self.quit = quit
        self.bus = bus or Gio.bus_get_sync(Gio.BusType.SESSION, None)
        self._id = 0            # the notification on screen, 0 for none
        self._wanted = False    # shown, or a Notify call on its way
        self._subscriptions = [
            self.bus.signal_subscribe(SERVICE, SERVICE, name, PATH, None,
                                      Gio.DBusSignalFlags.NONE, callback)
            for name, callback in (("NotificationClosed", self._on_closed),
                                   ("ActionInvoked", self._on_action))]

    @property
    def shown(self):
        return self._wanted

    def show(self):
        if self._wanted:
            return
        self._wanted = True
        hints = {"desktop-entry": GLib.Variant("s", APP_ID),
                 # Stays after an action, no sound or vibration.
                 "resident": GLib.Variant("b", True),
                 "suppress-sound": GLib.Variant("b", True)}
        args = GLib.Variant("(susssasa{sv}i)", (
            NAME, 0, APP_ID, SUMMARY, BODY,
            # The server's own timeout (-1): Phosh's banner goes after
            # it, the notification stays in the list (not transient).
            ["default", "Open", "quit", "Quit"], hints, -1))
        self.bus.call(SERVICE, PATH, SERVICE, "Notify", args,
                      GLib.VariantType("(u)"), Gio.DBusCallFlags.NONE, 5000,
                      None, self._on_shown)

    def _on_shown(self, bus, result):
        try:
            notification = bus.call_finish(result).unpack()[0]
        except GLib.Error as e:
            log.info("no background notification: %s", e.message)
            self._wanted = False
            return
        if self._wanted:
            self._id = notification
        else:
            # Withdrawn while the call was on its way.
            self._close(notification)

    def withdraw(self):
        """The window is back or Nauta quits: remove it without quitting."""
        self._wanted = False
        if self._id:
            notification, self._id = self._id, 0
            self._close(notification)

    def _close(self, notification):
        self.bus.call(SERVICE, PATH, SERVICE, "CloseNotification",
                      GLib.Variant("(u)", (notification,)), None,
                      Gio.DBusCallFlags.NONE, 5000, None, None)

    def close(self):
        self.withdraw()
        for subscription in self._subscriptions:
            self.bus.signal_unsubscribe(subscription)
        self._subscriptions = []

    def _on_closed(self, connection, sender, path, interface, signal, params):
        notification, reason = params.unpack()
        if not notification or notification != self._id:
            return              # another one, or withdrawn by us
        self._id = 0
        self._wanted = False
        if reason != EXPIRED:
            # Swiped away or cleared: the user is done listening.
            self.quit()

    def _on_action(self, connection, sender, path, interface, signal, params):
        notification, action = params.unpack()
        if not notification or notification != self._id:
            return
        if action == "quit":
            self.quit()
        elif action == "default":
            self.open_window()
