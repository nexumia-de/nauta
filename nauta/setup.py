"""Connect and sign in: the server address, the client certificate and
the home network (docs/connection.md). The connection form
(phosh_toolkit.connection_form) is also the "Connection" page of the
preferences."""
from gi.repository import Adw, GLib, Gtk
from phosh_toolkit.connection_form import ConnectionForm, describe_error
from phosh_toolkit.http import AUTH

from nauta import USER_AGENT, connection, settings


def connection_form(window, account, toast=None):
    return ConnectionForm(
        window, account, settings.certificates(), connection.probe_with,
        USER_AGENT,
        server_description="The address you use to reach Navidrome from anywhere",
        home_description="On these Wi-Fi networks Jukebox talks to the server "
                         "directly. The local address is used only on the "
                         "networks listed here.",
        toast=toast, proxy_basic=True)


def _button(label):
    button = Gtk.Button(label=label, halign=Gtk.Align.CENTER, margin_top=12)
    button.add_css_class("pill")
    button.add_css_class("suggested-action")
    return button


class SetupPage(Adw.NavigationPage):
    """First page: where the server is."""

    def __init__(self, window):
        super().__init__(title="Connect to Navidrome", tag="setup")
        self.window = window
        self.form = connection_form(window, window.connection.account)
        page = Adw.PreferencesPage()
        intro = Adw.PreferencesGroup()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.append(Gtk.Image(icon_name=window.app_icon, pixel_size=96))
        title = Gtk.Label(label="Welcome to Jukebox", wrap=True,
                          justify=Gtk.Justification.CENTER)
        title.add_css_class("title-1")
        box.append(title)
        box.append(Gtk.Label(label="Listen to the music on your Navidrome "
                                   "server", wrap=True,
                             justify=Gtk.Justification.CENTER))
        intro.add(box)
        page.add(intro)
        for group in self.form.groups:
            page.add(group)
        actions = Adw.PreferencesGroup()
        self.button = _button("Connect")
        self.button.connect("clicked", self._on_connect)
        actions.add(self.button)
        page.add(actions)
        view = Adw.ToolbarView(content=page)
        view.add_top_bar(Adw.HeaderBar(show_title=False))
        self.set_child(view)
        self.form.remote.connect("entry-activated", self._on_connect)

    def _on_connect(self, *_):
        def done(answers, http):
            self.button.set_sensitive(True)
            if answers is None:
                return
            self.window.connection.api.http.certificate = http.certificate
            self.window.connection.api.http.cookies = http.cookies
            self.window.connection.api.http.proxy_auth = http.proxy_auth
            self.window.nav.push(SignInPage(self.window, self.form,
                                            self.form.answer(answers),
                                            self.form.reachable_url(answers)))

        if self.form.check(done):
            self.button.set_sensitive(False)


class SignInPage(Adw.NavigationPage):
    def __init__(self, window, form, info, url):
        super().__init__(title="Sign In", tag="sign-in")
        self.window, self.form, self.info, self.url = window, form, info, url
        page = Adw.PreferencesPage()
        server = " ".join(p for p in (info.get("type", "").capitalize(),
                                      info.get("serverVersion", "")) if p)
        group = Adw.PreferencesGroup(
            title="Your Account",
            description=GLib.markup_escape_text(server or "Subsonic server"))
        self.user = Adw.EntryRow(title="User Name",
                                 text=window.connection.account.user_name)
        self.password = Adw.PasswordEntryRow(title="Password")
        # An API key instead of the password (OpenSubsonic
        # apiKeyAuthentication, docs/connection.md).
        self.use_key = Adw.SwitchRow(
            title="Sign In With an API Key",
            subtitle=GLib.markup_escape_text(
                "Create one in Navidrome under Players & API keys"),
            active=window.connection.account.auth == connection.API_KEY)
        self.use_key.connect("notify::active", self._on_use_key)
        group.add(self.user)
        group.add(self.password)
        group.add(self.use_key)
        page.add(group)
        self._on_use_key()
        actions = Adw.PreferencesGroup()
        self.button = _button("Sign In")
        self.button.connect("clicked", self._on_sign_in)
        actions.add(self.button)
        page.add(actions)
        self.password.connect("entry-activated", self._on_sign_in)
        self.user.connect("entry-activated", lambda *_: self.password.grab_focus())
        view = Adw.ToolbarView(content=page)
        view.add_top_bar(Adw.HeaderBar())
        self.set_child(view)
        self.connect("shown", lambda *_: self.user.grab_focus())

    @property
    def auth(self):
        return connection.API_KEY if self.use_key.get_active() else connection.PASSWORD

    def _on_use_key(self, *_):
        self.password.set_title("API Key" if self.use_key.get_active() else "Password")
        self.password.remove_css_class("error")

    def _on_sign_in(self, *_):
        user = self.user.get_text().strip()
        if not user:
            self.user.add_css_class("error")
            return
        conn = self.window.connection
        auth = self.auth
        self.button.set_sensitive(False)

        def done(info, error):
            self.button.set_sensitive(True)
            if error is not None:
                self.password.add_css_class("error")
                if auth == connection.API_KEY and getattr(error, "kind", None) == AUTH:
                    self.window.toast("Wrong API key")
                else:
                    self.window.toast(describe_error(error))
                return
            self.form.apply(conn.account)
            conn.save()
            conn.load_certificate()
            conn.load_proxy_login()
            conn.resolve()
            self.window.show_library()

        secret = self.password.get_text()
        if auth == connection.API_KEY:
            secret = secret.strip()     # pasted keys often bring a newline
        connection.sign_in(conn, self.url, user, secret, done, auth)
