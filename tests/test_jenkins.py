"""Tests for Jenkins hashlittle / hashlittle2 and CASC .idx hash functions."""

import os
import struct
import glob
import pytest

from d2r_mod.build import DEFAULT_GAME_DIR
from d2r_mod.jenkins import (
    hashlittle,
    hashlittle2,
    idx_header_hash,
    idx_data_hash,
)


# === Basic algorithm tests ===

class TestHashlittle:
    """Test hashlittle against known properties and vectors."""

    def test_empty_string_zero_seed(self):
        """Empty input with seed 0 returns 0xdeadbeef (the init constant)."""
        assert hashlittle(b"", 0) == 0xDEADBEEF

    def test_empty_string_nonzero_seed(self):
        """Empty input with nonzero seed returns seed + 0xdeadbeef."""
        # a=b=c = 0xdeadbeef + 0 + 1 = 0xdeadbef0, no mixing needed
        assert hashlittle(b"", 1) == 0xDEADBEF0

    def test_single_byte(self):
        """Single byte should produce a non-trivial hash."""
        h = hashlittle(b"\x00", 0)
        assert isinstance(h, int)
        assert 0 <= h <= 0xFFFFFFFF
        # Should NOT be 0xdeadbeef (that's empty-string hash)
        assert h != 0xDEADBEEF

    def test_different_inputs_different_hashes(self):
        """Different inputs produce different hashes (basic collision check)."""
        h1 = hashlittle(b"hello", 0)
        h2 = hashlittle(b"world", 0)
        assert h1 != h2

    def test_different_seeds_different_hashes(self):
        """Same input with different seeds produces different hashes."""
        h1 = hashlittle(b"test", 0)
        h2 = hashlittle(b"test", 1)
        assert h1 != h2

    def test_deterministic(self):
        """Same input and seed always produces the same hash."""
        data = b"deterministic test data"
        h1 = hashlittle(data, 42)
        h2 = hashlittle(data, 42)
        assert h1 == h2

    def test_all_lengths_1_through_24(self):
        """Exercise all remainder cases (1-12) plus one full mix pass (13-24)."""
        for length in range(1, 25):
            data = bytes(range(length))
            h = hashlittle(data, 0)
            assert isinstance(h, int)
            assert 0 <= h <= 0xFFFFFFFF

    def test_exactly_12_bytes(self):
        """12 bytes: fills a, b, c exactly, then final() with no main loop."""
        h = hashlittle(b"\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c", 0)
        assert isinstance(h, int)
        assert 0 <= h <= 0xFFFFFFFF

    def test_exactly_13_bytes(self):
        """13 bytes: one mix() pass + 1 remainder byte."""
        h = hashlittle(bytes(13), 0)
        assert isinstance(h, int)

    def test_large_input(self):
        """256 bytes: multiple mix passes."""
        h = hashlittle(bytes(256), 0)
        assert isinstance(h, int)
        assert 0 <= h <= 0xFFFFFFFF


class TestHashlittle2:
    """Test hashlittle2 against known properties and vectors."""

    def test_empty_string_zero_seeds(self):
        """Empty input with both seeds 0 returns (0xdeadbeef, 0xdeadbeef)."""
        pc, pb = hashlittle2(b"", 0, 0)
        assert pc == 0xDEADBEEF
        assert pb == 0xDEADBEEF

    def test_empty_string_nonzero_pc(self):
        """Empty input with nonzero pc seed."""
        pc, pb = hashlittle2(b"", 1, 0)
        assert pc == 0xDEADBEF0
        # pb should also shift since c = c + pb during init
        assert isinstance(pb, int)

    def test_returns_two_values(self):
        """hashlittle2 always returns a 2-tuple of ints."""
        pc, pb = hashlittle2(b"test", 0, 0)
        assert isinstance(pc, int)
        assert isinstance(pb, int)
        assert 0 <= pc <= 0xFFFFFFFF
        assert 0 <= pb <= 0xFFFFFFFF

    def test_pc_matches_hashlittle_for_zero_pb(self):
        """With pb=0, hashlittle2's pc output should match hashlittle."""
        data = b"consistency check"
        h = hashlittle(data, 0)
        pc, pb = hashlittle2(data, 0, 0)
        assert pc == h

    def test_accumulating_state(self):
        """Chaining hashlittle2 calls produces different results than single call."""
        data1 = b"first"
        data2 = b"second"

        # Single call on concatenation
        pc_single, pb_single = hashlittle2(data1 + data2, 0, 0)

        # Chained calls
        pc, pb = hashlittle2(data1, 0, 0)
        pc, pb = hashlittle2(data2, pc, pb)

        # They should be DIFFERENT (chaining is not the same as concatenation)
        assert (pc, pb) != (pc_single, pb_single)

    def test_deterministic(self):
        """Same inputs always produce the same outputs."""
        data = b"deterministic"
        r1 = hashlittle2(data, 7, 13)
        r2 = hashlittle2(data, 7, 13)
        assert r1 == r2


