#!/usr/bin/env python3
"""Unit tests for encoding primitives in d2r_chargen/build_lib.py.

Tests BitWriter, encode_property, and encode_properties_terminated
independently of full character builds.
"""
import unittest
import unittest.mock

# Skip entire file if game data not extracted
import pytest
pytest.importorskip("d2r_chargen.data.item_stat_cost",
                     reason="game data not extracted (run 'd2r-mod extract')")

from d2r_chargen.build_lib import (
    BitWriter,
    build_item,
    encode_property,
    encode_properties_terminated,
)
from d2r_chargen.data.huffman import HUFFMAN
from d2r_chargen.data.item_stat_cost import ITEM_STAT_COST
from d2r_chargen.decoder import decode_item_properties
from d2r_chargen.warnings import BuildWarnings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def read_bits(buf, pos, count):
    """Read `count` bits from `buf` starting at bit `pos`, LSB-first."""
    val = 0
    for i in range(count):
        byte_idx = (pos + i) >> 3
        bit_idx = (pos + i) & 7
        val |= ((buf[byte_idx] >> bit_idx) & 1) << i
    return val


def encode_properties_to_bytes(prop_tuples):
    """Encode a list of property tuples to terminated bytes.

    Each tuple is (stat_id, value) or (stat_id, value, param).
    Returns bytes with 0x1FF terminator.
    """
    w = BitWriter()
    for tup in prop_tuples:
        stat_id = tup[0]
        value = tup[1]
        param = tup[2] if len(tup) > 2 else 0
        encode_property(w, stat_id, value, param)
    w.write_bits(0x1FF, 9)  # terminator
    return w.get_bytes()


def roundtrip(prop_tuples):
    """Encode properties, decode them, return decoded list."""
    data = encode_properties_to_bytes(prop_tuples)
    decoded, _ = decode_item_properties(data, 0)
    return decoded


# =========================================================================
# TestBitWriter (~12 tests)
# =========================================================================
class TestBitWriter(unittest.TestCase):
    """Tests for BitWriter class in build_lib."""

    def test_write_single_value(self):
        """write_bits stores correct value in buffer."""
        w = BitWriter()
        w.write_bits(0b10110, 5)
        # Bits 0-4 should be 10110 LSB-first in buf[0]
        self.assertEqual(read_bits(w.buf, 0, 5), 0b10110)
        self.assertEqual(w.pos, 5)

    def test_lsb_first_ordering(self):
        """Bits are written LSB-first (D2R format).

        Writing value 5 (binary 101) in 3 bits should produce:
          bit 0 = 1 (LSB), bit 1 = 0, bit 2 = 1
        So buf[0] should have bit 0=1, bit 1=0, bit 2=1 -> 0b00000101 = 5.
        """
        w = BitWriter()
        w.write_bits(5, 3)
        self.assertEqual(w.buf[0] & 0x07, 5)

    def test_multi_write_packing(self):
        """Sequential writes pack into the buffer correctly."""
        w = BitWriter()
        w.write_bits(0b11, 2)   # bits 0-1
        w.write_bits(0b101, 3)  # bits 2-4
        # Combined: bits 0-4 = 11 | (101 << 2) = 0b10111 = 23
        val = read_bits(w.buf, 0, 5)
        self.assertEqual(val, 0b10111)
        self.assertEqual(w.pos, 5)

    def test_byte_boundary_crossing(self):
        """Values that span two bytes encode correctly."""
        w = BitWriter()
        w.write_bits(0, 6)       # fill 6 bits of byte 0
        w.write_bits(0b1011, 4)  # bits 6-9 span bytes 0 and 1
        val = read_bits(w.buf, 6, 4)
        self.assertEqual(val, 0b1011)

    def test_align_pads_to_byte(self):
        """align() advances to next byte boundary."""
        w = BitWriter()
        w.write_bits(1, 3)
        self.assertEqual(w.pos, 3)
        w.align()
        self.assertEqual(w.pos, 8)

    def test_align_noop_when_aligned(self):
        """align() is no-op when already byte-aligned."""
        w = BitWriter()
        w.write_bits(0xFF, 8)
        self.assertEqual(w.pos, 8)
        w.align()
        self.assertEqual(w.pos, 8)

    def test_get_bytes_returns_aligned(self):
        """get_bytes() byte-aligns and returns correct length."""
        w = BitWriter()
        w.write_bits(0xFF, 8)   # 1 byte
        w.write_bits(0b101, 3)  # 3 extra bits -> pads to 2 bytes
        result = w.get_bytes()
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], 0xFF)
        # byte 1: bits 0-2 = 101 = 5, rest zero-padded
        self.assertEqual(result[1], 0x05)

    def test_write_huff_known_codes(self):
        """write_huff produces expected bits for known type codes.

        Test with space (1, 2 bits) and 's' (4, 4 bits).
        """
        w = BitWriter()
        # Space: value=1, bits=2
        sp_val, sp_bits = HUFFMAN[' ']
        self.assertEqual(sp_val, 1)
        self.assertEqual(sp_bits, 2)

        # 's': value=4, bits=4
        s_val, s_bits = HUFFMAN['s']
        self.assertEqual(s_val, 4)
        self.assertEqual(s_bits, 4)

        w.write_huff(' ')
        w.write_huff('s')
        # First 2 bits: space = 1 (01 in LSB)
        self.assertEqual(read_bits(w.buf, 0, 2), 1)
        # Next 4 bits: s = 4 (0100 in LSB)
        self.assertEqual(read_bits(w.buf, 2, 4), 4)

    def test_write_zero_bits(self):
        """write_bits(0, N) writes N zero bits."""
        w = BitWriter()
        w.write_bits(0, 16)
        self.assertEqual(w.pos, 16)
        self.assertEqual(w.buf[0], 0)
        self.assertEqual(w.buf[1], 0)

    def test_write_max_value(self):
        """write_bits((1<<N)-1, N) writes all-ones in N bits."""
        w = BitWriter()
        w.write_bits((1 << 9) - 1, 9)  # 0x1FF = 511
        # Byte 0: all 8 bits set = 0xFF
        self.assertEqual(w.buf[0], 0xFF)
        # Byte 1: bit 0 set = 0x01
        self.assertEqual(w.buf[1] & 0x01, 0x01)
        self.assertEqual(w.pos, 9)

    def test_sequential_values(self):
        """Multiple write_bits calls produce expected byte sequence."""
        w = BitWriter()
        # Write 0xAB (8 bits) then 0xCD (8 bits)
        w.write_bits(0xAB, 8)
        w.write_bits(0xCD, 8)
        result = w.get_bytes()
        self.assertEqual(result[0], 0xAB)
        self.assertEqual(result[1], 0xCD)

    def test_large_write_near_buffer(self):
        """Writing near 8192-byte buffer limit works."""
        w = BitWriter()
        # Write 8191 bytes worth of data (65528 bits)
        for _ in range(8191):
            w.write_bits(0xAA, 8)
        self.assertEqual(w.pos, 8191 * 8)
        # Write a few more bits into the last byte
        w.write_bits(0b101, 3)
        result = w.get_bytes()
        self.assertEqual(len(result), 8192)
        self.assertEqual(result[-1] & 0x07, 0x05)


