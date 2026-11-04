---
type: Concept
title: Connection, home network, client certificates and the password
description: How Nauta picks the local address on a listed home Wi-Fi and the remote address elsewhere, presents a client certificate, keeps the password in the keyring and sends it only in request bodies.
tags: [connection, network, mtls, tls, keyring, security, subsonic]
resource: ../nauta/connection.py
generated: { by: claude-code/2.1.317, at: 2026-11-04T14:00:00Z }
---

The route, client certificates, connection form, keyring and media
proxy are phosh-toolkit's `phosh_toolkit` package, shared with Ephyra:
[shared connection and playback](../../phosh-toolkit/docs/shared-connection.md).
This file keeps what is Nauta's.

# The owner's setup

One Navidrome server, reachable at home on the LAN and elsewhere through
a public URL behind a reverse proxy that requires a **client
certificate** (mutual TLS). The existing Linux clients can't present
one; that is why Nauta exists.

# Route: strict about the local address

Jellyfin answers who it is without credentials (a server id), so Ephyra
can check that the local address is really its server before sending
the token. The Subsonic API has **no such id**
([Subsonic API](subsonic-api.md)), and every request carries
credentials. A stranger's server at the local address would get the
user name and a salted token, which it could replay.

So Nauta's `Connection` sets `strict_local`: the local address is
tried **only when NetworkManager reports a Wi-Fi from the home list**.
Without a list, without NetworkManager access, or on any other network
Nauta uses the remote address only.

| Situation | Tried in order |
|---|---|
| On a listed home Wi-Fi | local, then remote |
| Other Wi-Fi, mobile data | remote only |
| No home list, or NetworkManager not reachable | remote only |

The probe is `getOpenSubsonicExtensions` (no credentials): the server
must answer as an OpenSubsonic server with the `formPost` extension,
or setup stops with "Nauta needs an OpenSubsonic server such as
Navidrome".

# Proxy login

Some reverse proxies have their own login in front of Navidrome
(Pangolin's resource authentication, Authelia, Authentik, …). The owner's
proxy sets it for all resources: mutual TLS worked, then the proxy
answered `401 Unauthorized` (2026-11-04). The toolkit detects this and
shows the proxy's login page in a web view
([proxy login](../../phosh-toolkit/docs/shared-connection.md#proxy-login-proxy_login)):

- during setup, from the connection form;
- later, when the proxy's session runs out: the router's `proxy-login`
  signal opens the page from the window (`Window._on_proxy_login`), and
  the app is not signed out of Navidrome.

The proxy's cookies are kept in the keyring (kind `proxy-cookies`) and
loaded by `Connection`; they go only to the server's address, also for
playback through the media proxy.

## Proxy user name and password instead (HTTP Basic)

A proxy session ends (Pangolin: after 30 days by default), and with it
comes the login page again. Pangolin's **header authentication** (HTTP
Basic per resource) avoids that: the form's "Proxy Login" row takes a
user name and password once, the keyring keeps them (kind
`proxy-credentials`), and every request to the remote address carries
them, streams too
([toolkit](../../phosh-toolkit/docs/shared-connection.md#http-basic-auth-at-the-proxy-proxycredentials),
[decision and security trade-off](../../phosh-toolkit/docs/decisions/proxy-basic-auth.md)).

- Works for Navidrome because the Subsonic credentials are in the body:
  Pangolin passes the `Authorization` header on, and Navidrome's
  Subsonic API does not read it (`server/subsonic`, commit `7c1e68a`).
- Only with Platform SSO **off** and "extended compatibility" on does
  Pangolin answer a missing or wrong header with a Basic challenge; then
  setup expands "Proxy Login" and marks it, and later the window says to
  check it in Preferences → Connection. With SSO on (the owner's setup)
  Pangolin redirects to its login page instead (code read at `9af8dad`,
  `verifySession`): the web view appears, and "Proxy Login" is opened by
  hand. Browsers keep their SSO login either way.
- Owner's side in Pangolin: in the resource policy of Navidrome and
  MeTube, turn on "Basic header authentication" with a user name and
  password made for the phone only (random, from the password manager);
  keep Platform SSO and mTLS on. A policy's header auth counts for all
  its resources; separate pairs per resource need separate policies. In
  Nauta, open "Proxy Login" in the connection form and enter the pair.
  On a lost phone: change it and block the phone's client certificate.

# Sign-in and the password

- Setup checks the addresses and the certificate (toolkit form), then
  the sign-in page asks for user name and password and checks them with
  `ping`.
- Token authentication needs the **password itself** on the client
  (`t = md5(password + salt)`), so it is stored in the keyring
  (libsecret, schema `de.nexumia.Nauta`, attribute `kind` =
  `password`); in the Flatpak through the Secret portal.
- Every request is a `POST` with `u`, `t`, `s` in the form body and
  a fresh salt each time; the password itself never leaves the phone
  ([decision](decisions/form-post-credentials.md)).
- An error 40/41/44 signs out: the password is forgotten and the setup
  page shows, with a toast.
- The account file `$XDG_CONFIG_HOME/nauta/account.json` holds
  addresses, home networks, user name, server type and version,
  qualities and style; never the password.

# Verified (2026-11-04, cloud container)

`tests/test_api.py` and `tests/test_ui.py` against `nauta/demo.py`,
also over real mutual TLS with `openssl`-made certificates: refused
without the certificate, works with PKCS #12; credentials only in the
body with a fresh salt; the strict route at home, away, without
NetworkManager and without a list; a wrong password signs out. Not yet
against a real Navidrome or the owner's proxy (M1).
