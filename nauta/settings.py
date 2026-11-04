"""The server account on disk: addresses, home networks, user name,
streaming quality and style. The password and the certificate password
are in the keyring (nauta/keyring.py), the client certificate is a
private copy in the data directory (phosh_toolkit.certificate). No GTK."""
from dataclasses import dataclass, field

from phosh_toolkit.certificate import CertificateFile
from phosh_toolkit.settings import JsonStore, app_dir

from nauta import keyring

VERSION = 1
# Maximum streaming bitrate in kbit/s; 0 plays the original file. Above
# it the server converts to its default format (docs/playback.md).
QUALITIES = (
    (0, "Original"),
    (320, "320 kbit/s"),
    (192, "192 kbit/s"),
    (128, "128 kbit/s"),
    (96, "96 kbit/s"),
)


@dataclass
class Account:
    remote_url: str = ""
    local_url: str = ""
    home_networks: list = field(default_factory=list)
    certificate: bool = False
    user_name: str = ""
    # From the server's answer, for the preferences ("navidrome 0.64.2").
    server_type: str = ""
    server_version: str = ""
    quality_home: int = 0
    quality_away: int = 192
    style: str = "system"

    @property
    def signed_in(self):
        return bool(self.user_name and (self.remote_url or self.local_url))


def config_dir():
    return app_dir("config", "nauta")


def data_dir():
    return app_dir("data", "nauta")


def cache_dir():
    return app_dir("cache", "nauta")


def certificates():
    """The saved client certificate and its password in the keyring."""
    return CertificateFile(data_dir() / "client-certificate", keyring.KEYRING)


class Store(JsonStore):
    def __init__(self, path=None):
        super().__init__(path or config_dir() / "account.json", Account, VERSION)
