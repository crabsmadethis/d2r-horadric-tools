"""Tier 1: Encoding unit tests for d2r_chargen.build_lib.

Tests bit-level correctness of encode_property() across all encoding types,
bit-width boundaries, grouped stats, signed values, and parameterized stats.

Runtime: ~30s
"""
import pytest
# Skip entire file if game data not extracted
pytest.importorskip("d2r_chargen.data.item_stat_cost",
                     reason="game data not extracted (run 'd2r-mod extract')")

from d2r_chargen.build_lib import BitWriter, encode_property, encode_properties_terminated
from d2r_chargen.scanner import bits_at
from d2r_chargen.data.item_stat_cost import ITEM_STAT_COST


# ============================================================
# 1.1 Every stat encoding type (4 tests)
# ============================================================

class TestEncodingTypes:
    """One test per encoding type (e value). Each encodes a representative
    stat, then reads back the output bits to verify round-trip correctness."""

    def test_e0_standard(self):
        """e=0: stat 0 (strength), sB=8, sA=32. Encode value=50."""
        w = BitWriter()
        encode_property(w, stat_id=0, value=50, param=0)
        data = w.get_bytes()

        # 9-bit stat ID = 0
        assert bits_at(data, 0, 9) == 0
        # No param bits (sP=0 for stat 0)
        # Value: 50 + 32 = 82, stored in 8 bits starting at bit 9
        assert bits_at(data, 9, 8) == 82

    def test_e1_skill(self):
        """e=1: stat 107 (item_singleskill), sP=9, sB=3. Teleport (skill 54), +3."""
        w = BitWriter()
        encode_property(w, stat_id=107, value=3, param=54)
        data = w.get_bytes()

        # 9-bit stat ID = 107
        assert bits_at(data, 0, 9) == 107
        # 9-bit param = skill_id 54
        assert bits_at(data, 9, 9) == 54
        # 3-bit value = 3 + sA(0) = 3
        assert bits_at(data, 18, 3) == 3

    def test_e2_chance_to_cast(self):
        """e=2: stat 198 (item_skillonhit), sP=16, sB=7, sA=0.
        API input: value=5, param=(skill_level << 10) | skill_id = (10 << 10) | 54.
        Binary output: param field = (skill_id << 6) | skill_level = (54 << 6) | 10."""
        w = BitWriter()
        # API convention: param = (level << 10) | skill_id
        api_param = (10 << 10) | 54
        encode_property(w, stat_id=198, value=5, param=api_param)
        data = w.get_bytes()

        # 9-bit stat ID = 198
        assert bits_at(data, 0, 9) == 198
        # 16-bit param = (skill_id << 6) | skill_level = (54 << 6) | 10 = 3466
        encoded_param = bits_at(data, 9, 16)
        decoded_skill_id = encoded_param >> 6       # should be 54
        decoded_skill_level = encoded_param & 0x3F  # should be 10
        assert decoded_skill_id == 54, f"skill_id: expected 54, got {decoded_skill_id}"
        assert decoded_skill_level == 10, f"skill_level: expected 10, got {decoded_skill_level}"
        # 7-bit value = 5 + sA(0) = 5
        assert bits_at(data, 25, 7) == 5

    def test_e3_charges(self):
        """e=3: stat 204 (item_charged_skill), sP=16, sB=16, sA=0.
        API input: value=60 (current charges), param=(level << 10) | skill_id = (10 << 10) | 54.
        Binary output: param = (skill_id << 6) | skill_level, value = raw (NOT offset by sA)."""
        w = BitWriter()
        api_param = (10 << 10) | 54
        encode_property(w, stat_id=204, value=60, param=api_param)
        data = w.get_bytes()

        # 9-bit stat ID = 204
        assert bits_at(data, 0, 9) == 204
        # 16-bit param = (54 << 6) | 10 = 3466
        encoded_param = bits_at(data, 9, 16)
        assert (encoded_param >> 6) == 54
        assert (encoded_param & 0x3F) == 10
        # 16-bit value = 60 raw (no sA offset for e=3)
        assert bits_at(data, 25, 16) == 60


# ============================================================
# 1.2 Bit-width boundaries (parametrized, 42 tests)
# ============================================================

