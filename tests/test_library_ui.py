"""Spotify-like features through the real widgets against the demo
server: the song menu and swipe, likes, playlists, the artist page,
album orders, the queue on Now Playing, the sleep timer and lyrics
(docs/library.md, docs/playback.md). Needs a display."""
import os

import pytest

from conftest import run_until as _run_until
from conftest import visible

if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
    pytest.skip("needs a display", allow_module_level=True)

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk  # noqa: E402
from phosh_toolkit import router  # noqa: E402

from nauta import connection, keyring, settings  # noqa: E402
from nauta.demo import PASSWORD  # noqa: E402

pytestmark = pytest.mark.usefixtures("quiet")


def run_until(predicate, timeout=10):
    """conftest.run_until, dumping every thread's stack on a timeout
    (diagnostics for a hang seen only in CI)."""
    try:
        _run_until(predicate, timeout)
    except TimeoutError:
        import gc
        import sys

        from gi.repository import GLib
        from phosh_toolkit.media import Media
        context = GLib.MainContext.default()
        busy = sum(bool(context.pending()) for _ in range(200)
                   if context.iteration(False) or True)
        alive = [m for m in gc.get_objects() if isinstance(m, Media)
                 and m.pipeline is not None]
        print(f"main context pending in {busy}/200 iterations; "
              f"pipelines alive: {[(m.pipeline.get_state(0)[1].value_nick, m.playing) for m in alive]}; "
              f"predicate after: {predicate()}", file=sys.stderr)
        raise

ALBUM = "al-195308cfb6d233b94d9b"       # Low Tide, liked in the demo
SONG = "tr-a4151fee60ea58667850"        # its first song, with lyrics


@pytest.fixture
def window(app, demo, monkeypatch):
    from nauta.window import Window
    monkeypatch.setattr(router.network, "current_ssids", lambda: None)
    store = settings.Store()
    account = store.load()
    account.remote_url, account.user_name = demo.url, "robin"
    store.save(account)
    keyring.store(keyring.PASSWORD, PASSWORD)
    win = Window(app, connection.Connection(store, watch=False))
    win.toasts_seen = []
    monkeypatch.setattr(win, "toast", win.toasts_seen.append)
    win.present()
    run_until(lambda: win.favourites.loaded, 10)
    yield win
    win.player.clear()
    win.sleep_timer.cancel()
    win.destroy()


def activate(group, name):
    group.activate_action(name, None)


def open_album(window):
    from nauta.pages import AlbumPage
    window.show_album({"id": ALBUM})
    page = visible(window)
    assert isinstance(page, AlbumPage)
    run_until(lambda: page.stack.get_visible_child_name() == "content")
    return page


def test_song_menu_queue_like_and_go_to(window, demo):
    page = open_album(window)
    songs = page.album["song"]
    first = page.list.get_row_at_index(0)
    assert first.more.get_tooltip_text() == "More"   # "⋮" on every row
    page.list.emit("row-activated", first)
    run_until(lambda: window.player.song is not None)

    menu, group = window_actions(window).song_menu(songs[2], 2)
    activate(group, "play-next")
    assert window.player.queue[1] is songs[2]
    assert window.toasts_seen[-1] == "Plays next"
    activate(group, "add-to-queue")
    assert window.player.queue[-1] is songs[2]

    # Like: the menu says what happens, and the server learns it.
    song = songs[5]
    assert song["id"] not in demo.starred
    menu, group = window_actions(window).song_menu(song, 5)
    assert "Add to Liked Songs" in all_labels(menu)
    activate(group, "like")
    run_until(lambda: song["id"] in demo.starred)
    assert window.toasts_seen[-1] == "Added to Liked Songs"
    menu, group = window_actions(window).song_menu(song, 5)
    texts = all_labels(menu)
    assert "Remove from Liked Songs" in texts and "Go to Artist" in texts
    activate(group, "artist")
    from nauta.artist import ArtistPage
    assert isinstance(visible(window), ArtistPage)


def window_actions(window):
    from nauta.actions import SongActions
    return SongActions(window)


def all_labels(menu):
    out = []
    for i in range(menu.get_n_items()):
        section = menu.get_item_link(i, "section") or menu.get_item_link(i, "submenu")
        if section is not None:
            out += all_labels(section)
        label = menu.get_item_attribute_value(i, "label", None)
        if label is not None:
            out.append(label.unpack())
    return out


