"""Test fixture characters: YAML validation, item building, and full .d2s scan.

Parametrized across all fixture YAML files in tests/fixtures/ to verify:
1. YAML loads and validates (schema, required fields, stat minimums)
2. Item building produces valid binary output without errors
3. All equipment items produce non-empty bytes
4. Full .d2s build + scanner produces zero hard errors
"""
import os
import glob
import shutil
import struct
import tempfile
import pytest

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _fixture_yamls():
    """Collect all fixture YAML files for parametrization."""
    pattern = os.path.join(FIXTURES_DIR, "*_fixture.yaml")
    paths = sorted(glob.glob(pattern))
    if not paths:
        pytest.skip("No fixture YAML files found")
    return paths


@pytest.mark.integration
@pytest.mark.parametrize(
    "yaml_path",
    _fixture_yamls(),
    ids=lambda p: os.path.basename(p).replace("_fixture.yaml", ""),
)
def test_fixture_validates(yaml_path):
    """YAML parses and passes structural validation."""
    from d2r_chargen.character import load_character_yaml

    char_def = load_character_yaml(yaml_path)
    assert char_def["name"], "Character name must be non-empty"
    assert char_def["class"] in (
        "amazon", "sorceress", "necromancer", "paladin",
        "barbarian", "druid", "assassin", "warlock",
    )
    assert char_def["level"] > 0

    # All four stats must be > 0 (zero causes Error:7)
    for stat in ("strength", "dexterity", "vitality", "energy"):
        assert char_def["stats"][stat] > 0, f"{stat} must be > 0"


@pytest.mark.integration
@pytest.mark.parametrize(
    "yaml_path",
    _fixture_yamls(),
    ids=lambda p: os.path.basename(p).replace("_fixture.yaml", ""),
)
def test_fixture_builds_items(yaml_path):
    """Item building produces at least one item without errors."""
    from d2r_chargen.character import load_character_yaml, build_all_items

    char_def = load_character_yaml(yaml_path)
    items = build_all_items(char_def)
    assert len(items) > 0, f"Expected items from {os.path.basename(yaml_path)}"


@pytest.mark.integration
@pytest.mark.parametrize(
    "yaml_path",
    _fixture_yamls(),
    ids=lambda p: os.path.basename(p).replace("_fixture.yaml", ""),
)
def test_fixture_items_nonempty(yaml_path):
    """Every built item has non-empty bytes."""
    from d2r_chargen.character import load_character_yaml, build_all_items

    char_def = load_character_yaml(yaml_path)
    items = build_all_items(char_def)
    for i, (section, item_bytes) in enumerate(items):
        assert len(item_bytes) > 0, (
            f"Item {i} in {os.path.basename(yaml_path)} has empty bytes"
        )


@pytest.mark.integration
@pytest.mark.parametrize(
    "yaml_path",
    _fixture_yamls(),
    ids=lambda p: os.path.basename(p).replace("_fixture.yaml", ""),
)
def test_fixture_item_count_matches_definition(yaml_path):
    """Built item count is >= equipment count (runewords add filler items)."""
    from d2r_chargen.character import load_character_yaml, build_all_items

    char_def = load_character_yaml(yaml_path)
    items = build_all_items(char_def)

    # Count expected items from definition
    equip_count = len(char_def.get("equipment", []))
    charm_count = 0
    inventory = char_def.get("inventory", {})
    if isinstance(inventory, dict):
        for charm_def in inventory.get("charms", []):
            if isinstance(charm_def, dict):
                # Check for count: N style charms
                for key, val in charm_def.items():
                    if key.startswith("magic_") and isinstance(val, dict):
                        charm_count += val.get("count", 1)
                        break
                else:
                    charm_count += 1

    # Merc equipment placed in stash
    merc = char_def.get("merc", {})
    merc_count = 0
    if isinstance(merc, dict):
        merc_count = len(merc.get("equipment", []))

    min_expected = equip_count + charm_count + merc_count
    assert len(items) >= min_expected, (
        f"Expected >= {min_expected} items "
        f"(equip={equip_count}, charms={charm_count}, merc={merc_count}), "
        f"got {len(items)}"
    )


@pytest.mark.integration
@pytest.mark.parametrize(
    "yaml_path",
    _fixture_yamls(),
    ids=lambda p: os.path.basename(p).replace("_fixture.yaml", ""),
)
def test_fixture_scans_clean(yaml_path):
    """Full .d2s build + scanner produces zero hard errors."""
    from d2r_chargen.character import load_character_yaml, build_all_items
    from d2r_chargen.save import (
        set_character_stats, set_skills,
        rebuild_items, calc_checksum,
    )
    from d2r_chargen.resolve import resolve_skills
    from d2r_chargen.scanner import scan_character_data
    import d2r_chargen

    char_def = load_character_yaml(yaml_path)
    all_items = build_all_items(char_def)

    # Use bundled template .d2s
    template_path = os.path.join(
        os.path.dirname(os.path.abspath(d2r_chargen.__file__)),
        "data", "template.d2s",
    )

    with tempfile.NamedTemporaryFile(suffix=".d2s", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        shutil.copy2(template_path, tmp_path)

        # Set stats + skills
        data = bytearray(open(tmp_path, "rb").read())
        skill_array = resolve_skills(
            char_def["class"], char_def.get("skills", {})
        )
        stats = char_def["stats"]
        data = set_character_stats(
            data,
            stats["strength"], stats["dexterity"],
            stats["vitality"], stats["energy"],
            level=char_def.get("level", 99),
            char_class=char_def["class"],
            skill_points_spent=sum(skill_array),
        )
        data = set_skills(data, skill_array)

        # Fix size + checksum
        struct.pack_into("<I", data, 8, len(data))
        data[12:16] = b"\x00\x00\x00\x00"
        cs = calc_checksum(data)
        struct.pack_into("<I", data, 12, cs)
        with open(tmp_path, "wb") as f:
            f.write(data)

        # Inject all items
        item_bytes_list = [item_bytes for _, item_bytes in all_items]
        result_data = rebuild_items(tmp_path, item_bytes_list, [])
        with open(tmp_path, "wb") as f:
            f.write(result_data)

        # Scanner validation
        scan = scan_character_data(tmp_path)
        fixture_name = os.path.basename(yaml_path)

        assert scan["checksum_ok"], (
            f"{fixture_name}: checksum failed"
        )
        assert scan["size_ok"], (
            f"{fixture_name}: stored size != actual size"
        )
        assert len(scan["errors"]) == 0, (
            f"{fixture_name}: scanner errors:\n"
            + "\n".join(f"  - {e}" for e in scan["errors"])
        )
        # Item count sanity check (not exact — fillers are embedded in parents)
        assert scan["item_count"] > 0, (
            f"{fixture_name}: scanner found 0 items"
        )
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@pytest.mark.integration
def test_all_classes_covered():
    """Verify fixture files cover all 8 D2R classes."""
    from d2r_chargen.character import load_character_yaml

    classes_found = set()
    for yaml_path in _fixture_yamls():
        char_def = load_character_yaml(yaml_path)
        classes_found.add(char_def["class"])

    expected = {
        "amazon", "sorceress", "necromancer", "paladin",
        "barbarian", "druid", "assassin", "warlock",
    }
    missing = expected - classes_found
    assert not missing, f"Missing class coverage: {missing}"
