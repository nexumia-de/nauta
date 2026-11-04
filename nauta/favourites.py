"""What the user liked (starred) on the server: songs, albums and artists
(docs/library.md). Loaded once with getStarred2, kept current when Nauta
likes or unlikes something. No widgets."""
import logging

from gi.repository import GObject

log = logging.getLogger("nauta.favourites")

SONG, ALBUM, ARTIST = "song", "album", "artist"


class Favourites(GObject.Object):
    """Signals: "changed" (item id) when one item is liked or unliked (at
    once, and again if the server refuses), "saved" (item id) once the
    server has it, "loaded" when the list came from the server."""
    __gsignals__ = {
        "changed": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "saved": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "loaded": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self, connection):
        super().__init__()
        self.connection = connection
        self.ids = set()
        self.loaded = False

    def load(self, done=None):
        def answer(found, error):
            if error is None:
                self.ids = {item["id"] for kind in (SONG, ALBUM, ARTIST)
                            for item in found[kind]}
                self.loaded = True
                self.emit("loaded")
            else:
                log.info("liked items: %s", error)
            if done:
                done(found, error)
        self.connection.call(self.connection.api.starred, answer)

    def liked(self, item):
        """Whether a song, album or artist dict is liked."""
        if self.loaded:
            return item.get("id") in self.ids
        return bool(item.get("starred")) or item.get("id") in self.ids

    def set_liked(self, kind, item, liked, done=None):
        """Like or unlike; changes at once and back on an error.
        done(error)."""
        item_id = item["id"]
        before = item_id in self.ids
        (self.ids.add if liked else self.ids.discard)(item_id)
        self.emit("changed", item_id)
        ids = {SONG: "song_ids", ALBUM: "album_ids", ARTIST: "artist_ids"}[kind]

        def answer(result, error):
            if error is not None:
                (self.ids.add if before else self.ids.discard)(item_id)
                self.emit("changed", item_id)
            else:
                self.emit("saved", item_id)
            if done:
                done(error)
        api = self.connection.api
        self.connection.call(
            lambda: api.star(**{ids: [item_id], "starred": liked}), answer)

    def toggle(self, kind, item, done=None):
        liked = not self.liked(item)
        self.set_liked(kind, item, liked, done)
        return liked