def test_swipe_adds_to_the_queue(window):
    page = open_album(window)
    songs = page.album["song"]
    window.player.play(songs[:1])
    row = page.list.get_row_at_index(3)
    box = row.get_child()
    box.get_width = lambda: 300
    gesture = next(c for c in box.observe_controllers() if isinstance(c, Gtk.GestureDrag))
    # A mostly vertical drag (scrolling) is not a swipe.
    box._on_update(gesture, -40, 60)
    box._on_end(gesture, -40, 60)
    assert len(window.player.queue) == 1
    # Too short: springs back.
    box._on_update(gesture, -60, 2)
    box._on_end(gesture, -60, 2)
    assert box.offset == 0 and len(window.player.queue) == 1
    box._on_update(gesture, -150, 4)
    assert box.offset == -150
    box._on_end(gesture, -150, 4)
    assert window.player.queue[-1] is songs[3]
    assert window.toasts_seen[-1] == "Added to the queue"


def test_album_like_and_collection_menu(window, demo):
    page = open_album(window)
    assert page.like.get_icon_name() == "starred-symbolic"     # liked in the demo
    page.like.emit("clicked")
    run_until(lambda: ALBUM not in demo.starred)
    assert page.like.get_icon_name() == "non-starred-symbolic"
    from nauta.actions import collection_menu
    from nauta.favourites import ALBUM as KIND
    menu, group = collection_menu(window, page.album["song"], KIND, page.album)
    assert {"Play Next", "Add to Queue", "Add to Playlist…", "Radio",
            "Go to Artist"} <= set(all_labels(menu))
    activate(group, "add-to-queue")
    assert len(window.player.queue) == len(page.album["song"])
    activate(group, "radio")
    run_until(lambda: window.toasts_seen[-1] == "Radio started")
    assert all(s["albumId"] != ALBUM for s in window.player.queue)


def wait_for_list(dialog):
    """Until the "Add to Playlist" dialog shows its list (or an error,
    reported with its text)."""
    stack = dialog.get_child().get_content()
    run_until(lambda: stack.get_visible_child_name() != "loading", 30)
    page = stack.get_visible_child()
    assert stack.get_visible_child_name() == "list", \
        getattr(page, "get_description", lambda: "")()
    return stack


def test_playlists_new_add_rename_reorder_remove_delete(window, demo):
    from nauta import playlist_edit
    from nauta.pages import PlaylistPage
    songs = demo.library["songs"]
    # A new playlist with a song, from the song menu's dialog.
    dialog = playlist_edit.choose_playlist(window, [songs[0]])
    wait_for_list(dialog)
    dialog.close()
    made = []
    alert = playlist_edit.new_playlist(window, [songs[0]], made.append)
    alert.entry.set_text("Road Trip")
    alert.emit("response", "ok")
    run_until(lambda: made)
    playlist = made[0]
    assert window.toasts_seen[-1] == "Added to “Road Trip”"
    # Add two more through the dialog's list.
    dialog = playlist_edit.choose_playlist(window, songs[1:3])
    stack = wait_for_list(dialog)
    listbox = stack.get_visible_child().get_child().get_child().get_child()
    rows = []
    row = listbox.get_first_child()
    while row is not None:
        rows.append(row)
        row = row.get_next_sibling()
    road = next(r for r in rows if "Road Trip" in (r.get_title() or ""))
    road.emit("activated")
    run_until(lambda: len(demo._find_playlist(playlist["id"])["entries"]) == 3)

    window.show_playlist(playlist)
    page = visible(window)
    assert isinstance(page, PlaylistPage)
    run_until(lambda: page.stack.get_visible_child_name() == "content")
    assert page.editable
    page._move(0, 1)
    run_until(lambda: demo._find_playlist(playlist["id"])["entries"][:2]
              == [songs[1]["id"], songs[0]["id"]])
    run_until(lambda: page.stack.get_visible_child_name() == "content")
    page._remove(0)
    run_until(lambda: demo._find_playlist(playlist["id"])["entries"]
              == [songs[0]["id"], songs[2]["id"]])
    rename = playlist_edit.rename_playlist(window, page.playlist)
    rename.entry.set_text("Long Road")
    rename.emit("response", "ok")
    run_until(lambda: demo._find_playlist(playlist["id"])["name"] == "Long Road")
    gone = []
    confirm = playlist_edit.delete_playlist(window, page.playlist, lambda: gone.append(1))
    confirm.emit("response", "delete")
    run_until(lambda: gone)
    assert demo._find_playlist(playlist["id"]) is None


