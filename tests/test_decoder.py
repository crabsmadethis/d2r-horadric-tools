#!/usr/bin/env python3
"""Round-trip tests: encode via build_lib → decode via decoder → compare."""
import unittest
import pytest

item_stat_cost = pytest.importorskip("d2r_chargen.data.item_stat_cost",
                                      reason="game data not extracted (run 'd2r-mod extract')")
ITEM_STAT_COST = item_stat_cost.ITEM_STAT_COST
STAT_BY_NAME = item_stat_cost.STAT_BY_NAME

from d2r_chargen.build_lib import BitWriter, encode_property


def encode_properties(prop_tuples):
    """Encode a list of property tuples to bytes using build_lib.

    Each tuple is (stat_id, value) or (stat_id, value, param).
    Returns bytes.
    """
    w = BitWriter()
    for tup in prop_tuples:
        stat_id = tup[0]
        value = tup[1]
        param = tup[2] if len(tup) > 2 else 0
        encode_property(w, stat_id, value, param)
    w.write_bits(0x1FF, 9)  # terminator
    return w.get_bytes()


class TestDecoderRoundTrip(unittest.TestCase):
    """Encode properties via build_lib, decode back, verify equality."""

    def _round_trip(self, prop_tuples):
        """Encode tuples, decode, return decoded list."""
        from d2r_chargen.decoder import decode_item_properties
        data = encode_properties(prop_tuples)
        decoded, end_bit = decode_item_properties(data, 0)
        return decoded

    def test_simple_scalar_stat(self):
        """e=0: fire_res 30 round-trips."""
        props = [(39, 30)]
        result = self._round_trip(props)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], (39, 30))

    def test_signed_stat_with_offset(self):
        """e=0: defense +50 (stat 31, sA=10) round-trips."""
        props = [(31, 50)]
        result = self._round_trip(props)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], (31, 50))

    def test_skill_by_class_e1(self):
        """e=1: class_skills [2, 'necromancer'] = stat 83, param=class_id."""
        props = [(83, 2, 2)]
        result = self._round_trip(props)
        self.assertEqual(len(result), 1)
        stat_id, value, param = result[0]
        self.assertEqual(stat_id, 83)
        self.assertEqual(value, 2)
        self.assertEqual(param, 2)

    def test_skill_tab_e1(self):
        """e=1: skill_tab [3, 1] = stat 188, param = (class<<3)|tab."""
        props = [(188, 3, 17)]
        result = self._round_trip(props)
        self.assertEqual(len(result), 1)
        stat_id, value, param = result[0]
        self.assertEqual(stat_id, 188)
        self.assertEqual(value, 3)
        self.assertEqual(param, 17)

    def test_ctc_e2(self):
        """e=2: ctc_hit [5, 3, 'Amplify Damage'] round-trips.
        Internal param: (skill_level << 10) | skill_id
        Amplify Damage = skill 66, level 3
        Internal param = (3 << 10) | 66 = 3138
        Bitstream: encoded_param = (skill_id << 6) | skill_level = (66 << 6) | 3 = 4227
        """
        internal_param = (3 << 10) | 66
        props = [(198, 5, internal_param)]
        result = self._round_trip(props)
        self.assertEqual(len(result), 1)
        stat_id, value, param = result[0]
        self.assertEqual(stat_id, 198)
        self.assertEqual(value, 5)
        self.assertEqual(param & 0x3FF, 66)
        self.assertEqual((param >> 10) & 0x3F, 3)

    def test_charges_e3(self):
        """e=3: charges [30, 30, 12, 'Teleport'] round-trips.
        Teleport = skill 54, level 12
        Internal param: (12 << 10) | 54 = 12342
        Value: (max << 8) | cur = (30 << 8) | 30 = 7710
        """
        internal_param = (12 << 10) | 54
        value = (30 << 8) | 30
        props = [(204, value, internal_param)]
        result = self._round_trip(props)
        self.assertEqual(len(result), 1)
        stat_id, decoded_val, decoded_param = result[0]
        self.assertEqual(stat_id, 204)
        self.assertEqual(decoded_val, value)
        self.assertEqual(decoded_param & 0x3FF, 54)
        self.assertEqual((decoded_param >> 10) & 0x3F, 12)

    def test_grouped_stat_poison(self):
        """np=3: poison_min [100, 200, 75] round-trips."""
        props = [(57, [100, 200, 75])]
        result = self._round_trip(props)
        self.assertEqual(len(result), 1)
        stat_id, values = result[0]
        self.assertEqual(stat_id, 57)
        self.assertEqual(values, [100, 200, 75])

    def test_grouped_stat_enhanced_dmg(self):
        """np=2: enhanced_dmg [300, 250] round-trips."""
        props = [(17, [300, 250])]
        result = self._round_trip(props)
        self.assertEqual(len(result), 1)
        stat_id, values = result[0]
        self.assertEqual(stat_id, 17)
        self.assertEqual(values, [300, 250])

    def test_non_class_skill(self):
        """e=0 with param: non_class_skill [3, skill_id=54] round-trips."""
        props = [(97, 3, 54)]
        result = self._round_trip(props)
        self.assertEqual(len(result), 1)
        stat_id, value, param = result[0]
        self.assertEqual(stat_id, 97)
        self.assertEqual(value, 3)
        self.assertEqual(param, 54)

    def test_item_aura(self):
        """e=0 with param: item_aura [15, skill_id=123] round-trips."""
        props = [(151, 15, 123)]
        result = self._round_trip(props)
        self.assertEqual(len(result), 1)
        stat_id, value, param = result[0]
        self.assertEqual(stat_id, 151)
        self.assertEqual(value, 15)
        self.assertEqual(param, 123)

    def test_multiple_stats(self):
        """Multiple stats of different types in one property list."""
        props = [
            (39, 30),
            (57, [100, 100, 100]),
            (127, 2),
        ]
        result = self._round_trip(props)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0], (39, 30))
        self.assertEqual(result[1], (57, [100, 100, 100]))
        self.assertEqual(result[2], (127, 2))

    def test_empty_property_list(self):
        """Just a terminator, no stats."""
        from d2r_chargen.decoder import decode_item_properties
        w = BitWriter()
        w.write_bits(0x1FF, 9)
        data = w.get_bytes()
        decoded, end_bit = decode_item_properties(data, 0)
        self.assertEqual(decoded, [])
