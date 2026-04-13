"""Test fixture characters: YAML validation and item building across all classes.

Parametrized across all fixture YAML files in tests/fixtures/ to verify:
1. YAML loads and validates (schema, required fields, stat minimums)
2. Item building produces valid binary output without errors
3. All equipment items produce non-empty bytes
"""
import os
import glob
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
