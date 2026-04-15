# Pre-Release Validation: Secret Scanning + Packaging Test

**Date:** 2026-04-14
**Status:** Approved
**Goal:** Ensure no private info survives in git history and that a clean `pip install` produces working CLI tools.

---

## Phase 1: Git History Secret Scan

**Problem:** The audit cleaned current files, but `git log -p` still contains the original diffs. Anyone who clones the repo can see what was changed — including the old hardcoded paths, private hostnames, and the `d2r-editor` origin.

**Approach:** Pure `git log -p` + grep (no external tools available on Steam Deck).

### Scan Patterns

| Pattern | Risk | Action if found |
|---------|------|-----------------|
| `/home/deck` | Private filesystem path | Must fix (history rewrite) if in added lines of surviving files |
| `/run/media/deck/SK256` | Private SD card path | Same |
| `deck@steamdeck.home.local` | Private identity | Same — already planned as Task 3 |
| `steamdeck.home.local` | Private hostname | Same |
| `d2r-editor` | Private repo name | Acceptable in commit diffs (we changed them), flag if in surviving code |
| `d2rdoctor` | Private tool name | Same |
| `item_injector` | Private tool name (appears in build_lib.py comments without repo prefix) | Acceptable — historical reference, no repo path |
| `build_characters\|fix_obsidian` | Private script names (in docstrings) | Same |
| `password\|secret\|api.key\|token` | Generic secrets | Must fix if real credentials |
| `\.env\|credentials` | Config secrets | Must fix if real credentials |

### Classification

- **Must fix:** Private info in _added_ lines of files that still exist in HEAD. These are visible in `git show` for any commit.
- **Acceptable:** Private info in _removed_ lines (the `-` side of diffs). These show the cleanup happened — expected and harmless.
- **Note:** The initial sync commit (678badf) is highest risk since it imported the entire codebase from d2r-editor. All old values will appear as `+` lines in that commit.

### Decision Point

If the scan finds private info baked into the initial sync commit (which it almost certainly will — the hardcoded paths were there from the start), then Task 3 (git filter-branch) already handles the author identity, but the _content_ of old commits still contains `/home/deck` paths. Options:

1. **Accept it** — the current HEAD is clean, and the old diffs just show the evolution. Anyone reading commit history can see where the code came from, but there's no actionable secret.
2. **Squash everything** — collapse all commits into one, destroying diff history entirely. Nuclear but clean.
3. **Interactive rebase to squash the initial sync** — keep the audit commits but squash the first two (skeleton + sync) into one clean commit.

Recommendation: Option 1 unless the scan finds actual secrets (API keys, passwords). Hardcoded paths to `/home/deck` are not secrets — they reveal that the developer uses a Steam Deck, which is already obvious from the project description.

---

## Phase 2: Clean-Venv Packaging Test

**Problem:** `pip install -e .` (editable) hides packaging bugs that break real installs. Missing `package_data`, wrong `packages.find` config, or path resolution assumptions can all pass in editable mode but fail in production installs.

**Approach:** Create a clean venv, install non-editable, run the full CLI test matrix.

### Test Matrix

| Test | Command | Expected Result |
|------|---------|-----------------|
| setup | `mkdir -p /tmp/d2r-pkg-test/project/chars && cp /home/deck/d2r-tools/chars/ExamplePaladin.yaml /tmp/d2r-pkg-test/project/chars/` | Setup step — creates a project dir with chars/ |
| chargen help | `cd /tmp/d2r-pkg-test/project && d2r-chargen --help` | Shows help text, exit 0 |
| chargen list | `cd /tmp/d2r-pkg-test/project && d2r-chargen list` | Prints `ExamplePaladin`, exit 0 |
| mod help | `cd /tmp/d2r-pkg-test/project && d2r-mod --help` | Shows help text, exit 0 |
| mod build | `cd /tmp/d2r-pkg-test/project && d2r-mod build 2>&1` | Prints `"Error: vanilla/ not found. Run 'd2r-mod extract' first."` to stderr, exit 1 |
| core import | `python -c "from d2r_chargen.build_lib import BitWriter"` | No ImportError, exit 0 |
| mod import | `python -c "from d2r_mod.casc import extract_vanilla"` | No ImportError, exit 0 |
| template bundled | `python -c "import d2r_chargen; import os; print(os.path.exists(os.path.join(os.path.dirname(d2r_chargen.__file__), 'data', 'template.d2s')))"` | Prints `True` |
| pytest collection | `cd /home/deck/d2r-tools && python -m pytest tests/ --collect-only` | No collection errors (run from repo dir where tests/ lives) |

### Known Issue: CHARS_DIR Resolution

`d2r_chargen/config.py:_detect_chars_dir()` resolves `chars/` relative to the package's parent directory:

```python
pkg_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
return os.path.join(pkg_dir, 'chars')
```

In a non-editable install, `__file__` is inside `site-packages/d2r_chargen/`, so this resolves to `site-packages/chars/` — which doesn't exist.

**Fix:** Change the default to CWD-relative:

```python
def _detect_chars_dir():
    """Character YAML directory. Override with D2R_CHARS env var."""
    if 'D2R_CHARS' in os.environ:
        return os.environ['D2R_CHARS']
    return os.path.join(os.getcwd(), 'chars')
```

This matches user mental model: "I run `d2r-chargen` from my project directory, and my characters are in `chars/` next to my overlays."

### Environment

- Location: `/tmp/d2r-pkg-test/`
- Python: system python3 (3.x)
- Install: `pip install /home/deck/d2r-tools` (non-editable, from local path)
- Cleanup: remove `/tmp/d2r-pkg-test/` after test

---

## Execution Order

1. Run Phase 1 (secret scan) — read-only, no code changes
2. Review findings with user, decide on history approach
3. Run Phase 2 (packaging test) — may produce code fixes
4. Apply CHARS_DIR fix if confirmed
5. Re-run packaging test to verify fix
6. Commit any fixes
7. Run Task 3 (git filter-branch for author identity) — must be LAST since it rewrites all commit SHAs
