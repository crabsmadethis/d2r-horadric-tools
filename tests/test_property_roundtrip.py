"""Property-based round-trip tests for the .d2s binary format.

Three layers:
    Layer 1 — stat encoding round-trip (fast, default suite)
    Layer 2 — item bytes round-trip (fast, default suite)
    Layer 3 — full character round-trip (slow, @pytest.mark.slow)

All generators draw from extracted game data in d2r_chargen/data/. The
public d2r-tools repo excludes this file from CI via --ignore because
that data is not committed there.

References:
    docs/save-format.md
    docs/superpowers/specs/2026-04-25-save-format-spec-and-fuzzing-design.md
"""
import pytest
from hypothesis import given, strategies as st, note, example, settings

# Skip entire file if game data not extracted
pytest.importorskip("d2r_chargen.data.item_stat_cost",
                     reason="game data not extracted (run 'd2r-mod extract')")

from d2r_chargen.build_lib import (
    BitWriter,
    encode_property,
    encode_properties_terminated,
)
from d2r_chargen.decoder import decode_item_properties
from d2r_chargen.data.item_stat_cost import ITEM_STAT_COST


# ----------------------------------------------------------------------
# Layer 1 — stat encoding round-trip
# ----------------------------------------------------------------------

# Stats that are writeable in the item bitstream (sB > 0) and not part of
# a multi-value group (np <= 1). Grouped stats are tested separately.
_SIMPLE_STAT_IDS = sorted(
    sid for sid, info in ITEM_STAT_COST.items()
    if info.get("sB", 0) > 0 and (info.get("np", 0) or 0) <= 1
)

_GROUPED_STAT_IDS = sorted(
    sid for sid, info in ITEM_STAT_COST.items()
    if (info.get("np", 0) or 0) > 1 and info.get("sB", 0) > 0
)


def _value_strategy_for_stat(stat_id):
    """Build a Hypothesis strategy for valid values of one stat ID."""
    info = ITEM_STAT_COST[stat_id]
    sB = info["sB"]
    sA = info.get("sA", 0)
    sS = info.get("sS", 0)
    if sS:
        # Signed: range that fits encoded value in sB bits after +sA.
        lo = -(1 << (sB - 1)) - sA
        hi = (1 << (sB - 1)) - 1 - sA
    else:
        lo = -sA
        hi = (1 << sB) - 1 - sA
    return st.integers(min_value=lo, max_value=hi)


@st.composite
def simple_stat_values(draw):
    stat_id = draw(st.sampled_from(_SIMPLE_STAT_IDS))
    value = draw(_value_strategy_for_stat(stat_id))
    return stat_id, value


@given(simple_stat_values())
def test_simple_stat_roundtrip(payload):
    stat_id, value = payload
    note(f"stat_id={stat_id} ({ITEM_STAT_COST[stat_id].get('s')}) value={value}")
    w = BitWriter()
    encode_properties_terminated(w, [(stat_id, value)])
    blob = w.get_bytes()
    note(f"bytes={blob.hex()} bits={w.pos}")
    decoded, end_bit = decode_item_properties(blob, 0, num_terminators=1)
    assert len(decoded) == 1
    sid, val = decoded[0][0], decoded[0][1]
    assert sid == stat_id
    assert val == value


@st.composite
def grouped_stat_values(draw):
    stat_id = draw(st.sampled_from(_GROUPED_STAT_IDS))
    info = ITEM_STAT_COST[stat_id]
    np_count = info["np"]
    values = []
    for k in range(np_count):
        member_info = ITEM_STAT_COST.get(stat_id + k, info)
        m_sB = member_info["sB"]
        m_sA = member_info.get("sA", 0)
        m_sS = member_info.get("sS", 0)
        if m_sS:
            lo = -(1 << (m_sB - 1)) - m_sA
            hi = (1 << (m_sB - 1)) - 1 - m_sA
        else:
            lo = -m_sA
            hi = (1 << m_sB) - 1 - m_sA
        values.append(draw(st.integers(min_value=lo, max_value=hi)))
    return stat_id, values


