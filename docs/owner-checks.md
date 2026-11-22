---
type: Plan
title: Owner checks
description: What only the owner can do or check (the phone, their Navidrome and MeTube, a toolkit tag), per closed issue, as short checklists.
tags: [plan, owner, on-device, checklist]
generated: { by: claude-code/2.1.330, at: 2026-11-22T12:00:00Z }
---

# How to use this list

Issues whose remaining work needs the real phone, the owner's server or
account, a secret or an upstream project were closed with everything
else done; what is left is here. Nothing below has been run by an agent.
Write the result into the linked doc and tick the box (or delete the
section) in the same commit.

# Battery and CPU while streaming (#7)

On the phone, screen off, with the Flatpak from the latest release.
Four runs of one hour each: Wi-Fi and mobile data, each at "Original"
and at 192 kbit/s (Preferences → Playback). Before each run: charger
off, battery above 80 %, nothing else playing.

- [ ] Battery before and after each run:

  ```sh
  cat /sys/class/power_supply/*/capacity
  ```

- [ ] CPU time of Nauta's process at the end of each run (`TIME` column;
  divide by 3600 s for the average share of one core):

  ```sh
  ps -eo pid,time,args | grep -i [n]auta
  ```

- [ ] Write the table (route, quality, battery drop, CPU time) into
  [playback](playback.md#battery-and-cpu); if "Original" over mobile data
  costs clearly more than 192 kbit/s, lower the "Away" default there and
  in `nauta/settings.py` (`quality_away`).

# Gapless playback (#8)

Needs a change in phosh-toolkit, where the shared player lives; the
design is in [playback](playback.md#gapless-playback-8).

- [ ] Have the toolkit's `media.Media` take a next URI and switch to it on
  playbin3's `about-to-finish` (an issue or task in phosh-toolkit), then
  tag a toolkit release.
- [ ] Then, in Nauta: pin that tag, queue the next song's proxy URL from
  `player.py` as described in playback, with the test described there.
- [ ] On the phone: a live album or DJ mix plays through without a gap
  at the song changes, at home and away.

# API key sign-in (#12)

Built and tested against the demo server; not tried against a real
Navidrome.

- [ ] In Navidrome's web UI, "Players & API keys": generate a key for a
  player and copy it.
- [ ] In Jukebox, sign out (Preferences), connect, switch on "Sign In
  With an API Key", enter the user name and the key: the library shows.
- [ ] Restart Jukebox: still signed in. Revoke the key in Navidrome:
  the next action shows the setup page.
