"""Tests for the merc header writer in d2r_chargen/save.py.

Encoding verified 2026-04-19 via disk diff:
  0xa3  u32 LE   name seed
  0xa7  u16 LE   unknown (field_a7)
  0xa9  u16 LE   Hireling.txt Id column
  0xab  u32 LE   merc XP
"""
import struct
from pathlib import Path

import pytest

# Skip entire file if game data not extracted
pytest.importorskip("d2r_chargen.data.item_stat_cost",
                     reason="game data not extracted (run 'd2r-mod extract')")

from d2r_chargen.save import set_merc_header, MERC_HIRELING_ID


def _make_buffer(size: int = 0x200) -> bytearray:
    """Produce a zero-filled buffer large enough to hold merc fields."""
    return bytearray(size)


class TestSetMercHeader:
    def test_writes_hireling_id_u16_at_0xa9(self):
        buf = _make_buffer()
        set_merc_header(buf, hireling_id=21, seed=0x12345678, field_a7=10, xp=100)
        assert struct.unpack_from('<H', buf, 0xa9)[0] == 21

    def test_writes_seed_u32_at_0xa3(self):
        buf = _make_buffer()
        set_merc_header(buf, hireling_id=5, seed=0xDEADBEEF)
        assert struct.unpack_from('<I', buf, 0xa3)[0] == 0xDEADBEEF

    def test_writes_field_a7_u16(self):
        buf = _make_buffer()
        set_merc_header(buf, hireling_id=5, seed=0, field_a7=13)
        assert struct.unpack_from('<H', buf, 0xa7)[0] == 13

    def test_writes_xp_u32_at_0xab(self):
        buf = _make_buffer()
        set_merc_header(buf, hireling_id=5, seed=0, xp=0x07157FDC)
        assert struct.unpack_from('<I', buf, 0xab)[0] == 0x07157FDC

    def test_default_seed_random(self):
        """When seed=None, fills with a u32 value."""
        buf = _make_buffer()
        set_merc_header(buf, hireling_id=5)
        v = struct.unpack_from('<I', buf, 0xa3)[0]
        # Vanishingly unlikely two successive random u32s are both zero
        buf2 = _make_buffer()
        set_merc_header(buf2, hireling_id=5)
        v2 = struct.unpack_from('<I', buf2, 0xa3)[0]
        assert (v, v2) != (0, 0)

    def test_rejects_oversize_hireling_id(self):
        buf = _make_buffer()
        with pytest.raises(ValueError):
            set_merc_header(buf, hireling_id=0x10000)

    def test_does_not_touch_other_bytes(self):
        buf = bytearray(b'\xaa' * 0x200)
        set_merc_header(buf, hireling_id=5, seed=0, field_a7=0, xp=0)
        # Bytes before 0xa3 untouched
        assert all(b == 0xaa for b in buf[:0xa3])
        # Bytes after 0xaf untouched
        assert all(b == 0xaa for b in buf[0xaf:])


class TestHirelingIdMapping:
    """Sanity checks on the template → Hireling.Id lookup table."""

    def test_act3_fire_is_21(self):
        """Matches Geshef (Act 3 Fire Iron Wolf, Hell) from DR-3 diff."""
        assert MERC_HIRELING_ID['act3_fire'] == 21

    def test_act1_cold_is_5(self):
        """Matches Elexa (Cold Arrow Rogue, Hell) from DR-3 diff."""
        assert MERC_HIRELING_ID['act1_cold'] == 5

    def test_act2_might_is_35(self):
        """Might aura Act 2 Desert, Hell tier — key for infinity_might template."""
        assert MERC_HIRELING_ID['act2_might'] == 35


class TestRoundTripAgainstRealPyreDiff:
    """Apply set_merc_header to pre-dismiss Pyre.d2s and verify the merc
    region matches post-hire Elexa state exactly (except for seed/XP which
    are session-random)."""

    PRE_PATH = Path('/tmp/Pyre.d2s.pre_dismiss')
    POST_PATH = Path('/tmp/Pyre.d2s.post_elexa')

    @pytest.mark.skipif(
        not (Path('/tmp/Pyre.d2s.pre_dismiss').exists()
             and Path('/tmp/Pyre.d2s.post_elexa').exists()),
        reason="DR-3 diff fixture files not present",
    )
    def test_hireling_id_matches_elexa_post_hire(self):
        post = self.POST_PATH.read_bytes()
        assert struct.unpack_from('<H', post, 0xa9)[0] == 5
        # If we apply the same to the pre file, we should end up with Id=5
        pre = bytearray(self.PRE_PATH.read_bytes())
        set_merc_header(pre, hireling_id=5, seed=0xf8a9e29b, field_a7=13,
                        xp=0x07157FDC)
        assert struct.unpack_from('<H', pre, 0xa9)[0] == 5
        # And bytes 0xa3-0xae match the live post-hire file exactly
        assert pre[0xa3:0xaf] == post[0xa3:0xaf]
