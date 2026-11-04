"""Find new music: search YouTube Music (or YouTube) for songs, albums
and playlists and download them into the library through the user's
MeTube server (docs/downloads.md). Pages on the navigation view: setting
up the download server, search, the songs of an album or playlist, and
MeTube's list of downloads."""
from gi.repository import Adw, GLib, Gtk
from phosh_toolkit.connection_form import ConnectionForm, describe_error

from nauta import USER_AGENT, downloads, metube, settings, text, widgets
from nauta.ytmusic import ALBUMS


def download_form(window, account, toast=None):
    return ConnectionForm(
        window, account, settings.download_certificates(), downloads.probe_with,
        USER_AGENT,
        server_description="The address of your MeTube server. Set MeTube's "
                           "audio folder inside Navidrome's music folder.",
        home_description="On these Wi-Fi networks Nauta talks to MeTube "
                         "directly. The local address is used only on the "
                         "networks listed here.",
        toast=toast, proxy_basic=True)


def format_row(account, changed):
    """The audio format MeTube converts downloads to."""
    names = Gtk.StringList.new([name for _, name in metube.FORMATS])
    values = [value for value, _ in metube.FORMATS]
    row = Adw.ComboRow(title="Audio Format", model=names,
                       subtitle="With tags and cover")
    row.set_selected(values.index(account.audio_format)
                     if account.audio_format in values else 0)
    row.connect("notify::selected",
                lambda r, _: changed(values[r.get_selected()]))
    return row


def _pill(label):
    button = Gtk.Button(label=label, halign=Gtk.Align.CENTER)
    button.add_css_class("pill")
    button.add_css_class("suggested-action")
    return button


def _icon_button(icon, label):
    button = Gtk.Button(icon_name=icon, valign=Gtk.Align.CENTER,
                        tooltip_text=label)
    button.add_css_class("flat")
    button.update_property([Gtk.AccessibleProperty.LABEL], [label])
    return button


def song_row(window, result):
    """A song or video with its download button (row.download)."""
    title = result.get("title") or result.get("url") or ""
    duration = result.get("duration")
    row = Adw.ActionRow(title=widgets.escape(title),
                        subtitle=text.duration(duration) if duration else "")
    row.set_title_lines(2)
    row.add_prefix(Gtk.Image(icon_name="audio-x-generic-symbolic"))
    button = _icon_button("folder-download-symbolic", f"Download {title}")
    button.set_tooltip_text("Download")
    button.connect("clicked", lambda b: download(window, b, result["url"], title))
    row.add_suffix(button)
    row.download = button
    return row


def mark_downloading(button):
    button.set_sensitive(False)
    button.set_icon_name("object-select-symbolic")
    button.set_tooltip_text("Downloading")


def download(window, button, url, title, songs=None, label=None, then=None):
    """Send `url` (a song, or with `songs` a whole album or playlist) to
    MeTube; the button shows that it is on its way, then() runs after."""
    button.set_sensitive(False)

    def done(answer, error):
        if error is not None:
            button.set_sensitive(True)
            window.toast(f"Can't download “{title}”: {describe_error(error)}")
            return
        if label is None:
            mark_downloading(button)
        else:
            button.set_label(label)
        window.toast(answer.get("msg") or f"Downloading “{title}”")
        if then is not None:
            then()
    window.downloads.add(url, title, done, songs)


def _scrolled(child):
    clamp = Adw.Clamp(child=child, maximum_size=800, margin_top=6,
                      margin_bottom=24, margin_start=12, margin_end=12)
    return Gtk.ScrolledWindow(child=clamp, vexpand=True,
                              hscrollbar_policy=Gtk.PolicyType.NEVER)


def _linked_toggles(choices, active, toggled):
    """A row of linked toggle buttons, one of them active; returns the box
    and {value: button}."""
    box = Gtk.Box(halign=Gtk.Align.CENTER, homogeneous=True)
    box.add_css_class("linked")
    buttons = {}
    group = None
    for value, name in choices:
        button = Gtk.ToggleButton(label=name, group=group, active=value == active)
        button.connect("toggled", lambda b, v: b.get_active() and toggled(v), value)
        group = group or button
        box.append(button)
        buttons[value] = button
    return box, buttons


