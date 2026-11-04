"""Cover art, album cards and song rows; spinner, loading and error pages
come from phosh_toolkit."""
from gi.repository import Adw, GLib, GObject, Gtk, Pango
from phosh_toolkit.widgets import (Ratio, error_page, loading_page,  # noqa: F401
                                   spinner)

from nauta import text

CARD_WIDTH = 150    # two columns at 360 px


class Entry(GObject.Object):
    """An album, artist, playlist or song (its JSON dict) in a
    Gio.ListStore."""

    def __init__(self, data):
        super().__init__()
        self.data = data


def escape(value):
    return GLib.markup_escape_text(str(value or ""))


class Cover(Gtk.Overlay):
    """Square cover art with a placeholder icon until it loads. With
    `size` it has that fixed size; without, it fills its width."""

    def __init__(self, size=0, natural_width=0, max_height=0,
                 icon="folder-music-symbolic"):
        super().__init__()
        self.size = size
        self.picture = Gtk.Picture(content_fit=Gtk.ContentFit.COVER,
                                   can_shrink=True)
        self.placeholder = Gtk.Image(icon_name=icon, opacity=0.4,
                                     pixel_size=max(16, (size or 96) // 2))
        box = Gtk.Overlay(overflow=Gtk.Overflow.HIDDEN)
        box.add_css_class("nauta-cover")
        box.set_child(self.picture)
        box.add_overlay(self.placeholder)
        if size:
            box.set_size_request(size, size)
            box.set_valign(Gtk.Align.CENTER)
            self.set_child(box)
        else:
            self.set_child(Ratio(1, box, natural_width, max_height))
        self._key = None

    def show(self, covers, cover_id, size=None, icon=None):
        if icon:
            self.placeholder.set_from_icon_name(icon)
        self.placeholder.set_visible(True)
        self.picture.set_paintable(None)
        self._key = cover_id
        if not cover_id:
            return

        def done(texture, key=cover_id):
            if texture is not None and key == self._key:
                self.picture.set_paintable(texture)
                self.placeholder.set_visible(False)
        covers.load(cover_id, size or self.size or CARD_WIDTH, done)


class AlbumCard(Gtk.Box):
    """Cover with title and artist, for album grids."""

    def __init__(self, covers):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.covers = covers
        self.set_size_request(CARD_WIDTH, -1)
        self.cover = Cover(natural_width=CARD_WIDTH)
        self.append(self.cover)
        self.title = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END,
                               max_width_chars=1, hexpand=True)
        self.title.add_css_class("heading")
        self.subtitle = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END,
                                  max_width_chars=1)
        self.subtitle.add_css_class("caption")
        self.subtitle.add_css_class("dimmed")
        self.subtitle.add_css_class("dim-label")   # libadwaita < 1.7
        self.append(self.title)
        self.append(self.subtitle)

    def set_album(self, album, subtitle=None):
        self.album = album
        self.cover.show(self.covers, album.get("coverArt"), CARD_WIDTH)
        self.title.set_label(album.get("name") or "")
        if subtitle is None:
            subtitle = album.get("artist") or ""
        self.subtitle.set_label(subtitle)
        self.subtitle.set_visible(bool(subtitle))
        self.update_property([Gtk.AccessibleProperty.LABEL],
                             [f"{album.get('name', '')} {subtitle}".strip()])


class AlbumGrid(Gtk.GridView):
    """A recycling grid of album cards for long lists."""

    def __init__(self, covers, store, on_activate):
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", lambda f, li: li.set_child(AlbumCard(covers)))
        factory.connect("bind", lambda f, li: li.get_child().set_album(
            li.get_item().data))
        super().__init__(model=Gtk.NoSelection(model=store), factory=factory,
                         min_columns=2, max_columns=12,
                         single_click_activate=True, margin_start=6,
                         margin_end=6, margin_top=6, margin_bottom=6)
        self.add_css_class("nauta-grid")
        self.connect("activate", lambda grid, pos: on_activate(
            store.get_item(pos).data))


def album_box(covers, albums, on_activate, subtitle=None):
    """A FlowBox of album cards for short lists (an artist's albums)."""
    flow = Gtk.FlowBox(homogeneous=True, max_children_per_line=12,
                       row_spacing=18, column_spacing=12,
                       selection_mode=Gtk.SelectionMode.NONE,
                       activate_on_single_click=True, valign=Gtk.Align.START)
    flow.set_min_children_per_line(2)
    for album in albums:
        card = AlbumCard(covers)
        card.set_album(album, subtitle(album) if subtitle else None)
        flow.append(card)
    flow.connect("child-activated",
                 lambda f, child: on_activate(child.get_child().album))
    return flow


