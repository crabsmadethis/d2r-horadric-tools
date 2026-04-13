"""Tests for TVFS CFT locator and patcher using REAL CASC data."""

import os
import struct
import sys

import pytest

pytestmark = pytest.mark.slow

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from d2r_mod.casc import (
    DEFAULT_GAME_DIR,
    _build_index,
    _parse_build_config,
    _parse_tvfs,
    _read_blte,
)
from d2r_mod.casc_tvfs import locate_cft_entries, patch_cft_entry


def load_tvfs():
    """Load real TVFS data from D2R's CASC archive."""
    game_dir = DEFAULT_GAME_DIR
    data_dir = os.path.join(game_dir, "data", "data")
    config = _parse_build_config(game_dir)
    index = _build_index(data_dir)
    vfs2_ekey9 = bytes.fromhex(config["vfs-2"][1])[:9]
    return _read_blte(data_dir, *index[vfs2_ekey9])


# Cache the TVFS data across tests (read-only; tests that mutate make a copy)
_tvfs_cache = None


def get_tvfs():
    global _tvfs_cache
    if _tvfs_cache is None:
        _tvfs_cache = load_tvfs()
    return _tvfs_cache


# ---------------------------------------------------------------------------
# locate_cft_entries tests
# ---------------------------------------------------------------------------


class TestLocateKnownUIFile:
    """test_locate_known_ui_file: find hudpanelhd.json (keyboard variant)."""

    def test_locate_known_ui_file(self):
        tvfs = get_tvfs()
        path = "data/global/ui/layouts/hudpanelhd.json"
        offsets = locate_cft_entries(tvfs, [path])
        assert path in offsets, f"Expected to find {path} in TVFS"
        off = offsets[path]
        # Offset should be within the TVFS data bounds
        assert 0 < off < len(tvfs), f"Offset {off} out of bounds"
        # EKey at that offset should not be all-zeros
        ekey = tvfs[off:off + 9]
        assert ekey != b"\x00" * 9, "EKey should not be null"


class TestLocateKnownTxtFile:
    """test_locate_known_txt_file: find skills.txt."""

    def test_locate_known_txt_file(self):
        tvfs = get_tvfs()
        path = "data/global/excel/skills.txt"
        offsets = locate_cft_entries(tvfs, [path])
        assert path in offsets, f"Expected to find {path} in TVFS"
        off = offsets[path]
        assert 0 < off < len(tvfs)
        ekey = tvfs[off:off + 9]
        assert ekey != b"\x00" * 9


class TestLocateNonexistentPath:
    """test_locate_nonexistent_path: returns empty dict for unknown path."""

    def test_locate_nonexistent_path(self):
        tvfs = get_tvfs()
        offsets = locate_cft_entries(tvfs, ["data/nonexistent/fake_file.xyz"])
        assert len(offsets) == 0


class TestCaseInsensitive:
    """test_case_insensitive: mixed-case input normalizes to same offset."""

    def test_case_insensitive(self):
        tvfs = get_tvfs()
        offsets_lower = locate_cft_entries(
            tvfs, ["data/global/ui/layouts/hudpanelhd.json"]
        )
        offsets_mixed = locate_cft_entries(
            tvfs, ["data/global/ui/layouts/HudPanelHD.json"]
        )
        # Both should resolve to the same lowercase key and offset
        key = "data/global/ui/layouts/hudpanelhd.json"
        assert key in offsets_lower
        assert key in offsets_mixed
        assert offsets_lower[key] == offsets_mixed[key]


class TestLocateMultipleFiles:
    """test_locate_multiple_files: find 3+ paths in one call."""

    def test_locate_multiple_files(self):
        tvfs = get_tvfs()
        paths = [
            "data/global/ui/layouts/hudpanelhd.json",
            "data/global/excel/skills.txt",
            "data/global/excel/weapons.txt",
        ]
        offsets = locate_cft_entries(tvfs, paths)
        for p in paths:
            assert p in offsets, f"Expected to find {p}"
        # All offsets should be distinct
        offset_values = list(offsets.values())
        assert len(set(offset_values)) == len(offset_values), "Offsets should be unique"