def test_liked_songs_page(window, demo):
    from nauta.liked import LikedPage
    window.show_view(2)
    playlists = window.main.views["playlists"]
    run_until(lambda: playlists.get_visible_child_name() == "content")
    playlists.top.get_row_at_index(0).emit("activated")
    page = visible(window)
    assert isinstance(page, LikedPage)
    run_until(lambda: page.stack.get_visible_child_name() == "content")
    liked_songs = [s for s in demo.library["songs"] if s["id"] in demo.starred]
    assert [s["id"] for s in page.songs] == [s["id"] for s in liked_songs]
    # Unliking reloads the page.
    window.favourites.set_liked("song", page.songs[0], False)
    run_until(lambda: page.stack.get_visible_child_name() == "content"
              and len(page.songs) == len(liked_songs) - 1)


def test_artist_page_popular_radio_and_similar(window):
    from nauta.artist import ArtistPage
    window.show_artist({"id": "ar-0cc9bd8a19dfe4c22d8f", "name": "Harbour Lights"})
    page = visible(window)
    assert isinstance(page, ArtistPage)
    run_until(lambda: page.stack.get_visible_child_name() == "content")
    assert len(page.top) == 5
    assert [a["name"] for a in page.similar] == ["The Copper Gulls", "Juniper Vale"]
    page.radio.emit("clicked")
    run_until(lambda: window.player.song is not None)
    assert window.player.song["artistId"] != "ar-0cc9bd8a19dfe4c22d8f"


def test_album_order_is_kept(window):
    main = window.main
    albums = main.views["albums"]
    run_until(lambda: albums.get_visible_child_name() == "content")
    main.sort_action.activate(main.sort_action.get_state().__class__("s", "starred"))
    run_until(lambda: albums.get_visible_child_name() == "content"
              and albums.store.get_n_items() == 2)
    assert settings.Store().load().album_sort == "starred"
    window.show_view(1)
    assert not main.sort_button.get_visible()


def test_now_playing_queue_repeat_shuffle_sleep_and_lyrics(window, demo):
    from nauta.lyrics import LyricsPage
    page = open_album(window)
    songs = page.album["song"]
    window.player.play(songs, 0)
    window.show_now_playing()
    now = visible(window)
    assert now.like.get_icon_name() == "starred-symbolic"
    assert now.queue.list.get_row_at_index(0).song is songs[1]
    # Remove the next song with its swipe (the queue's swipe removes).
    now.queue.actions.swiped(songs[1], 0)
    assert window.player.upcoming[0] is songs[2]
    run_until(lambda: now.queue.list.get_row_at_index(0).song is songs[2])
    now.queue._move(0, 1)
    assert window.player.upcoming[1] is songs[2]
    now.repeat.emit("clicked")
    assert window.player.repeat == "all" and now.repeat.has_css_class("accent")
    now.shuffle.set_active(True)
    assert window.player.shuffled
    now.queue.clear.emit("clicked")
    assert window.player.upcoming == [] and not now.queue.get_visible()

    menu, group = now._menu()
    assert "Sleep Timer" in all_labels(menu)
    activate(group, "sleep-30")
    assert window.sleep_timer.minutes == 30
    assert now.sleep_label.get_label() == "Pauses in 30 min"
    activate(group, "sleep-off")
    assert not now.sleep_label.get_visible()

    # Lyrics follow the song and mark the current line.
    run_until(lambda: window.player.playing and window.player.position > 0.2, 15)
    now.lyrics.emit("clicked")
    lyrics = visible(window)
    assert isinstance(lyrics, LyricsPage)
    run_until(lambda: lyrics.stack.get_visible_child_name() == "lyrics")
    run_until(lambda: lyrics.current == 0)
    assert lyrics.labels[0].has_css_class("accent")
    lyrics.list.emit("row-activated", lyrics.list.get_row_at_index(3))
    run_until(lambda: lyrics.current == 3, 10)
    window.player.add([songs[1]])      # no lyrics
    window.player.next()
    run_until(lambda: lyrics.stack.get_visible_child_name() == "status")


def test_lyrics_lines():
    from nauta.lyrics import best, current_line
    lines = [{"start": 0, "value": "a"}, {"start": 1000, "value": "b"},
             {"start": 2500, "value": "c"}]
    assert current_line(lines, 999) == 0 and current_line(lines, 2500) == 2
    assert current_line([{"start": 500, "value": "x"}], 100) == -1
    plain = {"synced": False, "line": [{"value": "x"}]}
    synced = {"synced": True, "line": lines}
    assert best([plain, synced]) is synced and best([plain]) is plain
    assert best([]) is None
