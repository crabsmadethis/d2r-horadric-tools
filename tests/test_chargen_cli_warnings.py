"""Tests for chargen validation warnings."""


# Skip entire file if game data not extracted
import pytest
pytest.importorskip("d2r_chargen.data.item_stat_cost",
                     reason="game data not extracted (run 'd2r-mod extract')")

from d2r_chargen.character import validate_char_def


def _base_warlock_char_def():
    return {
        'schema_version': 1,
        'name': 'TestWarlock',
        'class': 'warlock',
        'level': 20,
        'stats': {'strength': 10, 'dexterity': 10, 'vitality': 10, 'energy': 10},
        'skills': {'Bind Demon': 1},
        'equipment': [],
    }


def test_warn_bound_demon_source_affixes_need_template_context(capsys):
    char_def = _base_warlock_char_def()
    char_def['bound_demon'] = {
        'template': 'black_lancer_example',
        'source_affixes': ['Fanaticism', 'Cursed'],
        'skill_affixes': 'auto',
    }

    validate_char_def(char_def)
    captured = capsys.readouterr()
    output = captured.err or captured.out

    assert 'bound_demon.source_affixes' in output
    assert 'template-derived or validated package context' in output
    assert 'does not synthesize arbitrary source effects' in output
    assert 'tools/d2s_demon_template_inspect.py' in output
    assert 'docs/bound-demon-template-recipes.md' in output


def test_validate_accepts_validated_bound_demon_package(capsys):
    char_def = _base_warlock_char_def()
    char_def['bound_demon'] = {
        'mode': 'synthesis_validated',
        'package_id': 'row724-black-lancer-seedg-holy-shock-v1',
        'monster_hcidx': 724,
    }

    validate_char_def(char_def)
    captured = capsys.readouterr()
    output = captured.err or captured.out
    assert 'bound_demon.synthesis_validated' in output
    assert 'row724-black-lancer-seedg-holy-shock-v1' in output


def test_validate_rejects_algorithmic_bound_demon_synthesis_mode():
    char_def = _base_warlock_char_def()
    char_def['bound_demon'] = {
        'mode': 'synthesis',
        'monster': 'Black Lancer',
    }

    with pytest.raises(
        ValueError,
        match='algorithmic synthesis surface',
    ):
        validate_char_def(char_def)


def test_validate_rejects_synthesis_only_context_fields():
    char_def = _base_warlock_char_def()
    char_def['bound_demon'] = {
        'template': 'black_lancer_example',
        'runtime_stats_24_31': '02 00 00 00 43 00 00 00',
    }

    with pytest.raises(
        ValueError,
        match='runtime_stats_24_31.*validated package',
    ):
        validate_char_def(char_def)


def test_no_bound_demon_source_warning_without_source_affixes(capsys):
    char_def = _base_warlock_char_def()
    char_def['bound_demon'] = {
        'template': 'black_lancer_example',
        'skill_affixes': 'auto',
    }

    validate_char_def(char_def)
    captured = capsys.readouterr()
    output = captured.err or captured.out

    assert 'bound_demon.source_affixes' not in output


def test_no_bound_demon_source_warning_for_empty_source_affixes(capsys):
    char_def = _base_warlock_char_def()
    char_def['bound_demon'] = {
        'template': 'black_lancer_example',
        'source_affixes': [],
        'skill_affixes': 'auto',
    }

    validate_char_def(char_def)
    captured = capsys.readouterr()
    output = captured.err or captured.out

    assert 'bound_demon.source_affixes' not in output


