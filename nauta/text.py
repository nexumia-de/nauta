"""Texts shown for albums, songs and times. No GTK."""


def duration(seconds):
    """"3:07", "1:02:05"."""
    seconds = int(seconds or 0)
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def total(seconds):
    """"42 min", "1 h 05 min" for an album or playlist."""
    minutes = round((seconds or 0) / 60)
    if minutes >= 60:
        return f"{minutes // 60} h {minutes % 60:02d} min"
    return f"{minutes} min"


def songs(count):
    return "1 song" if count == 1 else f"{count or 0} songs"


def album_details(album):
    """"2024 · 9 songs · 42 min"."""
    parts = []
    if album.get("year"):
        parts.append(str(album["year"]))
    songs_ = album.get("songCount") or len(album.get("song") or [])
    parts.append(songs(songs_))
    if album.get("duration"):
        parts.append(total(album["duration"]))
    return " · ".join(parts)


def song_subtitle(song, with_album=True):
    """"Artist · Album" or just the artist."""
    parts = [song.get("artist") or "Unknown Artist"]
    if with_album and song.get("album"):
        parts.append(song["album"])
    return " · ".join(parts)


def albums(count):
    return "1 album" if count == 1 else f"{count or 0} albums"
