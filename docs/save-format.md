---
status: compatibility-pointer
canonical: docs/d2s_format.md
last_updated: 2026-05-09
---

# D2R `.d2s` Save Format Reference

`docs/d2s_format.md` is the authoritative public save-format reference for
this repo.

This file is kept only for older links and agent prompts that still mention
`docs/save-format.md`. Do not add new format knowledge here; update
`docs/d2s_format.md` instead.

The former duplicate reference was retired because it overlapped with the
canonical document and carried stale version, follower-tail, and merc-status
wording. The current material that was still useful has been folded into
`docs/d2s_format.md`, especially:

- item bit-order and item-record invariants
- socketed sub-item counting rules
- item property-list encoding rules
- checksum and write invariants
- current follower, bound-demon, merc-status, and Iron Golem findings

For validation and live-save safety rules, also read `AGENTS.md`, `CLAUDE.md`,
and the hub docs under `../docs/`.
