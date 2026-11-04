---
okf_version: "0.2"
---

# Nauta knowledge bundle

[Open Knowledge Format](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)
(OKF v0.2) bundle of this app. Shared Phosh knowledge lives in
[../../phosh-toolkit/docs/index.md](../../phosh-toolkit/docs/index.md).
Change history is in [log.md](log.md).

# Plan

* [Roadmap](roadmap.md) - Goals and exit criteria of the milestones; the work items are GitHub issues.

# Design

* [Visual design](design.md) - Stock libadwaita with Nauta's sea-teal accent, the screens and the player bar, with a review checklist.
* [Connection](connection.md) - Local address only on a listed home Wi-Fi, remote address elsewhere, client certificates, password in the keyring and in request bodies only.
* [Playback](playback.md) - Play queue, streaming through the local media proxy as POST, quality per route, scrobbling.
* [Subsonic API](subsonic-api.md) - The calls Nauta uses, read from Navidrome's source at a recorded commit.

# Development

* [Bundled dependencies](dependencies.md) - Only phosh-toolkit's shared package; everything else comes from the GNOME runtime.
* [Release channels](release-channels.md) - Stable from tags, nightly from main, releases and store screenshots from the demo library.
* [Development environment](dev-environment.md) - Blocked hosts, host packages, how to run, test, screenshot and build.

# Decision records

* [Decisions](decisions/index.md) - Name, licence, credentials in form bodies.
