"""Likes, playlists, discovery and lyrics through the Subsonic client
against the demo server (docs/library.md, docs/subsonic-api.md)."""
from nauta.api import Subsonic
from nauta.demo import PASSWORD

SONG = "tr-a4151fee60ea58667850"      # Morning Swell, with synced lyrics


def api_for(demo):
    api = Subsonic()
    api.base_url, api.user, api.password = demo.url, "robin", PASSWORD
    return api


def test_star_and_unstar_send_repeated_ids(demo):
    api = api_for(demo)
    album = demo.library["albums"][5]["id"]
    api.star(song_ids=["tr-a", "tr-b"], album_ids=[album])
    form_pairs = demo.requests[-1][2]
    assert form_pairs["albumId"] == album
    assert {"tr-a", "tr-b", album} <= demo.starred
    liked = api.starred()
    assert album in {a["id"] for a in liked["album"]}
    assert all(s.get("starred") for s in liked["song"])
    api.star(album_ids=[album], starred=False)
    assert album not in demo.starred
    assert demo.requests[-1][1] == "/rest/unstar"


def test_playlists_are_made_changed_reordered_and_deleted(demo):
    api = api_for(demo)
    songs = [s["id"] for s in demo.library["songs"][:3]]
    made = api.create_playlist("Road Trip", songs[:2])
    assert made["name"] == "Road Trip" and [e["id"] for e in made["entry"]] == songs[:2]
    assert not made["readonly"]
    api.update_playlist(made["id"], name="Long Road", add=[songs[2]], remove=[0])
    changed = api.playlist(made["id"])
    assert changed["name"] == "Long Road"
    assert [e["id"] for e in changed["entry"]] == [songs[1], songs[2]]
    api.set_playlist_songs(made["id"], [songs[2], songs[1]])
    assert [e["id"] for e in api.playlist(made["id"])["entry"]] == [songs[2], songs[1]]
    api.delete_playlist(made["id"])
    assert made["id"] not in {p["id"] for p in api.playlists()}


def test_discovery(demo):
    api = api_for(demo)
    harbour = demo.library["artists"][0]
    similar = api.similar_songs(SONG)
    assert similar and all(s["artistId"] != harbour["id"] for s in similar)
    top = api.top_songs(harbour["name"], 3)
    assert len(top) == 3 and all(s["artistId"] == harbour["id"] for s in top)
    info = api.artist_info(harbour["id"])
    assert [a["name"] for a in info["similarArtist"]] == ["The Copper Gulls",
                                                          "Juniper Vale"]
    assert api.top_songs("Nobody Known") == []


def test_lyrics(demo):
    api = api_for(demo)
    lyrics = api.lyrics(SONG)
    assert lyrics[0]["synced"] and lyrics[0]["line"][1]["start"] == 2200
    assert api.lyrics(demo.library["songs"][1]["id"]) == []


def test_album_orders(demo):
    api = api_for(demo)
    liked = api.albums("starred")
    assert {a["id"] for a in liked} == {a for a in demo.starred
                                        if a.startswith("al-")}
    played = api.albums("frequent")
    counts = [a["playCount"] for a in played]
    assert counts == sorted(counts, reverse=True)
    assert len(api.albums("random", size=4)) == 4
