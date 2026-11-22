"""Report a Problem (phosh-toolkit docs/feedback.md): the action, the menu
entry and the About dialog's issue link. Needs a display."""
import os

import pytest

if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
    pytest.skip("needs a display", allow_module_level=True)

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw  # noqa: E402
from phosh_toolkit import feedback, router  # noqa: E402

import nauta  # noqa: E402
from conftest import run_until, visible  # noqa: E402
from nauta import connection, keyring, settings  # noqa: E402
from nauta.demo import PASSWORD  # noqa: E402

pytestmark = pytest.mark.usefixtures("quiet")


def test_report_problem_action_is_installed(app):
    assert app.lookup_action("report-problem") is not None


def test_menu_offers_report_a_problem_next_to_about(app, demo, monkeypatch):
    from nauta.library import MainPage
    from nauta.window import Window
    monkeypatch.setattr(router.network, "current_ssids", lambda: None)
    store = settings.Store()
    account = store.load()
    account.remote_url = demo.url
    account.user_name = "robin"
    store.save(account)
    keyring.store(keyring.PASSWORD, PASSWORD)
    window = Window(app, connection.Connection(store, watch=False))
    window.present()
    run_until(lambda: isinstance(visible(window), MainPage))
    menus = []

    def walk(widget):
        child = widget.get_first_child()
        while child is not None:
            model = getattr(child, "get_menu_model", lambda: None)()
            if model is not None:
                menus.append(model)
            walk(child)
            child = child.get_next_sibling()
    walk(window)
    entries = [(m.get_item_attribute_value(i, "label", None).get_string(),
                m.get_item_attribute_value(i, "action", None).get_string())
               for m in menus for i in range(m.get_n_items())]
    labels = [label for label, _ in entries]
    assert ("Report a Problem…", "app.report-problem") in entries
    assert labels.index("Report a Problem…") + 1 == labels.index(f"About {nauta.NAME}")
    window.destroy()


def test_about_issue_link_is_the_filled_form(app, monkeypatch):
    shown = []
    monkeypatch.setattr(Adw.AboutDialog, "present",
                        lambda self, parent=None: shown.append(self))
    app._on_about()
    url = shown[0].get_issue_url()
    assert url == feedback.issue_url("nexumia-de/nauta", nauta.VERSION)
    assert url.startswith("https://github.com/nexumia-de/nauta/issues/new?")
    assert "template=bug.yml" in url
    assert f"version={nauta.VERSION}" in url
