# Nauta

Latin for *sailor*, a nod to Navidrome.

Adaptive GTK4/libadwaita music client for
[Navidrome](https://www.navidrome.org/) and other OpenSubsonic servers
on [Phosh](https://phosh.mobi/) phones and the desktop: albums, artists,
playlists and search, a play queue, and a player bar that stays at the
bottom while you browse.

- **Home and away**: on your home Wi-Fi Nauta talks to the server's
  local address; everywhere else it uses the public one.
- **Client certificates**: servers behind mutual TLS work with a
  PKCS #12 (`.p12`) or PEM certificate.
- **Password stays private**: kept in the keyring, sent only in request
  bodies, never in a URL.
- **Phone-friendly streaming**: separate quality limits at home and
  away; the server converts above them.

Status: first version (milestone M0), not yet tested on a phone. See
the [milestones](https://github.com/nexumia-de/nauta/milestones) and
[docs/roadmap.md](docs/roadmap.md).

Nauta is an independent project and not affiliated with the Navidrome
project.

## Install

After the first release, on the phone open <https://flatpak.nexumia.de/>
and tap Nauta; GNOME Software installs it and keeps it updated.
*Nauta (Nightly)* follows every push to `main`. See
[docs/release-channels.md](docs/release-channels.md).

## Support

Nauta is free for everyone. If you want to support its development
and more free apps, you can do so on
[Liberapay](https://liberapay.com/suitably). What the money pays for
and which fees each platform takes:
[support](https://github.com/nexumia-de/phosh-toolkit/blob/main/docs/support.md).

## Development

This repository uses
[phosh-toolkit](https://github.com/nexumia-de/phosh-toolkit), checked out
next to it; its shared Python package `phosh_toolkit` is part of the app:

```
workspace/
  phosh-toolkit/
  nauta/
```

```sh
[ -d phosh-toolkit ] || git clone https://github.com/nexumia-de/phosh-toolkit.git
bash phosh-toolkit/setup.sh
```

Run with `PYTHONPATH=../phosh-toolkit/lib python3 -m nauta` (or with the
demo library: add `NAUTA_DEMO=$PWD/tests/data/demo`), test with
`xvfb-run -a python3 -m pytest`. Details:
[docs/dev-environment.md](docs/dev-environment.md).

Agent rules: [AGENTS.md](AGENTS.md). Knowledge bundle:
[docs/index.md](docs/index.md).

## License

GNU Affero General Public License v3.0 or later
(`AGPL-3.0-or-later`), see [LICENSE](LICENSE). Why:
[license decision](docs/decisions/license.md). Contributions are
accepted only under the terms in [CONTRIBUTING.md](CONTRIBUTING.md).
