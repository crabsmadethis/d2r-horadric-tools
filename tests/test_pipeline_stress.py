"""Tier 2: Pipeline integration tests for d2r_chargen.

Builds complete .d2s files from programmatic character definitions and
validates them with scan_character_data(). Covers every quality path,
property alias coverage, grid packing, and multi-encoding items.

Requires game data files (auto-skipped if absent via conftest.py
pytest_collection_modifyitems hook).

Runtime: ~2min
"""
import os
import shutil
import tempfile
import pytest

# Skip entire file if game data not extracted
pytest.importorskip("d2r_chargen.data.item_stat_cost",
                     reason="game data not extracted (run 'd2r-mod extract')")

from d2r_chargen.character import build_all_items
from d2r_chargen.save import rebuild_items
from d2r_chargen.scanner import scan_character_data


TEMPLATE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "d2r_chargen", "data", "template.d2s"
)


def _make_char_def(name="StressTest", class_name="sorceress", level=80,
                   equipment=None, inventory=None, merc=None):
    """Build a minimal valid character definition dict."""
    char_def = {
        "schema_version": 1,
        "name": name,
        "class": class_name,
        "level": level,
        "stats": {
            "strength": 156,
            "dexterity": 60,
            "vitality": 200,
            "energy": 35,
        },
        "equipment": equipment or [],
    }
    if inventory is not None:
        char_def["inventory"] = inventory
    if merc is not None:
        char_def["merc"] = merc
    return char_def


def _build_and_scan(char_def):
    """Build items from char_def, assemble .d2s, scan, return scan result.

    Note: build_all_items() returns all items (including merc stash items)
    as section='char'. This is correct per Rule 6.
    """
    items = build_all_items(char_def)
    char_items = [ib for _, ib in items]

    with tempfile.NamedTemporaryFile(suffix=".d2s", delete=False) as f:
        tmp_path = f.name
        shutil.copy2(TEMPLATE_PATH, tmp_path)

    try:
        result_data = rebuild_items(tmp_path, char_items, [])
        with open(tmp_path, "wb") as f:
            f.write(result_data)
        return scan_character_data(tmp_path)
    finally:
        os.unlink(tmp_path)


# ============================================================
# Smoke test
# ============================================================

@pytest.mark.integration
def test_smoke_empty_character():
    """Smoke test: empty equipment produces valid .d2s."""
    char_def = _make_char_def(equipment=[])
    result = _build_and_scan(char_def)
    assert result["errors"] == [], f"Scanner errors: {result['errors']}"


# ============================================================
# 2.1 Every quality path (6 tests)
# ============================================================

@pytest.mark.integration
def test_quality_unique():
    """Quality 7: Build 5 unique items spanning different base types."""
    char_def = _make_char_def(equipment=[
        {"slot": "helm", "unique": "Griffon's Eye"},
        {"slot": "body", "unique": "Skin of the Vipermagi"},
        {"slot": "belt", "unique": "Arachnid Mesh"},
        {"slot": "ring_left", "unique": "The Stone of Jordan"},
        {"slot": "weapon", "unique": "The Oculus"},
    ])
    result = _build_and_scan(char_def)
    assert result["errors"] == [], f"Scanner errors: {result['errors']}"


@pytest.mark.integration
def test_quality_set():
    """Quality 5: Build 3 set items with explicit properties."""
    char_def = _make_char_def(equipment=[
        {"slot": "helm", "set": "Tal Rasha's Horadric Crest",
         "properties": {"fire_res": 15, "cold_res": 15, "life": 60, "mana_leech": 10}},
        {"slot": "belt", "set": "Tal Rasha's Fire-Spun Cloth",
         "properties": {"dexterity": 20, "mana": 30, "mf": 15}},
        {"slot": "body", "set": "Tal Rasha's Howling Wind",
         "properties": {"mf": 88, "fire_res": 15, "cold_res": 15}},
    ])
    result = _build_and_scan(char_def)
    assert result["errors"] == [], f"Scanner errors: {result['errors']}"


@pytest.mark.integration
def test_quality_runeword():
    """Quality 2 + runeword flag: 3 runewords across weapon/armor/shield."""
    char_def = _make_char_def(equipment=[
        {"slot": "weapon", "runeword": "Spirit", "base": "9ls"},
        {"slot": "shield", "runeword": "Spirit", "base": "uit"},
        {"slot": "body", "runeword": "Enigma", "base": "xtp"},
    ])
    result = _build_and_scan(char_def)
    assert result["errors"] == [], f"Scanner errors: {result['errors']}"


@pytest.mark.integration
def test_quality_magic():
    """Quality 4: Magic charms via magic_small_charm/magic_grand_charm."""
    char_def = _make_char_def(
        equipment=[],
        inventory={"charms": [
            {"magic_small_charm": {"properties": {"life": 20, "fire_res": 5}}},
            {"magic_grand_charm": {"properties": {"life": 45, "mf": 7}}},
        ]},
    )
    result = _build_and_scan(char_def)
    assert result["errors"] == [], f"Scanner errors: {result['errors']}"


@pytest.mark.integration
def test_quality_rare():
    """Quality 6: Rare helm, gloves, boots."""
    char_def = _make_char_def(equipment=[
        {"slot": "helm", "rare": True, "base": "ci3",
         "properties": {"fcr": 20, "fire_res": 15, "life": 60}},
        {"slot": "hands", "rare": True, "base": "xtg",
         "properties": {"ias": 20, "strength": 15}},
        {"slot": "feet", "rare": True, "base": "xtb",
         "properties": {"frw": 30, "fire_res": 40}},
    ])
    result = _build_and_scan(char_def)
    assert result["errors"] == [], f"Scanner errors: {result['errors']}"