# =========================================================================
# TestEncodeProperty (~25 tests)
# =========================================================================
class TestEncodeProperty(unittest.TestCase):
    """Tests for encode_property() in build_lib.

    Uses roundtrip verification: encode via encode_property, decode via
    decoder.decode_item_properties, assert values match.
    """

    # --- e=0 standard encoding ---

    def test_e0_simple_unsigned(self):
        """e=0: fire_res (stat 39, sA=200, sB=9) value=30 roundtrips.

        Actual data: stat 39 fireresist has sB=9, sA=200, sS=1.
        Encoded value = 30 + 200 = 230 in 9 bits.
        """
        info = ITEM_STAT_COST[39]
        self.assertEqual(info['s'], 'fireresist')
        self.assertEqual(info['sB'], 9)
        self.assertEqual(info.get('sA', 0), 200)

        result = roundtrip([(39, 30)])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], (39, 30))

    def test_e0_enhanced_defense(self):
        """e=0: item_armor_percent (stat 16, sA=0, sB=9) value=200."""
        info = ITEM_STAT_COST[16]
        self.assertEqual(info['s'], 'item_armor_percent')
        self.assertEqual(info['sB'], 9)

        result = roundtrip([(16, 200)])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], (16, 200))

    def test_e0_all_skills(self):
        """e=0: item_allskills (stat 127, sB=3) value=2."""
        info = ITEM_STAT_COST[127]
        self.assertEqual(info['s'], 'item_allskills')
        self.assertEqual(info['sB'], 3)

        result = roundtrip([(127, 2)])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], (127, 2))

    def test_e0_signed_positive(self):
        """e=0 signed: armorclass (stat 31, sA=10, sB=11, sS=1) value=50.

        Encoded = 50 + 10 = 60 in 11 bits (positive, no two's complement).
        """
        info = ITEM_STAT_COST[31]
        self.assertEqual(info['s'], 'armorclass')
        self.assertEqual(info['sB'], 11)
        self.assertEqual(info.get('sA', 0), 10)
        self.assertEqual(info.get('sS', 0), 1)

        result = roundtrip([(31, 50)])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], (31, 50))

    def test_e0_signed_negative(self):
        """e=0 signed negative: mindamage (stat 21, sA=0, sB=6, sS=1) value=-3.

        encoded = -3 + 0 = -3 -> two's complement in 6 bits = 61.
        The decoder returns raw_val - sA = 61 - 0 = 61 (unsigned interpretation)
        because the decoder does not perform sign extension.
        Verify at the bit level that two's complement is stored correctly.
        """
        info = ITEM_STAT_COST[21]
        self.assertEqual(info['s'], 'mindamage')
        self.assertEqual(info['sB'], 6)
        self.assertEqual(info.get('sA', 0), 0)
        self.assertEqual(info.get('sS', 0), 1)

        # Encode value=-3
        w = BitWriter()
        encode_property(w, 21, -3)
        # Verify at bit level: 9-bit stat_id=21 + 6-bit two's complement(-3)
        stat_id_bits = read_bits(w.buf, 0, 9)
        self.assertEqual(stat_id_bits, 21)
        val_bits = read_bits(w.buf, 9, 6)
        # -3 in 6-bit two's complement = (1<<6) - 3 = 61
        self.assertEqual(val_bits, 61)

        # Roundtrip: decoder sign-extends the two's complement value back to -3
        result = roundtrip([(21, -3)])
        self.assertEqual(len(result), 1)
        stat_id, value = result[0]
        self.assertEqual(stat_id, 21)
        self.assertEqual(value, -3)

    # --- e=0 direct bit-level verification ---

    def test_e0_bit_level_fire_res(self):
        """Verify fire_res bit-level encoding directly.

        stat 39: sB=9, sA=200, value=30 -> encoded_val=230
        Bitstream: 9-bit stat_id(39) + 9-bit value(230)
        """
        w = BitWriter()
        encode_property(w, 39, 30)

        stat_id = read_bits(w.buf, 0, 9)
        self.assertEqual(stat_id, 39)

        encoded_val = read_bits(w.buf, 9, 9)
        self.assertEqual(encoded_val, 230)  # 30 + 200

    # --- e=1 skill-by-class encoding ---

    def test_e1_class_skills(self):
        """e=1: item_addclassskills (stat 83, sP=3) value=2, param=2 (necro).

        Bitstream: 9-bit stat_id(83) + 3-bit param(2) + 3-bit value(2).
        """
        info = ITEM_STAT_COST[83]
        self.assertEqual(info['s'], 'item_addclassskills')
        self.assertEqual(info['sP'], 3)
        self.assertEqual(info['sB'], 3)

        # Bit-level check
        w = BitWriter()
        encode_property(w, 83, 2, 2)
        stat_id = read_bits(w.buf, 0, 9)
        self.assertEqual(stat_id, 83)
        param_bits = read_bits(w.buf, 9, 3)
        self.assertEqual(param_bits, 2)
        val_bits = read_bits(w.buf, 12, 3)
        self.assertEqual(val_bits, 2)

        # Roundtrip
        result = roundtrip([(83, 2, 2)])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], (83, 2, 2))

    def test_e1_skill_tab(self):
        """e=1: item_addskill_tab (stat 188, sP=16) value=3, param=17.

        param = (class_id << 3) | tab = (2 << 3) | 1 = 17
        Bitstream: 9-bit stat_id + 16-bit param + 3-bit value
        """
        info = ITEM_STAT_COST[188]
        self.assertEqual(info['s'], 'item_addskill_tab')
        self.assertEqual(info['sP'], 16)
        self.assertEqual(info['sB'], 3)

        # Bit-level check
        w = BitWriter()
        encode_property(w, 188, 3, 17)
        stat_id = read_bits(w.buf, 0, 9)
        self.assertEqual(stat_id, 188)
        param_bits = read_bits(w.buf, 9, 16)
        self.assertEqual(param_bits, 17)
        val_bits = read_bits(w.buf, 25, 3)
        self.assertEqual(val_bits, 3)

        # Roundtrip
        result = roundtrip([(188, 3, 17)])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], (188, 3, 17))

    # --- e=2 chance-to-cast encoding ---

    def test_e2_ctc_hit(self):
        """e=2: item_skillonhit (stat 198, sP=16, sA=0).

        Caller param: skill_id | (skill_level << 10) = 66 | (3 << 10) = 3138
        Encoder re-packs: (skill_id << 6) | skill_level = (66 << 6) | 3 = 4227
        Value = 5 (chance %), encoded = 5 + 0 = 5
        """
        info = ITEM_STAT_COST[198]
        self.assertEqual(info['s'], 'item_skillonhit')
        self.assertEqual(info['sP'], 16)
        self.assertEqual(info.get('e', 0), 2)

        internal_param = 66 | (3 << 10)  # 3138
        self.assertEqual(internal_param, 3138)

        # Bit-level check
        w = BitWriter()
        encode_property(w, 198, 5, internal_param)
        stat_id = read_bits(w.buf, 0, 9)
        self.assertEqual(stat_id, 198)
        # Encoded param = (66 << 6) | 3 = 4227
        encoded_param = read_bits(w.buf, 9, 16)
        self.assertEqual(encoded_param, 4227)
        # Value = 5 + sA(0) = 5 in 7 bits
        val_bits = read_bits(w.buf, 25, 7)
        self.assertEqual(val_bits, 5)

        # Roundtrip
        result = roundtrip([(198, 5, internal_param)])
        self.assertEqual(len(result), 1)
        stat_id, value, param = result[0]
        self.assertEqual(stat_id, 198)
        self.assertEqual(value, 5)
        self.assertEqual(param & 0x3FF, 66)
        self.assertEqual((param >> 10) & 0x3F, 3)

    def test_e2_ctc_value_with_offset(self):
        """e=2: verify value + sA encoding for item_skillonattack (stat 195).

        stat 195: sB=7, sA=0, sP=16, e=2
        """
        info = ITEM_STAT_COST[195]
        self.assertEqual(info['s'], 'item_skillonattack')
        self.assertEqual(info.get('e', 0), 2)
        self.assertEqual(info.get('sA', 0), 0)

        # skill_id=54 (Teleport), level=5
        internal_param = 54 | (5 << 10)
        result = roundtrip([(195, 10, internal_param)])
        self.assertEqual(len(result), 1)
        stat_id, value, param = result[0]
        self.assertEqual(stat_id, 195)
        self.assertEqual(value, 10)
        self.assertEqual(param & 0x3FF, 54)
        self.assertEqual((param >> 10) & 0x3F, 5)

    # --- e=3 charges encoding ---

    def test_e3_charges(self):
        """e=3: item_charged_skill (stat 204, sP=16).

        Value is raw (NOT offset by sA). (max_charges << 8) | cur_charges
        Teleport skill_id=54, level=12.
        Internal param = 54 | (12 << 10) = 12342
        Value = (30 << 8) | 30 = 7710
        """
        info = ITEM_STAT_COST[204]
        self.assertEqual(info['s'], 'item_charged_skill')
        self.assertEqual(info.get('e', 0), 3)
        self.assertEqual(info['sB'], 16)
        self.assertEqual(info['sP'], 16)

        internal_param = 54 | (12 << 10)
        value = (30 << 8) | 30

        # Bit-level: verify value is written raw (not offset)
        w = BitWriter()
        encode_property(w, 204, value, internal_param)
        stat_id = read_bits(w.buf, 0, 9)
        self.assertEqual(stat_id, 204)
        # Encoded param = (54 << 6) | 12 = 3468
        encoded_param = read_bits(w.buf, 9, 16)
        self.assertEqual(encoded_param, (54 << 6) | 12)
        # Value stored raw
        raw_val = read_bits(w.buf, 25, 16)
        self.assertEqual(raw_val, value)

    def test_e3_charges_param(self):
        """e=3: verify param re-packing for charges.

        Caller: param = skill_id | (skill_level << 10)
        Bitstream: encoded_param = (skill_id << 6) | skill_level
        """
        # Battle Orders skill_id=149, level=3
        internal_param = 149 | (3 << 10)
        value = (40 << 8) | 40  # 40/40 charges

        # Roundtrip
        result = roundtrip([(204, value, internal_param)])
        self.assertEqual(len(result), 1)
        stat_id, decoded_val, decoded_param = result[0]
        self.assertEqual(stat_id, 204)
        self.assertEqual(decoded_val, value)
        self.assertEqual(decoded_param & 0x3FF, 149)
        self.assertEqual((decoded_param >> 10) & 0x3F, 3)

    # --- Grouped stats ---

    def test_grouped_fire_np2(self):
        """firemindam (stat 48, np=2): value=[10, 20].

        Writes stat_id 48 once, then two member values:
          firemindam: sB=8, sA=0 -> 10 in 8 bits
          firemaxdam:  sB=9, sA=0 -> 20 in 9 bits
        """
        info48 = ITEM_STAT_COST[48]
        info49 = ITEM_STAT_COST[49]
        self.assertEqual(info48['s'], 'firemindam')
        self.assertEqual(info49['s'], 'firemaxdam')

        # Bit-level check
        w = BitWriter()
        encode_property(w, 48, [10, 20])
        stat_id = read_bits(w.buf, 0, 9)
        self.assertEqual(stat_id, 48)
        val0 = read_bits(w.buf, 9, 8)     # firemindam sB=8
        self.assertEqual(val0, 10)
        val1 = read_bits(w.buf, 17, 9)    # firemaxdam sB=9
        self.assertEqual(val1, 20)

        # Roundtrip
        result = roundtrip([(48, [10, 20])])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], (48, [10, 20]))

    def test_grouped_poison_np3(self):
        """poisonmindam (stat 57, np=3): value=[100, 100, 200].

        Members: 57 (sB=10), 58 (sB=10), 59 (sB=9)
        """
        info57 = ITEM_STAT_COST[57]
        info58 = ITEM_STAT_COST[58]
        info59 = ITEM_STAT_COST[59]
        self.assertEqual(info57['s'], 'poisonmindam')
        self.assertEqual(info58['s'], 'poisonmaxdam')
        self.assertEqual(info59['s'], 'poisonlength')
        self.assertEqual(info57['sB'], 10)
        self.assertEqual(info58['sB'], 10)
        self.assertEqual(info59['sB'], 9)

        # Bit-level check
        w = BitWriter()
        encode_property(w, 57, [100, 100, 200])
        stat_id = read_bits(w.buf, 0, 9)
        self.assertEqual(stat_id, 57)
        val0 = read_bits(w.buf, 9, 10)
        self.assertEqual(val0, 100)
        val1 = read_bits(w.buf, 19, 10)
        self.assertEqual(val1, 100)
        val2 = read_bits(w.buf, 29, 9)
        self.assertEqual(val2, 200)

        # Roundtrip
        result = roundtrip([(57, [100, 100, 200])])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], (57, [100, 100, 200]))

    def test_grouped_cold_np3(self):
        """coldmindam (stat 54, np=3): value=[50, 75, 100].

        Members: 54 (sB=8), 55 (sB=9), 56 (sB=8)
        """
        info54 = ITEM_STAT_COST[54]
        info55 = ITEM_STAT_COST[55]
        info56 = ITEM_STAT_COST[56]
        self.assertEqual(info54['s'], 'coldmindam')
        self.assertEqual(info55['s'], 'coldmaxdam')
        self.assertEqual(info56['s'], 'coldlength')

        # Roundtrip
        result = roundtrip([(54, [50, 75, 100])])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], (54, [50, 75, 100]))

    def test_grouped_enhanced_dmg_np2(self):
        """item_maxdamage_percent (stat 17, np=2): value=[200, 100].

        Members: 17 (sB=9, sA=0), 18 (sB=9, sA=0)
        """
        info17 = ITEM_STAT_COST[17]
        info18 = ITEM_STAT_COST[18]
        self.assertEqual(info17['s'], 'item_maxdamage_percent')
        self.assertEqual(info18['s'], 'item_mindamage_percent')

        # Bit-level check
        w = BitWriter()
        encode_property(w, 17, [200, 100])
        stat_id = read_bits(w.buf, 0, 9)
        self.assertEqual(stat_id, 17)
        val0 = read_bits(w.buf, 9, 9)   # sB=9
        self.assertEqual(val0, 200)
        val1 = read_bits(w.buf, 18, 9)  # sB=9
        self.assertEqual(val1, 100)

        # Roundtrip
        result = roundtrip([(17, [200, 100])])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], (17, [200, 100]))

    # --- Error cases ---

    def test_overflow_raises(self):
        """encode_property raises ValueError if value overflows sB bits.

        hpregen (stat 74): sB=6, sA=30, sS=0 (unsigned).
        max encoded = (1<<6)-1 = 63. So max value = 63-30 = 33.
        value=34 -> encoded=64 -> exceeds 6-bit range [0, 63].
        """
        w = BitWriter()
        info = ITEM_STAT_COST[74]
        self.assertEqual(info['s'], 'hpregen')
        self.assertEqual(info['sB'], 6)
        self.assertEqual(info.get('sA', 0), 30)
        with self.assertRaises(ValueError):
            encode_property(w, 74, 34)

    def test_e0_with_param_nonclass_skill(self):
        """e=0 with param: item_nonclassskill (stat 97, sP=9, e=1).

        Actually e=1 but encoding is same as e=0 with param.
        """
        info = ITEM_STAT_COST[97]
        self.assertEqual(info['s'], 'item_nonclassskill')
        self.assertEqual(info.get('e', 0), 1)

        result = roundtrip([(97, 3, 54)])
        self.assertEqual(len(result), 1)
        stat_id, value, param = result[0]
        self.assertEqual(stat_id, 97)
        self.assertEqual(value, 3)
        self.assertEqual(param, 54)


