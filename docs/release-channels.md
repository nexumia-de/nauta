---
type: Playbook
title: Release channels
description: Nauta (stable, from tags v<version>) and Nauta (Nightly) (de.nexumia.Nauta.Devel, from every push to main), automated releases with changelog fragments, and store screenshots from the demo library.
tags: [release, nightly, flatpak, ci, changelog, screenshots]
generated: { by: claude-code/2.1.317, at: 2026-11-04T14:00:00Z }
---

# Channels

| Channel | App | App id | Fed by |
|---|---|---|---|
| Stable | Nauta | `de.nexumia.Nauta` | tags `v0.1.0`, … |
| Nightly | Nauta (Nightly) | `de.nexumia.Nauta.Devel` | every push to `main` |

Both come from the shared repository `https://flatpak.nexumia.de/` once
`nexumia-de/nauta` is listed in phosh-apps' `apps.txt` (after the
first tag). Mechanics: the toolkit's
[Flatpak workflow](../../phosh-toolkit/docs/flatpak-workflow.md#release-channels)
and [releases](../../phosh-toolkit/docs/releases.md).

# Nightly variant

`-Dprofile=development` gives the app id `de.nexumia.Nauta.Devel`
(`nauta/config.py`, generated) and derives desktop file and metainfo
from `data/` with `sed` in `meson.build`; `-Dbuild_label` shows the
commit in the About dialog. The window gets the striped `devel` header
bar.

# Release

Every pull request users notice adds a fragment to `changelog.d/`;
the weekly release pull request writes them into the metainfo. The
first release, 0.1.0, is in the metainfo already: push the tag
`v0.1.0` after merging the first pull request, then add the repository
to phosh-apps.

# Screenshots

`release.toml` lists them; CI takes each at 360×720 and 1000×700,
light and dark, from the built Flatpak with `NAUTA_DEMO` pointing at
`tests/data/demo`: the app starts `nauta/demo.py` on 127.0.0.1 and is
signed in to it, with nothing stored. The demo server draws the covers
(gradients) and plays sine tones, so the repository holds no images or
audio. No network is used.

| Shot | State | Actions |
|---|---|---|
| `albums` | Albums | – |
| `album` | An album | `app.show-album('<id>')` |
| `now-playing` | Now Playing with the queue | `app.play-album('<id>')` |

The demo library (`tests/data/demo/library.json`, invented names, CC0)
was generated once with a script in the first pull request's session;
edit it by hand.