def _pick_stat_for_sB(target_sB):
    """Find the first simple (np=0, e=0) stat with the given sB value."""
    for stat_id, info in sorted(ITEM_STAT_COST.items()):
        if info is None:
            continue
        if (info.get('sB', 0) == target_sB
                and info.get('np', 0) == 0
                and info.get('e', 0) == 0
                and info.get('sP', 0) == 0):
            return stat_id, info
    # Fallback: accept any encoding type with matching sB
    for stat_id, info in sorted(ITEM_STAT_COST.items()):
        if info is None:
            continue
        if info.get('sB', 0) == target_sB and info.get('np', 0) == 0:
            return stat_id, info
    return None


_ALL_SB_VALUES = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 16, 22, 24]


def _boundary_cases():
    """Generate (sB, stat_id, value, label) for min/near-max/max per sB."""
    cases = []
    for sB in _ALL_SB_VALUES:
        result = _pick_stat_for_sB(sB)
        if result is None:
            continue
        stat_id, info = result
        sA = info.get('sA', 0)
        max_encoded = (1 << sB) - 1
        max_value = max_encoded - sA

        cases.append((sB, stat_id, 0, "min"))
        if max_value > 1:
            cases.append((sB, stat_id, max_value - 1, "near_max"))
        cases.append((sB, stat_id, max_value, "max"))
    return cases


@pytest.mark.parametrize(
    "sB, stat_id, value, label",
    _boundary_cases(),
    ids=lambda x: str(x) if not isinstance(x, tuple) else None,
)
def test_bitwidth_boundary(sB, stat_id, value, label):
    """Encode a stat at boundary values and verify output bit length and decoded value."""
    info = ITEM_STAT_COST[stat_id]
    sA = info.get('sA', 0)
    sP = info.get('sP', 0)
    e = info.get('e', 0)

    w = BitWriter()
    encode_property(w, stat_id, value, param=0)
    data = w.get_bytes()

    # Stat ID is always 9 bits
    assert bits_at(data, 0, 9) == stat_id

    # Value starts after stat_id (9 bits) + param (sP bits)
    value_offset = 9 + sP
    expected_encoded = value + sA if e != 3 else value
    assert bits_at(data, value_offset, sB) == expected_encoded

    # Total bits should be 9 + sP + sB, rounded up to bytes
    expected_bits = 9 + sP + sB
    expected_bytes = (expected_bits + 7) // 8
    assert len(data) == expected_bytes


# ============================================================
# 1.3 Grouped stats (6 tests)
# ============================================================

_GROUPED_STATS = [
    # (stat_id, name, np, sub_values)
    (17, "item_maxdamage_percent", 2, [300, 300]),
    (48, "firemindam", 2, [10, 20]),
    (50, "lightmindam", 2, [1, 496]),
    (52, "magicmindam", 2, [5, 15]),
    (54, "coldmindam", 3, [30, 60, 50]),
    (57, "poisonmindam", 3, [102, 102, 200]),
]


@pytest.mark.parametrize(
    "stat_id, name, np_count, values",
    _GROUPED_STATS,
    ids=[g[1] for g in _GROUPED_STATS],
)
def test_grouped_stat(stat_id, name, np_count, values):
    """Grouped stats (np > 0): one 9-bit stat ID, then np values back-to-back."""
    w = BitWriter()
    encode_property(w, stat_id, values)
    data = w.get_bytes()

    # 9-bit stat ID
    assert bits_at(data, 0, 9) == stat_id

    # Decode each sub-value
    bit_pos = 9
    for i in range(np_count):
        member_info = ITEM_STAT_COST[stat_id + i]
        member_sB = member_info['sB']
        member_sA = member_info.get('sA', 0)
        encoded = bits_at(data, bit_pos, member_sB)
        decoded = encoded - member_sA
        assert decoded == values[i], (
            f"Sub-value {i} (stat {stat_id + i}): "
            f"expected {values[i]}, got {decoded} "
            f"(encoded={encoded}, sA={member_sA}, sB={member_sB})"
        )
        bit_pos += member_sB


# ============================================================
# 1.4 Signed stats (5 tests)
# ============================================================