class DownloadSetupPage(Adw.NavigationPage):
    """Where the MeTube server is; shown before the first search."""

    def __init__(self, window, query=""):
        super().__init__(title="Set Up Downloads", tag="download-setup")
        self.window = window
        self.query = query
        account = window.downloads.account
        self.form = download_form(window, account)
        page = Adw.PreferencesPage()
        intro = Adw.PreferencesGroup()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.append(Gtk.Image(icon_name="folder-download-symbolic",
                             pixel_size=64, opacity=0.6))
        title = Gtk.Label(label="Find New Music", wrap=True,
                          justify=Gtk.Justification.CENTER)
        title.add_css_class("title-2")
        box.append(title)
        box.append(Gtk.Label(
            label="Search YouTube Music and download songs into your library "
                  "with your own MeTube server. MeTube saves them on the "
                  "server, and Navidrome adds them at its next scan.",
            wrap=True, justify=Gtk.Justification.CENTER))
        intro.add(box)
        page.add(intro)
        for group in self.form.groups:
            page.add(group)
        options = Adw.PreferencesGroup(title="Downloads")
        options.add(format_row(account, self._on_format))
        page.add(options)
        actions = Adw.PreferencesGroup()
        self.button = _pill("Connect")
        self.button.connect("clicked", self._on_connect)
        actions.add(self.button)
        page.add(actions)
        view = Adw.ToolbarView(content=page)
        view.add_top_bar(Adw.HeaderBar())
        self.set_child(view)
        self.form.remote.connect("entry-activated", self._on_connect)

    def _on_format(self, value):
        self.window.downloads.account.audio_format = value

    def _on_connect(self, *_):
        dl = self.window.downloads

        def done(answers, http):
            self.button.set_sensitive(True)
            if answers is None:
                return
            self.form.apply(dl.account)
            dl.save()
            dl.reconnect()
            nav = self.window.nav
            # Search replaces this page, so the swipe back goes to where
            # the user came from.
            nav.pop()
            nav.push(FindMusicPage(self.window, self.query))

        if self.form.check(done):
            self.button.set_sensitive(False)


class FindMusicPage(Adw.NavigationPage):
    """Search through MeTube (songs, videos) or YouTube Music (albums,
    playlists) and download a result."""

    def __init__(self, window, query=""):
        super().__init__(title="Find New Music", tag="find-music")
        self.window = window
        dl = window.downloads
        self.entry = Gtk.SearchEntry(hexpand=True)
        self.entry.update_property([Gtk.AccessibleProperty.LABEL],
                                   ["Search for new music"])
        # Every search runs yt-dlp on the server: search on Enter, not on
        # every key.
        self.entry.connect("activate", self._on_search)
        header = Adw.HeaderBar(title_widget=Adw.Clamp(child=self.entry,
                                                      maximum_size=500))
        list_button = _icon_button("folder-download-symbolic", "Downloads")
        list_button.connect("clicked", lambda *_: window.nav.push(
            DownloadsPage(window)))
        header.pack_end(list_button)

        # Where to search: YouTube Music or YouTube; on YouTube Music also
        # what: songs, albums or playlists.
        sources, self.source_buttons = _linked_toggles(
            metube.SOURCES, dl.account.source, self._on_source)
        kinds, self.kind_buttons = _linked_toggles(
            metube.KINDS, dl.account.kind, self._on_kind)
        kinds.set_margin_top(6)
        self.kinds = Gtk.Revealer(child=kinds)
        filters = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                          margin_top=6, margin_bottom=6)
        filters.append(sources)
        filters.append(self.kinds)

        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE,
                               vexpand=True)
        self.stack.add_named(Adw.StatusPage(
            icon_name="folder-download-symbolic", title="Find New Music",
            description="Search for songs, albums or playlists and download "
                        "them into your library. A link to an album or "
                        "playlist works too."), "start")
        self.stack.add_named(widgets.loading_page(), "loading")
        self.stack.add_named(Adw.StatusPage(
            icon_name="system-search-symbolic", title="No Results",
            description="Try other words or another filter"), "empty")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.append(filters)
        box.append(self.stack)
        view = Adw.ToolbarView(content=box)
        view.add_top_bar(header)
        self.set_child(view)
        self._query = None
        self._update_filters()
        self.connect("shown", lambda *_: self.entry.grab_focus())
        if query:
            # After this page is on the navigation view: a link opens its
            # album or playlist on top of it.
            self.entry.set_text(query)
            GLib.idle_add(lambda: self._on_search(self.entry))

    @property
    def source(self):
        return self.window.downloads.account.source

    @property
    def kind(self):
        """What is searched: songs, albums or playlists on YouTube Music,
        videos (metube.SONGS) on YouTube."""
        if self.source == metube.YOUTUBE:
            return metube.SONGS
        return self.window.downloads.account.kind

    def search(self, query):
        self.entry.set_text(query)
        self._on_search(self.entry)

    def _update_filters(self):
        self.kinds.set_reveal_child(self.source == metube.YOUTUBE_MUSIC)
        self.entry.set_placeholder_text({
            metube.SONGS: "Songs and artists", ALBUMS: "Albums and artists"
        }.get(self.kind, "Playlists"))

    def _changed(self, field, value):
        dl = self.window.downloads
        if getattr(dl.account, field) == value:
            return
        setattr(dl.account, field, value)
        dl.save()
        self._update_filters()
        if self.entry.get_text().strip():
            self._on_search(self.entry)

    def _on_source(self, value):
        self._changed("source", value)

    def _on_kind(self, value):
        self._changed("kind", value)

    def _on_search(self, entry):
        query = entry.get_text().strip()
        if not query:
            self.stack.set_visible_child_name("start")
            return
        link = metube.collection_link(query)
        if link:
            # A pasted album or playlist: straight to its songs.
            self.window.nav.push(CollectionPage(self.window, {"url": link}))
            return
        key = (query, self.source, self.kind)
        self._query = key
        self.stack.set_visible_child_name("loading")
        self.window.downloads.search(
            query, self.source, self.kind,
            lambda r, e: self._on_results(key, r, e))

    def _on_results(self, key, results, error):
        if key != self._query:
            return   # an older search
        old = self.stack.get_child_by_name("results")
        if old is not None:
            self.stack.remove(old)
        if error is not None:
            self.stack.add_named(widgets.error_page(
                "Can't Search", describe_error(error),
                lambda: self.search(key[0])), "results")
            self.stack.set_visible_child_name("results")
            return
        if not results:
            self.stack.set_visible_child_name("empty")
            return
        box = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE,
                          valign=Gtk.Align.START)
        box.add_css_class("boxed-list")
        for result in results:
            box.append(self._collection_row(result) if result.get("kind")
                       else song_row(self.window, result))
        self.stack.add_named(_scrolled(box), "results")
        self.stack.set_visible_child_name("results")

    def _collection_row(self, result):
        """An album or playlist: opens its songs; the button downloads all
        of them."""
        title = result["title"]
        row = Adw.ActionRow(title=widgets.escape(title),
                            subtitle=widgets.escape(result.get("subtitle") or ""),
                            activatable=True)
        row.set_title_lines(2)
        row.set_subtitle_lines(2)
        row.add_prefix(Gtk.Image(icon_name="media-optical-cd-audio-symbolic"
                                 if result["kind"] == ALBUMS
                                 else "view-list-symbolic"))
        row.add_suffix(Gtk.Image(icon_name="go-next-symbolic"))
        row.connect("activated", lambda *_: self.window.nav.push(
            CollectionPage(self.window, result)))
        return row


