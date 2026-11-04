"""Media controls for Phosh's lock screen and quick settings: the MPRIS
D-Bus interface (org.mpris.MediaPlayer2 and .Player) on the session bus,
driven by the Player (docs/playback.md). The Flatpak may own the name
(--own-name in the manifest)."""
import logging

from gi.repository import Gio, GLib

from nauta import APP_ID, NAME, NIGHTLY

log = logging.getLogger("nauta.mpris")

BUS_NAME = "org.mpris.MediaPlayer2.Nauta" + (".Devel" if NIGHTLY else "")
PATH = "/org/mpris/MediaPlayer2"
ROOT = "org.mpris.MediaPlayer2"
PLAYER = "org.mpris.MediaPlayer2.Player"
NO_TRACK = "/org/mpris/MediaPlayer2/TrackList/NoTrack"
COVER_SIZE = 300

XML = """
<node>
  <interface name="org.mpris.MediaPlayer2">
    <method name="Raise"/>
    <method name="Quit"/>
    <property name="CanQuit" type="b" access="read"/>
    <property name="CanRaise" type="b" access="read"/>
    <property name="HasTrackList" type="b" access="read"/>
    <property name="Identity" type="s" access="read"/>
    <property name="DesktopEntry" type="s" access="read"/>
    <property name="SupportedUriSchemes" type="as" access="read"/>
    <property name="SupportedMimeTypes" type="as" access="read"/>
  </interface>
  <interface name="org.mpris.MediaPlayer2.Player">
    <method name="Next"/>
    <method name="Previous"/>
    <method name="Pause"/>
    <method name="PlayPause"/>
    <method name="Stop"/>
    <method name="Play"/>
    <method name="Seek"><arg direction="in" name="Offset" type="x"/></method>
    <method name="SetPosition">
      <arg direction="in" name="TrackId" type="o"/>
      <arg direction="in" name="Position" type="x"/>
    </method>
    <method name="OpenUri"><arg direction="in" name="Uri" type="s"/></method>
    <signal name="Seeked"><arg name="Position" type="x"/></signal>
    <property name="PlaybackStatus" type="s" access="read"/>
    <property name="Rate" type="d" access="readwrite"/>
    <property name="Metadata" type="a{sv}" access="read"/>
    <property name="Volume" type="d" access="readwrite"/>
    <property name="Position" type="x" access="read"/>
    <property name="MinimumRate" type="d" access="read"/>
    <property name="MaximumRate" type="d" access="read"/>
    <property name="CanGoNext" type="b" access="read"/>
    <property name="CanGoPrevious" type="b" access="read"/>
    <property name="CanPlay" type="b" access="read"/>
    <property name="CanPause" type="b" access="read"/>
    <property name="CanSeek" type="b" access="read"/>
    <property name="CanControl" type="b" access="read"/>
  </interface>
</node>
"""

# Properties whose changes are announced (Position is read on demand).
WATCHED = ("PlaybackStatus", "Metadata", "CanGoNext", "CanGoPrevious",
           "CanPlay", "CanPause", "CanSeek")


def track_id(song):
    """A D-Bus object path for a song (ids may contain any character)."""
    safe = "".join(c if c.isalnum() else "_" for c in song.get("id", ""))
    return f"/de/nexumia/Nauta/Track/{safe or 'none'}"


