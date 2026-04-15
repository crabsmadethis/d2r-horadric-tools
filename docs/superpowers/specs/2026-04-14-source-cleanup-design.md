# Source Cleanup: Private Name Removal + Guarded Data Imports

**Date:** 2026-04-14
**Status:** Approved
**Goal:** Remove private tool/script name references from source code and make `build_lib.py` importable without extracted game data.

---

## Context

The pre-release validation (Phase 1 secret scan, Phase 2 packaging test) identified two issues in the current HEAD:

1. **Private names in comments/docstrings** — ~46 references to predecessor scripts and internal planning docs across 3 source files. These are artifacts from the private `d2r-editor` repo. While not secrets, they leak internal development history that has no value to public consumers.

2. **Hard data imports break `build_lib.py` import** — The packaging test expects `from d2r_chargen.build_lib import BitWriter` to succeed in a clean install (no extracted game data). It fails because `build_lib.py` has 7 unconditional `from d2r_chargen.data.*` imports at the top level, plus a module-level stat constant block that dereferences the imported data. Both crash on `ModuleNotFoundError` / `TypeError` when data modules are absent.

---

## Fix 1: Remove Private Name References

### Scope

Private names to remove:

| Name | Type | Refs |
|------|------|------|
| `item_injector.py` | Predecessor script | 13 in `build_lib.py` |
| `fix_obsidian_rw.py` | Predecessor script | 13 in `build_lib.py` |
| `rca_master_plan.md` | Internal planning doc | 7 in `build_lib.py` |
| `build_characters.py` | Predecessor script | 3 in `build_lib.py`, 1 in `save.py`, 1 in `scanner.py` |
| `d2r_inject.py` | Predecessor script | 3 in `build_lib.py` |
| `build_safe.py` | Predecessor script | 1 in `scanner.py` |

**Total: ~42 references across 3 files.**

**`d2r_chargen/build_lib.py`** (~39 references):
- Module docstring (lines 3-16): Names `item_injector.py`, `build_characters.py`, `fix_obsidian_rw.py`
- `# Reference:` comments throughout: point to line numbers in predecessor scripts and `rca_master_plan.md`
- Line 50: Comment naming `item_injector.py` as Huffman source
- Line 136: Docstring naming `item_injector.py`

**`d2r_chargen/save.py`** (1 reference):
- Line 4: Docstring `"Extracted from build_characters.py"`

**`d2r_chargen/scanner.py`** (2 references):
- Line 824: User-facing print: `"Items built with build_safe.py or build_item(unique_id=X)..."`
- Line 825: User-facing print: `"Use build_characters.py with encode_property()..."`

### Approach

- **Module docstring** in `build_lib.py`: Rewrite to describe what the module does without naming predecessors. Keep the "Key fixes" list but reference what was fixed, not where from.
- **All `# Reference:` comments**: Remove entirely. These point to line numbers in scripts and docs that don't exist in this repo. The code itself is the reference now.
- **`save.py` docstring**: Replace `"Extracted from build_characters.py"` with a plain description.
- **`scanner.py` print statements** (lines 824-825): Replace private script names with current tool/function names (`build_lib`, `encode_property()`).

### What NOT to change

- Comments that explain *what the code does* (as opposed to *where it came from*) stay unchanged.
- Section header comments (e.g., `# H. Stat ID Shortcuts`) stay — they're descriptive, not provenance.

---

## Fix 2: Guard Data Imports in `build_lib.py`

### Problem

Two separate crash points prevent `from d2r_chargen.build_lib import BitWriter` from working without game data:

**Crash 1 — Import block (lines 28-52):** Seven hard imports from generated data modules:

```python
from d2r_chargen.data.item_bases import ITEM_BASES as ITEM_BASES_FULL
from d2r_chargen.data.unique_items import UNIQUE_ITEMS
from d2r_chargen.data.set_items import SET_ITEMS
from d2r_chargen.data.runewords import RUNEWORDS
from d2r_chargen.data.item_stat_cost import ITEM_STAT_COST, STAT_BY_NAME
from d2r_chargen.data.item_dimensions import ITEM_DIMENSIONS
from d2r_chargen.data.huffman import HUFFMAN
```

Raises `ModuleNotFoundError` when data modules are absent.

**Crash 2 — Stat constant block (lines 854-881):** Module-level code dereferences `STAT_BY_NAME`:

