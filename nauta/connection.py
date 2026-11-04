"""The signed-in account and the route to the server: local address on a
home network, remote address elsewhere (docs/connection.md). The route
itself is phosh_toolkit.router.Router."""
import logging

from gi.repository import GObject
from phosh_toolkit import tasks, tls
from phosh_toolkit.http import NETWORK, HttpError
from phosh_toolkit.router import CONNECTING, OFFLINE, Router  # noqa: F401

from nauta import keyring, settings
from nauta.api import Subsonic

log = logging.getLogger("nauta.connection")


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
            self.api.password = keyring.lookup(keyring.PASSWORD) or ""
        self.load_certificate()

    # --- account -----------------------------------------------------

    @property
    def signed_in(self):
        return self.account.signed_in and bool(self.api.password)

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

    def signed_in_as(self, user, password, info):
        self.account.user_name = user
        self.account.server_type = info.get("type", "")
        self.account.server_version = info.get("serverVersion", "")
        keyring.store(keyring.PASSWORD, password)
        self.api.user, self.api.password = user, password
        self.save()

    def sign_out(self):
        """Forget the password; addresses and certificate stay."""
        keyring.clear(keyring.PASSWORD)
        self.api.password = ""
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


def probe_with(http):
    """Ask getOpenSubsonicExtensions (no credentials) through `http`.
    Subsonic has no public server id, so the id is empty."""
    def probe(url, timeout):
        return "", Subsonic(http).probe(url, timeout=timeout)
    return probe


def sign_in(connection, url, user, password, done):
    """Check the credentials with ping at `url`; done(info, error) with
    the server's answer."""
    api = Subsonic(connection.api.http)
    api.user, api.password = user, password

    def work():
        info = api.probe(url)
        api.ping(url)
        return info

    def finished(info, error):
        if error is None:
            connection.api.base_url = url
            connection.base_url = url
            connection.signed_in_as(user, password, info)
        done(info, error)

    tasks.run(work, finished)
