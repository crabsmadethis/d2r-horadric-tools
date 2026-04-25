# Contributing to d2r-tools

Thanks for considering a contribution. This project is small and Linux-first; the notes below should get you from clone to working PR in one sitting.

## Project shape

- **Linux / Steam Deck (Proton) only.** Windows path detection exists but is untested — bug reports welcome, PRs more so.
- **Python 3.10+** (CI runs 3.11 and 3.12).
- **AI-agent-first.** Most users drive the toolkit through Claude Code, Codex, Cursor, etc. via the bundled MCP server. Please keep that workflow in mind when changing CLI flags, error envelopes, or tool descriptions.
- **Game data is never committed.** `d2r_chargen/data/*.py` (other than `template.d2s`) is generated locally from a D2R install and `.gitignore`d. Don't commit extracted data.

## Dev setup

```bash
git clone https://github.com/crabsmadethis/d2r-horadric-tools.git
cd d2r-horadric-tools
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"   # includes pytest + ruff
```

If you have D2R installed, generate the local data modules:

```bash
d2r-mod extract                 # auto-detects Steam install
# or:
d2r-mod extract --game-dir /path/to/Diablo\ II\ Resurrected
```

You can develop and run the Tier 1 test suite without D2R installed.

## Running tests

The CI-equivalent set (no game data required):

```bash
pytest tests/ -v --timeout=60 \
  -m "not integration and not slow and not e2e and not smoke"
```

Test markers (defined in `pyproject.toml`):

| Marker | What it needs |
|--------|---------------|
| (unmarked) | Nothing — pure Python, runs in CI |
| `smoke` | Lightweight checks that may touch generated data |
| `slow` | CASC I/O, host patching, engine disasm |
| `integration` | Real D2R binaries on disk |
| `e2e` | D2R running |

Run a single tier locally with `-m smoke`, `-m slow`, etc.

## Code style

No formatter is enforced. Match the surrounding code: 4-space indents, type hints where the existing code has them, no comments on obvious code (see `CLAUDE.md` rule on comments). Keep functions small.

**Linting** — `ruff` runs in CI with a conservative bug-catcher rule set (`E9`, `F63`, `F7`, `F82`). Run locally before pushing:

```bash
ruff check .
```

The rule selection is in `pyproject.toml` under `[tool.ruff.lint]`. It's deliberately narrow to avoid noisy style enforcement on existing code; tightening it is welcome but should be its own PR.

If you add a dependency, add it to `pyproject.toml` and explain why in the PR description.

## Commit messages

[Conventional Commits](https://www.conventionalcommits.org/) — match the existing history:

```
feat(chargen): merc direct-mode encoding
fix(ci): restore None-game-dir guards
docs(mcp): rewrite tool descriptions
test: add cross-client parity harness
chore: scrub private-repo references
```

Common scopes: `chargen`, `mod`, `mcp`, `ci`, `casc`, `scanner`.

## Branching and PRs

1. Branch off `main`. Use a descriptive name (`feat/merc-encoding`, `fix/scanner-checksum`).
2. Keep PRs focused — one feature or fix per PR. Smaller diffs get reviewed faster.
3. CI must pass. If you're touching code that needs a D2R install to test, mark new tests with the appropriate marker so CI skips them.
4. The PR template will prompt for a summary, what you tested, and any save-file safety considerations. Fill it in.

## Save-file safety

If your change writes to `.d2s` files, the rules in [`CLAUDE.md`](./CLAUDE.md) apply to humans too:

- Always backup before write (`shutil.copy2(path, path + '.pre_*_bak')`).
- Write to a temp file, run the scanner, only then promote to the live path.
- Never deploy a file that fails scanner validation.
- Never trust web research for D2R item UIDs / stat encoding — read `d2r_chargen/data/`.

PRs that bypass these will be asked to add them back.

## MCP tools

If you add or change an MCP tool in `d2r_mcp/`:

- Update `d2r_mcp/README.md` (tool count + description).
- Update the README at the repo root if the tool count there is now stale.
- Add tests in `tests/test_mcp_*.py`.
- Mutation tools must enforce the same backup/scan/promote pipeline as `d2r_chargen_build`.

## Reporting bugs

Open an issue using the bug-report template. The most useful reports include:

- Exact command (CLI invocation or MCP tool call).
- Scanner output if a save was involved (`d2r-chargen scan <name>`).
- Python version, distro, whether you're on Steam Deck.
- The character YAML that triggers it, if applicable.

## Releases (maintainers)

Release flow:

1. Bump `version` in `pyproject.toml` (semver — `MAJOR.MINOR.PATCH`).
2. Commit: `chore(release): vX.Y.Z`.
3. Tag: `git tag vX.Y.Z && git push --tags`.
4. On GitHub: **Releases** → **Draft a new release** → pick the tag → **Generate release notes** (categorizes via `.github/release.yml`) → **Publish release**.
5. Publishing the release triggers `.github/workflows/publish.yml`, which builds and uploads to PyPI via trusted publishing.

The publish workflow refuses to run if the tag and `pyproject.toml` version disagree.

## License

By contributing, you agree your contribution is licensed under the MIT License (same as the repo).