class Mpris:
    """Exports the player. `raise_window()` and `quit()` are the
    application's; `covers` is nauta.images.Covers (for mpris:artUrl as a
    local file, never a server URL)."""

    def __init__(self, player, covers, raise_window, quit, bus=None,
                 name=BUS_NAME):
        self.player = player
        self.covers = covers
        self.raise_window = raise_window
        self.quit = quit
        self.name = name
        self._art = {}           # cover id -> file:// URI
        self._last = {}
        self._registrations = []
        self._owner = 0
        self.bus = bus or Gio.bus_get_sync(Gio.BusType.SESSION, None)
        info = Gio.DBusNodeInfo.new_for_xml(XML)
        for interface in info.interfaces:
            self._registrations.append(self.bus.register_object(
                PATH, interface, self._on_call, self._on_get, self._on_set))
        self._owner = Gio.bus_own_name_on_connection(
            self.bus, name, Gio.BusNameOwnerFlags.NONE, None, None)
        self._handlers = [player.connect("song-changed", self._on_song),
                          player.connect("state-changed", self._changed)]
        self._last = self._snapshot()

    def close(self):
        for handler in self._handlers:
            self.player.disconnect(handler)
        self._handlers = []
        if self._owner:
            Gio.bus_unown_name(self._owner)
            self._owner = 0
        for registration in self._registrations:
            self.bus.unregister_object(registration)
        self._registrations = []

    # --- state -------------------------------------------------------

    def status(self):
        if self.player.playing:
            return "Playing"
        return "Paused" if self.player.media is not None else "Stopped"

    def metadata(self):
        song = self.player.song
        if song is None:
            return {"mpris:trackid": GLib.Variant("o", NO_TRACK)}
        data = {
            "mpris:trackid": GLib.Variant("o", track_id(song)),
            "mpris:length": GLib.Variant("x", int(self.player.duration * 1_000_000)),
            "xesam:title": GLib.Variant("s", song.get("title") or ""),
            "xesam:artist": GLib.Variant("as", [song.get("artist") or ""]),
            "xesam:album": GLib.Variant("s", song.get("album") or ""),
        }
        if song.get("track"):
            data["xesam:trackNumber"] = GLib.Variant("i", int(song["track"]))
        art = self._art.get(song.get("coverArt"))
        if art:
            data["mpris:artUrl"] = GLib.Variant("s", art)
        return data

    def _properties(self):
        player = self.player
        has = player.song is not None
        return {
            ROOT: {
                "CanQuit": GLib.Variant("b", True),
                "CanRaise": GLib.Variant("b", True),
                "HasTrackList": GLib.Variant("b", False),
                "Identity": GLib.Variant("s", NAME),
                "DesktopEntry": GLib.Variant("s", APP_ID),
                "SupportedUriSchemes": GLib.Variant("as", []),
                "SupportedMimeTypes": GLib.Variant("as", []),
            },
            PLAYER: {
                "PlaybackStatus": GLib.Variant("s", self.status()),
                "Rate": GLib.Variant("d", 1.0),
                "Metadata": GLib.Variant("a{sv}", self.metadata()),
                "Volume": GLib.Variant("d", 1.0),
                "Position": GLib.Variant("x", int(player.position * 1_000_000)),
                "MinimumRate": GLib.Variant("d", 1.0),
                "MaximumRate": GLib.Variant("d", 1.0),
                "CanGoNext": GLib.Variant("b", player.index + 1 < len(player.queue)),
                "CanGoPrevious": GLib.Variant("b", has),
                "CanPlay": GLib.Variant("b", has),
                "CanPause": GLib.Variant("b", has),
                "CanSeek": GLib.Variant("b", bool(player.media and player.media.is_seekable())),
                "CanControl": GLib.Variant("b", True),
            },
        }

    def _snapshot(self):
        props = self._properties()[PLAYER]
        return {name: props[name] for name in WATCHED}

    def _changed(self, *_):
        now = self._snapshot()
        changed = {k: v for k, v in now.items() if self._last.get(k) != v}
        self._last = now
        if changed:
            self.bus.emit_signal(
                None, PATH, "org.freedesktop.DBus.Properties", "PropertiesChanged",
                GLib.Variant("(sa{sv}as)", (PLAYER, changed, [])))

    def _on_song(self, player):
        song = player.song
        cover = (song or {}).get("coverArt")
        if cover and cover not in self._art:
            def loaded(texture, cover=cover):
                if texture is None:
                    return
                path = self.covers.path(cover, COVER_SIZE)
                if path.exists():
                    self._art[cover] = path.as_uri()
                    self._changed()
            self.covers.load(cover, COVER_SIZE, loaded)
        self._changed()

    # --- D-Bus -------------------------------------------------------

    def _on_get(self, connection, sender, path, interface, name):
        return self._properties().get(interface, {}).get(name)

    def _on_set(self, connection, sender, path, interface, name, value):
        return True     # Rate and Volume are fixed

    def _on_call(self, connection, sender, path, interface, method, params,
                 invocation):
        player = self.player
        if method == "Raise":
            self.raise_window()
        elif method == "Quit":
            self.quit()
        elif method == "Next":
            player.next()
        elif method == "Previous":
            player.previous()
        elif method == "Pause":
            if player.playing:
                player.toggle()
        elif method == "Play":
            if not player.playing:
                player.toggle()
        elif method == "PlayPause":
            player.toggle()
        elif method == "Stop":
            player.stop()
        elif method == "Seek":
            offset = params.unpack()[0]
            target = player.position + offset / 1_000_000
            if target >= player.duration > 0:
                player.next()
            else:
                player.seek(max(0, target))
                self._seeked()
        elif method == "SetPosition":
            track, position = params.unpack()
            song = player.song
            if song is not None and track == track_id(song) and \
                    0 <= position / 1_000_000 <= player.duration:
                player.seek(position / 1_000_000)
                self._seeked()
        invocation.return_value(None)

    def _seeked(self):
        self.bus.emit_signal(None, PATH, PLAYER, "Seeked",
                             GLib.Variant("(x)", (int(self.player.position * 1_000_000),)))
