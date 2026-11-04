---
type: Decision Record
title: AGPL-3.0 license
description: Nauta is AGPL-3.0-or-later like Cirro and Ephyra, with the same contributor terms.
tags: [decision, license]
generated: { by: claude-code/2.1.317, at: 2026-11-04T14:00:00Z }
---

# Status

Accepted (2026-11-04), following the owner's choice for Cirro and
Ephyra.

# Decision

`AGPL-3.0-or-later`, contributions under the terms in
`CONTRIBUTING.md` (the author may relicense). AppStream metadata and
the demo library are CC0-1.0.

# Consequences

Nauta talks to Navidrome only over its HTTP API and copies no code
from Navidrome (GPL-3.0). phosh-toolkit's package (GPL-3.0-or-later)
combines with it ([dependencies](../dependencies.md)).
