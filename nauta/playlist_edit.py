"""Dialogs that change playlists (docs/library.md): add songs to one (or
to a new one), rename, delete, save a new order. Afterwards
window.playlists_changed() reloads the Playlists view."""
from gi.repository import Adw, Gtk

from nauta import text, widgets


def editable(window, playlist):
    """Whether the user may change a playlist: not a smart playlist
    (OpenSubsonic "readonly") and their own."""
    owner = playlist.get("owner")
    return not playlist.get("readonly") and \
        (not owner or owner == window.connection.account.user_name)


def choose_playlist(window, songs):
    """A dialog listing the user's playlists; tapping one adds the songs."""
    dialog = Adw.Dialog(title="Add to Playlist", content_width=420,
                        content_height=520)
    stack = Gtk.Stack()
    stack.add_named(widgets.loading_page(), "loading")
    view = Adw.ToolbarView(content=stack)
    view.add_top_bar(Adw.HeaderBar())
    dialog.set_child(view)
    conn = window.connection

    def add_to(playlist):
        dialog.close()
        ids = [s["id"] for s in songs]

        def done(result, error):
            if error is not None:
                window.toast(f"Can't add to “{playlist.get('name')}”: {error}")
                return
            window.toast(f"Added to “{playlist.get('name')}”")
            window.playlists_changed()
        conn.call(lambda: conn.api.update_playlist(playlist["id"], add=ids), done)

    def loaded(playlists, error):
        if error is not None:
            stack.add_named(widgets.error_page(
                "Can't Load Playlists", str(error), lambda: (
                    stack.set_visible_child_name("loading"),
                    conn.call(conn.api.playlists, loaded))), "error")
            stack.set_visible_child_name("error")
            return
        box = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        box.add_css_class("boxed-list")
        new = Adw.ButtonRow(title="New Playlist…", start_icon_name="list-add-symbolic") \
            if hasattr(Adw, "ButtonRow") else widgets.nav_row("New Playlist…",
                                                              icon="list-add-symbolic")
        new.connect("activated", lambda r: (dialog.close(),
                                            new_playlist(window, songs)))
        box.append(new)
        for playlist in playlists:
            if not editable(window, playlist):
                continue
            row = widgets.nav_row(playlist.get("name"),
                                  text.songs(playlist.get("songCount")),
                                  covers=window.covers,
                                  cover_id=playlist.get("coverArt"),
                                  icon="view-list-bullet-symbolic")
            row.connect("activated", lambda r, p=playlist: add_to(p))
            box.append(row)
        body = Adw.Clamp(child=box, margin_top=12, margin_bottom=12,
                         margin_start=12, margin_end=12)
        stack.add_named(Gtk.ScrolledWindow(
            child=body, hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True),
            "list")
        stack.set_visible_child_name("list")
    conn.call(conn.api.playlists, loaded)
    dialog.present(window)
    return dialog


def _name_dialog(window, heading, response_label, name, on_name):
    """An alert dialog asking for a playlist name."""
    dialog = Adw.AlertDialog(heading=heading)
    entry = Gtk.Entry(text=name, activates_default=True,
                      placeholder_text="Playlist name")
    entry.update_property([Gtk.AccessibleProperty.LABEL], ["Playlist name"])
    dialog.set_extra_child(entry)
    dialog.add_response("cancel", "Cancel")
    dialog.add_response("ok", response_label)
    dialog.set_response_appearance("ok", Adw.ResponseAppearance.SUGGESTED)
    dialog.set_default_response("ok")
    dialog.set_close_response("cancel")

    def changed(*_):
        dialog.set_response_enabled("ok", bool(entry.get_text().strip()))
    entry.connect("changed", changed)
    changed()
    dialog.connect("response", lambda d, r: r == "ok" and on_name(
        entry.get_text().strip()))
    dialog.present(window)
    entry.grab_focus()
    dialog.entry = entry
    return dialog


def new_playlist(window, songs=(), done=None):
    """Ask for a name and make a playlist with `songs`."""
    conn = window.connection
    ids = [s["id"] for s in songs]

    def make(name):
        def answer(playlist, error):
            if error is not None:
                window.toast(f"Can't make the playlist: {error}")
                return
            window.toast(f"Added to “{name}”" if ids else f"Made “{name}”")
            window.playlists_changed()
            if done:
                done(playlist)
        conn.call(lambda: conn.api.create_playlist(name, ids), answer)
    return _name_dialog(window, "New Playlist", "Create", "", make)


def rename_playlist(window, playlist, done=None):
    conn = window.connection

    def rename(name):
        def answer(result, error):
            if error is not None:
                window.toast(f"Can't rename the playlist: {error}")
                return
            window.playlists_changed()
            if done:
                done(name)
        conn.call(lambda: conn.api.update_playlist(playlist["id"], name=name), answer)
    return _name_dialog(window, "Rename Playlist", "Rename",
                        playlist.get("name") or "", rename)


def delete_playlist(window, playlist, done=None):
    """Ask, then delete."""
    conn = window.connection
    dialog = Adw.AlertDialog(
        heading="Delete Playlist?",
        body=f"“{playlist.get('name')}” is deleted on the server. The songs "
             "stay in the library.")
    dialog.add_response("cancel", "Cancel")
    dialog.add_response("delete", "Delete")
    dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
    dialog.set_close_response("cancel")

    def answer(result, error):
        if error is not None:
            window.toast(f"Can't delete the playlist: {error}")
            return
        window.toast(f"Deleted “{playlist.get('name')}”")
        window.playlists_changed()
        if done:
            done()
    dialog.connect("response", lambda d, r: r == "delete" and conn.call(
        lambda: conn.api.delete_playlist(playlist["id"]), answer))
    dialog.present(window)
    return dialog


def save_order(window, playlist, songs, done=None):
    """Save a playlist's songs in a new order."""
    conn = window.connection
    ids = [s["id"] for s in songs]

    def answer(result, error):
        if error is not None:
            window.toast(f"Can't save the order: {error}")
        elif done:
            done()
    conn.call(lambda: conn.api.set_playlist_songs(playlist["id"], ids), answer)
