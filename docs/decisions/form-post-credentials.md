---
type: Decision Record
title: Credentials in form bodies
description: Nauta signs every Subsonic request with a salted token in a POST body, keeps the password in the keyring, and uses the local address only on listed home Wi-Fi networks.
tags: [decision, security, authentication, subsonic]
generated: { by: claude-code/2.1.317, at: 2026-11-04T14:00:00Z }
---

# Status

Accepted (2026-11-04).

# Context

Subsonic clients usually put `u`, `t` and `s` (or the password) into
every URL, including stream URLs. Those land in reverse-proxy access
logs and in the player. Subsonic also has no public server id, so a
client can't check who it talks to before sending credentials
([Subsonic API](../subsonic-api.md)).

# Decision

- Every call is a `POST` with the parameters and `u`, `t`, `s` in
  the form body (OpenSubsonic `formPost`, which Navidrome supports);
  a fresh salt per request. Streams too: the local media proxy forwards
  the player's GET as POST.
- Token authentication needs the password on the client; it is kept in
  the keyring, never in a file, log line or URL.
- Servers without `formPost` are refused at setup.
- The local address is used only on a home Wi-Fi from the list that
  NetworkManager reports (`Router.strict_local`).

# Alternatives

- **API key** (`apiKey`, OpenSubsonic `apiKeyAuthentication`):
  avoids storing the password, but the key is as replayable as a token
  and must be created on the server first. Planned as a sign-in option
  (M2).
- **Reverse-proxy authentication** (the proxy maps the client
  certificate to a user header): no password at all, but needs proxy
  and Navidrome configuration; documented as an idea for the owner.

# Consequences

Credentials appear in no URL. A server that copies Subsonic without
`formPost` does not work with Nauta.
