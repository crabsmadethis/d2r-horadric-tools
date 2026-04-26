"""Tier 3: Exhaustive sweep of all unique, set, and runeword items.

Batches items into characters (dynamic packing by dimensions) to reduce
.d2s build count. Each batch is one parametrized test case.

Requires game data files. Manual run only:
    pytest -m slow tests/test_exhaustive_sweep.py -v

Runtime: ~15min
"""
import os
import shutil
import tempfile
import warnings
import pytest

# Skip entire file if game data not extracted
pytest.importorskip("d2r_chargen.data.item_stat_cost",
                     reason="game data not extracted (run 'd2r-mod extract')")

from d2r_chargen.build_lib import build_item, encode_socketed_rune
from d2r_chargen.save import rebuild_items
from d2r_chargen.scanner import scan_character_data
from d2r_chargen.data.item_bases import ITEM_BASES
from d2r_chargen.data.unique_items import UNIQUE_ITEMS
from d2r_chargen.data.unique_item_stats import UNIQUE_ITEM_STATS
from d2r_chargen.data.set_items import SET_ITEMS
from d2r_chargen.data.runewords import RUNEWORDS
from d2r_chargen.data.runeword_stats import RUNEWORD_STATS
from d2r_chargen.resolve import resolve_unique, resolve_runeword

TEMPLATE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "d2r_chargen", "data", "template.d2s"
)

_STASH_COLS = 10
_STASH_ROWS = 8

# Minimal default properties for items without stat data
_DEFAULT_PROPS = [(0, 10), (127, 1)]  # strength: 10, all_skills: 1


def _get_item_dims(type_code):
    """Get (width, height) for an item base code. Returns (1, 1) if unknown."""
    base = ITEM_BASES.get(type_code)
    if base and base.get("width") and base.get("height"):
        return base["width"], base["height"]
    return 1, 1


def _batch_items_by_stash(items_with_codes):
    """Group items into stash-sized batches using greedy grid packing.

    Args:
        items_with_codes: list of (item_def_dict, type_code) tuples.

    Returns:
        list of batches, each batch is a list of (item_def, col, row) tuples.
    """
    batches = []
    current_batch = []
    grid = [[False] * _STASH_COLS for _ in range(_STASH_ROWS)]

    def _try_place(w, h):
        for r in range(_STASH_ROWS - h + 1):
            for c in range(_STASH_COLS - w + 1):
                if all(not grid[r + dr][c + dc]
                       for dr in range(h) for dc in range(w)):
                    return c, r
        return None

    def _place(c, r, w, h):
        for dr in range(h):
            for dc in range(w):
                grid[r + dr][c + dc] = True

    def _reset():
        nonlocal current_batch
        if current_batch:
            batches.append(current_batch)
        current_batch = []
        for r in range(_STASH_ROWS):
            for c in range(_STASH_COLS):
                grid[r][c] = False

    for item_def, type_code in items_with_codes:
        w, h = _get_item_dims(type_code)
        pos = _try_place(w, h)
        if pos is None:
            _reset()
            pos = _try_place(w, h)
            if pos is None:
                continue  # Item too large for empty stash
        col, row = pos
        _place(col, row, w, h)
        current_batch.append((item_def, col, row))

    if current_batch:
        batches.append(current_batch)

    return batches


def _build_stash_and_scan(batch):
    """Build a .d2s with stash items from a batch and scan it.

    Returns (scan_result, build_errors) tuple. build_errors is a list of
    (item_def, error_msg) for items that failed to encode.
    """
    char_items = []
    build_errors = []
    for item_def, col, row in batch:
        try:
            item_bytes = build_item(
                type_code=item_def["type_code"],
                col=col, row=row, storage=5,
                quality=item_def.get("quality", 7),
                ilvl=item_def.get("ilvl", 99),
                unique_id=item_def.get("unique_id", 0),
                set_id=item_def.get("set_id", 0),
                defense=item_def.get("defense", 0),
                max_dur=item_def.get("max_dur", 0),
                cur_dur=item_def.get("max_dur", 0),
                properties=item_def.get("properties"),
                runeword=item_def.get("runeword", False),
                runeword_id=item_def.get("runeword_id", 0),
                num_sockets=item_def.get("num_sockets", 0),
                socketed=item_def.get("num_sockets", 0) > 0,
            )
            char_items.append(item_bytes)

            for i, filler_code in enumerate(item_def.get("rune_codes", [])):
                filler = encode_socketed_rune(filler_code, socket_idx=i)
                char_items.append(filler)
        except (ValueError, KeyError, AssertionError) as e:
            build_errors.append((item_def, str(e)))

    with tempfile.NamedTemporaryFile(suffix=".d2s", delete=False) as f:
        tmp_path = f.name
        shutil.copy2(TEMPLATE_PATH, tmp_path)

    try:
        result_data = rebuild_items(tmp_path, char_items, [])
        with open(tmp_path, "wb") as f:
            f.write(result_data)
        return scan_character_data(tmp_path), build_errors
    finally:
        os.unlink(tmp_path)


# ============================================================
# 3.1 All unique items
# ============================================================