class CollectionPage(Adw.NavigationPage):
    """The songs of an album or playlist, listed by MeTube: download all
    of them at once, or single songs."""

    def __init__(self, window, result):
        title = result.get("title") or ""
        super().__init__(title=title or "Album or Playlist")
        self.window = window
        self.result = result
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        self.stack.add_named(widgets.loading_page(), "loading")
        self.stack.add_named(Adw.StatusPage(
            icon_name="view-list-symbolic", title="No Songs",
            description="This album or playlist is empty or unavailable"),
            "empty")
        self.download_all = None
        view = Adw.ToolbarView(content=self.stack)
        view.add_top_bar(Adw.HeaderBar())
        self.set_child(view)
        self.load()

    def load(self):
        self.stack.set_visible_child_name("loading")
        self.window.downloads.browse(self.result["url"], self._on_songs)

    def _on_songs(self, answer, error):
        old = self.stack.get_child_by_name("songs")
        if old is not None:
            self.stack.remove(old)
        if error is not None:
            self.stack.add_named(widgets.error_page(
                "Can't List the Songs", describe_error(error), self.load),
                "songs")
            self.stack.set_visible_child_name("songs")
            return
        name, songs = answer
        title = self.result.get("title") or name or self.result["url"]
        self.set_title(title)
        if not songs:
            self.stack.set_visible_child_name("empty")
            return
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                       margin_top=12)
        heading = Gtk.Label(label=title, wrap=True,
                            justify=Gtk.Justification.CENTER)
        heading.add_css_class("title-2")
        body.append(heading)
        details = self.result.get("subtitle") or ""
        count = (f"{len(songs)} or more songs"
                 if len(songs) >= metube.COLLECTION_LIMIT
                 else f"{len(songs)} song" + ("" if len(songs) == 1 else "s"))
        info = Gtk.Label(label=" • ".join(p for p in (details, count) if p),
                         wrap=True, justify=Gtk.Justification.CENTER)
        info.add_css_class("dimmed")
        body.append(info)
        self.download_all = _pill("Download All")
        self.download_all.connect("clicked", self._on_download_all, title, songs)
        body.append(self.download_all)
        box = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE,
                          valign=Gtk.Align.START, margin_top=12)
        box.add_css_class("boxed-list")
        self.rows = [song_row(self.window, song) for song in songs]
        for row in self.rows:
            box.append(row)
        body.append(box)
        self.stack.add_named(_scrolled(body), "songs")
        self.stack.set_visible_child_name("songs")

    def _on_download_all(self, button, title, songs):
        # MeTube gets the album or playlist itself: it numbers the tracks
        # and keeps them together in a folder.
        def started():
            for row in self.rows:
                mark_downloading(row.download)
        download(self.window, button, self.result["url"], title, songs,
                 label="Downloading", then=started)