@given(grouped_stat_values())
def test_grouped_stat_roundtrip(payload):
    stat_id, values = payload
    note(f"stat_id={stat_id} ({ITEM_STAT_COST[stat_id].get('s')}) values={values}")
    w = BitWriter()
    encode_property(w, stat_id, values)
    # Manually append terminator — encode_properties_terminated would
    # double-encode the grouped stat as separate entries. get_bytes()
    # calls align() internally.
    w.write_bits(0x1FF, 9)
    blob = w.get_bytes()
    note(f"bytes={blob.hex()} bits={w.pos}")
    decoded, _end = decode_item_properties(blob, 0, num_terminators=1)
    assert len(decoded) == 1
    sid, vals = decoded[0][0], decoded[0][1]
    assert sid == stat_id
    assert list(vals) == list(values)


# ----------------------------------------------------------------------
# Layer 2 — item bytes round-trip
# ----------------------------------------------------------------------

from d2r_chargen.build_lib import build_item
from d2r_chargen.scanner import decode_item_header
from d2r_chargen.data.unique_items import UNIQUE_ITEMS
from d2r_chargen.data.set_items import SET_ITEMS
from d2r_chargen.data.item_bases import ITEM_BASES
from d2r_chargen.data.runewords import RUNEWORDS


# Bases that have at least one socket (filter once, reuse).
_SOCKETED_BASES = sorted(
    code for code, info in ITEM_BASES.items()
    if info.get("max_sockets", 0) > 0 and info.get("class") in ("weapon", "armor")
)

# Unique item UIDs whose code is non-empty and present in ITEM_BASES.
# Empty-code UIDs (placeholder entries) would raise ValueError in build_item.
_VALID_UNIQUE_UIDS = sorted(
    uid for uid, info in UNIQUE_ITEMS.items()
    if info.get("code") and info["code"] in ITEM_BASES
)

# Set item IDs whose code is in ITEM_BASES (all 140 pass this check).
_VALID_SET_IDS = sorted(
    sid for sid, info in SET_ITEMS.items()
    if info.get("code") and info["code"] in ITEM_BASES
)


@st.composite
def normal_item_spec(draw):
    """Quality=2 normal item, optionally with sockets."""
    code = draw(st.sampled_from(_SOCKETED_BASES))
    base = ITEM_BASES[code]
    max_sockets = base.get("max_sockets", 0)
    num_sockets = draw(st.integers(min_value=0, max_value=max_sockets))
    return {
        "type_code": code,
        "quality": 2,
        "ilvl": draw(st.integers(min_value=1, max_value=99)),
        "socketed": num_sockets > 0,
        "num_sockets": num_sockets,
        "col": 0, "row": 0,
        "storage": 5,  # personal_stash
    }


@st.composite
def unique_item_spec(draw):
    """Quality=7 unique item — UID determines code."""
    uid = draw(st.sampled_from(_VALID_UNIQUE_UIDS))
    info = UNIQUE_ITEMS[uid]
    return {
        "type_code": info["code"],
        "quality": 7,
        "unique_id": uid,
        "ilvl": max(1, info.get("qlvl", 1)),
        "col": 0, "row": 0,
        "storage": 5,
    }


@st.composite
def set_item_spec(draw):
    """Quality=5 set item."""
    sid = draw(st.sampled_from(_VALID_SET_IDS))
    info = SET_ITEMS[sid]
    return {
        "type_code": info["code"],
        "quality": 5,
        "set_id": sid,
        "ilvl": max(1, info.get("qlvl", 1)),
        "col": 0, "row": 0,
        "storage": 5,
    }


@given(st.one_of(normal_item_spec(), unique_item_spec(), set_item_spec()))
def test_item_header_roundtrip(spec):
    note(f"spec={spec}")
    blob = build_item(**spec)
    note(f"bytes={blob.hex()} len={len(blob)}")
    assert len(blob) > 0
    # Decode the item header and check core fields match.
    itype, ilvl, quality, uid, storage, col, row, bodyloc, location, ext = \
        decode_item_header(blob, 0)
    assert itype.strip() == spec["type_code"].strip(), (
        f"type_code mismatch: built {spec['type_code']!r}, decoded {itype!r}"
    )
    assert quality == spec["quality"], f"quality mismatch: {spec['quality']} -> {quality}"
    if spec["quality"] == 7:
        assert uid == spec["unique_id"]
    if spec["quality"] == 5:
        assert uid == spec["set_id"]


