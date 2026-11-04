---
type: Reference
title: Bundled dependencies
description: Nauta bundles only phosh-toolkit's shared package; everything else comes from the GNOME runtime.
tags: [dependencies, licensing, flatpak]
generated: { by: claude-code/2.1.317, at: 2026-11-04T14:00:00Z }
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

Only `lib/phosh_toolkit/` is installed: the shared connection and
playback code ([shared connection](../../phosh-toolkit/docs/shared-connection.md)).
GPL-3.0-or-later code may be combined with Nauta's AGPL-3.0-or-later
(section 13 of both licences).

# From the runtime (not bundled)

`org.gnome.Platform//51` provides Python 3 and PyGObject, GTK 4,
libadwaita, libsoup 3 with glib-networking (GnuTLS) for mutual TLS,
libsecret and GStreamer with its plugins.

# Not used

No code or assets from Navidrome's repository (GPL-3.0); API facts were
read from its source ([Subsonic API](subsonic-api.md)).