@pytest.mark.integration
def test_quality_crafted():
    """Quality 8: Crafted amulet and belt."""
    char_def = _make_char_def(equipment=[
        {"slot": "neck", "crafted": True, "base": "amu",
         "properties": {"fcr": 10, "life": 30, "mana_regen": 10}},
        {"slot": "belt", "crafted": True, "base": "ztb",
         "properties": {"fhr": 10, "life": 40}},
    ])
    result = _build_and_scan(char_def)
    assert result["errors"] == [], f"Scanner errors: {result['errors']}"


# ============================================================
# 2.2 Property alias coverage (1 test)
# ============================================================

@pytest.mark.integration
def test_property_alias_coverage():
    """Every simple alias in PROPERTY_ALIASES appears on at least one item.

    Uses extra_properties on unique items in merc-stash placement.
    Aliases requiring special list formats (CTC, charges, skill params) are
    excluded — they're covered by encoding type tests in Tier 1.
    """
    from d2r_chargen.config import PROPERTY_ALIASES
    from d2r_chargen.data.item_stat_cost import ITEM_STAT_COST, STAT_BY_NAME

    COMPLEX_ALIASES = {
        "charges", "ctc_hit", "ctc_kill", "ctc_struck",
        "class_skills", "skill_tab", "non_class_skill", "item_aura",
    }
    GROUPED_SECONDARIES = {
        "cold_max", "fire_max", "light_max", "poison_max",
        "cold_len", "poison_len",
    }

    simple_aliases = {
        k: v for k, v in PROPERTY_ALIASES.items()
        if k not in COMPLEX_ALIASES and k not in GROUPED_SECONDARIES
    }

    alias_list = list(simple_aliases.items())
    merc_equipment = []
    for i in range(0, len(alias_list), 12):
        batch = alias_list[i:i + 12]
        props = {}
        for alias_name, stat_name in batch:
            stat_id = STAT_BY_NAME.get(stat_name)
            if stat_id is None:
                continue
            info = ITEM_STAT_COST.get(stat_id)
            if info is None or info.get('sB', 0) == 0:
                continue
            sA = info.get('sA', 0)
            sB = info.get('sB', 0)
            max_val = (1 << sB) - 1 - sA
            safe_val = min(10, max(1, max_val // 2))
            props[alias_name] = safe_val
        if props:
            merc_equipment.append({
                "unique": "The Gnasher",
                "extra_properties": props,
            })

    char_def = _make_char_def(
        equipment=[{"slot": "weapon", "unique": "The Oculus"}],
        merc={"type": "act1_cold", "equipment": merc_equipment},
    )
    result = _build_and_scan(char_def)
    assert result["errors"] == [], f"Scanner errors: {result['errors']}"


# ============================================================
# 2.3 Grid packing pressure (2 tests)
# ============================================================

@pytest.mark.integration
def test_inventory_85pct():
    """Inventory at 85% capacity: 8 GCs + Annihilus + Torch + 7 SCs = 34/40 cells."""
    charms = [
        {"magic_grand_charm": {"properties": {"life": 45}}},
    ] * 8
    charms.append(
        {"unique": "Annihilus",
         "properties": {"all_skills": 1, "strength": 20,
                        "fire_res": 20, "cold_res": 20,
                        "light_res": 20, "poison_res": 20,
                        "add_exp": 10}},
    )
    charms.append(
        {"unique": "Hellfire Torch",
         "properties": {"all_skills": 3, "fire_res": 20,
                        "cold_res": 20, "light_radius": 8}},
    )
    charms.extend([
        {"magic_small_charm": {"properties": {"life": 20}}},
    ] * 7)

    char_def = _make_char_def(
        equipment=[{"slot": "weapon", "unique": "The Oculus"}],
        inventory={"charms": charms},
    )
    result = _build_and_scan(char_def)
    assert result["errors"] == [], f"Scanner errors: {result['errors']}"


@pytest.mark.integration
def test_stash_81pct():
    """Stash at ~81% capacity: mixed-dimension merc items in stash."""
    merc_equipment = []
    for _ in range(4):
        merc_equipment.append(
            {"unique": "The Gnasher", "extra_properties": {"strength": 10}}
        )
    for _ in range(6):
        merc_equipment.append(
            {"unique": "Tarnhelm", "extra_properties": {"mf": 25}}
        )
    for _ in range(17):
        merc_equipment.append({"unique": "The Stone of Jordan"})

    char_def = _make_char_def(
        equipment=[{"slot": "weapon", "unique": "The Oculus"}],
        merc={"type": "act1_cold", "equipment": merc_equipment},
    )
    result = _build_and_scan(char_def)
    assert result["errors"] == [], f"Scanner errors: {result['errors']}"


# ============================================================
# 2.4 Multi-stat item (1 test)
# ============================================================

@pytest.mark.integration
def test_multi_stat_item():
    """One unique item with 15+ extra_properties spanning e=0, e=1, e=2."""
    char_def = _make_char_def(equipment=[
        {"slot": "weapon", "unique": "The Oculus",
         "extra_properties": {
             "strength": 20, "dexterity": 15, "vitality": 30,
             "energy": 25, "life": 100, "mana": 80,
             "fire_res": 30, "cold_res": 30,
             "light_res": 30, "poison_res": 30,
             "fcr": 20, "mf": 50, "dr_pct": 10,
             "mdr": 5, "light_radius": 3,
             "non_class_skill": [1, "Teleport"],
             "ctc_hit": [10, 3, "Frost Nova"],
         }},
    ])
    result = _build_and_scan(char_def)
    assert result["errors"] == [], f"Scanner errors: {result['errors']}"
