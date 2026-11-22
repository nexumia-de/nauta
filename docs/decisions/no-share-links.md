---
type: Decision Record
title: No share links
description: Nauta does not create Navidrome share links (createShare): behind the owner's mutual TLS nobody else could open them, and making them work would open a public path past the client certificate.
tags: [decision, sharing, security, mtls, subsonic]
generated: { by: claude-code/2.1.330, at: 2026-11-22T12:00:00Z }
sources:
  - id: nd-api
    resource: https://github.com/navidrome/navidrome/blob/7c1e68a1e4e68e7257affba4f25cd9cb545c7016/server/subsonic/api.go
    title: Navidrome server/subsonic/api.go (share calls only with EnableSharing, 501 otherwise)
  - id: nd-public
    resource: https://github.com/navidrome/navidrome/blob/7c1e68a1e4e68e7257affba4f25cd9cb545c7016/server/public/public.go
    title: Navidrome server/public/public.go (public share pages under /share, ShareURL)
---

# Status

Accepted (2026-11-22). Decided by the agent while closing issue 36, the
"needs decision" question of whether sharing is wanted at all; the
owner asked for open issues to be decided by best practice.

# Context

Navidrome's `createShare` makes a public link to a song, album or
playlist. The share calls exist only when the server has
`EnableSharing` on; otherwise they answer 501[^nd-api]. The link points
to `<server>/share/<id>` (or to the host in `ShareURL`), a page that
plays without a login[^nd-public].

The owner reaches Navidrome away from home only through a reverse proxy
that asks for a client certificate ([connection](../connection.md)).
Anyone without that certificate gets no further than the TLS
handshake, so a share link would not open for the people it is sent
to.

# Decision

Nauta offers no Share action.

- A button whose links do not open for anyone but the owner would be a
  broken feature.
- Making them open needs a hole in the proxy: `/share/` (and its
  streams) without the client certificate, or a second public host via
  `ShareURL`. That puts a public, unauthenticated way into the music
  server next to a set-up whose point is that nothing is public.
- A server that wants share links can still make them in Navidrome's
  own web UI.

# Consequences

- No `createShare`, `getShares` or Share menu item in Nauta; issue 36
  is closed as not planned.
- Reconsider only for a server without mutual TLS where the owner
  turns on `EnableSharing` on purpose; then a "Copy Share Link" item
  in the song and album menus, shown only when the server answers the
  share calls, would be the small way to add it.