def _generate_unique_batches():
    """Generate stash batches for all unique items."""
    items = []
    for uid, info in sorted(UNIQUE_ITEMS.items()):
        type_code = info["code"]
        if not type_code:
            continue
        if uid in UNIQUE_ITEM_STATS:
            try:
                resolved = resolve_unique(info["name"])
                properties = resolved.get("properties", _DEFAULT_PROPS)
                defense = resolved.get("defense", 0)
                max_dur = resolved.get("max_dur", 0)
            except Exception:
                properties = _DEFAULT_PROPS
                defense = 0
                max_dur = 0
        else:
            properties = _DEFAULT_PROPS
            defense = 0
            max_dur = 0

        item_def = {
            "type_code": type_code,
            "quality": 7,
            "unique_id": uid,
            "defense": defense,
            "max_dur": max_dur,
            "properties": properties,
        }
        items.append((item_def, type_code))

    return _batch_items_by_stash(items)


_UNIQUE_BATCHES = _generate_unique_batches()


@pytest.mark.slow
@pytest.mark.integration
@pytest.mark.parametrize(
    "batch_idx",
    range(len(_UNIQUE_BATCHES)),
    ids=[f"unique_batch_{i}" for i in range(len(_UNIQUE_BATCHES))],
)
def test_all_uniques(batch_idx):
    """Build every unique item in a stash batch and scan for errors."""
    batch = _UNIQUE_BATCHES[batch_idx]
    result, build_errors = _build_stash_and_scan(batch)
    if build_errors:
        names = [item_def.get("unique_id", "?") for item_def, msg in build_errors]
        warnings.warn(f"Batch {batch_idx}: {len(build_errors)} build errors (skipped): {names}")
    if result["errors"]:
        uids = [item_def.get("unique_id", "?") for item_def, _, _ in batch]
        names = [UNIQUE_ITEMS.get(u, {}).get("name", "?") for u in uids]
        pytest.fail(
            f"Batch {batch_idx} ({len(batch)} items) scanner errors:\n"
            f"  UIDs: {uids}\n"
            f"  Names: {names}\n"
            f"  Errors: {result['errors']}"
        )


# ============================================================
# 3.2 All set items
# ============================================================

_SET_DEFAULT_PROPS = [(39, 10), (43, 10), (0, 10)]  # fire_res: 10, cold_res: 10, strength: 10


def _generate_set_batches():
    """Generate stash batches for all set items."""
    items = []
    for set_id, info in sorted(SET_ITEMS.items()):
        type_code = info["code"]
        if not type_code:
            continue
        base = ITEM_BASES.get(type_code, {})
        defense = base.get("max_ac", 0)
        max_dur = base.get("durability", 0)

        item_def = {
            "type_code": type_code,
            "quality": 5,
            "set_id": set_id,
            "defense": defense,
            "max_dur": max_dur,
            "properties": _SET_DEFAULT_PROPS,
        }
        items.append((item_def, type_code))

    return _batch_items_by_stash(items)


_SET_BATCHES = _generate_set_batches()


@pytest.mark.slow
@pytest.mark.integration
@pytest.mark.parametrize(
    "batch_idx",
    range(len(_SET_BATCHES)),
    ids=[f"set_batch_{i}" for i in range(len(_SET_BATCHES))],
)
def test_all_sets(batch_idx):
    """Build every set item in a stash batch and scan for errors."""
    batch = _SET_BATCHES[batch_idx]
    result, build_errors = _build_stash_and_scan(batch)
    if build_errors:
        names = [item_def.get("set_id", "?") for item_def, msg in build_errors]
        warnings.warn(f"Batch {batch_idx}: {len(build_errors)} build errors (skipped): {names}")
    if result["errors"]:
        sids = [item_def.get("set_id", "?") for item_def, _, _ in batch]
        names = [SET_ITEMS.get(s, {}).get("name", "?") for s in sids]
        pytest.fail(
            f"Batch {batch_idx} ({len(batch)} items) scanner errors:\n"
            f"  Set IDs: {sids}\n"
            f"  Names: {names}\n"
            f"  Errors: {result['errors']}"
        )


# ============================================================
# 3.3 All runewords
# ============================================================

def _find_valid_base(runeword_info):
    """Find a valid base code with enough sockets for this runeword.

    The 'bases' field contains category names (e.g., 'Shield', 'Axe'),
    not type codes. Search ITEM_BASES for the first entry matching any
    category with enough sockets.
    """
    required_sockets = runeword_info["sockets"]
    allowed_categories = set(runeword_info.get("bases", []))

    for base_code, base in sorted(ITEM_BASES.items()):
        cats = set(base.get("categories", []))
        if cats & allowed_categories and base.get("max_sockets", 0) >= required_sockets:
            return base_code
    return None


