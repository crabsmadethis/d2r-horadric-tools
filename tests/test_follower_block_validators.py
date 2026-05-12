"""Tests for bound_demon: YAML validators (Task 3.3).

Validators live inline in d2r_chargen/character.py at the bound_demon
resolution site. They run before the fixture is read, so a misconfigured
YAML errors fast with a clear message rather than producing a malformed
save.
"""
from pathlib import Path

import pytest


def _build_minimal_char_def(class_name: str, skills: dict | None,
                            bound_demon: dict | None) -> dict:
    """Compose the smallest dict that the validator block walks."""
    cd = {
        'class': class_name,
        'name': 'TestChar',
    }
    if skills is not None:
        cd['skills'] = skills
    if bound_demon is not None:
        cd['bound_demon'] = bound_demon
    return cd


def _run_validators(char_def: dict, fixtures_dir: Path) -> bytes | None:
    """Run the validator block in isolation, mirroring character.py:1296-1318."""
    from d2r_chargen.character import _effective_bind_demon_level
    from d2r_chargen.follower_block import parse_demon_payload
    from d2r_chargen.resolve import resolve_bound_demon

    bound_demon_spec = char_def.get('bound_demon')
    if bound_demon_spec is None:
        return None
    if char_def['class'] != 'warlock':
        raise ValueError(
            f"bound_demon: requires class=warlock, got {char_def['class']!r}"
        )
    bind_demon_lvl = _effective_bind_demon_level(char_def)
    if isinstance(bound_demon_spec, dict) and 'effective_bind_level' in bound_demon_spec:
        try:
            bind_demon_lvl = int(bound_demon_spec['effective_bind_level'])
        except (TypeError, ValueError):
            bind_demon_lvl = 0
    if bind_demon_lvl < 1:
        raise ValueError(
            f"bound_demon: requires effective Bind Demon skill >= 1, got {bind_demon_lvl}"
        )
    payload = resolve_bound_demon(
        bound_demon_spec,
        fixtures_dir,
        effective_bind_level=bind_demon_lvl,
    )
    # Keep the import above live so this isolated validator test fails if the
    # payload is no longer parseable by the public follower decoder.
    parse_demon_payload(payload)
    return payload


FIX = Path(__file__).resolve().parent / 'fixtures'

if not (FIX / 'marrowbind_demon_b.d2s').exists():
    pytest.skip('.d2s fixtures not present (gitignored in public repo)',
                allow_module_level=True)


def test_validator_passes_for_warlock_with_skill():
    """Warlock + Bind Demon >= 1 (canonical YAML form) + valid template = success."""
    cd = _build_minimal_char_def(
        class_name='warlock',
        skills={'Bind Demon': 7},  # canonical form used in chars/*.yaml
        bound_demon={'template': 'marrowbind_demon_b'},
    )
    payload = _run_validators(cd, FIX)
    assert payload is not None
    assert len(payload) == 116


def test_validator_accepts_snake_case_skill_name():
    """Be friendly to YAML written with snake_case skill names."""
    cd = _build_minimal_char_def(
        class_name='warlock',
        skills={'bind_demon': 5},
        bound_demon={'template': 'marrowbind_demon_b'},
    )
    payload = _run_validators(cd, FIX)
    assert payload is not None


def test_validator_rejects_non_warlock_class():
    """Sorceress with bound_demon must error with a class message."""
    cd = _build_minimal_char_def(
        class_name='sorceress',
        skills={'Bind Demon': 7},  # ignored by Sorceress; should still reject on class
        bound_demon={'template': 'marrowbind_demon_b'},
    )
    with pytest.raises(ValueError, match='warlock'):
        _run_validators(cd, FIX)


def test_validator_rejects_warlock_without_skill():
    """Warlock without Bind Demon skill must error."""
    cd = _build_minimal_char_def(
        class_name='warlock',
        skills={},  # no Bind Demon key at all
        bound_demon={'template': 'marrowbind_demon_b'},
    )
    with pytest.raises(ValueError, match='Bind Demon skill'):
        _run_validators(cd, FIX)


def test_validator_rejects_warlock_with_zero_skill():
    """Warlock with Bind Demon: 0 must error (same as missing)."""
    cd = _build_minimal_char_def(
        class_name='warlock',
        skills={'Bind Demon': 0},
        bound_demon={'template': 'marrowbind_demon_b'},
    )
    with pytest.raises(ValueError, match='Bind Demon skill'):
        _run_validators(cd, FIX)


def test_validator_rejects_unknown_template():
    """Unknown fixture template surfaces FileNotFoundError from the resolver."""
    cd = _build_minimal_char_def(
        class_name='warlock',
        skills={'Bind Demon': 1},
        bound_demon={'template': 'nonexistent_fixture'},
    )
    with pytest.raises(FileNotFoundError):
        _run_validators(cd, FIX)


def test_validator_skipped_when_no_bound_demon():
    """No bound_demon: in YAML = no validation, returns None."""
    cd = _build_minimal_char_def(
        class_name='warlock',
        skills={'Bind Demon': 0},
        bound_demon=None,
    )
    assert _run_validators(cd, FIX) is None


def test_validator_composes_auto_skill_affixes_from_effective_level():
    """Player YAML path derives skill affixes from hard points plus gear."""
    from d2r_chargen.follower_block import parse_demon_payload

    cd = _build_minimal_char_def(
        class_name='warlock',
        skills={'Bind Demon': 10},
        bound_demon={
            'template': 'marrowbind_demon_b',
            'source_affixes': [
                'Fanaticism',
                'Aura Enchanted',
                'Cursed',
                'Stone Skin',
            ],
            'skill_affixes': 'auto',
        },
    )
    cd['equipment'] = [
        {
            'slot': 'helm',
            'rare': True,
            'base': 'ci3',
            'properties': {'all_skills': 10},
        }
    ]

    payload = _run_validators(cd, FIX)
    fields = parse_demon_payload(payload)
    assert fields.affix_indices == bytes([37, 30, 7, 28, 5, 6, 27])


def test_validator_effective_level_override_controls_auto_skill_affixes():
    """Explicit binding-state override is honored for auto skill affixes."""
    from d2r_chargen.follower_block import parse_demon_payload

    cd = _build_minimal_char_def(
        class_name='warlock',
        skills={'Bind Demon': 1},
        bound_demon={
            'template': 'marrowbind_demon_b',
            'source_affixes': ['Cursed'],
            'skill_affixes': 'auto',
            'effective_bind_level': 15,
        },
    )

    payload = _run_validators(cd, FIX)
    fields = parse_demon_payload(payload)
    assert fields.affix_indices == bytes([7, 5, 6, 27, 0, 0, 0])