# =========================================================================
# TestEncodePropertiesTerminated (~8 tests)
# =========================================================================
class TestEncodePropertiesTerminated(unittest.TestCase):
    """Tests for encode_properties_terminated() in build_lib."""

    def test_single_property_terminated(self):
        """One property followed by 0x1FF terminator."""
        w = BitWriter()
        encode_properties_terminated(w, [(39, 30)])
        data = w.get_bytes()

        # Decode: should find one property and stop at terminator
        decoded, end_bit = decode_item_properties(data, 0)
        self.assertEqual(len(decoded), 1)
        self.assertEqual(decoded[0], (39, 30))

        # Verify terminator: 9 bits of 0x1FF just before end
        # stat 39: 9 bits id + 9 bits value = 18 bits
        term = read_bits(data, 18, 9)
        self.assertEqual(term, 0x1FF)

    def test_multiple_properties_terminated(self):
        """Correct concatenation + single terminator."""
        w = BitWriter()
        props = [(39, 30), (127, 2)]
        encode_properties_terminated(w, props)
        data = w.get_bytes()

        decoded, end_bit = decode_item_properties(data, 0)
        self.assertEqual(len(decoded), 2)
        self.assertEqual(decoded[0], (39, 30))
        self.assertEqual(decoded[1], (127, 2))

    def test_runeword_double_terminator(self):
        """is_runeword=True writes two 0x1FF markers."""
        w = BitWriter()
        encode_properties_terminated(w, [(39, 30)], is_runeword=True)
        data = w.get_bytes()

        # Decode with num_terminators=2
        decoded, end_bit = decode_item_properties(data, 0, num_terminators=2)
        self.assertEqual(len(decoded), 1)
        self.assertEqual(decoded[0], (39, 30))

        # Verify two terminators: after 18 bits of data
        term1 = read_bits(data, 18, 9)
        self.assertEqual(term1, 0x1FF)
        term2 = read_bits(data, 27, 9)
        self.assertEqual(term2, 0x1FF)

    def test_empty_list_single_terminator(self):
        """Empty props list produces just 0x1FF."""
        w = BitWriter()
        encode_properties_terminated(w, [])
        data = w.get_bytes()

        decoded, end_bit = decode_item_properties(data, 0)
        self.assertEqual(decoded, [])

        # First 9 bits should be 0x1FF
        term = read_bits(data, 0, 9)
        self.assertEqual(term, 0x1FF)

    def test_empty_list_runeword_double(self):
        """Empty props + is_runeword produces two 0x1FF."""
        w = BitWriter()
        encode_properties_terminated(w, [], is_runeword=True)
        data = w.get_bytes()

        # Should be 18 bits = ceil(18/8) = 3 bytes
        self.assertEqual(len(data), 3)

        term1 = read_bits(data, 0, 9)
        self.assertEqual(term1, 0x1FF)
        term2 = read_bits(data, 9, 9)
        self.assertEqual(term2, 0x1FF)

    def test_legacy_pair_merge_lightning(self):
        """Consecutive (50, val), (51, val) merged into one stat_id write.

        lightmindam (50, np=2): consecutive entries (50, 1), (51, 20)
        merged into single stat_id=50, then 6-bit + 10-bit values.
        """
        w = BitWriter()
        props = [(50, 1), (51, 20)]
        encode_properties_terminated(w, props)
        data = w.get_bytes()

        # Should decode as a single grouped stat
        decoded, end_bit = decode_item_properties(data, 0)
        self.assertEqual(len(decoded), 1)
        stat_id, values = decoded[0]
        self.assertEqual(stat_id, 50)
        self.assertEqual(values, [1, 20])

    def test_legacy_pair_merge_poison(self):
        """Consecutive (57, v), (58, v), (59, v) merged into one stat.

        poisonmindam (57, np=3): consecutive (57, 100), (58, 200), (59, 75)
        """
        w = BitWriter()
        props = [(57, 100), (58, 200), (59, 75)]
        encode_properties_terminated(w, props)
        data = w.get_bytes()

        decoded, end_bit = decode_item_properties(data, 0)
        self.assertEqual(len(decoded), 1)
        stat_id, values = decoded[0]
        self.assertEqual(stat_id, 57)
        self.assertEqual(values, [100, 200, 75])

    def test_no_merge_when_non_consecutive(self):
        """Non-consecutive stat IDs don't trigger legacy merge.

        (50, 1), (39, 30): stat 50 has np=2 but the next entry is stat 39,
        not stat 51. The merge check fails (paired=False), falling through
        to encode_property with a scalar for an np>0 stat -> ValueError.
        """
        w = BitWriter()
        with self.assertRaises(ValueError):
            encode_properties_terminated(w, [(50, 1), (39, 30)])

    def test_non_grouped_stats_no_merge(self):
        """Two unrelated non-grouped stats encode independently."""
        w = BitWriter()
        props = [(39, 30), (127, 2)]
        encode_properties_terminated(w, props)
        data = w.get_bytes()

        decoded, end_bit = decode_item_properties(data, 0)
        self.assertEqual(len(decoded), 2)
        self.assertEqual(decoded[0], (39, 30))
        self.assertEqual(decoded[1], (127, 2))


