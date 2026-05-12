# Agent Instructions

This is a public Diablo II: Resurrected tooling repository. Keep every change
usable by a GitHub reader who has only this repo and their own local D2R
install.

## Read First

Before editing, read the files relevant to the task:

- `README.md`
- `CONTRIBUTING.md`
- `CLAUDE.md`
- `docs/d2s_format.md` for save-format work
- `d2r_mcp/README.md` for MCP tool changes

## Public Boundary

Committed content must be public-safe. Do not add:

- personal `.d2s` saves or raw save corpora
- raw memory dumps or live process captures
- machine-local paths, account identifiers, tokens, or secrets
- extracted Blizzard game data
- internal planning notes, disposable probe queues, or live-session diaries
- recovered private source or references that require private repositories to
  understand this project

Public docs may include source behavior, CLI and MCP usage, synthetic fixtures,
sanitized binary-layout findings, repeatable validation commands, known
limitations, and open research questions that belong to this public toolkit.

If local manual validation matters, record the stable technical result and a
repeatable public procedure. Leave private artifacts and machine-specific
details out of the repo.

## Save-File Rules

For `.d2s` work:

- Prefer targeted edits over rebuilding a save from scratch.
- Back up before writing any local save file.
- Write to temp or staging files first.
- Run the scanner after every edit phase.
- Verify checksums and file-size fields.
- Promote only after validation passes.
- Do not stack risky edits before scanning.
- Treat scanner hard errors as deployment blockers unless bit-level evidence
  proves the scanner is wrong.

Use repo-generated data modules for D2R constants. Do not use web research as
the source of truth for item UIDs, item codes, stat encoding, runeword indices,
or skill IDs.

## MCP Rules

MCP tool changes require synchronized docs and tests. If you add, remove,
rename, or change a tool in `d2r_mcp/`, update:

- `d2r_mcp/README.md` with the current tool count and tool behavior.
- Root `README.md` if its MCP tool count is now stale.
- `tests/test_mcp_*.py`.

Mutation tools must enforce the same backup, scan, and promote pipeline as
`d2r_chargen_build`.

## Validation Commands

Use the narrowest command set that proves the change:

```bash
python tools/public_hygiene_check.py
ruff check .
python -m pytest
python -m d2r_chargen validate <name>
python -m d2r_chargen build <name> --force
python -m d2r_chargen scan <name>
python tools/d2s_corpus_scan.py <paths> --examples 5
d2r-mod build
d2r-mod diff --summary
```

For fixture-light CI parity:

```bash
pytest tests/ -v --timeout=60 \
  -m "not integration and not slow and not e2e and not smoke" \
  --ignore=tests/fixtures/ \
  --ignore=tests/test_chargen.py \
  --ignore=tests/test_decoder.py \
  --ignore=tests/test_fixtures.py \
  --ignore=tests/test_importer.py
```

If a change requires local game data, Offline game validation, or private
fixtures, state that limit in the handoff and keep those artifacts out of the
repo.

## Handoff

Before handing off a meaningful change:

- Run `python tools/public_hygiene_check.py`.
- Run the relevant tests or explain why they were not run.
- Summarize save-file safety impact when `.d2s` writes are involved.
- For MCP changes, confirm the README and `tests/test_mcp_*.py` updates.
- Report only verified GitHub branch, PR, or release state.