# === CASC .idx integration tests ===

IDX_DIR = os.path.join(DEFAULT_GAME_DIR, "data", "data") if DEFAULT_GAME_DIR else ""


def _idx_available():
    """Check if D2R .idx files are accessible."""
    return os.path.isdir(IDX_DIR) and len(glob.glob(os.path.join(IDX_DIR, "*.idx"))) > 0


@pytest.mark.skipif(not _idx_available(), reason="D2R .idx files not accessible")
class TestIdxHashReal:
    """Verify hash computation against real D2R .idx files."""

    def _read_idx(self, path):
        """Parse an .idx file and return its components."""
        with open(path, "rb") as f:
            data = f.read()

        hdr_size = struct.unpack_from("<I", data, 0x00)[0]
        hdr_hash = struct.unpack_from("<I", data, 0x04)[0]
        hdr_bytes = data[0x08:0x08 + hdr_size]

        data_size = struct.unpack_from("<I", data, 0x20)[0]
        data_hash = struct.unpack_from("<I", data, 0x24)[0]
        data_bytes = data[0x28:0x28 + data_size]

        ekey_len = data[0x0E]
        storage_len = data[0x0D]
        enc_len = data[0x0C]
        entry_len = ekey_len + storage_len + enc_len

        return {
            "hdr_size": hdr_size,
            "hdr_hash": hdr_hash,
            "hdr_bytes": hdr_bytes,
            "data_size": data_size,
            "data_hash": data_hash,
            "data_bytes": data_bytes,
            "entry_len": entry_len,
        }

    def test_all_header_hashes(self):
        """HeaderBlockHash matches hashlittle(header, 0) for all .idx files."""
        for path in sorted(glob.glob(os.path.join(IDX_DIR, "*.idx"))):
            info = self._read_idx(path)
            computed = idx_header_hash(info["hdr_bytes"])
            assert computed == info["hdr_hash"], (
                f"{os.path.basename(path)}: header hash mismatch "
                f"stored=0x{info['hdr_hash']:08x} computed=0x{computed:08x}"
            )

    def test_all_data_hashes(self):
        """DataBlockHash matches hashlittle2 per-entry for all .idx files."""
        for path in sorted(glob.glob(os.path.join(IDX_DIR, "*.idx"))):
            info = self._read_idx(path)
            computed = idx_data_hash(info["data_bytes"], info["entry_len"])
            assert computed == info["data_hash"], (
                f"{os.path.basename(path)}: data hash mismatch "
                f"stored=0x{info['data_hash']:08x} computed=0x{computed:08x}"
            )

    def test_entry_length_is_18(self):
        """D2R V2 .idx files always have 18-byte entries (9+5+4)."""
        for path in sorted(glob.glob(os.path.join(IDX_DIR, "*.idx"))):
            info = self._read_idx(path)
            assert info["entry_len"] == 18, (
                f"{os.path.basename(path)}: unexpected entry_len={info['entry_len']}"
            )

    def test_header_is_16_bytes(self):
        """V2 header is always 16 bytes."""
        for path in sorted(glob.glob(os.path.join(IDX_DIR, "*.idx"))):
            info = self._read_idx(path)
            assert info["hdr_size"] == 16, (
                f"{os.path.basename(path)}: unexpected hdr_size={info['hdr_size']}"
            )
