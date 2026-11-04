---
type: Playbook
title: Development environment
description: Hosts the cloud environment needs, host packages, and how to run, test, screenshot and build Nauta.
tags: [development, environment, hosts, testing]
generated: { by: claude-code/2.1.317, at: 2026-11-04T14:00:00Z }
---

# Hosts

Unreachable from the cloud environment on 2026-11-04 (proxy `403`):

| Host | Needed for |
|---|---|
| `www.navidrome.org` | Navidrome documentation |
| `opensubsonic.netlify.app` | OpenSubsonic API specification |
| `demo.navidrome.org` | Navidrome's public demo server, to check the client against a real server |
| `www.subsonic.org` | Original Subsonic API reference |

Workaround used: Navidrome's source is cloned with git
(`github.com/navidrome/navidrome`), which works. `dl.flathub.org`
answered on 2026-11-04, so the Flatpak can be built locally.

# Host packages (Ubuntu 24.04)

After `bash ../phosh-toolkit/setup.sh`:

```sh
sudo apt-get install gir1.2-soup-3.0 gir1.2-secret-1 gir1.2-gstreamer-1.0 \
  gstreamer1.0-plugins-good python3-pytest xvfb
```

The cloud image's default `python3` (3.13) has no `gi`; use
`/usr/bin/python3.12`.

# Run, test, screenshot

```sh
export PYTHONPATH=$PWD/../phosh-toolkit/lib                     # shared package
NAUTA_DEMO=$PWD/tests/data/demo /usr/bin/python3.12 -m nauta     # demo library
/usr/bin/python3.12 -m nauta                                      # real server
dbus-run-session -- xvfb-run -a /usr/bin/python3.12 -m pytest    # all tests, as in CI
../phosh-toolkit/scripts/screenshot.sh -i de.nexumia.Nauta -e NAUTA_DEMO=$PWD/tests/data/demo -e PYTHONPATH=$PYTHONPATH -o shot.png -- /usr/bin/python3.12 -m nauta
```

The tests find the shared package in the sibling checkout
`../phosh-toolkit` by themselves; CI checks out phosh-toolkit at the
commit the manifest pins (`tests.yml`).

`NAUTA_DEBUG=1` logs the route, proxy requests and playback.
`NAUTA_KEYRING=memory` keeps secrets in memory (tests, screenshots).
Screenshots of other states: `-a "app.show-view(1)"` (Artists),
`-a "app.show-album('<id>')"`, `-a "app.play-album('<id>')"`.