def song_row(song, prefix, covers=None, with_album=True, actions=None, index=0):
    """An activatable row: track number (prefix str) or a small cover
    (covers given), title, artist, duration. With `actions`
    (nauta.actions.SongActions) a "⋮" menu, the same menu on a long
    press or right click, and the swipe (nauta.swipe)."""
    row = Gtk.ListBoxRow(activatable=True)
    box = Gtk.Box(spacing=12, margin_top=8, margin_bottom=8, margin_start=12,
                  margin_end=6 if actions is not None else 12)
    if covers is not None:
        cover = Cover(size=40)
        cover.show(covers, song.get("coverArt"), 40)
        box.append(cover)
    else:
        number = Gtk.Label(label=prefix, width_chars=2, xalign=1)
        number.add_css_class("dimmed")
        number.add_css_class("dim-label")
        number.add_css_class("numeric")
        box.append(number)
    labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True,
                     valign=Gtk.Align.CENTER)
    title = Gtk.Label(label=song.get("title") or "", xalign=0,
                      ellipsize=Pango.EllipsizeMode.END, max_width_chars=1)
    subtitle = Gtk.Label(label=text.song_subtitle(song, with_album), xalign=0,
                         ellipsize=Pango.EllipsizeMode.END, max_width_chars=1)
    subtitle.add_css_class("caption")
    subtitle.add_css_class("dimmed")
    subtitle.add_css_class("dim-label")
    labels.append(title)
    labels.append(subtitle)
    box.append(labels)
    length = Gtk.Label(label=text.duration(song.get("duration")))
    length.add_css_class("dimmed")
    length.add_css_class("dim-label")
    length.add_css_class("numeric")
    box.append(length)
    row.song = song
    row.title_label = title
    if actions is None:
        row.set_child(box)
    else:
        _add_actions(row, box, song, index, actions)
    row.update_property([Gtk.AccessibleProperty.LABEL],
                        [f"{song.get('title', '')}, {text.song_subtitle(song, with_album)}"])
    return row


def _add_actions(row, box, song, index, actions):
    from nauta.swipe import SwipeBox
    more = Gtk.Button(icon_name="view-more-symbolic", tooltip_text="More",
                      valign=Gtk.Align.CENTER)
    more.add_css_class("flat")
    more.update_property([Gtk.AccessibleProperty.LABEL],
                         [f"More for {song.get('title', '')}"])
    more.connect("clicked", lambda b: actions.open(b, song, index))
    box.append(more)
    row.more = more
    press = Gtk.GestureLongPress()
    press.connect("pressed", lambda g, x, y: (
        g.set_state(Gtk.EventSequenceState.CLAIMED), actions.open(more, song, index)))
    row.add_controller(press)
    click = Gtk.GestureClick(button=3)
    click.connect("pressed", lambda g, n, x, y: actions.open(more, song, index))
    row.add_controller(click)
    icon, label, _ = actions.swipe
    row.set_child(SwipeBox(box, icon, label, lambda: actions.swiped(song, index)))


def song_list(songs, on_activate, covers=None, numbers=True, with_album=True,
              actions=None):
    """A boxed list of song rows; on_activate(index). `actions`: see
    song_row."""
    box = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
    box.add_css_class("boxed-list")
    for i, song in enumerate(songs):
        prefix = str(song.get("track") or i + 1) if numbers else str(i + 1)
        box.append(song_row(song, prefix, covers, with_album, actions, i))
    box.connect("row-activated", lambda b, row: on_activate(row.get_index()))
    return box


def nav_row(title, subtitle="", icon=None, covers=None, cover_id=None):
    """An activatable row that opens a page (artist, playlist)."""
    row = Adw.ActionRow(title=escape(title), subtitle=escape(subtitle),
                        activatable=True)
    row.set_title_lines(1)
    row.set_subtitle_lines(1)
    if covers is not None:
        cover = Cover(size=40, icon=icon or "folder-music-symbolic")
        cover.show(covers, cover_id, 40)
        row.add_prefix(cover)
    elif icon:
        row.add_prefix(Gtk.Image(icon_name=icon))
    row.add_suffix(Gtk.Image(icon_name="go-next-symbolic"))
    return row


def section(title, child):
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    label = Gtk.Label(label=title, xalign=0, ellipsize=Pango.EllipsizeMode.END)
    label.add_css_class("title-4")
    box.append(label)
    box.append(child)
    return box
