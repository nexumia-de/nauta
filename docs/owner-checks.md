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

# Pasted YouTube links (#42)

Tested with the MeTube stand-in only.

- [ ] Which link the "does nothing useful" report came from (Share
  button = `youtu.be/…`?); if it was another form, note it in
  [finding new music](downloads.md#search) and the tests.
- [ ] On the phone, paste a `youtu.be` link and a YouTube Music song
  link into Find New Music: one "Pasted Link" row each; Download puts
  the song into MeTube and later into Navidrome.

# Album and playlist search on the phone (#22)

Song search was confirmed on the phone on 2026-11-06. With the owner's
MeTube, in Find New Music on YouTube Music:

- [ ] Albums and Playlists filters: results with title and the
  "Album • Artist • Year" line. Note the system language (`hl`).
- [ ] Opening an album and a playlist lists its songs.
- [ ] "Download All" on an album: every song queued in MeTube, track
  numbers set, the album appears in Navidrome. Note the folder MeTube
  used (`OUTPUT_TEMPLATE_PLAYLIST`).
- [ ] Downloading a single song from an album page.
- [ ] Pasting an album link (`…/browse/MPREb_…`) and a playlist link
  opens the album or playlist page.
- [ ] If YouTube Music answers differently than
  [finding new music](downloads.md#search) describes, note the
  difference there; the parser is `nauta/ytmusic.py`.

# Adopt phosh-toolkit v0.7.0

nexumia-de/phosh-toolkit#59 (not merged on 2026-11-22) prints the
stacks of all threads when `phosh_toolkit.testing.run_until` times out,
so a UI test that hangs in CI shows where (toolkit #27). Nauta's tests
already call that function (`tests/conftest.py`), so the pin alone
brings it. Nauta may only pin a tag, so this waits for `v0.7.0`.

- [ ] Merge phosh-toolkit#59 and create the tag `v0.7.0`.
- [ ] Then (an agent can do this in one pull request): in
  `de.nexumia.Nauta.yml` set the `phosh-toolkit` source to
  `tag: v0.7.0` with its commit, and pin the three reusable workflows
  in `.github/workflows/` (`flatpak.yml`, `release.yml`,
  `update-check.yml`) to that commit with `# v0.7.0`, as the toolkit's
  `docs/toolkit-usage.md` describes at that tag. Record it in
  [dependencies](dependencies.md) and the log.
- [ ] If that pull request switches the required Flatpak check to
  `flatpak / Flatpak OK` in `.github/rulesets/main.json`, import the
  ruleset again in the repository settings.
