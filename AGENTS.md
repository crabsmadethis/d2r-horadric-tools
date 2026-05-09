# Agent Instructions for d2r-horadric-tools

This is a public D2R tooling repository. Keep every committed file useful to a
GitHub reader who only has this repo.

## Read First

Before editing, read:

- `README.md`
- `CONTRIBUTING.md`
- `CLAUDE.md`
- `docs/d2s_format.md` for save-format work

## Public Repo Standard

GitHub-facing docs should be product, API, format, or contributor docs. Do not
commit internal planning scratchpads, agent orchestration notes, disposable
test-session logs, machine-specific paths, or project-hub assumptions.

Public docs may include:

- source-code behavior
- CLI and MCP usage
- synthetic fixtures and examples
- sanitized save-format findings
- repeatable validation commands
- known limitations and remaining research questions

Public docs should not include:

- personal save files or raw save corpora
- machine-local paths or account identifiers
- internal project lanes or recovered-source references
- low-level research planning unrelated to this public toolkit
- one-off probe queues or live-session diary entries
- claims about GitHub state that have not been verified against the remote

If a local manual validation result matters, summarize the stable technical
finding and put the reusable procedure in `docs/manual-save-validation.md`.

## `.d2s` Work Rules

- Never rebuild a `.d2s` from scratch when targeted edits are possible.
- Back up before writing local save files.
- Write to staging/temp files first.
- Run the scanner after every edit phase.
- Verify checksums and file-size fields.
- Do not stack risky edits before testing.
- Scanner hard errors block deployment unless disproven with bit-level evidence.

## Validation Commands

Use the narrowest command that proves the change:

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

## Handoff

Before opening or updating a PR, run the public hygiene check and record the
tests you ran. If a change needs local game data, fixtures, or manual game
validation, say so explicitly and keep those artifacts out of the repo.
