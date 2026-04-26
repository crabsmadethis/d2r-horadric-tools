"""Tests for d2r_chargen/data/monumod_affixes.py affix lookup table."""
# Skip entire file if game data not extracted
import pytest
pytest.importorskip("d2r_chargen.data.item_stat_cost",
                     reason="game data not extracted (run 'd2r-mod extract')")

from d2r_chargen.data.monumod_affixes import AFFIXES, affix_name


def test_known_affixes_in_bind_demon():
    """Bind Demon (Skills.txt:384) par2..par5 = 5/6/27/30. Display names must match D2R UI."""
    assert AFFIXES[5] == 'Extra Strong'
    assert AFFIXES[6] == 'Extra Fast'
    assert AFFIXES[27] == 'Spectral Hit'
    assert AFFIXES[30] == 'Aura Enchanted'


def test_table_covers_all_monumod_indices():
    """MonUMod.txt has 45 rows (0=none + 44 modifiers). Table must cover 0..44."""
    assert set(AFFIXES.keys()) == set(range(45))


def test_affix_name_known():
    assert affix_name(5) == 'Extra Strong'


def test_affix_name_unknown():
    """Unknown indices return '?<idx>' rather than raising."""
    assert affix_name(99) == '?99'
    assert affix_name(-1) == '?-1'


def test_zero_is_none():
    assert AFFIXES[0] == 'none'
