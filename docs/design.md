---
type: Concept
title: Visual design
description: Stock libadwaita with Nauta's sea-teal accent, the screens at 360 px and on the desktop, and the review checklist.
tags: [design, accent, adaptive, libadwaita]
resource: ../nauta/style.css
generated: { by: claude-code/2.1.317, at: 2026-11-04T14:00:00Z }
---

Nauta follows the toolkit's [visual design](../../phosh-toolkit/docs/design.md)
and [adaptive UI](../../phosh-toolkit/docs/adaptive-libadwaita.md) rules.

# Accent

Sea teal `#127a8a` with white text (contrast 5.0:1), set only through
`--accent-bg-color`/`--accent-fg-color` in `style.css` (plus
`@define-color` for libadwaita 1.5 hosts)
([one accent per app](../../phosh-toolkit/docs/decisions/app-accent-colours.md)).
Light and dark follow the system; Preferences → General → Style offers
Follow System / Light / Dark (`phosh_toolkit.style`). The metainfo
branding colours are `#9fdde6` (light) and `#0d4f59` (dark).

# Screens

| Screen | Narrow (≤ 600 sp) | Wide |
|---|---|---|
| Library | Albums / Artists / Playlists in an `AdwViewStack`, switcher at the bottom (`AdwViewSwitcherBar`) | switcher in the header |
| Albums | two columns of cover cards (`GtkGridView`, recycled) | as many columns as fit |
| Album, playlist | cover 200 px, title, artist (button to the artist), details, Play and Shuffle, song list | same, clamped to 900 px |
| Artist | name, album cards with year | same |
| Search | search entry in the header; artists, albums, songs | same |
| Now Playing | cover, title, slider, controls, queue | clamped to 600 px |
| Find New Music | search entry in the header, YouTube Music / YouTube toggle and, for YouTube Music, Songs / Albums / Playlists (linked buttons, the second row in a revealer); songs with a download button, albums and playlists as rows that open their page; Downloads button in the header | clamped to 800 px |
| Album or playlist | title (`title-2`), details and song count (`dimmed`), "Download All" pill (`suggested-action`), songs with a download button each | clamped to 800 px |
| Downloads | MeTube's running and finished downloads with cancel / remove | clamped to 800 px |
| Set Up Downloads | intro, the connection form for MeTube, audio format, Connect | same |

Every page is pushed onto one `AdwNavigationView`, so the swipe back
closes it. The player bar sits below the navigation view, outside the
pages, and hides on Now Playing.

Covers are rounded (`.nauta-cover`, 8 px) on a faint tile until they
load; the placeholder is a symbolic icon. No Navidrome branding.

# Review checklist

Run the toolkit's checklist; for Nauta also: no horizontal scrolling at
360 px with long titles (labels ellipsize), the player bar does not
cover the last row (it is a bottom bar, not an overlay), icon-only
buttons (search, menu, play, next, previous) have tooltips and
accessible labels.