def _signed_stat_cases():
    """Pick 5 signed stats with sA > 0 (so negative values are meaningful)."""
    cases = []
    seen_sA = set()
    for stat_id, info in sorted(ITEM_STAT_COST.items()):
        if info is None:
            continue
        if (info.get('sS', 0) == 1
                and info.get('sB', 0) > 0
                and info.get('sA', 0) > 0
                and info.get('np', 0) == 0
                and info.get('sP', 0) == 0
                and info.get('e', 0) == 0):
            sA = info['sA']
            if sA not in seen_sA:
                seen_sA.add(sA)
                neg_val = -(sA // 2)
                cases.append((stat_id, info['s'], neg_val))
                if len(cases) >= 5:
                    break
    return cases


@pytest.mark.parametrize(
    "stat_id, name, value",
    _signed_stat_cases(),
    ids=[c[1] for c in _signed_stat_cases()],
)
def test_signed_stat(stat_id, name, value):
    """Signed stats: negative value + sA produces a positive encoded value."""
    info = ITEM_STAT_COST[stat_id]
    sA = info['sA']
    sB = info['sB']

    w = BitWriter()
    encode_property(w, stat_id, value)
    data = w.get_bytes()

    assert bits_at(data, 0, 9) == stat_id
    encoded = bits_at(data, 9, sB)
    assert encoded == value + sA
    assert encoded >= 0, f"Encoded value should be non-negative, got {encoded}"
    decoded = encoded - sA
    assert decoded == value


# ============================================================
# 1.5 Parameterized stats (3 tests)
# ============================================================

class TestParameterizedStats:
    """Stats with sP > 0 where the param field carries semantic meaning."""

    def test_skill_tab_188(self):
        """stat 188 (item_addskill_tab): sP=16, sB=3.
        Paladin offensive auras: param = (class << 3) | tab = (3 << 3) | 1 = 25."""
        w = BitWriter()
        param = (3 << 3) | 1  # paladin (class 3), tab 1 (offensive auras)
        encode_property(w, stat_id=188, value=1, param=param)
        data = w.get_bytes()

        assert bits_at(data, 0, 9) == 188
        decoded_param = bits_at(data, 9, 16)
        assert decoded_param == 25, f"param: expected 25, got {decoded_param}"
        assert (decoded_param >> 3) == 3   # class = paladin
        assert (decoded_param & 0x7) == 1  # tab = offensive auras
        assert bits_at(data, 25, 3) == 1   # value

    def test_singleskill_107(self):
        """stat 107 (item_singleskill): sP=9, sB=3. Teleport (skill 54), +3."""
        w = BitWriter()
        encode_property(w, stat_id=107, value=3, param=54)
        data = w.get_bytes()

        assert bits_at(data, 0, 9) == 107
        assert bits_at(data, 9, 9) == 54
        assert bits_at(data, 18, 3) == 3

    def test_nonclassskill_97(self):
        """stat 97 (item_nonclassskill): sP=9, sB=6. Oskill Teleport, +1."""
        w = BitWriter()
        encode_property(w, stat_id=97, value=1, param=54)
        data = w.get_bytes()

        assert bits_at(data, 0, 9) == 97
        assert bits_at(data, 9, 9) == 54
        assert bits_at(data, 18, 6) == 1


# ============================================================
# 1.6 Stat list terminator (2 tests)
# ============================================================

class TestStatListTerminator:
    """encode_properties_terminated() must end with 9-bit 0x1FF sentinel."""

    def test_three_stats_terminated(self):
        """3-stat list ends with 0x1FF sentinel."""
        props = [
            (0, 50),      # strength = 50 (sB=8, sA=32, max=223)
            (2, 60),      # dexterity = 60 (sB=7, sA=32, max=95)
            (127, 2),     # all_skills = 2 (sB=3, sA=0, max=7)
        ]
        w = BitWriter()
        encode_properties_terminated(w, props)
        data = w.get_bytes()

        # Calculate expected bit position after 3 stats
        total_bits = 0
        for stat_id, value in props:
            info = ITEM_STAT_COST[stat_id]
            total_bits += 9 + info.get('sP', 0) + info['sB']

        terminator = bits_at(data, total_bits, 9)
        assert terminator == 0x1FF, (
            f"Expected 0x1FF terminator at bit {total_bits}, got {terminator:#x}"
        )

    def test_empty_list_terminated(self):
        """Empty prop list produces just the 0x1FF sentinel (9 bits -> 2 bytes)."""
        w = BitWriter()
        encode_properties_terminated(w, [])
        data = w.get_bytes()

        assert bits_at(data, 0, 9) == 0x1FF
        assert len(data) == 2
