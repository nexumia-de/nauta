"""Find new music: search YouTube Music (or YouTube) through the user's
MeTube server and download songs into the library (docs/downloads.md).
Three pages on the navigation view: setting up the download server,
search, and MeTube's list of downloads."""
from gi.repository import Adw, GLib, Gtk
from phosh_toolkit.connection_form import ConnectionForm, describe_error

from nauta import USER_AGENT, downloads, metube, settings, text, widgets


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
    """Search through MeTube and download a result."""

    def __init__(self, window, query=""):
        super().__init__(title="Find New Music", tag="find-music")
        self.window = window
        dl = window.downloads
        self.entry = Gtk.SearchEntry(placeholder_text="Songs and artists",
                                     hexpand=True)
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

        # Where to search: YouTube Music's songs, or YouTube.
        sources = Gtk.Box(halign=Gtk.Align.CENTER, margin_top=6,
                          margin_bottom=6, homogeneous=True)
        sources.add_css_class("linked")
        self.source_buttons = {}
        group = None
        for value, name in metube.SOURCES:
            button = Gtk.ToggleButton(label=name, group=group,
                                      active=value == dl.account.source)
            button.connect("toggled", self._on_source, value)
            group = group or button
            sources.append(button)
            self.source_buttons[value] = button

        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE,
                               vexpand=True)
        self.stack.add_named(Adw.StatusPage(
            icon_name="folder-download-symbolic", title="Find New Music",
            description="Search for a song and download it into your "
                        "library"), "start")
        self.stack.add_named(widgets.loading_page(), "loading")
        self.stack.add_named(Adw.StatusPage(
            icon_name="system-search-symbolic", title="No Results",
            description="Try other words or the other source"), "empty")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.append(sources)
        box.append(self.stack)
        view = Adw.ToolbarView(content=box)
        view.add_top_bar(header)
        self.set_child(view)
        self._query = None
        self.connect("shown", lambda *_: self.entry.grab_focus())
        if query:
            self.search(query)

    @property
    def source(self):
        return self.window.downloads.account.source

    def search(self, query):
        self.entry.set_text(query)
        self._on_search(self.entry)

    def _on_source(self, button, value):
        if not button.get_active() or value == self.source:
            return
        dl = self.window.downloads
        dl.account.source = value
        dl.save()
        if self.entry.get_text().strip():
            self._on_search(self.entry)

    def _on_search(self, entry):
        query = entry.get_text().strip()
        if not query:
            self.stack.set_visible_child_name("start")
            return
        key = (query, self.source)
        self._query = key
        self.stack.set_visible_child_name("loading")
        self.window.downloads.search(
            query, self.source, lambda r, e: self._on_results(key, r, e))

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
            box.append(self._row(result))
        clamp = Adw.Clamp(child=box, maximum_size=800, margin_top=6,
                          margin_bottom=24, margin_start=12, margin_end=12)
        self.stack.add_named(Gtk.ScrolledWindow(
            child=clamp, hscrollbar_policy=Gtk.PolicyType.NEVER,
            vexpand=True), "results")
        self.stack.set_visible_child_name("results")

    def _row(self, result):
        title = result.get("title") or result.get("url") or ""
        duration = result.get("duration")
        row = Adw.ActionRow(title=widgets.escape(title),
                            subtitle=text.duration(duration) if duration else "")
        row.set_title_lines(2)
        row.add_prefix(Gtk.Image(icon_name="audio-x-generic-symbolic"))
        button = _icon_button("folder-download-symbolic", f"Download {title}")
        button.set_tooltip_text("Download")
        button.connect("clicked", self._on_download, result, title)
        row.add_suffix(button)
        row.download = button
        return row

    def _on_download(self, button, result, title):
        button.set_sensitive(False)

        def done(answer, error):
            if error is not None:
                button.set_sensitive(True)
                self.window.toast(f"Can't download “{title}”: "
                                  f"{describe_error(error)}")
                return
            button.set_icon_name("object-select-symbolic")
            button.set_tooltip_text("Downloading")
            self.window.toast(answer.get("msg") or f"Downloading “{title}”")
        self.window.downloads.add(result["url"], title, done)


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
