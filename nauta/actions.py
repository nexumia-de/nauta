"""What can be done with a song, or with all songs of an album or a
playlist (docs/library.md): play next, add to the queue, like, add to a
playlist, radio, go to the album or artist. The menus are built when
they open, so "Like" or "Unlike" is current."""
from gi.repository import Gio, GLib, Gtk

from nauta import favourites, playlist_edit


def popup(anchor, menu, group):
    """A popover menu pointing at `anchor`, gone after it closes."""
    popover = Gtk.PopoverMenu.new_from_model(menu)
    popover.insert_action_group("item", group)
    popover.set_parent(anchor)
    popover.set_has_arrow(True)
    popover.connect("closed", lambda p: GLib.idle_add(_unparent, p))
    popover.popup()
    return popover


def _unparent(popover):
    if popover.get_parent() is not None:
        popover.unparent()
    return GLib.SOURCE_REMOVE


def _group(actions):
    """A Gio.SimpleActionGroup of name → callback."""
    group = Gio.SimpleActionGroup()
    for name, callback in actions.items():
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", lambda a, p, cb=callback: cb())
        group.add_action(action)
    return group


def start_radio(window, item_id, first=None):
    """Play songs like a song, album or artist; `first` (a song) leads."""
    conn = window.connection

    def done(songs, error):
        if error is not None:
            window.toast(f"Can't start the radio: {error}")
            return
        if first is not None:
            songs = [first] + [s for s in songs if s.get("id") != first.get("id")]
        if len(songs) <= (1 if first is not None else 0):
            window.toast("No similar songs. The server finds them with Last.fm "
                         "or another agent.")
            return
        window.player.play(songs)
        window.toast("Radio started")
    conn.call(conn.api.similar_songs, done, item_id)


class SongActions:
    """The menu and swipe of song rows in one list. `extras` are
    (label, callback(index)) for this list only (Remove from Playlist,
    Move Up…). `swipe` replaces the swipe's action: (icon, label,
    callback(song, index))."""

    def __init__(self, window, extras=(), swipe=None, show_queue=True):
        self.window = window
        self.extras = list(extras)
        self.swipe = swipe or ("list-add-symbolic", "Add to Queue",
                               lambda song, index: self.add_to_queue([song]))
        self.show_queue = show_queue

    # --- what the actions do --------------------------------------------

    def play_next(self, songs):
        self.window.player.play_next(songs)
        self.window.toast("Plays next" if len(songs) == 1 else
                          f"{len(songs)} songs play next")

    def add_to_queue(self, songs):
        self.window.player.add(songs)
        self.window.toast("Added to the queue" if len(songs) == 1 else
                          f"Added {len(songs)} songs to the queue")

    def toggle_like(self, kind, item):
        def done(error):
            if error is not None:
                self.window.toast(f"Can't save this: {error}")
        liked = self.window.favourites.toggle(kind, item, done)
        self.window.toast("Added to Liked Songs" if liked and kind == favourites.SONG
                          else "Liked" if liked
                          else "Removed from your likes")

    # --- menus ---------------------------------------------------------

    def song_menu(self, song, index):
        """(Gio.Menu, action group) for one song."""
        window = self.window
        actions, menu = {}, Gio.Menu()
        if self.show_queue:
            queue = Gio.Menu()
            queue.append("Play Next", "item.play-next")
            queue.append("Add to Queue", "item.add-to-queue")
            actions["play-next"] = lambda: self.play_next([song])
            actions["add-to-queue"] = lambda: self.add_to_queue([song])
            menu.append_section(None, queue)
        mine = Gio.Menu()
        liked = window.favourites.liked(song)
        mine.append("Remove from Liked Songs" if liked else "Add to Liked Songs",
                    "item.like")
        actions["like"] = lambda: self.toggle_like(favourites.SONG, song)
        mine.append("Add to Playlist…", "item.add-to-playlist")
        actions["add-to-playlist"] = lambda: playlist_edit.choose_playlist(
            window, [song])
        for n, (label, callback) in enumerate(self.extras):
            mine.append(label, f"item.extra-{n}")
            actions[f"extra-{n}"] = lambda cb=callback: cb(index)
        menu.append_section(None, mine)
        go = Gio.Menu()
        go.append("Song Radio", "item.radio")
        actions["radio"] = lambda: start_radio(window, song["id"], song)
        if song.get("albumId"):
            go.append("Go to Album", "item.album")
            actions["album"] = lambda: window.show_album(
                {"id": song["albumId"], "name": song.get("album")})
        if song.get("artistId"):
            go.append("Go to Artist", "item.artist")
            actions["artist"] = lambda: window.show_artist(
                {"id": song["artistId"], "name": song.get("artist")})
        menu.append_section(None, go)
        return menu, _group(actions)

    def open(self, anchor, song, index):
        return popup(anchor, *self.song_menu(song, index))

    def swiped(self, song, index):
        self.swipe[2](song, index)


