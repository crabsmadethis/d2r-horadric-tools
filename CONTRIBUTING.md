# Contributing to Horadric Tools

Horadric Tools is a Linux-first Python toolkit for offline Diablo II:
Resurrected save-file and data-mod workflows. Contributions should keep the
repository useful to someone who has only the public GitHub project, a local D2R
install, and the commands documented here.

## Project Scope

- Python 3.11+; CI currently covers Python 3.11 and 3.12.
- Linux and Steam Deck are the primary targets. Windows path detection exists
  but is not the main test surface.
- The repo supports CLI and MCP users. Treat command flags, tool schemas,
  error messages, and README examples as public interfaces.
- Do not commit extracted game data, personal saves, raw save corpora, machine
  paths, account identifiers, local validation logs, or private research notes.
- `d2r_chargen/data/*.py` files are generated locally from a D2R install and
  are ignored, except for tracked template/support files already in the repo.

## Setup

```bash
git clone https://github.com/crabsmadethis/d2r-horadric-tools.git
cd d2r-horadric-tools
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Generate local lookup data when you need game-data-backed commands or tests:

```bash
d2r-mod extract
d2r-mod extract --game-dir "/path/to/Diablo II Resurrected"
```

The core test suite should still run without a D2R install.

## Validation

Run the narrowest set that proves the change. For most PRs, start with:

```bash
python tools/public_hygiene_check.py
ruff check .
python -m pytest
```

The CI-equivalent fixture-light set is:

```bash
python tools/public_hygiene_check.py
ruff check .
pytest tests/ -v --timeout=60 \
  -m "not integration and not slow and not e2e and not smoke" \
  --ignore=tests/fixtures/ \
  --ignore=tests/test_chargen.py \
  --ignore=tests/test_decoder.py \
  --ignore=tests/test_fixtures.py \
  --ignore=tests/test_importer.py
```

Use targeted commands for affected workflows:

```bash
python -m d2r_chargen validate <name>
python -m d2r_chargen build <name> --force
python -m d2r_chargen scan <name>
python tools/d2s_corpus_scan.py <paths> --examples 5
d2r-mod build
d2r-mod diff --summary
```

Test markers are defined in `pyproject.toml`:

| Marker | Requirement |
| --- | --- |
| unmarked | Pure Python; suitable for CI |
| `smoke` | Lightweight checks that may touch generated data |
| `slow` | CASC I/O |
| `integration` | Local D2R files |
| `e2e` | Running D2R instance |

Mark new tests honestly. Tests that require local game data, save fixtures, or
manual D2R validation must not block the default CI path.

## Code Standards

- Match the surrounding code style: 4-space indents, type hints where the
  module already uses them, and small focused functions.
- Avoid comments that restate obvious code. Add comments only for non-obvious
  format rules, binary-layout decisions, or safety constraints.
- Keep dependencies minimal. Add new runtime or dev dependencies to
  `pyproject.toml` and explain the need in the PR.
- `ruff check .` is intentionally configured as a narrow bug-catcher. Tighten
  lint rules only in a separate cleanup PR.

## Save-File Safety

Changes that write or mutate `.d2s` files must preserve these invariants:

- Start from an existing `.d2s`; do not rebuild one from scratch when a
  targeted edit is possible.
- Back up before writing: `shutil.copy2(path, path + ".pre_DESCRIPTION_bak")`.
- Write to a temp or staging file first.
- Run the scanner after every edit phase.
- Verify checksum and file-size fields after writing.
- Promote to the live path only after validation passes.
- Treat scanner hard errors as deployment blockers unless bit-level evidence
  proves the scanner is wrong.
- Use `d2r_chargen/data/` for item IDs, runeword IDs, stat encoding, skills,
  and item bases. Do not use web data as the source of truth.

## MCP Changes

MCP tools are part of the public API. If you add, remove, rename, or change a
tool in `d2r_mcp/`, update all coupled surfaces in the same PR:

- `d2r_mcp/README.md` with the current tool count and tool description.
- Root `README.md` if its MCP tool count is now stale.
- Tests in `tests/test_mcp_*.py`.

Mutation tools must enforce the same backup, scan, and promote pipeline as
`d2r_chargen_build`.

## Documentation Standards

Public documentation should explain product behavior, CLI/MCP usage, file
formats, examples, known limitations, and reproducible validation commands.

Do not add internal planning scratchpads, agent orchestration notes, local
machine paths, disposable probe queues, private save names, recovered-source
references, or one-off live-session diary entries. If manual validation
produces a durable result, document the stable technical finding and the
repeatable procedure, not the private artifacts that produced it.

## Branches and PRs

1. Branch from `main` with a descriptive name such as `feat/merc-encoding` or
   `fix/scanner-checksum`.
2. Keep each PR focused on one feature, fix, or documentation change.
3. Fill in the PR summary, validation performed, and save-file safety notes.
4. Confirm CI passes before merge. If a workflow cannot be fully tested without
   local data or D2R, state that clearly.

Use Conventional Commits where practical:

```text
feat(chargen): merc direct-mode encoding
fix(ci): restore None-game-dir guards
docs(mcp): rewrite tool descriptions
test: add cross-client parity harness
chore: scrub private-repo references
```

Common scopes include `chargen`, `mod`, `mcp`, `ci`, `casc`, and `scanner`.

## Bug Reports

Useful bug reports include:

- Exact CLI invocation or MCP tool call.
- Scanner output when a save file is involved.
- Python version, distro, and Steam Deck status.
- Minimal YAML or command inputs needed to reproduce the issue.

Do not attach personal saves or extracted game data unless a maintainer
explicitly requests a private reproduction path.

## Releases

Maintainer release flow:

1. Bump `version` in `pyproject.toml` using semver.
2. Commit with `chore(release): vX.Y.Z`.
3. Tag and push: `git tag vX.Y.Z && git push --tags`.
4. Draft a GitHub release from the tag and generate release notes.
5. Publish the release to trigger `.github/workflows/publish.yml`.

The publish workflow requires the tag and `pyproject.toml` version to match.

## License

By contributing, you agree your contribution is licensed under the MIT License.
