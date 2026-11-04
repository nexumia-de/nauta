@../phosh-toolkit/AGENTS.md

# Nauta

Music client for [Navidrome](https://www.navidrome.org/) (and other
OpenSubsonic servers) on Phosh phones and the desktop. The shared rules
in ../phosh-toolkit/AGENTS.md apply as well.

- App id: `de.nexumia.Nauta`.
- Plan: work items are [issues](https://github.com/nexumia-de/nauta/issues)
  in [milestones](https://github.com/nexumia-de/nauta/milestones); goals
  per milestone are in [docs/roadmap.md](docs/roadmap.md). Work on the
  issues of the current milestone first; do not start later milestones
  without asking.
- Connection: local address on the owner's home Wi-Fi, remote address
  elsewhere, the remote one behind mutual TLS. Read
  [docs/connection.md](docs/connection.md) before touching
  `connection.py`, `api.py` or `setup.py`. The HTTP client, route, client
  certificates, connection form, media proxy and player are shared with
  Ephyra in phosh-toolkit's `phosh_toolkit` package
  ([shared connection](../phosh-toolkit/docs/shared-connection.md));
  change them there.
- The password is a secret: keep it in the keyring, never in a settings
  file, a log line or a URL. Every API request is a `POST` with the
  credentials in the form body (OpenSubsonic `formPost`); the player
  gets only local proxy URLs.
- API facts come from Navidrome's source (`github.com/navidrome/navidrome`,
  `server/subsonic/`) at a recorded commit:
  [docs/subsonic-api.md](docs/subsonic-api.md). Navidrome's and the
  OpenSubsonic websites are blocked in the cloud environment
  ([dev environment](docs/dev-environment.md)).
- Never use Navidrome's logo or present the app as official. "Navidrome"
  may appear only to say what the app works with.
- Screenshots and UI tests use the demo library (`NAUTA_DEMO`,
  `nauta/demo.py`, `tests/data/demo`), never a real server.
- Send a descriptive `User-Agent` (`Nauta/<version> (+repo URL)`) with
  every HTTP request.
- Run PyGObject code with `/usr/bin/python3.12` on the cloud host; the
  default `python3` has no `gi`.
