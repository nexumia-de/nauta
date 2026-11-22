"""The signed-in account and the route to the server: local address on a
home network, remote address elsewhere (docs/connection.md). The route
itself is phosh_toolkit.router.Router."""
import logging

from gi.repository import GObject
from phosh_toolkit import tasks, tls
from phosh_toolkit.proxy_login import CookieJar, ProxyCredentials
from phosh_toolkit.http import NETWORK, SERVER, HttpError
from phosh_toolkit.router import CONNECTING, OFFLINE, Router  # noqa: F401

from nauta import keyring, settings
from nauta.api import API_KEY_EXTENSION, Subsonic, extensions

log = logging.getLogger("nauta.connection")

# Values of Account.auth: signed in with the password or an API key.
PASSWORD = "password"
API_KEY = "api-key"


class Connection(Router):
    """state: "connecting", "local", "remote" or "offline"."""
    __gsignals__ = {
        # The server rejected the password: the UI shows the setup page.
        "signed-out": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    # Subsonic servers can't say who they are without credentials, so the
    # local address is used only on a listed home Wi-Fi
    # (docs/connection.md).
    strict_local = True

    def __init__(self, store=None, watch=True):
        super().__init__(watch=watch)
        self.store = store or settings.Store()
        self.account = self.store.load()
        self.api = Subsonic()
        self.certificate_error = None
        if self.account.signed_in:
            self.api.user = self.account.user_name
            if self.account.auth == API_KEY:
                self.api.api_key = keyring.lookup(keyring.API_KEY) or ""
            else:
                self.api.password = keyring.lookup(keyring.PASSWORD) or ""
        self.load_certificate()
        # A reverse proxy's own login (docs/connection.md): its session
        # cookies, or its HTTP Basic user name and password.
        self.proxy_cookies = CookieJar(keyring.KEYRING)
        self.proxy_credentials = ProxyCredentials(keyring.KEYRING)
        self.load_proxy_login()

    def load_proxy_login(self):
        self.api.http.cookies = self.proxy_cookies.load()
        self.api.http.proxy_auth = self.proxy_credentials.headers()

    # --- account -----------------------------------------------------

    @property
    def signed_in(self):
        return self.account.signed_in and bool(self.api.password or self.api.api_key)

    def load_certificate(self):
        self.certificate_error = None
        self.api.http.certificate = None
        if not self.account.certificate:
            return
        try:
            self.api.http.certificate = settings.certificates().load()
        except (OSError, tls.CertificateError) as e:
            self.certificate_error = str(e)
            log.warning("client certificate: %s", e)

    def save(self):
        self.store.save(self.account)

    def signed_in_as(self, user, secret, info, auth=PASSWORD):
        """Keep the password or the API key (`auth`) in the keyring and
        forget the other one."""
        self.account.user_name = user
        self.account.auth = auth
        self.account.server_type = info.get("type", "")
        self.account.server_version = info.get("serverVersion", "")
        kept, dropped = (keyring.API_KEY, keyring.PASSWORD) if auth == API_KEY \
            else (keyring.PASSWORD, keyring.API_KEY)
        keyring.store(kept, secret)
        keyring.clear(dropped)
        self.api.user = user
        self.api.password, self.api.api_key = ("", secret) if auth == API_KEY \
            else (secret, "")
        self.save()

    def sign_out(self):
        """Forget the password or API key; addresses and certificate stay."""
        keyring.clear(keyring.PASSWORD)
        keyring.clear(keyring.API_KEY)
        self.api.password = self.api.api_key = ""
        self.account.user_name = ""
        self.save()

    # --- Router ------------------------------------------------------

    def probe(self, url, timeout):
        return probe_with(self.api.http)(url, timeout)

    def addresses(self):
        a = self.account
        return a.remote_url, a.local_url, a.home_networks

    def resolved(self, kind, url, info):
        self.api.base_url = url
        version = info.get("serverVersion", "")
        if version and version != self.account.server_version:
            self.account.server_version = version
            self.save()

    def unauthorized(self):
        self.sign_out()
        self.emit("signed-out")

    def forward(self, path):
        """The media proxy's upstream for a server path: the current route,
        the credentials in a POST body (phosh_toolkit.proxy)."""
        if not self.api.base_url:
            raise HttpError(NETWORK, "Not connected")
        return (self.api.http, self.api.base_url + path, {},
                self.api.stream_body())


def probe_through(http, url, timeout):
    """The probe in the form phosh_toolkit.proxy_login wants."""
    return probe_with(http)(url, timeout)


def probe_with(http):
    """Ask getOpenSubsonicExtensions (no credentials) through `http`.
    Subsonic has no public server id, so the id is empty."""
    def probe(url, timeout):
        return "", Subsonic(http).probe(url, timeout=timeout)
    return probe


def sign_in(connection, url, user, secret, done, auth=PASSWORD):
    """Check the credentials with ping at `url`; done(info, error) with
    the server's answer. `secret` is the password, or with auth=API_KEY
    an API key, which must belong to `user` (getUser)."""
    api = Subsonic(connection.api.http)
    api.user = user
    if auth == API_KEY:
        api.api_key = secret
    else:
        api.password = secret

    def work():
        info = api.probe(url)
        if auth == API_KEY and API_KEY_EXTENSION not in extensions(info):
            raise HttpError(SERVER, "This server doesn't accept API keys")
        api.ping(url)
        if auth == API_KEY:
            try:
                api.user_info(user, url)
            except HttpError as e:
                if e.kind != SERVER:
                    raise
                raise HttpError(SERVER, "This API key belongs to another user") \
                    from None
        return info

    def finished(info, error):
        if error is None:
            connection.api.base_url = url
            connection.base_url = url
            connection.signed_in_as(user, secret, info, auth)
        done(info, error)

    tasks.run(work, finished)
