"""Tests for save.py preserving the follower block on rebuild (Task 3.1).

.d2s fixtures are gitignored in the public d2r-tools mirror — skip the
whole file if the source saves aren't present.
"""
import shutil
import struct
from pathlib import Path

import pytest

# Skip entire file if game data not extracted
pytest.importorskip("d2r_chargen.data.item_stat_cost",
                     reason="game data not extracted (run 'd2r-mod extract')")

from d2r_chargen.follower_block import decode_follower_block
from d2r_chargen.save import rebuild_items

FIX = Path(__file__).resolve().parent / 'fixtures'

if not (FIX / 'marrowbind_demon_b.d2s').exists() or not (FIX / 'tempest.d2s').exists():
    pytest.skip('.d2s fixtures not present (gitignored in public repo)',
                allow_module_level=True)


def test_round_trip_preserves_follower_block(tmp_path):
    """Marrowbind fixture (warlock + bound demon) must round-trip with the
    follower block intact when items are not changed.

    Approach: feed the fixture through rebuild_items with empty char/merc
    item lists. The follower block lives AFTER the items in the file layout,
    so rebuild_items only needs to preserve it — it doesn't depend on item
    contents. Default behavior (preserve_followers=True) keeps the block.
    """
    src = FIX / 'marrowbind_demon_b.d2s'
    dst = tmp_path / 'marrowbind_copy.d2s'
    shutil.copy2(src, dst)

    original = decode_follower_block(src.read_bytes())
    assert original.follower_count == 1
    assert original.payload_len == 116

    rebuilt = rebuild_items(str(dst), [], [])
    rebuilt_block = decode_follower_block(bytes(rebuilt))

    assert rebuilt_block.follower_count == 1
    assert rebuilt_block.payload == original.payload


def test_round_trip_preserves_follower_block_explicit_true(tmp_path):
    """preserve_followers=True (explicit) keeps the follower block."""
    src = FIX / 'marrowbind_demon_b.d2s'
    dst = tmp_path / 'marrowbind_copy.d2s'
    shutil.copy2(src, dst)

    original = decode_follower_block(src.read_bytes())

    rebuilt = rebuild_items(str(dst), [], [], preserve_followers=True)
    rebuilt_block = decode_follower_block(bytes(rebuilt))

    assert rebuilt_block.follower_count == original.follower_count
    assert rebuilt_block.payload == original.payload


def test_strip_follower_when_preserve_false(tmp_path):
    """preserve_followers=False explicitly strips the follower block.

    Output must have follower_count=0 and no payload, even though the input
    had a valid 116B follower block.
    """
    src = FIX / 'marrowbind_demon_b.d2s'
    dst = tmp_path / 'marrowbind_copy.d2s'
    shutil.copy2(src, dst)

    original = decode_follower_block(src.read_bytes())
    assert original.has_follower  # sanity: starting from a save WITH a follower

    rebuilt = rebuild_items(str(dst), [], [], preserve_followers=False)
    rebuilt_block = decode_follower_block(bytes(rebuilt))

    assert rebuilt_block.follower_count == 0
    assert rebuilt_block.payload == b''
    assert rebuilt_block.has_follower is False


def test_round_trip_no_follower_unchanged(tmp_path):
    """Tempest fixture (no follower) round-trips with count=0, no payload.

    Common case for non-warlocks (and warlocks-without-demon) — output stays
    as today: lf 00 00, no payload.
    """
    src = FIX / 'tempest.d2s'
    dst = tmp_path / 'tempest_copy.d2s'
    shutil.copy2(src, dst)

    original = decode_follower_block(src.read_bytes())
    assert original.follower_count == 0

    rebuilt = rebuild_items(str(dst), [], [])
    rebuilt_block = decode_follower_block(bytes(rebuilt))

    assert rebuilt_block.follower_count == 0
    assert rebuilt_block.payload == b''


def test_rebuilt_save_checksum_valid_when_preserving_follower(tmp_path):
    """Rebuilt save with preserved follower block must have a valid checksum.

    Guards against the failure mode where preservation accidentally changes
    file size without recomputing the checksum (Rule 5).
    """
    from d2r_chargen.build_lib import calc_checksum

    src = FIX / 'marrowbind_demon_b.d2s'
    dst = tmp_path / 'marrowbind_copy.d2s'
    shutil.copy2(src, dst)

    rebuilt = rebuild_items(str(dst), [], [])
    rebuilt_bytes = bytes(rebuilt)

    stored_cs = struct.unpack_from('<I', rebuilt_bytes, 12)[0]
    calc_cs = calc_checksum(bytearray(rebuilt_bytes))
    assert stored_cs == calc_cs

    # File-size header at offset 8 must match actual length.
    stored_size = struct.unpack_from('<I', rebuilt_bytes, 8)[0]
    assert stored_size == len(rebuilt_bytes)