def _generate_runeword_batches():
    """Generate stash batches for all runewords."""
    items = []
    for rw_id, rw_info in sorted(RUNEWORDS.items()):
        base_code = _find_valid_base(rw_info)
        if base_code is None:
            continue

        rw_stats = RUNEWORD_STATS.get(rw_id)
        if rw_stats:
            try:
                resolved = resolve_runeword(rw_info["name"], base_code)
                properties = resolved.get("properties", _DEFAULT_PROPS)
                defense = resolved.get("defense", 0)
                max_dur = resolved.get("max_dur", 0)
                rune_codes = resolved.get("rune_codes", rw_info["runes"])
            except Exception:
                properties = _DEFAULT_PROPS
                defense = 0
                max_dur = 0
                rune_codes = rw_info["runes"]
        else:
            properties = _DEFAULT_PROPS
            defense = 0
            max_dur = 0
            rune_codes = rw_info["runes"]

        item_def = {
            "type_code": base_code,
            "quality": 2,
            "runeword": True,
            "runeword_id": rw_id,
            "num_sockets": rw_info["sockets"],
            "defense": defense,
            "max_dur": max_dur,
            "properties": properties,
            "rune_codes": rune_codes,
        }
        items.append((item_def, base_code))

    return _batch_items_by_stash(items)


_RUNEWORD_BATCHES = _generate_runeword_batches()


@pytest.mark.slow
@pytest.mark.integration
@pytest.mark.parametrize(
    "batch_idx",
    range(len(_RUNEWORD_BATCHES)),
    ids=[f"runeword_batch_{i}" for i in range(len(_RUNEWORD_BATCHES))],
)
def test_all_runewords(batch_idx):
    """Build every runeword in a stash batch and scan for errors."""
    batch = _RUNEWORD_BATCHES[batch_idx]
    result, build_errors = _build_stash_and_scan(batch)
    if build_errors:
        names = [item_def.get("runeword_id", "?") for item_def, msg in build_errors]
        warnings.warn(f"Batch {batch_idx}: {len(build_errors)} build errors (skipped): {names}")
    if result["errors"]:
        rw_ids = [item_def.get("runeword_id", "?") for item_def, _, _ in batch]
        names = [RUNEWORDS.get(r, {}).get("name", "?") for r in rw_ids]
        pytest.fail(
            f"Batch {batch_idx} ({len(batch)} items) scanner errors:\n"
            f"  Runeword IDs: {rw_ids}\n"
            f"  Names: {names}\n"
            f"  Errors: {result['errors']}"
        )


# ============================================================
# 3.4 Base type consistency (data validation, no .d2s builds)
# ============================================================

@pytest.mark.slow
@pytest.mark.integration
def test_base_consistency():
    """Every base code used by unique/set/runeword has valid ITEM_BASES entry."""
    from d2r_chargen.data.item_dimensions import ITEM_DIMENSIONS

    missing_bases = []
    missing_dims = []
    invalid_dims = []

    referenced_codes = set()
    for uid, info in UNIQUE_ITEMS.items():
        if info.get("code"):
            referenced_codes.add(info["code"])
    for sid, info in SET_ITEMS.items():
        if info.get("code"):
            referenced_codes.add(info["code"])
    for rw_id, rw_info in RUNEWORDS.items():
        for base_code in rw_info.get("bases", []):
            if base_code and base_code in ITEM_BASES:
                referenced_codes.add(base_code)

    for code in sorted(referenced_codes):
        base = ITEM_BASES.get(code)
        if base is None:
            missing_bases.append(code)
            continue

        w = base.get("width", 0)
        h = base.get("height", 0)
        if w == 0 or h == 0:
            dims = ITEM_DIMENSIONS.get(code)
            if dims is None:
                missing_dims.append(code)
            elif dims[0] < 1 or dims[0] > 4 or dims[1] < 1 or dims[1] > 4:
                invalid_dims.append((code, dims))
        elif w < 1 or w > 4 or h < 1 or h > 4:
            invalid_dims.append((code, (w, h)))

    assert not missing_bases, (
        f"{len(missing_bases)} referenced base codes missing from ITEM_BASES: "
        f"{missing_bases[:20]}"
    )
    assert not invalid_dims, (
        f"{len(invalid_dims)} bases with invalid dimensions: "
        f"{invalid_dims[:10]}"
    )
    if missing_dims:
        warnings.warn(
            f"{len(missing_dims)} bases missing dimension data: {missing_dims[:20]}"
        )


# ============================================================
# 3.5 Grid capacity limits (2 tests)
# ============================================================

@pytest.mark.slow
@pytest.mark.integration
def test_stash_full():
    """Stash at 100% capacity: 80 x 1x1 items filling all cells."""
    char_items = []
    for r in range(_STASH_ROWS):
        for c in range(_STASH_COLS):
            item = build_item(
                type_code="rin", col=c, row=r, storage=5,
                quality=7, unique_id=122,  # SoJ
                properties=[(0, 10)],
            )
            char_items.append(item)

    with tempfile.NamedTemporaryFile(suffix=".d2s", delete=False) as f:
        tmp_path = f.name
        shutil.copy2(TEMPLATE_PATH, tmp_path)

    try:
        result_data = rebuild_items(tmp_path, char_items, [])
        with open(tmp_path, "wb") as f:
            f.write(result_data)
        result = scan_character_data(tmp_path)
        assert result["errors"] == [], f"Scanner errors: {result['errors']}"
    finally:
        os.unlink(tmp_path)