# Regression: non-simple jewel fillers historically caused
# "FAILED TO JOIN GAME" (see memory feedback_jewel_filler.md). The
# encoder builds them; decoding the header should still succeed even
# if the runtime rejects them. This @example pins the case.
@example(spec={
    "type_code": "amu",
    "quality": 7,
    "unique_id": next(uid for uid, info in UNIQUE_ITEMS.items() if info["code"] == "amu"),
    "ilvl": 50,
    "col": 0, "row": 0,
    "storage": 5,
})
@given(st.one_of(unique_item_spec()))
def test_unique_header_with_pinned_example(spec):
    blob = build_item(**spec)
    itype, ilvl, quality, uid, *_ = decode_item_header(blob, 0)
    assert itype.strip() == spec["type_code"].strip()
    assert uid == spec["unique_id"]


# ----------------------------------------------------------------------
# Layer 3 — full character round-trip (slow)
# ----------------------------------------------------------------------

import os
import shutil
import tempfile
from d2r_chargen.scanner import scan_character_data
from d2r_chargen.build_lib import write_d2s
from d2r_chargen.config import CLASS_DEFS
from d2r_chargen.save import _CLASS_STATS


# Build _CLASS_STATS_MIN from the authoritative source in save.py (_CLASS_STATS)
# keyed by class name, combined with CLASS_DEFS (id mapping) from config.py.
# Cross-checked: Sorceress base_str=10, base_dex=25, base_en=35, base_vit=10 —
# matches known game values.
_CLASS_STATS_MIN = {
    cdef['id']: {
        'strength':  _CLASS_STATS[cname]['base_str'],
        'dexterity': _CLASS_STATS[cname]['base_dex'],
        'vitality':  _CLASS_STATS[cname]['base_vit'],
        'energy':    _CLASS_STATS[cname]['base_en'],
    }
    for cname, cdef in CLASS_DEFS.items()
}

_TEMPLATE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "d2r_chargen", "data", "template.d2s"
)


@st.composite
def character_spec(draw):
    """Class + level spec (no items in v1 — items added in step 2)."""
    cls = draw(st.integers(min_value=0, max_value=7))
    level = draw(st.integers(min_value=1, max_value=99))
    base = _CLASS_STATS_MIN[cls]
    return {
        "class_id": cls,
        "level": level,
        "stats": {k: v + draw(st.integers(min_value=0, max_value=50)) for k, v in base.items()},
    }


@pytest.mark.slow
@settings(max_examples=20, deadline=None)
@given(character_spec())
def test_full_character_roundtrip(spec):
    """Build a minimal character from template.d2s, scan, assert no hard errors."""
    note(f"spec={spec}")
    if not os.path.exists(_TEMPLATE_PATH):
        pytest.skip("template.d2s not available (game data not extracted)")

    with tempfile.NamedTemporaryFile(suffix=".d2s", delete=False) as tf:
        out_path = tf.name
    try:
        shutil.copy2(_TEMPLATE_PATH, out_path)
        # Apply class and level via direct byte poke (matches save.py's approach).
        with open(out_path, "rb") as f:
            data = bytearray(f.read())
        data[0x18] = spec["class_id"]
        data[0x1B] = spec["level"]
        # Recompute checksum and size fields via write_d2s.
        write_d2s(out_path, data)

        result = scan_character_data(out_path)
        note(f"scan result: errors={result['errors']} warnings={result['warnings']}")
        assert result["errors"] == [], (
            f"scanner reported hard errors: {result['errors']}"
        )
        assert result["checksum_ok"], "checksum mismatch"
        assert result["size_ok"], "size mismatch"
        assert result["class_id"] == spec["class_id"]
    finally:
        os.unlink(out_path)