def status_text(item):
    """"Waiting", "Downloading · 42 %", "Converting", "Done", "Failed: …"."""
    status = item.get("status")
    if status == "finished":
        return "Done"
    if status == "error":
        return f"Failed: {item.get('msg') or item.get('error') or 'unknown error'}"
    if status == "downloading":
        percent = item.get("percent")
        return f"Downloading · {int(percent)} %" if percent is not None \
            else "Downloading"
    if status == "postprocessing":
        return "Converting"
    if status == "preparing":
        return "Preparing"
    return "Waiting"


class DownloadsPage(Adw.NavigationPage):
    """MeTube's list: running downloads and finished ones."""

    def __init__(self, window):
        super().__init__(title="Downloads", tag="downloads")
        self.window = window
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        self.stack.add_named(widgets.loading_page(), "loading")
        self.stack.add_named(Adw.StatusPage(
            icon_name="folder-download-symbolic", title="No Downloads",
            description="Songs you download appear here"), "empty")
        self.error = Adw.StatusPage(icon_name="network-offline-symbolic",
                                    title="Can't Reach MeTube")
        self.stack.add_named(self.error, "error")
        view = Adw.ToolbarView(content=self.stack)
        view.add_top_bar(Adw.HeaderBar())
        self.set_child(view)
        self._handler = 0
        self.connect("shown", self._on_shown)
        self.connect("hidden", self._on_hidden)

    def _on_shown(self, *_):
        dl = self.window.downloads
        if self._handler == 0:
            self._handler = dl.connect("history", self._on_history)
            if dl.history is not None:
                self._on_history(dl, dl.history)
            dl.watch()

    def _on_hidden(self, *_):
        if self._handler:
            dl = self.window.downloads
            dl.disconnect(self._handler)
            self._handler = 0
            dl.unwatch()

    def _on_history(self, dl, history):
        if history is None:
            if self.stack.get_visible_child_name() in ("loading", "error"):
                error = dl.error
                self.error.set_description(GLib.markup_escape_text(
                    describe_error(error) if error else "No answer"))
                self.stack.set_visible_child_name("error")
            return
        running = history["queue"] + history["pending"]
        done = sorted(history["done"], key=lambda i: i.get("timestamp") or 0,
                      reverse=True)
        old = self.stack.get_child_by_name("list")
        if old is not None:
            self.stack.remove(old)
        if not running and not done:
            self.stack.set_visible_child_name("empty")
            return
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        if running:
            body.append(widgets.section("Downloading", self._list(running, "queue")))
        if done:
            body.append(widgets.section("Done", self._list(done, "done")))
        clamp = Adw.Clamp(child=body, maximum_size=800, margin_top=12,
                          margin_bottom=24, margin_start=12, margin_end=12)
        self.stack.add_named(Gtk.ScrolledWindow(
            child=clamp, hscrollbar_policy=Gtk.PolicyType.NEVER,
            vexpand=True), "list")
        self.stack.set_visible_child_name("list")

    def _list(self, items, where):
        box = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        box.add_css_class("boxed-list")
        for item in items:
            title = item.get("title") or item.get("url") or ""
            row = Adw.ActionRow(title=widgets.escape(title),
                                subtitle=widgets.escape(status_text(item)))
            row.set_title_lines(2)
            row.set_subtitle_lines(2)
            icon = {"finished": "object-select-symbolic",
                    "error": "dialog-error-symbolic"}.get(
                item.get("status"), "folder-download-symbolic")
            row.add_prefix(Gtk.Image(icon_name=icon))
            if where == "queue":
                button = _icon_button("process-stop-symbolic", f"Cancel {title}")
                button.set_tooltip_text("Cancel")
            else:
                button = _icon_button("edit-clear-symbolic",
                                      f"Remove {title} from the list")
                button.set_tooltip_text("Remove from List")
            button.connect("clicked", self._on_remove, item, where)
            row.add_suffix(button)
            box.append(row)
        return box

    def _on_remove(self, button, item, where):
        button.set_sensitive(False)

        def done(result, error):
            if error is not None:
                button.set_sensitive(True)
                self.window.toast(describe_error(error))
        self.window.downloads.remove([item], where, done)