# =========================================================================
# TestEncodingRejections (~10 tests)
# =========================================================================
class TestEncodingRejections(unittest.TestCase):
    """Verify encode_property() raises ValueError for bad inputs."""

    def test_unknown_stat_id(self):
        """stat_id=9999 is not in ITEM_STAT_COST -> ValueError."""
        w = BitWriter()
        with self.assertRaises(ValueError):
            encode_property(w, 9999, 1)

    def test_sb_zero_stat(self):
        """Stat 4 (statpts) has no sB key -> sB=0 -> ValueError.

        From item_stat_cost.py: 4: {'s': 'statpts', 'cB': 10, 'cS': 0}
        """
        info = ITEM_STAT_COST[4]
        self.assertEqual(info['s'], 'statpts')
        self.assertNotIn('sB', info)  # defaults to 0

        w = BitWriter()
        with self.assertRaises(ValueError):
            encode_property(w, 4, 10)

    def test_unsigned_negative_overflow(self):
        """Unsigned stat where value + sA < 0.

        Stat 74 (hpregen): sB=6, sA=30, sS not present (unsigned).
        value = -(30+1) = -31 -> encoded = -31 + 30 = -1 < 0 -> ValueError.
        """
        info = ITEM_STAT_COST[74]
        self.assertEqual(info['s'], 'hpregen')
        self.assertEqual(info['sB'], 6)
        self.assertEqual(info.get('sA', 0), 30)
        self.assertEqual(info.get('sS', 0), 0)

        w = BitWriter()
        with self.assertRaises(ValueError):
            encode_property(w, 74, -31)

    def test_unsigned_positive_overflow(self):
        """Unsigned stat where value + sA > (1<<sB)-1.

        Stat 74 (hpregen): sB=6, sA=30. Max encoded = 63.
        Max value = 63 - 30 = 33. value=34 -> encoded=64 -> ValueError.
        """
        info = ITEM_STAT_COST[74]
        self.assertEqual(info['s'], 'hpregen')
        sA = info.get('sA', 0)
        sB = info['sB']
        max_val = (1 << sB) - 1  # 63
        overflow_value = max_val - sA + 1  # 34

        w = BitWriter()
        with self.assertRaises(ValueError):
            encode_property(w, 74, overflow_value)

    def test_signed_underflow(self):
        """Signed stat where value + sA < -(1<<(sB-1)).

        Stat 21 (mindamage): sB=6, sA=0, sS=1.
        min signed = -(1<<5) = -32.
        value = -33 -> encoded = -33 + 0 = -33 < -32 -> ValueError.
        """
        info = ITEM_STAT_COST[21]
        self.assertEqual(info['s'], 'mindamage')
        self.assertEqual(info['sB'], 6)
        self.assertEqual(info.get('sA', 0), 0)
        self.assertEqual(info.get('sS', 0), 1)

        min_signed = -(1 << (info['sB'] - 1))  # -32
        underflow_value = min_signed - 1  # -33

        w = BitWriter()
        with self.assertRaises(ValueError):
            encode_property(w, 21, underflow_value)

    def test_grouped_scalar_instead_of_list(self):
        """Stat 57 (poisonmindam, np=3) with scalar value -> ValueError."""
        info = ITEM_STAT_COST[57]
        self.assertEqual(info['s'], 'poisonmindam')
        self.assertEqual(info.get('np', 0), 3)

        w = BitWriter()
        with self.assertRaises(ValueError):
            encode_property(w, 57, 100)

    def test_grouped_wrong_length(self):
        """Stat 57 (poisonmindam, np=3) with 2-element list -> ValueError."""
        w = BitWriter()
        with self.assertRaises(ValueError):
            encode_property(w, 57, [100, 200])

    def test_grouped_member_overflow(self):
        """Stat 57 (poisonmindam, np=3): third member overflows.

        Member 59 (poisonlength): sB=9, sA=0, sS=1.
        For unsigned-like positive overflow: max_val = (1<<9)-1 = 511.
        value[2] = 512 -> encoded = 512 + 0 = 512 > 511 -> ValueError.
        """
        info59 = ITEM_STAT_COST[59]
        self.assertEqual(info59['s'], 'poisonlength')
        self.assertEqual(info59['sB'], 9)
        self.assertEqual(info59.get('sA', 0), 0)

        w = BitWriter()
        with self.assertRaises(ValueError):
            encode_property(w, 57, [100, 100, 512])

    def test_e2_value_overflow(self):
        """CTC stat 198 (item_skillonhit, e=2): value overflow.

        sB=7, sA=0. Max encoded = 127. value=128 -> ValueError.
        """
        info = ITEM_STAT_COST[198]
        self.assertEqual(info['s'], 'item_skillonhit')
        self.assertEqual(info.get('e', 0), 2)
        self.assertEqual(info['sB'], 7)
        self.assertEqual(info.get('sA', 0), 0)

        internal_param = 66 | (3 << 10)  # some valid skill param
        w = BitWriter()
        with self.assertRaises(ValueError):
            encode_property(w, 198, 128, internal_param)

    def test_e3_value_overflow(self):
        """Charges stat 204 (item_charged_skill, e=3): no overflow check.

        sB=16, sA=0. Value is raw (not offset by sA). Max = 65535.
        Unlike e=0/e=2, the e=3 path writes value directly via
        w.write_bits(value, sB) with no range check.  65536 is silently
        truncated to 0 (only low 16 bits are written).

        This test documents the current behavior: e=3 does NOT raise
        ValueError on overflow.  If overflow checking is added later this
        test should be updated to expect ValueError.
        """
        info = ITEM_STAT_COST[204]
        self.assertEqual(info['s'], 'item_charged_skill')
        self.assertEqual(info.get('e', 0), 3)
        self.assertEqual(info['sB'], 16)

        internal_param = 54 | (12 << 10)
        w = BitWriter()
        # No ValueError raised — value silently truncated
        encode_property(w, 204, 65536, internal_param)
        # Verify truncation: the 16-bit value field should be 0
        # (65536 & 0xFFFF = 0)
        # Bit layout: 9-bit stat_id + 16-bit param + 16-bit value
        raw_val = read_bits(w.buf, 25, 16)
        self.assertEqual(raw_val, 0)


