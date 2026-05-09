# Agent Instructions for d2r-horadric-tools

This is the public-safe D2R tooling repo. It should remain publishable at all
times.

For whole-project context, read the hub docs in `../`:

- `../D2R-PROJECT.md`
- `../docs/status.md`
- `../docs/public-private-boundary.md`
- `../docs/validation-ladder.md`

For D2R-specific save and modding rules, read `CLAUDE.md` in this repo. Treat
those rules as binding for Codex too.

## Public Repo Boundary

Allowed here:

- public-safe source code
- synthetic fixtures
- sanitized `.d2s` layout findings
- aggregate corpus statistics
- MCP tools and agent workflows
- tests and docs that can be published

Not allowed here:

- private `.d2s` saves or raw corpora
- Steam userdata or Proton compatdata paths as committed fixtures
- raw memory dumps or live process captures
- recovered private source
- machine-local calibration data
- secrets or account identifiers

## `.d2s` Work Rules

- Never rebuild a `.d2s` from scratch when targeted edits are possible.
- Back up before live save writes.
- Write to staging/temp files first.
- Run the scanner after every edit phase.
- Verify checksums and file-size fields.
- Do not stack risky edits before testing.
- Scanner hard errors block deployment unless disproven with bit-level evidence.

## Validation Commands

Use the narrowest command that proves the change:

```bash
python3 -m pytest
python3 -m d2r_chargen validate <name>
python3 -m d2r_chargen build <name> --force
python3 -m d2r_chargen scan <name>
python3 tools/d2s_corpus_scan.py <paths> --examples 5
d2r-mod build
d2r-mod diff --summary
```

## Agent Workflow

For architecture-sensitive tasks:

1. State the lane and non-goals.
2. Write or update the plan before editing.
3. Make bounded changes.
4. Run validation.
5. Update the relevant doc if the project state changed.

If working in parallel with other agents, own a disjoint file/module set and do
not revert unrelated changes.

Before final handoff on meaningful work, run the hub closeout script from the
project root:

```bash
cd .. && ./scripts/agent_session_close.sh
```

If the script flags docs, validation, or boundary updates, handle those before
the final response.
