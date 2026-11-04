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

`music.youtube.com` and `www.youtube.com` were allowed by the owner on
2026-11-04 and answer. But YouTube Music **does not serve its licensed
catalogue to the cloud container**. Song and album searches answer "No
results", even with `gl: DE` and a visitor id. Album pages come back
empty, and an artist page lists no albums. Only videos, artists,
podcasts, profiles and community playlists come through. So album search
and album resolution can only be checked on the phone (#22).

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

# UI tests and animations

The UI tests switch GTK's animations off (`tests/conftest.py`). On CI's
xvfb with software rendering, an animated spinner (a loading page)
redraws so slowly that GTK's frame source is always ready; it outranks
the idle callbacks through which `phosh_toolkit.tasks` delivers worker
results, so a dialog stayed on its spinner for 30 s (found 2026-11-04,
measured as a main context busy in 200 of 200 iterations; locally 12–72
of 300). Whether a slow phone can show the same delay is not known.