# =========================================================================
# TestBuildItemRejections (~6 tests)
# =========================================================================
class TestBuildItemRejections(unittest.TestCase):
    """Verify build_item() raises ValueError/AssertionError for bad inputs."""

    def test_unknown_unique_id(self):
        """quality=7 with unique_id=9999 (not in UNIQUE_ITEMS) -> ValueError."""
        with self.assertRaises(ValueError):
            build_item(type_code='amu', col=0, row=0, storage=5,
                       quality=7, unique_id=9999)

    def test_unique_type_mismatch(self):
        """Valid UID 0 (The Gnasher, code='hax') but wrong type_code -> ValueError.

        From unique_items.py: 0: {'name': 'The Gnasher', 'code': 'hax', ...}
        """
        with self.assertRaises(ValueError):
            build_item(type_code='amu', col=0, row=0, storage=5,
                       quality=7, unique_id=0)

    def test_unknown_set_id(self):
        """quality=5 with set_id=9999 (not in SET_ITEMS) -> ValueError."""
        with self.assertRaises(ValueError):
            build_item(type_code='amu', col=0, row=0, storage=5,
                       quality=5, set_id=9999)

    def test_set_type_mismatch(self):
        """Valid set_id 0 (Civerb's Ward, code='lrg') but wrong type_code.

        From set_items.py: 0: {'name': "Civerb's Ward", 'code': 'lrg', ...}
        """
        with self.assertRaises(ValueError):
            build_item(type_code='amu', col=0, row=0, storage=5,
                       quality=5, set_id=0)

    def test_unknown_runeword_id(self):
        """runeword=True with runeword_id=9999 -> ValueError."""
        with self.assertRaises(ValueError):
            build_item(type_code='crs', col=0, row=0, storage=5,
                       runeword=True, runeword_id=9999)

    def test_bad_type_code_length(self):
        """type_code='ab' (2 chars) -> AssertionError from assert statement.

        build_lib.py line 678: assert len(type_code) == 4
        The padding branch only triggers for len==3. 'ab' is 2 chars, so
        it skips padding and hits the assert (2 != 4) -> AssertionError.
        """
        with self.assertRaises(AssertionError):
            build_item(type_code='ab', col=0, row=0, storage=5)


