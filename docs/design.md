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
| Albums header | sort button (`view-sort-descending-symbolic`) beside the main menu, Albums view only | same |
| Playlists | Liked Songs and New Playlist rows, then the playlists (`boxed-list`) | clamped to 800 px |
| Album, playlist | cover 200 px, title, artist (button to the artist), details; star (album), Play and Shuffle pills, "⋮" in one row; song list with "⋮" per row | same, clamped to 900 px |
| Liked Songs | star placeholder as cover, Play and Shuffle, songs, liked albums and artists | same |
| Artist | name (`title-1`), star and Artist Radio pill, Popular (5 songs), album cards with year, Fans Also Like | same |
| Search | search entry in the header; artists, albums, songs | same |
| Now Playing | cover, title and artist left-aligned with the star, slider, shuffle / previous / play / next / repeat (active modes in the accent colour), sleep timer note, Next Up with Clear; Lyrics and "⋮" in the header | clamped to 600 px |
| Lyrics | lines as `title-4`, dimmed; the current line in the accent colour | clamped to 700 px |
| Add to Playlist | `AdwDialog` (bottom sheet on phones): New Playlist…, the editable playlists | 420×520 |
| Find New Music | search entry in the header, YouTube Music / YouTube toggle and, for YouTube Music, Songs / Albums / Playlists (linked buttons, the second row in a revealer); songs with a download button, albums and playlists as rows that open their page; Downloads button in the header | clamped to 800 px |
| Album or playlist | title (`title-2`), details and song count (`dimmed`), "Download All" pill (`suggested-action`), songs with a download button each | clamped to 800 px |
| Downloads | MeTube's running and finished downloads with cancel / remove | clamped to 800 px |
| Set Up Downloads | intro, the connection form for MeTube, audio format, Connect | same |

Every page is pushed onto one `AdwNavigationView`, so the swipe back
closes it. The player bar sits below the navigation view, outside the
pages, and hides on Now Playing.

Song rows: "⋮" (`view-more-symbolic`, flat) at the end; a long press
or right click opens the same `GtkPopoverMenu`. Swiping a row right to
left uncovers an icon on `.nauta-swipe` (accent background); see
[library features](library.md#swipe-swipepy).

Covers are rounded (`.nauta-cover`, 8 px) on a faint tile until they
load; the placeholder is a symbolic icon. No Navidrome branding.

# Review checklist

Run the toolkit's checklist; for Nauta also: no horizontal scrolling at
360 px with long titles (labels ellipsize), the player bar does not
cover the last row (it is a bottom bar, not an overlay), icon-only
buttons (search, menu, play, next, previous) have tooltips and
accessible labels.
