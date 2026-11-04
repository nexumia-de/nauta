"""Metadata, build files and manifest agree with each other."""
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import nauta

ROOT = Path(__file__).resolve().parent.parent
APP_ID = "de.nexumia.Nauta"


def test_version_matches_meson_and_metainfo():
    meson = (ROOT / "meson.build").read_text()
    assert re.search(r"version: '([^']+)'", meson).group(1) == nauta.VERSION
    metainfo = ET.parse(ROOT / "data" / f"{APP_ID}.metainfo.xml")
    assert metainfo.find("releases/release").get("version") == nauta.VERSION


def test_every_module_is_installed():
    meson = (ROOT / "meson.build").read_text()
    for path in (ROOT / "nauta").glob("*.py"):
        assert f"'nauta/{path.name}'" in meson, path.name


def test_phone_metadata():
    desktop = (ROOT / "data" / f"{APP_ID}.desktop").read_text()
    # Phosh matches the substring "mobile;" case-insensitively.
    assert re.search(r"^X-Purism-FormFactor=.*mobile;", desktop,
                     re.IGNORECASE | re.MULTILINE)
    root = ET.parse(ROOT / "data" / f"{APP_ID}.metainfo.xml").getroot()
    length = root.find("recommends/display_length")
    assert length.get("compare") == "ge" and length.text == "360"
    assert {"touch", "pointing", "keyboard"} <= {
        c.text for c in root.findall("supports/control")}
    assert root.find("url[@type='donation']").text == nauta.SUPPORT_URL


def test_manifest_bundles_the_toolkit_and_may_read_the_wifi_name():
    manifest = (ROOT / f"{APP_ID}.yml").read_text()
    assert "--system-talk-name=org.freedesktop.NetworkManager" in manifest
    commit = re.search(r"- name: phosh-toolkit.*?commit: (\w+)", manifest, re.S)
    assert commit and len(commit.group(1)) == 40


def test_screenshot_actions_exist():
    release = (ROOT / "release.toml").read_text()
    main = (ROOT / "nauta" / "main.py").read_text()
    for action in re.findall(r'"app\.([a-z-]+)', release):
        assert f'"{action}"' in main, action


def test_stable_build_from_source_tree():
    assert nauta.APP_ID == APP_ID and not nauta.NIGHTLY
    assert nauta.VERSION_LABEL == nauta.VERSION
