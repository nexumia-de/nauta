"""Cover art: fetched through the connection, cached on disk and as
textures in memory (phosh_toolkit.images)."""
from phosh_toolkit.images import ImageCache

from nauta import settings


class Covers:
    def __init__(self, connection):
        self.connection = connection
        self._cache = ImageCache(settings.cache_dir() / "covers", connection.call)

    def load(self, cover_id, size, done):
        """done(texture or None) on the main loop. `size` in logical
        pixels; the server scales to twice that for HiDPI screens."""
        if not cover_id:
            done(None)
            return
        name = f"{cover_id}-{size}"
        self._cache.load(name, lambda: self.connection.api.cover(cover_id, size * 2),
                         done)
