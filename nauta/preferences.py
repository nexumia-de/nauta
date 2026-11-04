"""Preferences: style and streaming quality, the connection (the setup
form) and the account, and the download server (docs/downloads.md)."""
from gi.repository import Adw, GLib, Gtk
from phosh_toolkit.style import style_row

from nauta import loudness, settings
from nauta.find import download_form, format_row
from nauta.setup import connection_form


class PreferencesDialog(Adw.PreferencesDialog):
    def __init__(self, window):
        super().__init__(title="Preferences")
        self.window = window
        account = window.connection.account

        general = Adw.PreferencesPage(title="General",
                                      icon_name="preferences-system-symbolic")
        appearance = Adw.PreferencesGroup(title="Appearance")
        self.style_row = style_row(account.style, self._on_style)
        appearance.add(self.style_row)
        general.add(appearance)
        quality = Adw.PreferencesGroup(
            title="Streaming Quality",
            description="Above this bitrate the server converts songs. "
                        "Original plays the file as it is.")
        names = Gtk.StringList.new([name for _, name in settings.QUALITIES])
        values = [value for value, _ in settings.QUALITIES]
        self.quality_rows = {}
        for attr, title in (("quality_home", "At Home"), ("quality_away", "Away")):
            row = Adw.ComboRow(title=title, model=names)
            current = getattr(account, attr)
            row.set_selected(values.index(current) if current in values else 0)
            row.connect("notify::selected", self._on_quality, attr, values)
            quality.add(row)
            self.quality_rows[attr] = row
        general.add(quality)
        playback = Adw.PreferencesGroup(title="Playback")
        modes = [value for value, _ in loudness.MODES]
        self.loudness_row = Adw.ComboRow(
            title="Volume Normalisation",
            subtitle="Uses the songs' ReplayGain tags; takes effect with the "
                     "next song",
            model=Gtk.StringList.new([name for _, name in loudness.MODES]))
        self.loudness_row.set_selected(modes.index(account.replay_gain)
                                       if account.replay_gain in modes else 0)
        self.loudness_row.connect("notify::selected", self._on_loudness, modes)
        playback.add(self.loudness_row)
        general.add(playback)
        self.add(general)

        connection_page = Adw.PreferencesPage(
            title="Connection", icon_name="network-server-symbolic")
        self.form = connection_form(window, account, toast=self.toast)
        for group in self.form.groups:
            connection_page.add(group)
        actions = Adw.PreferencesGroup()
        self.save = Gtk.Button(label="Save and Reconnect", halign=Gtk.Align.CENTER)
        self.save.add_css_class("pill")
        self.save.add_css_class("suggested-action")
        self.save.connect("clicked", self._on_save)
        actions.add(self.save)
        connection_page.add(actions)
        account_group = Adw.PreferencesGroup(title="Account")
        server = " ".join(p for p in (account.server_type.capitalize(),
                                      account.server_version) if p)
        user = Adw.ActionRow(
            title=GLib.markup_escape_text(account.user_name or "Not signed in"),
            subtitle=GLib.markup_escape_text(server))
        user.add_prefix(Gtk.Image(icon_name="avatar-default-symbolic"))
        sign_out = Gtk.Button(label="Sign Out", valign=Gtk.Align.CENTER)
        sign_out.add_css_class("destructive-action")
        sign_out.connect("clicked", self._on_sign_out)
        user.add_suffix(sign_out)
        account_group.add(user)
        connection_page.add(account_group)
        self.add(connection_page)
        self.downloads_page = self._downloads_page()
        self.add(self.downloads_page)

    def _on_loudness(self, row, pspec, modes):
        account = self.window.connection.account
        account.replay_gain = modes[row.get_selected()]
        self.window.connection.save()

    def _downloads_page(self):
        """MeTube: where it is and what it makes."""
        dl = self.window.downloads
        page = Adw.PreferencesPage(title="Downloads",
                                   icon_name="folder-download-symbolic")
        options = Adw.PreferencesGroup(
            title="Downloads",
            description="Find New Music searches YouTube Music and downloads "
                        "songs with your own MeTube server.")
        options.add(format_row(dl.account, self._on_format))
        page.add(options)
        self.download_form = download_form(self.window, dl.account,
                                           toast=self.toast)
        for group in self.download_form.groups:
            page.add(group)
        actions = Adw.PreferencesGroup()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                      halign=Gtk.Align.CENTER)
        self.download_save = Gtk.Button(label="Save and Connect")
        self.download_save.add_css_class("pill")
        self.download_save.add_css_class("suggested-action")
        self.download_save.connect("clicked", self._on_download_save)
        box.append(self.download_save)
        self.download_remove = Gtk.Button(label="Remove Download Server")
        self.download_remove.add_css_class("pill")
        self.download_remove.add_css_class("destructive-action")
        self.download_remove.set_visible(dl.configured)
        self.download_remove.connect("clicked", self._on_download_remove)
        box.append(self.download_remove)
        actions.add(box)
        page.add(actions)
        return page

    def toast(self, message):
        self.add_toast(Adw.Toast(title=GLib.markup_escape_text(message)))

    def _on_style(self, style):
        self.window.connection.account.style = style
        self.window.connection.save()

    def _on_quality(self, row, pspec, attr, values):
        setattr(self.window.connection.account, attr, values[row.get_selected()])
        self.window.connection.save()

    def _on_format(self, value):
        dl = self.window.downloads
        dl.account.audio_format = value
        dl.save()

    def _on_download_save(self, *_):
        dl = self.window.downloads

        def done(answers, http):
            self.download_save.set_sensitive(True)
            if answers is None:
                return
            self.download_form.apply(dl.account)
            dl.save()
            dl.reconnect()
            self.download_remove.set_visible(True)
            self.toast("Saved")

        if self.download_form.check(done):
            self.download_save.set_sensitive(False)

    def _on_download_remove(self, *_):
        dialog = Adw.AlertDialog(
            heading="Remove Download Server?",
            body="Nauta forgets MeTube's addresses, certificate and proxy "
                 "login. Songs already downloaded stay in your library.")
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("remove", "Remove")
        dialog.set_response_appearance("remove", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.connect("response", self._on_download_remove_response)
        dialog.present(self)

    def _on_download_remove_response(self, dialog, response):
        if response != "remove":
            return
        self.window.downloads.forget()
        # A fresh, empty form.
        self.remove(self.downloads_page)
        self.downloads_page = self._downloads_page()
        self.add(self.downloads_page)
        self.set_visible_page(self.downloads_page)
        self.toast("Download server removed")

    def _on_save(self, *_):
        conn = self.window.connection

        def done(answers, http):
            self.save.set_sensitive(True)
            if answers is None:
                return
            self.form.apply(conn.account)
            conn.save()
            conn.load_certificate()
            conn.load_proxy_login()
            conn.base_url = conn.api.base_url = ""
            conn.resolve()
            self.toast("Saved")

        if self.form.check(done):
            self.save.set_sensitive(False)

    def _on_sign_out(self, *_):
        dialog = Adw.AlertDialog(
            heading="Sign Out?",
            body="Nauta forgets your password and stops playing. The server "
                 "address and certificate stay.")
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("sign-out", "Sign Out")
        dialog.set_response_appearance("sign-out", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.connect("response", self._on_sign_out_response)
        dialog.present(self)

    def _on_sign_out_response(self, dialog, response):
        if response != "sign-out":
            return
        self.window.player.clear()
        self.window.connection.sign_out()
        self.close()
        self.window.show_setup()
