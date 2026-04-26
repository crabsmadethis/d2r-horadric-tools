"""Regression test: HC-flip scripts must preserve the warlock follower block.

The make_*_hc.py scripts modify only byte 0x14 (status) and recompute the
checksum. They read the entire file into a bytearray and write it back,
so the post-kf follower section passes through verbatim. This test locks
that property in so a future "optimization" that rebuilds the file from
sections doesn't silently strip the bound demon.
"""
import shutil
from pathlib import Path

import pytest

# Skip entire file if game data not extracted
pytest.importorskip("d2r_chargen.data.item_stat_cost",
                     reason="game data not extracted (run 'd2r-mod extract')")

from d2r_chargen.follower_block import decode_follower_block

FIX = Path(__file__).resolve().parent / 'fixtures'

if not (FIX / 'marrowbind_demon_b.d2s').exists():
    pytest.skip('.d2s fixtures not present (gitignored in public repo)',
                allow_module_level=True)


def test_marrowbind_hc_flip_preserves_follower(tmp_path):
    """Run make_hc on a copy of marrowbind_demon_b.d2s; follower block intact."""
    src = FIX / 'marrowbind_demon_b.d2s'
    work = tmp_path / 'Marrowbind.d2s'
    shutil.copy(src, work)

    # Snapshot follower state pre-flip.
    pre = decode_follower_block(work.read_bytes())
    assert pre.has_follower
    assert len(pre.payload) == 116

    from make_marrowbind_hc import make_hc
    make_hc(work)

    # After HC flip: same follower payload.
    post = decode_follower_block(work.read_bytes())
    assert post.follower_count == pre.follower_count
    assert post.payload == pre.payload, (
        'HC flip stripped or mutated the follower payload — bound demon would vanish'
    )
    assert post.monster_hcidx == 20  # fallen2 unchanged
    assert post.bind_demon_level == 7


def test_marrowbind_hc_flip_sets_hardcore_bit(tmp_path):
    """Sanity: confirm the script actually flipped HC. If the script regresses
    so it does nothing, the follower-preservation test alone wouldn't catch it."""
    src = FIX / 'marrowbind_demon_b.d2s'
    work = tmp_path / 'Marrowbind.d2s'
    shutil.copy(src, work)

    from make_marrowbind_hc import make_hc
    make_hc(work)

    data = work.read_bytes()
    assert data[0x14] & 0x04, 'HC bit (0x04) not set after make_hc'
