"""The toolkit's "Other Certificate Hosts" row in Nauta's forms (#45, #52)."""
import gi

gi.require_version("Adw", "1")

from nauta import settings  # noqa: E402
from nauta.find import download_form  # noqa: E402
from nauta.setup import connection_form  # noqa: E402


class Window:
    def toast(self, message):
        pass


def test_form_keeps_certificate_hosts(app):
    account = settings.Account(remote_url="https://music.example.org",
                               certificate_hosts=["auth.example.org"])
    form = connection_form(Window(), account)
    assert form.hosts_entry.get_text() == "auth.example.org"
    assert form.hosts.get_expanded()
    form.hosts_entry.set_text("Auth.example.org, https://idp.example.org/x")
    form.apply(account)
    assert account.certificate_hosts == ["auth.example.org", "idp.example.org"]
    store = settings.Store()
    store.save(account)
    assert store.load().certificate_hosts == ["auth.example.org", "idp.example.org"]


def test_download_form_keeps_certificate_hosts(app):
    account = settings.DownloadServer(remote_url="https://metube.example.org",
                                      certificate_hosts=["auth.example.org"])
    form = download_form(Window(), account)
    assert form.hosts_entry.get_text() == "auth.example.org"
    form.hosts_entry.set_text("idp.example.org")
    form.apply(account)
    assert account.certificate_hosts == ["idp.example.org"]
