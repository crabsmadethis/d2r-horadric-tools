"""Regression test for CTC (chance-to-cast) level encoding.

Bug observed 2026-04-19: Grief Berserker Axe rendered in-game as
"level 0 Venom on striking" because resolve.py Format 3 (plain skill-name
param) encoded skill_id alone in the param field, omitting the level bits.

D2R CTC param encoding: (level << 10) | skill_id.
"""
import pytest

# Skip entire file if game data not extracted
pytest.importorskip("d2r_chargen.data.item_stat_cost",
                     reason="game data not extracted (run 'd2r-mod extract')")

from d2r_chargen.resolve import _resolve_stat_entry


def _decode_ctc_param(param: int) -> tuple[int, int]:
    """Return (level, skill_id) from a CTC-encoded param."""
    skill_id = param & 0x3FF  # 10 bits
    level = (param >> 10) & 0x3F  # 6 bits
    return level, skill_id


class TestFormat3SkillNamePlain:
    """Plain skill name string (e.g. 'Venom') — the path that broke Grief."""

    def test_grief_venom_encodes_level_and_skill(self):
        entry = {
            'stat': 'item_skillonhit',
            'min': 35, 'max': 15,
            'param_type': 'ctc', 'param': 'Venom',
        }
        result = _resolve_stat_entry(entry, use_max=True)
        assert len(result) == 1
        stat_id, chance, encoded_param = result[0]
        assert stat_id == 198  # item_skillonhit
        assert chance == 35   # from min
        level, skill_id = _decode_ctc_param(encoded_param)
        assert level == 15    # from max
        assert skill_id == 278  # Venom

    def test_bone_bonespear_encodes_correctly(self):
        """Bone runeword — Bone Spear CTC on hit."""
        entry = {
            'stat': 'item_skillonhit',
            'min': 15, 'max': 10,
            'param_type': 'ctc', 'param': 'Bone Spear',
        }
        result = _resolve_stat_entry(entry, use_max=True)
        stat_id, chance, encoded_param = result[0]
        assert chance == 15
        level, skill_id = _decode_ctc_param(encoded_param)
        assert level == 10

    def test_level_never_zero_when_max_is_positive(self):
        """Any CTC with positive 'max' must yield non-zero level bits."""
        entry = {
            'stat': 'item_skillonhit',
            'min': 10, 'max': 17,
            'param_type': 'ctc', 'param': 'Chain Lightning',
        }
        result = _resolve_stat_entry(entry, use_max=True)
        _, _, encoded_param = result[0]
        level, _ = _decode_ctc_param(encoded_param)
        assert level > 0, f"level bits are 0 in param 0x{encoded_param:x}"


class TestFormat2NumericSkillId:
    """Numeric skill-id string — baseline, should already work."""

    def test_numeric_skill_id_still_encodes_level(self):
        # Artificial: Charge (skill_id 77) as a numeric-string CTC
        entry = {
            'stat': 'item_skillonhit',
            'min': 20, 'max': 12,
            'param_type': 'ctc', 'param': '77',
        }
        result = _resolve_stat_entry(entry, use_max=True)
        stat_id, chance, encoded_param = result[0]
        assert chance == 20
        level, skill_id = _decode_ctc_param(encoded_param)
        assert level == 12
        assert skill_id == 77