def collection_menu(window, songs, kind=None, item=None, extras=()):
    """(Gio.Menu, group) for all songs of an album or a playlist: queue,
    add to a playlist, radio; liking the album (kind ALBUM); extras are
    (label, callback) (Rename, Delete…)."""
    helper = SongActions(window)
    actions, menu = {}, Gio.Menu()
    queue = Gio.Menu()
    queue.append("Play Next", "item.play-next")
    queue.append("Add to Queue", "item.add-to-queue")
    actions["play-next"] = lambda: helper.play_next(songs)
    actions["add-to-queue"] = lambda: helper.add_to_queue(songs)
    menu.append_section(None, queue)
    mine = Gio.Menu()
    mine.append("Add to Playlist…", "item.add-to-playlist")
    actions["add-to-playlist"] = lambda: playlist_edit.choose_playlist(window, songs)
    if item is not None and kind == favourites.ALBUM:
        mine.append("Radio", "item.radio")
        actions["radio"] = lambda: start_radio(window, item["id"])
    for n, (label, callback) in enumerate(extras):
        mine.append(label, f"item.extra-{n}")
        actions[f"extra-{n}"] = callback
    menu.append_section(None, mine)
    if item is not None and kind == favourites.ALBUM and item.get("artistId"):
        go = Gio.Menu()
        go.append("Go to Artist", "item.artist")
        actions["artist"] = lambda: window.show_artist(
            {"id": item["artistId"], "name": item.get("artist")})
        menu.append_section(None, go)
    return menu, _group(actions)


def menu_button(build, tooltip="More"):
    """A "⋮" button whose menu build() makes when it is clicked."""
    button = Gtk.Button(icon_name="view-more-symbolic", tooltip_text=tooltip,
                        valign=Gtk.Align.CENTER)
    button.add_css_class("flat")
    button.update_property([Gtk.AccessibleProperty.LABEL], [tooltip])
    button.connect("clicked", lambda b: popup(b, *build()))
    return button


def like_button(window, kind, item):
    """A heart toggle for a song, album or artist, kept current."""
    button = Gtk.Button(valign=Gtk.Align.CENTER)
    button.add_css_class("flat")
    button.add_css_class("circular")
    helper = SongActions(window)

    def update(*_):
        liked = window.favourites.liked(item)
        label = "Remove from Likes" if liked else "Like"
        button.set_icon_name("starred-symbolic" if liked else "non-starred-symbolic")
        button.set_tooltip_text(label)
        button.update_property([Gtk.AccessibleProperty.LABEL], [label])
        if liked:
            button.add_css_class("accent")
        else:
            button.remove_css_class("accent")
    handlers = [window.favourites.connect("changed", lambda f, i: i == item.get("id")
                                          and update()),
                window.favourites.connect("loaded", update)]
    button.connect("destroy", lambda b: [window.favourites.disconnect(h)
                                         for h in handlers])
    button.connect("clicked", lambda b: helper.toggle_like(kind, item))
    update()
    return button
