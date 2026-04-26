"""Tests for bound_demon: YAML template resolution (Task 3.2)."""
import shutil
import struct
from pathlib import Path

import pytest

# Skip entire file if game data not extracted
pytest.importorskip("d2r_chargen.data.item_stat_cost",
                     reason="game data not extracted (run 'd2r-mod extract')")

from d2r_chargen.follower_block import decode_follower_block
from d2r_chargen.resolve import resolve_bound_demon
from d2r_chargen.save import rebuild_items

FIX = Path(__file__).resolve().parent / 'fixtures'

if not (FIX / 'marrowbind_demon_b.d2s').exists() or not (FIX / 'tempest.d2s').exists():
    pytest.skip('.d2s fixtures not present (gitignored in public repo)',
                allow_module_level=True)


def test_resolve_bound_demon_returns_payload():
    """Resolver returns the 116-byte payload from the named fixture."""
    payload = resolve_bound_demon({'template': 'marrowbind_demon_b'}, FIX)
    assert len(payload) == 116
    expected = (FIX / 'demon_block_b.bin').read_bytes()
    assert payload == expected


def test_resolve_bound_demon_missing_template():
    """Spec without `template` key must raise ValueError mentioning template."""
    with pytest.raises(ValueError, match='template'):
        resolve_bound_demon({}, FIX)


def test_resolve_bound_demon_template_empty_string():
    """`template: ''` is also rejected (empty/missing both unusable)."""
    with pytest.raises(ValueError, match='template'):
        resolve_bound_demon({'template': ''}, FIX)


def test_resolve_bound_demon_unknown_template():
    """Template fixture not on disk must raise FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        resolve_bound_demon({'template': 'does_not_exist'}, FIX)


def test_resolve_bound_demon_template_has_no_demon():
    """Template that has no follower block must error, not silently fail."""
    with pytest.raises(ValueError, match='no follower block'):
        resolve_bound_demon({'template': 'tempest'}, FIX)


def test_rebuild_items_with_follower_payload(tmp_path):
    """rebuild_items override path: follower_payload arg wins over preserve.

    Stage Tempest fixture (no follower) into tmp, call rebuild_items with
    follower_payload set to Marrowbind's bytes. Output must have
    follower_count=1 and the override payload, even though the input had
    no follower block.
    """
    src = FIX / 'tempest.d2s'
    dst = tmp_path / 'tempest_with_demon.d2s'
    shutil.copy2(src, dst)

    # Sanity: source has no follower
    assert decode_follower_block(src.read_bytes()).follower_count == 0

    override_payload = (FIX / 'demon_block_b.bin').read_bytes()
    assert len(override_payload) == 116

    rebuilt = rebuild_items(str(dst), [], [], follower_payload=override_payload)
    rebuilt_block = decode_follower_block(bytes(rebuilt))

    assert rebuilt_block.follower_count == 1
    assert rebuilt_block.payload == override_payload
    assert rebuilt_block.has_follower is True


def test_rebuild_items_payload_overrides_preserve_false(tmp_path):
    """follower_payload wins even when preserve_followers=False.

    Override is the strongest signal — explicit YAML > preserve > strip.
    """
    src = FIX / 'marrowbind_demon_b.d2s'
    dst = tmp_path / 'marrowbind_copy.d2s'
    shutil.copy2(src, dst)

    override_payload = (FIX / 'demon_block_a.bin').read_bytes()
    assert len(override_payload) == 116

    rebuilt = rebuild_items(
        str(dst), [], [],
        preserve_followers=False,
        follower_payload=override_payload,
    )
    rebuilt_block = decode_follower_block(bytes(rebuilt))

    assert rebuilt_block.follower_count == 1
    assert rebuilt_block.payload == override_payload


def test_rebuild_items_rejects_wrong_payload_size(tmp_path):
    """follower_payload must be exactly 116 bytes (not 0, not 115, not 117)."""
    src = FIX / 'tempest.d2s'
    dst = tmp_path / 'tempest_copy.d2s'
    shutil.copy2(src, dst)

    for bad_size in (0, 1, 115, 117, 232):
        bad = b'\x00' * bad_size
        with pytest.raises(ValueError, match='116 bytes'):
            rebuild_items(str(dst), [], [], follower_payload=bad)


def test_rebuild_items_with_follower_payload_checksum_valid(tmp_path):
    """Override path must produce a save with valid checksum + size header.

    Guards Rule 5 — adding 116 bytes of payload changes the file size and
    therefore the checksum; both must be recomputed.
    """
    from d2r_chargen.build_lib import calc_checksum

    src = FIX / 'tempest.d2s'
    dst = tmp_path / 'tempest_with_demon.d2s'
    shutil.copy2(src, dst)

    override_payload = (FIX / 'demon_block_b.bin').read_bytes()
    rebuilt = rebuild_items(str(dst), [], [], follower_payload=override_payload)
    rebuilt_bytes = bytes(rebuilt)

    stored_cs = struct.unpack_from('<I', rebuilt_bytes, 12)[0]
    calc_cs = calc_checksum(bytearray(rebuilt_bytes))
    assert stored_cs == calc_cs

    stored_size = struct.unpack_from('<I', rebuilt_bytes, 8)[0]
    assert stored_size == len(rebuilt_bytes)
