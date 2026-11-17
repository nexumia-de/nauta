"""The toolkit's connection form plus Nauta's "Certificate Hosts" row:
hosts besides the server's that get the client certificate in the proxy
login's web view, e.g. an identity provider on another host behind the
same mutual TLS (docs/connection.md#proxy-login)."""
from urllib.parse import urlsplit

from gi.repository import Adw
from phosh_toolkit.connection_form import ConnectionForm


def parse_hosts(text):
    """Lower-case host names from a comma or space separated list; an
    entry with a scheme ("https://auth.example.org/") gives its host."""
    hosts = []
    for entry in text.replace(",", " ").split():
        host = urlsplit(entry if "://" in entry else "//" + entry).hostname
        if host and host not in hosts:
            hosts.append(host)
    return hosts


class Form(ConnectionForm):
    """`account` also has `certificate_hosts` (list of host names)."""

    def __init__(self, window, account, *args, **kwargs):
        super().__init__(window, account, *args, proxy_basic=True, **kwargs)
        self.certificate_hosts = Adw.EntryRow(
            title="Certificate Hosts",
            text=", ".join(account.certificate_hosts),
            tooltip_text="Login hosts that also get the client certificate, "
                         "e.g. the proxy's sign-in page on another address")
        self.proxy.add_row(self.certificate_hosts)
        if account.certificate_hosts:
            self.proxy.set_expanded(True)

    def apply(self, account):
        super().apply(account)
        account.certificate_hosts = parse_hosts(self.certificate_hosts.get_text())
