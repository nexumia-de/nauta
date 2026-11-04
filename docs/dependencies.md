---
type: Reference
title: Bundled dependencies
description: Nauta bundles phosh-toolkit's shared package and the Noto Sans CJK font; everything else comes from the GNOME runtime.
tags: [dependencies, licensing, flatpak]
generated: { by: claude-code/2.1.317, at: 2026-11-04T20:10:00Z }
---

# Rules

The shared rules are in
[../../phosh-toolkit/docs/licensing.md](../../phosh-toolkit/docs/licensing.md).
CI fails if a module of `de.nexumia.Nauta.yml` is missing here or
installs no licence files.

# Modules

| Module | Version | Licence | Licence files |
|---|---|---|---|
| `phosh-toolkit` | commit `7d29bea` (nexumia-de/phosh-toolkit#34, until the next tag) | GPL-3.0-or-later (own code, same author) | `LICENSE` → `/app/share/licenses/<app id>/phosh-toolkit/` |
| `noto-cjk` | tag `Sans2.004`, `Sans/Variable/OTC/NotoSansCJK-VF.otf.ttc` | OFL-1.1 (read from the tag's `LICENSE`) | `LICENSE` → `/app/share/licenses/<app id>/noto-cjk/` |

Only `lib/phosh_toolkit/` is installed: the shared connection and
playback code ([shared connection](../../phosh-toolkit/docs/shared-connection.md)).
GPL-3.0-or-later code may be combined with Nauta's AGPL-3.0-or-later
(section 13 of both licences).

# Fonts

The GNOME 51 runtime ships Adwaita Sans, Cantarell, DejaVu, Liberation,
GNU FreeFont, Carlito, Caladea, TeX Gyre and Noto Color Emoji, but **no
font with Japanese, Chinese or Korean glyphs** (checked in
`org.gnome.Platform//51`, `files/share/fonts/`). Inside the Flatpak,
fontconfig also reads the host's `/usr/share/fonts` (as
`/run/host/fonts`), so CJK artist, album and track names showed only
where the host had such a font installed. Ephyra had the same gap on the
owner's phone (nexumia-de/ephyra#26).

Nauta therefore bundles Noto Sans CJK as the variable OpenType
collection (one file, about 33 MB, every weight; faces JP, KR, SC, TC
and HK, JP first). The runtime's fontconfig reads `/app/share/fonts`,
so Pango falls back to it for any CJK character the UI font lacks; no
CSS or code change is needed. The Japanese-only subset (about 8 MB)
would leave Chinese and Korean names as boxes. OFL-1.1 allows bundling
the font with any software; it may not be sold on its own and keeps its
name.

# From the runtime (not bundled)

`org.gnome.Platform//51` provides Python 3 and PyGObject, GTK 4,
libadwaita, libsoup 3 with glib-networking (GnuTLS) for mutual TLS,
libsecret and GStreamer with its plugins.

# Not used

No code or assets from Navidrome's repository (GPL-3.0); API facts were
read from its source ([Subsonic API](subsonic-api.md)).
