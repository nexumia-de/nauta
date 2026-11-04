"""Preferences: style and streaming quality, the connection (the setup
form) and the account."""
from gi.repository import Adw, GLib, Gtk
from phosh_toolkit.style import style_row

from nauta import settings
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

    def toast(self, message):
        self.add_toast(Adw.Toast(title=GLib.markup_escape_text(message)))

    def _on_style(self, style):
        self.window.connection.account.style = style
        self.window.connection.save()

    def _on_quality(self, row, pspec, attr, values):
        setattr(self.window.connection.account, attr, values[row.get_selected()])
        self.window.connection.save()

    def _on_save(self, *_):
        conn = self.window.connection

        def done(answers, http):
            self.save.set_sensitive(True)
            if answers is None:
                return
            self.form.apply(conn.account)
            conn.save()
            conn.load_certificate()
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