# =========================================================================
# TestBuildWarnings (~3 tests)
# =========================================================================
class TestBuildWarnings(unittest.TestCase):
    """Test the BuildWarnings class from d2r_chargen/warnings.py."""

    def test_warn_and_dump(self):
        """warn() stores (context, message) tuple; dump() prints to stdout."""
        bw = BuildWarnings()
        bw.warn('amu', 'test warning message')

        self.assertEqual(len(bw.warnings), 1)
        self.assertEqual(bw.warnings[0], ('amu', 'test warning message'))

        # Verify dump() prints
        with unittest.mock.patch('builtins.print') as mock_print:
            bw.dump()
            mock_print.assert_called_once()
            call_args = mock_print.call_args[0][0]
            self.assertIn('amu', call_args)
            self.assertIn('test warning message', call_args)

    def test_has_warnings(self):
        """has_warnings() is False when empty, True after warn()."""
        bw = BuildWarnings()
        self.assertFalse(bw.has_warnings())

        bw.warn('crs', 'something')
        self.assertTrue(bw.has_warnings())

    def test_clear(self):
        """clear() resets warnings list to empty."""
        bw = BuildWarnings()
        bw.warn('lea', 'w1')
        bw.warn('lea', 'w2')
        self.assertEqual(len(bw.warnings), 2)

        bw.clear()
        self.assertEqual(len(bw.warnings), 0)
        self.assertFalse(bw.has_warnings())


