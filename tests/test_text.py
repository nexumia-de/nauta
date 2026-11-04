from nauta import text


def test_durations():
    assert text.duration(187) == "3:07"
    assert text.duration(3725) == "1:02:05"
    assert text.duration(None) == "0:00"
    assert text.total(2520) == "42 min"
    assert text.total(3900) == "1 h 05 min"


def test_album_details_and_counts():
    assert text.album_details({"year": 2024, "songCount": 9, "duration": 2520}) == \
        "2024 · 9 songs · 42 min"
    assert text.album_details({"song": [{}]}) == "1 song"
    assert text.albums(1) == "1 album" and text.albums(3) == "3 albums"


def test_song_subtitle():
    song = {"artist": "Juniper Vale", "album": "Northbound"}
    assert text.song_subtitle(song) == "Juniper Vale · Northbound"
    assert text.song_subtitle(song, with_album=False) == "Juniper Vale"
    assert text.song_subtitle({}) == "Unknown Artist"