```python
S = STAT_BY_NAME
STRENGTH     = S['strength']       # TypeError if S is None
ENERGY       = S['energy']
# ... 23 more constants
```

Even if the imports are guarded and `STAT_BY_NAME` is set to `None`, this block crashes with `TypeError: 'NoneType' object is not subscriptable`.

### Approach

**Guard the imports** with `try/except ImportError` (matching `config.py:validate_aliases()` pattern):

```python
try:
    from d2r_chargen.data.item_bases import ITEM_BASES as ITEM_BASES_FULL
    from d2r_chargen.data.unique_items import UNIQUE_ITEMS
    from d2r_chargen.data.set_items import SET_ITEMS
    from d2r_chargen.data.runewords import RUNEWORDS
    from d2r_chargen.data.item_stat_cost import ITEM_STAT_COST, STAT_BY_NAME
    from d2r_chargen.data.item_dimensions import ITEM_DIMENSIONS
    from d2r_chargen.data.huffman import HUFFMAN
    _HAS_DATA = True
except ImportError:
    ITEM_BASES_FULL = None
    UNIQUE_ITEMS = None
    SET_ITEMS = None
    RUNEWORDS = None
    ITEM_STAT_COST = None
    STAT_BY_NAME = None
    ITEM_DIMENSIONS = None
    HUFFMAN = None
    _HAS_DATA = False
```

**Guard the stat constant block** with `if _HAS_DATA:`:

```python
if _HAS_DATA:
    S = STAT_BY_NAME
    STRENGTH     = S['strength']
    ENERGY       = S['energy']
    # ... rest of constants
```

When data is absent, these module-level names simply won't exist. Any function that references them will hit `NameError` at call time — which is correct behavior (you can't build items without data).

**Add a `_require_data()` guard** for public entry-point functions:

```python
def _require_data():
    if not _HAS_DATA:
        raise RuntimeError(
            "Game data not available. Run 'd2r-mod extract' first."
        )
```

Add `_require_data()` as the first line of these public entry points:
- `build_item()` (line 446) — calls `get_base_flags()`, `validate_*()`, uses `HUFFMAN` via `write_huff()`
- `encode_property()` (line 157) — accesses `ITEM_STAT_COST`
- `encode_properties_terminated()` (line 284) — accesses `ITEM_STAT_COST`
- `encode_socketed_rune()` (line 747) — uses `HUFFMAN` via `write_huff()`

Other public functions (`get_base_flags`, `validate_unique_item`, `validate_set_item`, `validate_runeword`) are only called from `build_item()`, which already guards. Direct callers of these would get a `TypeError` on `None` — acceptable since they're lower-level APIs.

### What this enables

- `from d2r_chargen.build_lib import BitWriter` succeeds in a clean install
- `from d2r_chargen.build_lib import build_item` succeeds (import works)
- `build_item(...)` raises `RuntimeError("Game data not available...")` if data is missing
- `BitWriter()` is fully functional except for `write_huff()`, which depends on `HUFFMAN` — acceptable since Huffman encoding inherently requires the game's encoding table
- No behavior change when data is present (the normal case)

### What NOT to change

- Other modules (`scanner.py`, `character.py`, `resolve.py`, etc.) keep their hard imports. They're internal to the chargen pipeline and only imported when building characters, which inherently requires data. The packaging test only validates `build_lib.BitWriter`.
- The `from d2r_chargen.config import RW_BASE_CATEGORIES` import (line 54) is NOT a data import — `config.py` has no generated-data dependency. Leave it as-is.

---

## Verification

After both fixes, re-run the packaging test matrix from the pre-release validation spec. All 9 tests should pass, including:

```
| core import | python -c "from d2r_chargen.build_lib import BitWriter" | No ImportError, exit 0 |
```

Verify no private names remain:

```bash
grep -rn 'item_injector\|build_characters\|fix_obsidian\|d2r_inject\|build_safe\|rca_master_plan' d2r_chargen/ --include='*.py'
```

Expected: zero matches.

---

## Execution Order

1. Fix 1 (comment cleanup) and Fix 2 (guarded imports) touch different parts of `build_lib.py` but should be done sequentially to avoid merge conflicts in the same file
2. Run existing test suite after each fix to verify no regressions
3. Re-run full packaging test (clean venv, non-editable install, test matrix)
4. Commit fixes