# =========================================================================
# TestPreEncodeChecks (~7 tests)
# =========================================================================
class TestPreEncodeChecks(unittest.TestCase):
    """Test pre-encode warning checks in build_item().

    These checks emit warnings (not exceptions) when values exceed field
    bit ranges. Warnings are collected in a BuildWarnings instance passed
    via the warnings= parameter.
    """

    def test_socket_overflow_warns(self):
        """num_sockets=7 on a base with max_sockets=2 -> warning.

        'qui' (Quilted Armor) has max_sockets=2.
        """
        bw = BuildWarnings()
        build_item(type_code='qui', col=0, row=0, storage=5,
                   socketed=True, num_sockets=7,
                   defense=10, max_dur=20, cur_dur=20,
                   warnings=bw)
        self.assertTrue(bw.has_warnings())
        msgs = [msg for _, msg in bw.warnings]
        self.assertTrue(any('num_sockets=7' in m and 'max_sockets=2' in m
                            for m in msgs))

    def test_durability_overflow_warns(self):
        """max_dur=300 exceeds 8-bit max (255) -> warning.

        'lea' (Leather Armor): flags=6 (has durability + defense).
        """
        bw = BuildWarnings()
        build_item(type_code='lea', col=0, row=0, storage=5,
                   defense=15, max_dur=300, cur_dur=200,
                   warnings=bw)
        self.assertTrue(bw.has_warnings())
        msgs = [msg for _, msg in bw.warnings]
        self.assertTrue(any('max_dur=300' in m and '255' in m
                            for m in msgs))

    def test_defense_overflow_warns(self):
        """defense=3000 exceeds 11-bit max (2047) -> warning.

        'qui' (Quilted Armor): flags=6 (has defense).
        """
        bw = BuildWarnings()
        build_item(type_code='qui', col=0, row=0, storage=5,
                   defense=3000, max_dur=20, cur_dur=20,
                   warnings=bw)
        self.assertTrue(bw.has_warnings())
        msgs = [msg for _, msg in bw.warnings]
        self.assertTrue(any('defense=3000' in m and '2047' in m
                            for m in msgs))

    def test_quantity_overflow_warns(self):
        """quantity=600 exceeds 9-bit max (511) -> warning.

        'aqv' (Arrows): flags=1 (stackable).
        """
        bw = BuildWarnings()
        build_item(type_code='aqv', col=0, row=0, storage=5,
                   quantity=600,
                   warnings=bw)
        self.assertTrue(bw.has_warnings())
        msgs = [msg for _, msg in bw.warnings]
        self.assertTrue(any('quantity=600' in m and '511' in m
                            for m in msgs))

    def test_property_value_overflow_warns(self):
        """Stat value exceeding sB range -> warning emitted before encode error.

        Stat 74 (hpregen): sB=6, sA=30. Max encoded = 63, max value = 33.
        value=34 -> encoded=64 -> overflow warning THEN encode_property raises.
        The warning is recorded before the ValueError propagates.
        """
        bw = BuildWarnings()
        with self.assertRaises(ValueError):
            build_item(type_code='amu', col=0, row=0, storage=5,
                       properties=[(74, 34)],
                       warnings=bw)
        # Warning was recorded before the error was raised
        self.assertTrue(bw.has_warnings())
        msgs = [msg for _, msg in bw.warnings]
        self.assertTrue(any('stat 74' in m or 'hpregen' in m
                            for m in msgs))

    def test_valid_item_no_warnings(self):
        """Normal valid item produces no warnings.

        Amulet with fire res +30 (stat 39, well within 9-bit range).
        """
        bw = BuildWarnings()
        build_item(type_code='amu', col=0, row=0, storage=5,
                   properties=[(39, 30)],
                   warnings=bw)
        self.assertFalse(bw.has_warnings())

    def test_cur_dur_overflow_warns(self):
        """cur_dur=600 exceeds 9-bit max (511) -> warning."""
        bw = BuildWarnings()
        build_item(type_code='lea', col=0, row=0, storage=5,
                   max_dur=20, cur_dur=600,
                   warnings=bw)
        self.assertTrue(bw.has_warnings())
        msgs = [m for _, m in bw.warnings]
        self.assertTrue(any('cur_dur=600' in m and '511' in m for m in msgs),
                        f"Expected cur_dur overflow warning, got: {msgs}")

    def test_grouped_scalar_warns(self):
        """Grouped stat (np>0) given scalar value -> 'bounds check skipped' warning."""
        bw = BuildWarnings()
        # stat 57 (poisonmindam, np=3) as scalar triggers the warning
        # but encode_property will raise ValueError, so we catch that
        with self.assertRaises(ValueError):
            build_item(type_code='amu', col=0, row=0, storage=5,
                       properties=[(57, 100)],
                       warnings=bw)
        self.assertTrue(bw.has_warnings())
        msgs = [m for _, m in bw.warnings]
        self.assertTrue(any('grouped stat' in m and 'scalar' in m for m in msgs),
                        f"Expected grouped-stat scalar warning, got: {msgs}")

    def test_warnings_not_raised_without_collector(self):
        """warnings=None and no _current_warnings -> no error, no warnings.

        Build should succeed silently even with overflow values, since
        no warning collector is present.
        """
        # Temporarily ensure _current_warnings is None
        import d2r_chargen.build_lib as _bl
        saved = _bl._current_warnings
        _bl._current_warnings = None
        try:
            # defense=3000 would warn, but no collector -> silent
            result = build_item(type_code='qui', col=0, row=0, storage=5,
                                defense=3000, max_dur=20, cur_dur=20,
                                warnings=None)
            # Should return bytes without error
            self.assertIsInstance(result, bytes)
        finally:
            _bl._current_warnings = saved


if __name__ == '__main__':
    unittest.main()
