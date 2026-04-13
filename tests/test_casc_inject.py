"""Tests for CASC injection orchestrator."""

import hashlib
import os
import shutil
import struct
import sys
import tempfile

import pytest

pytestmark = pytest.mark.slow

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from d2r_mod.casc import (
    DEFAULT_GAME_DIR,
    _build_index,
    _decompress_blte,
    _parse_build_config,
    _parse_build_info,
    _parse_tvfs,
    _read_blte,
)
from d2r_mod.casc_write import (
    CASCWriteError,
    _find_writable_archive,
    _update_build_config,
    blte_encode,
    inject_files,
)

CASC_DATA_DIR = os.path.join(DEFAULT_GAME_DIR, "data", "data")


def _casc_available():
    return os.path.isdir(CASC_DATA_DIR)


# ---------------------------------------------------------------------------
# _find_writable_archive tests
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _casc_available(), reason="D2R CASC not available")
class TestFindWritableArchive:
    def test_finds_archive(self):
        path, idx = _find_writable_archive(CASC_DATA_DIR)
        assert os.path.exists(path)
        assert idx >= 0
        assert os.path.getsize(path) < 0x3FFFFFFF

    def test_returns_highest_under_limit(self):
        """Should prefer higher-numbered archives."""
        path, idx = _find_writable_archive(CASC_DATA_DIR)
        # Just verify it's a valid data.NNN path
        assert path.endswith(f"data.{idx:03d}")


class TestFindWritableArchiveSynthetic:
    def test_empty_dir_raises(self, tmp_path):
        with pytest.raises(CASCWriteError, match="No data.NNN"):
            _find_writable_archive(str(tmp_path))

    def test_small_archives(self, tmp_path):
        """Should find a small archive."""
        for i in range(3):
            p = tmp_path / f"data.{i:03d}"
            p.write_bytes(b"\x00" * (100 + i * 50))
        path, idx = _find_writable_archive(str(tmp_path))
        assert idx == 2  # highest-numbered, all under limit


# ---------------------------------------------------------------------------
# _update_build_config tests (non-destructive: uses temp copy)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _casc_available(), reason="D2R CASC not available")
class TestUpdateBuildConfig:
    def test_update_roundtrip(self, tmp_path):
        """Update config in a temp copy, verify Build Key changes."""
        # Copy just the essential CASC structure to tmp
        game_copy = str(tmp_path / "d2r")
        os.makedirs(os.path.join(game_copy, "data", "config"), exist_ok=True)

        # Copy .build.info
        shutil.copy2(
            os.path.join(DEFAULT_GAME_DIR, ".build.info"),
            os.path.join(game_copy, ".build.info"),
        )

        # Copy config file
        old_key = _parse_build_info(DEFAULT_GAME_DIR)
        old_config_path = os.path.join(
            DEFAULT_GAME_DIR, "data", "config",
            old_key[:2], old_key[2:4], old_key,
        )
        new_config_dir = os.path.join(
            game_copy, "data", "config",
            old_key[:2], old_key[2:4],
        )
        os.makedirs(new_config_dir, exist_ok=True)
        shutil.copy2(old_config_path, os.path.join(new_config_dir, old_key))

        # Update
        new_key = _update_build_config(
            game_copy, "vfs-2",
            ["aaaa" * 8, "bbbb" * 8, "12345", "6789"],
        )

        # Verify Build Key changed
        assert new_key != old_key

        # Verify .build.info references new key
        stored_key = _parse_build_info(game_copy)
        assert stored_key == new_key

        # Verify new config file exists
        new_config_path = os.path.join(
            game_copy, "data", "config",
            new_key[:2], new_key[2:4], new_key,
        )
        assert os.path.exists(new_config_path)

        # Verify new config has updated vfs-2 line
        with open(new_config_path, "r") as f:
            content = f.read()
        assert "aaaa" * 8 in content
        assert "bbbb" * 8 in content

        # Verify MD5 of new config = new Build Key
        with open(new_config_path, "rb") as f:
            actual_md5 = hashlib.md5(f.read()).hexdigest()
        assert actual_md5 == new_key


# ---------------------------------------------------------------------------
# inject_files tests (non-destructive: NOT run by default)
# ---------------------------------------------------------------------------
# These tests would modify the real CASC. They're gated behind an env var.
# Set CASC_INJECT_LIVE_TEST=1 to enable.


@pytest.mark.skipif(
    not _casc_available() or not os.environ.get("CASC_INJECT_LIVE_TEST"),
    reason="Live inject test disabled (set CASC_INJECT_LIVE_TEST=1)",
)
class TestInjectFilesLive:
    """Live injection test — MODIFIES real CASC data.

    Only enabled with CASC_INJECT_LIVE_TEST=1 env var.
    Creates backups and restores on completion.
    """

    def test_inject_single_file(self):
        """Inject a trivially modified hudpanelhd.json."""
        # Extract the current file
        config = _parse_build_config(DEFAULT_GAME_DIR)
        index = _build_index(CASC_DATA_DIR)
        vfs2_ekey9 = bytes.fromhex(config["vfs-2"][1])[:9]
        tvfs = _read_blte(CASC_DATA_DIR, *index[vfs2_ekey9])
        paths = _parse_tvfs(tvfs)

        target = "data/global/ui/layouts/hudpanelhd.json"
        assert target in paths

        ekey = paths[target]
        original = _read_blte(CASC_DATA_DIR, *index[ekey])

        # Make a trivial modification (add trailing whitespace)
        modified = original + b" "

        # Backup .build.info
        build_info = os.path.join(DEFAULT_GAME_DIR, ".build.info")
        shutil.copy2(build_info, build_info + ".pre_inject_test_bak")

        try:
            result = inject_files(DEFAULT_GAME_DIR, {target: modified})
            assert len(result["injected"]) == 1
            assert result["injected"][0]["path"] == target
            assert len(result["idx_files"]) >= 1
            assert result["new_build_key"]
            assert result["tvfs_ekey"]

            # Verify readback: re-read the CASC and find our content
            new_config = _parse_build_config(DEFAULT_GAME_DIR)
            new_index = _build_index(CASC_DATA_DIR)
            new_vfs2_ekey9 = bytes.fromhex(new_config["vfs-2"][1])[:9]
            new_tvfs = _read_blte(CASC_DATA_DIR, *new_index[new_vfs2_ekey9])
            new_paths = _parse_tvfs(new_tvfs)

            new_ekey = new_paths[target]
            readback = _read_blte(CASC_DATA_DIR, *new_index[new_ekey])
            assert readback == modified
        finally:
            # Cleanup: restore .build.info
            bak = build_info + ".pre_inject_test_bak"
            if os.path.exists(bak):
                shutil.copy2(bak, build_info)
                os.remove(bak)


# ---------------------------------------------------------------------------
# Orchestrator unit tests (synthetic, no real CASC modification)
# ---------------------------------------------------------------------------


class TestInjectFilesValidation:
    """Test inject_files error handling with mocks."""

    @pytest.mark.skipif(not _casc_available(), reason="D2R CASC not available")
    def test_missing_path_raises(self):
        """Injecting a non-existent TVFS path should raise CASCWriteError."""
        with pytest.raises(CASCWriteError, match="not found in TVFS"):
            inject_files(DEFAULT_GAME_DIR, {
                "data/nonexistent/fake_file.xyz": b"content",
            })