# ---------------------------------------------------------------------------
# patch_cft_entry tests
# ---------------------------------------------------------------------------


class TestPatchCFTEntryOverwritesFields:
    """test_patch_cft_entry_overwrites_fields: EKey, EncodedSize, ContentSize, CKey all updated."""

    def test_patch_cft_entry_overwrites_fields(self):
        tvfs = get_tvfs()
        tvfs_mut = bytearray(tvfs)

        offsets = locate_cft_entries(tvfs, ["data/global/ui/layouts/hudpanelhd.json"])
        off = offsets["data/global/ui/layouts/hudpanelhd.json"]

        # Save the original 35 bytes
        original_35 = bytes(tvfs_mut[off:off + 35])

        # Patch with fake values
        fake_ekey = b"\xDE\xAD\xBE\xEF\x01\x02\x03\x04\x05"
        fake_enc_size = 12345
        fake_content_size = 98765
        fake_ckey = b"\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0A\x0B\x0C\x0D\x0E\x0F\x10"
        patch_cft_entry(tvfs_mut, off, fake_ekey, fake_enc_size,
                        content_size=fake_content_size, new_ckey=fake_ckey)

        # First 9 bytes: new EKey
        assert tvfs_mut[off:off + 9] == fake_ekey

        # Bytes 9-12: new EncodedSize (BE)
        stored_size = struct.unpack_from(">I", tvfs_mut, off + 9)[0]
        assert stored_size == fake_enc_size

        # Bytes 13-17: new ContentSize (5 bytes BE)
        stored_content_size = int.from_bytes(tvfs_mut[off + 13:off + 18], "big")
        assert stored_content_size == fake_content_size

        # Bytes 18-33: new CKey (16 bytes)
        assert bytes(tvfs_mut[off + 18:off + 34]) == fake_ckey

        # Byte 34: padding unchanged
        assert tvfs_mut[off + 34] == original_35[34]


class TestPatchCFTEntryPreservesParsability:
    """test_patch_cft_entry_preserves_tvfs_parsability: _parse_tvfs still works."""

    def test_patch_cft_entry_preserves_tvfs_parsability(self):
        tvfs = get_tvfs()
        tvfs_mut = bytearray(tvfs)

        offsets = locate_cft_entries(tvfs, ["data/global/ui/layouts/hudpanelhd.json"])
        off = offsets["data/global/ui/layouts/hudpanelhd.json"]

        fake_ekey = b"\xAA\xBB\xCC\xDD\xEE\xFF\x11\x22\x33"
        fake_enc_size = 9999
        fake_ckey = b"\xFF" * 16
        patch_cft_entry(tvfs_mut, off, fake_ekey, fake_enc_size,
                        content_size=5000, new_ckey=fake_ckey)

        # _parse_tvfs should still work and return the patched EKey
        paths = _parse_tvfs(bytes(tvfs_mut))
        assert "data/global/ui/layouts/hudpanelhd.json" in paths
        assert paths["data/global/ui/layouts/hudpanelhd.json"] == fake_ekey


class TestCFTOffsetPointsToValidEKey:
    """test_cft_offset_points_to_valid_ekey: located offset has the file's real EKey."""

    def test_cft_offset_points_to_valid_ekey(self):
        tvfs = get_tvfs()
        path = "data/global/excel/skills.txt"

        # Get the offset via our locator
        offsets = locate_cft_entries(tvfs, [path])
        off = offsets[path]

        # Get the EKey via the standard parser
        file_map = _parse_tvfs(tvfs)
        expected_ekey = file_map[path]

        # The EKey at the located offset should match the parser's result
        located_ekey = tvfs[off:off + 9]
        assert located_ekey == expected_ekey, (
            f"EKey mismatch at offset {off}: "
            f"located={located_ekey.hex()} expected={expected_ekey.hex()}"
        )
