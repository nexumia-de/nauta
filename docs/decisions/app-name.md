---
type: Decision Record
title: App name Nauta
description: The code name is Nauta, Latin for sailor; app id de.nexumia.Nauta. The visible name is Jukebox.
tags: [decision, name]
generated: { by: claude-code/2.1.317, at: 2026-11-04T14:00:00Z }
---

# Status

Accepted (2026-11-04) by the owner, who created `nexumia-de/nauta`.
The visible name **Jukebox** was chosen by the owner on 2026-11-06
(issue #26), from the suggestions Music Stream, Jukebox, Music and
Nauta, under the toolkit decision
[code names and visible names](../../../phosh-toolkit/docs/decisions/app-names.md).

# Decision

*Nauta* is Latin for "sailor": a nod to Navidrome (*navis*, ship)
without using its name, short and easy to say. App id
`de.nexumia.Nauta`, Python package and command `nauta`, repository
`nexumia-de/nauta`. The other candidate was *Celeusma*, the
boatswain's rowing chant.

Users see **Jukebox**: the `.desktop` `Name`, the metainfo `<name>`, the
window title, the About dialog, the welcome page, MPRIS `Identity`
(Phosh's media widget) and the texts that name the app; the nightly
build says "Jukebox (Nightly)". `GenericName` is "Music Player" and the
keywords include `nauta` and `navidrome`. The Subsonic client name
(`c=Nauta`), the MPRIS bus name, the keyring labels and the
`User-Agent` keep the code name.

# Consequences

Whether the code name is free on Flathub was not checked. On 2026-11-06
Flathub's search had no app named "Jukebox".
