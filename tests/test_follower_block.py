"""Tests for d2r_chargen/follower_block.py decoder skeleton."""
from pathlib import Path

import pytest

# Skip entire file if game data not extracted
pytest.importorskip("d2r_chargen.data.item_stat_cost",
                     reason="game data not extracted (run 'd2r-mod extract')")

from d2r_chargen.follower_block import (
    decode_follower_block,
    demon_payload_unknown_slices,
    parse_demon_payload,
)

FIX = Path(__file__).resolve().parent / 'fixtures'

# .d2s fixtures are gitignored in the public d2r-tools mirror — present in
# d2r-editor, absent on fresh public clones. Skip rather than error.
_HAS_D2S_FIXTURES = (FIX / 'marrowbind_demon_b.d2s').exists() and (FIX / 'tempest.d2s').exists()
needs_fixtures = pytest.mark.skipif(
    not _HAS_D2S_FIXTURES,
    reason='.d2s fixtures not present (gitignored in public repo)',
)


@needs_fixtures
def test_decode_no_follower():
    """A non-warlock save (or warlock with no active demon) has follower_count=0."""
    d = (FIX / 'tempest.d2s').read_bytes()
    block = decode_follower_block(d)
    assert block.follower_count == 0
    assert block.has_follower is False
    assert block.payload == b''


@needs_fixtures
def test_decode_with_follower():
    """A warlock with an active bound demon has follower_count=1 and a 116-byte payload."""
    d = (FIX / 'marrowbind_demon_b.d2s').read_bytes()
    block = decode_follower_block(d)
    assert block.follower_count == 1
    assert block.has_follower is True
    assert block.payload_len == 116


@needs_fixtures
def test_decode_payload_matches_extracted_block():
    """The extracted demon_block_b.bin should equal the in-save payload byte-for-byte."""
    d = (FIX / 'marrowbind_demon_b.d2s').read_bytes()
    block = decode_follower_block(d)
    expected = (FIX / 'demon_block_b.bin').read_bytes()
    assert block.payload == expected


def test_decode_handles_missing_kf():
    """A save without a kf marker (corrupted/truncated) returns empty block."""
    block = decode_follower_block(b'random bytes with no markers')
    assert block.follower_count == 0


def test_decode_rejects_kf_lf_as_data_substrings():
    """kf and lf appearing as data (not at the structural 5-byte gap) must be rejected.

    Without the gap check, the decoder would accept any byte stream containing
    `kf` and `lf` substrings and read the next 2 bytes as a count — producing
    bogus follower_count values from random data.
    """
    # 'kf' followed by 'lf' at gap=4 (not the structural 5) — bogus structure.
    block = decode_follower_block(b'XX kf__lf' + (1).to_bytes(2, 'little') + b'X' * 116)
    assert block.follower_count == 0


@needs_fixtures
def test_decode_payload_capped_at_116_bytes():
    """Payload is sliced to exactly 116 bytes, not to EOF.

    Protects against future saves where bytes follow the demon block (e.g., a
    real golem section appearing after the follower block).
    """
    d = (FIX / 'marrowbind_demon_b.d2s').read_bytes()
    # Append junk to simulate a longer trailer.
    d_with_trailer = d + b'\xab' * 50
    block = decode_follower_block(d_with_trailer)
    assert block.payload_len == 116
    assert b'\xab' not in block.payload


# ---------------------------------------------------------------------------
# Task 1.2: high-confidence demon payload field parsing
# ---------------------------------------------------------------------------

def test_parse_demon_payload_fixture_a():
    """Fixture A (pre-rebind) parses to known high-confidence values."""
    payload = (FIX / 'demon_block_a.bin').read_bytes()
    assert len(payload) == 116
    parsed = parse_demon_payload(payload)
    assert parsed.monster_hcidx == 42
    assert parsed.monster_seed == 0x000A5BDA
    assert parsed.bind_demon_level == 7
    assert parsed.affix_indices == bytes([27, 30, 5, 28, 6, 0, 0])


def test_parse_demon_payload_fixture_b():
    """Fixture B (post-rebind to fallen) parses to known high-confidence values.

    NOTE: The seed 0x0018281B (= 1583131) is the actual u32-LE read from
    fixture bytes `1b 28 18 00`. The Phase 0 decode prose at one point quoted
    `0x00181B28 = 1579816` for this seed — that was a byte-swap typo in the
    notes. The pre-flight verification command in the Task 1.2 brief printed
    `0x18281b` (this value), confirming the bytes themselves are stable.
    """
    payload = (FIX / 'demon_block_b.bin').read_bytes()
    assert len(payload) == 116
    parsed = parse_demon_payload(payload)
    assert parsed.monster_hcidx == 20
    assert parsed.monster_seed == 0x0018281B
    assert parsed.bind_demon_level == 7
    assert parsed.affix_indices == bytes([25, 6, 5, 27, 30, 0, 0])


def test_demon_payload_unknown_slices_fixture_b():
    """Unknown-slice helper exposes raw evidence without semantic overclaiming."""
    payload = (FIX / 'demon_block_b.bin').read_bytes()
    slices = demon_payload_unknown_slices(payload)

    assert slices['runtime_stats_24_31'] == payload[24:32]
    assert slices['percent_or_caps_44_51'] == payload[44:52]
    assert slices['bitfields_64_79'] == payload[64:80]
    assert slices['hash_or_runtime_byte_88'] == payload[88:89]
    assert slices['volatile_runtime_89_91'] == payload[89:92]
    assert slices['post_gf_opcode_94'] == payload[94:95]
    assert slices['post_gf_tail_95_115'] == payload[95:116]


@needs_fixtures
def test_followerblock_exposes_demon_fields_from_save():
    """Live save end-to-end: decode_follower_block -> FollowerBlock -> demon fields."""
    d = (FIX / 'marrowbind_demon_b.d2s').read_bytes()
    block = decode_follower_block(d)
    assert block.has_follower
    # Same expected values as fixture B (the save the fixture was extracted from).
    assert block.monster_hcidx == 20
    assert block.monster_seed == 0x0018281B  # see test_parse_demon_payload_fixture_b
    assert block.bind_demon_level == 7
    assert block.affix_indices == bytes([25, 6, 5, 27, 30, 0, 0])
    assert block.unknown_slices['volatile_runtime_89_91'] == block.payload[89:92]


@needs_fixtures
def test_followerblock_demon_fields_none_when_no_follower():
    """When follower_count == 0, demon-field accessors return None / empty bytes.

    Documented contract: numeric fields -> None, affix_indices -> b''.
    Callers should gate on `block.has_follower` before reading.
    """
    d = (FIX / 'tempest.d2s').read_bytes()
    block = decode_follower_block(d)
    assert block.follower_count == 0
    assert block.monster_hcidx is None
    assert block.monster_seed is None
    assert block.bind_demon_level is None
    assert block.affix_indices == b''


def test_parse_demon_payload_rejects_short_input():
    """parse_demon_payload demands a full 116-byte buffer."""
    with pytest.raises(ValueError):
        parse_demon_payload(b'\x00' * 80)


def test_demon_payload_unknown_slices_rejects_short_input():
    """Unknown-slice reporting uses the same full-payload guard."""
    with pytest.raises(ValueError):
        demon_payload_unknown_slices(b'\x00' * 80)
