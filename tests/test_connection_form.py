"""Nauta's extra certificate hosts in the connection form (#45)."""
import gi

gi.require_version("Adw", "1")

from nauta import settings  # noqa: E402
from nauta.connection_form import parse_hosts  # noqa: E402
from nauta.setup import connection_form  # noqa: E402


def test_parse_hosts():
    assert parse_hosts("") == []
    assert parse_hosts(" Auth.Example.org, https://sso.example.org:8443/login "
                       "auth.example.org") == ["auth.example.org", "sso.example.org"]


def test_form_keeps_certificate_hosts(app):
    account = settings.Account(remote_url="https://music.example.org",
                               certificate_hosts=["auth.example.org"])

    class Window:
        def toast(self, message):
            pass

    form = connection_form(Window(), account)
    assert form.certificate_hosts.get_text() == "auth.example.org"
    assert form.proxy.get_expanded()
    form.certificate_hosts.set_text("auth.example.org, idp.example.org")
    form.apply(account)
    assert account.certificate_hosts == ["auth.example.org", "idp.example.org"]
    store = settings.Store()
    store.save(account)
    assert store.load().certificate_hosts == ["auth.example.org", "idp.example.org"]
