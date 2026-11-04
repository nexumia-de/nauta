"""Nauta: music from your Navidrome server on Phosh phones."""

try:
    from nauta.config import APP_ID, BUILD_LABEL
except ImportError:  # run from the source tree, config.py is not built
    APP_ID = "de.nexumia.Nauta"
    BUILD_LABEL = ""
VERSION = "0.1.0"
# The nightly app is built from every push to main
# (docs/release-channels.md).
NIGHTLY = APP_ID.endswith(".Devel")
NAME = "Nauta (Nightly)" if NIGHTLY else "Nauta"
# About dialog, e.g. "0.1.0 (main · 8534d2c)" for a nightly build.
VERSION_LABEL = f"{VERSION} ({BUILD_LABEL})" if BUILD_LABEL else VERSION
REPO_URL = "https://github.com/nexumia-de/nauta"
# Voluntary support for development (phosh-toolkit docs/support.md).
SUPPORT_URL = "https://liberapay.com/suitably"
# Sent with every HTTP request.
USER_AGENT = f"Nauta/{VERSION} (+{REPO_URL})"
# Client name ("c") in every Subsonic request; Navidrome shows it under
# players.
CLIENT_NAME = "Nauta"