def test_warn_redundant_unique_properties_matches_canonical(capsys):
    """When a unique item's properties: block exactly matches canonical,
    chargen should warn that it's redundant."""
    char_def = {
        'schema_version': 1,
        'name': 'TestChar',
        'class': 'sorceress',
        'level': 1,
        'stats': {'strength': 10, 'dexterity': 10, 'vitality': 10, 'energy': 10},
        'skills': {},
        'equipment': [
            {
                'slot': 'hands',
                'unique': 'Magefist',
                # Specify properties that match canonical exactly
                # From Magefist canonical: [105, 20], [27, 25], [126, 1],
                # [48, [1, 6]], [31, 10], [16, 30]
                'properties': {
                    'fcr': 20,           # stat 105, value 20
                    'mana_regen': 25,    # stat 27, value 25
                    'item_elemskill': 1, # stat 126, value 1
                    'fire_min': 1,       # part of stat 48 grouped [1, 6]
                    'fire_max': 6,       # part of stat 48 grouped
                    'defense': 10,       # stat 31, value 10
                    'ed': 30,            # stat 16, value 30
                },
            },
        ],
    }
    validate_char_def(char_def)
    captured = capsys.readouterr()
    warning = captured.err or captured.out
    assert 'Magefist' in warning
    assert 'redundant' in warning.lower() or 'extra_properties' in warning.lower()


def test_no_warning_when_using_extra_properties(capsys):
    """extra_properties: block should never trigger the warning."""
    char_def = {
        'schema_version': 1,
        'name': 'TestChar',
        'class': 'sorceress',
        'level': 1,
        'stats': {'strength': 10, 'dexterity': 10, 'vitality': 10, 'energy': 10},
        'skills': {},
        'equipment': [
            {
                'slot': 'hands',
                'unique': 'Magefist',
                'extra_properties': {
                    'fcr': 20,
                    'mana_regen': 25,
                },
            },
        ],
    }
    validate_char_def(char_def)
    captured = capsys.readouterr()
    output = captured.err or captured.out
    assert 'Magefist' not in output or 'redundant' not in output.lower()


def test_no_warning_when_properties_override_canonical(capsys):
    """When properties: values differ from canonical, user intends override.
    No warning — this is the legitimate use case."""
    char_def = {
        'schema_version': 1,
        'name': 'TestChar',
        'class': 'sorceress',
        'level': 1,
        'stats': {'strength': 10, 'dexterity': 10, 'vitality': 10, 'energy': 10},
        'skills': {},
        'equipment': [
            {
                'slot': 'hands',
                'unique': 'Magefist',
                'properties': {
                    'fcr': 50,  # Canonical is 20 — override, so no warning
                },
            },
        ],
    }
    validate_char_def(char_def)
    captured = capsys.readouterr()
    output = captured.err or captured.out
    # Should not warn about redundancy
    assert 'Magefist' not in output or 'redundant' not in output.lower()


def test_no_warning_on_non_unique_items(capsys):
    """Non-unique items (rare, magic, crafted) have no canonical to compare.
    No warning on those."""
    char_def = {
        'schema_version': 1,
        'name': 'TestChar',
        'class': 'sorceress',
        'level': 1,
        'stats': {'strength': 10, 'dexterity': 10, 'vitality': 10, 'energy': 10},
        'skills': {},
        'equipment': [
            {
                'slot': 'hands',
                'base': 'tgl',  # Leather Gloves
                'properties': {
                    'fcr': 20,
                },
            },
        ],
    }
    validate_char_def(char_def)
    captured = capsys.readouterr()
    output = captured.err or captured.out
    # Should have no warning about redundancy (only base items, not uniques)
    assert 'redundant' not in output.lower()


def test_magic_damage_stat_id_correct():
    """Regression test: magic damage uses stat 52 (magicmindam), not stat 50 (lightmindam).

    This test directly verifies that _accumulate_grouped_damage_stats correctly
    maps 'magic_min'/'magic_max' to stat_id 52."""
    from d2r_chargen.character import _accumulate_grouped_damage_stats

    # Simulate user properties with magic damage
    user_props = {
        'magic_min': 5,
        'magic_max': 10,
    }
    result = {}
    _accumulate_grouped_damage_stats(user_props, result)

    # Should accumulate to stat_id 52 with grouped value [5, 10]
    assert 52 in result, f"Expected stat_id 52 in result, got {result}"
    assert result[52] == [5, 10], f"Expected [5, 10] for stat_id 52, got {result[52]}"

    # Stat 50 (light damage) should not be in result
    assert 50 not in result, f"Stat 50 should not be in result (that is light damage), got {result}"
