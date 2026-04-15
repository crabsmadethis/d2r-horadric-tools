"""Tests for .idx file writer (CASC V2 format)."""

import glob
import os
import struct
import tempfile

import pytest

pytestmark = pytest.mark.slow

from d2r_mod.build import DEFAULT_GAME_DIR
from d2r_mod.casc_write import (
    IDX_FILE_SIZE,
    MAX_ENTRIES_PER_IDX,
    build_idx_file,
    bucket_index,
    write_new_idx_files,
)
from d2r_mod.jenkins import idx_data_hash, idx_header_hash


# ── Test data ──────────────────────────────────────────────────────────

EKEY_A = b"\x01\x02\x03\x04\x05\x06\x07\x08\x09"
EKEY_B = b"\x0a\x0b\x0c\x0d\x0e\x0f\x10\x11\x12"
EKEY_C = b"\xDE\xAD\xBE\xEF\x01\x02\x03\x04\x05"

SINGLE_ENTRY = [(EKEY_A, 0, 0x1000, 500)]
TWO_ENTRIES = [
    (EKEY_A, 0, 0x1000, 500),
    (EKEY_B, 1, 0x2000, 1000),
]


# ── build_idx_file tests ──────────────────────────────────────────────


class TestBuildIdxFileSize:
    """Output must be exactly 262,144 bytes."""

    def test_empty_entries(self):
        result = build_idx_file(bucket=0, entries=[])
        assert len(result) == IDX_FILE_SIZE

    def test_single_entry(self):
        result = build_idx_file(bucket=0, entries=SINGLE_ENTRY)
        assert len(result) == IDX_FILE_SIZE

    def test_multiple_entries(self):
        result = build_idx_file(bucket=0, entries=TWO_ENTRIES)
        assert len(result) == IDX_FILE_SIZE

    def test_many_entries(self):
        """100 entries should still produce exactly 262,144 bytes."""
        entries = [
            (bytes([i % 256] * 9), 0, i * 100, 50 + i)
            for i in range(100)
        ]
        result = build_idx_file(bucket=5, entries=entries)
        assert len(result) == IDX_FILE_SIZE


class TestBuildIdxFileHeaderHash:
    """HeaderBlockHash must match jenkins.idx_header_hash."""

    def test_header_hash_single_entry(self):
        idx = build_idx_file(bucket=0, entries=SINGLE_ENTRY)
        stored_hash = struct.unpack_from("<I", idx, 0x04)[0]
        header_bytes = idx[0x08:0x18]
        computed_hash = idx_header_hash(header_bytes)
        assert stored_hash == computed_hash

    def test_header_hash_empty(self):
        idx = build_idx_file(bucket=7, entries=[])
        stored_hash = struct.unpack_from("<I", idx, 0x04)[0]
        header_bytes = idx[0x08:0x18]
        computed_hash = idx_header_hash(header_bytes)
        assert stored_hash == computed_hash

    def test_header_hash_each_bucket(self):
        """Each bucket should have a different header hash (different BucketIndex byte)."""
        hashes = set()
        for b in range(16):
            idx = build_idx_file(bucket=b, entries=[])
            stored = struct.unpack_from("<I", idx, 0x04)[0]
            hashes.add(stored)
        # All 16 hashes should be distinct
        assert len(hashes) == 16


class TestBuildIdxFileDataHash:
    """DataBlockHash must match jenkins.idx_data_hash."""

    def test_data_hash_single_entry(self):
        idx = build_idx_file(bucket=0, entries=SINGLE_ENTRY)
        data_block_len = struct.unpack_from("<I", idx, 0x20)[0]
        stored_hash = struct.unpack_from("<I", idx, 0x24)[0]
        data_block = idx[0x28:0x28 + data_block_len]
        computed_hash = idx_data_hash(data_block, entry_length=18)
        assert stored_hash == computed_hash

    def test_data_hash_multiple_entries(self):
        idx = build_idx_file(bucket=0, entries=TWO_ENTRIES)
        data_block_len = struct.unpack_from("<I", idx, 0x20)[0]
        stored_hash = struct.unpack_from("<I", idx, 0x24)[0]
        data_block = idx[0x28:0x28 + data_block_len]
        computed_hash = idx_data_hash(data_block, entry_length=18)
        assert stored_hash == computed_hash

    def test_data_hash_empty(self):
        """Empty data block should have DataBlockSize=0 and DataBlockHash=0."""
        idx = build_idx_file(bucket=0, entries=[])
        data_block_len = struct.unpack_from("<I", idx, 0x20)[0]
        stored_hash = struct.unpack_from("<I", idx, 0x24)[0]
        assert data_block_len == 0
        assert stored_hash == 0

    def test_data_hash_changes_with_entries(self):
        """Different entries produce different data hashes."""
        idx1 = build_idx_file(bucket=0, entries=SINGLE_ENTRY)
        idx2 = build_idx_file(bucket=0, entries=TWO_ENTRIES)
        hash1 = struct.unpack_from("<I", idx1, 0x24)[0]
        hash2 = struct.unpack_from("<I", idx2, 0x24)[0]
        assert hash1 != hash2


class TestBuildIdxFileParseable:
    """Generated .idx files must be parseable by the existing CASC reader."""

    def test_parseable_by_build_index(self):
        """_build_index should find our entries in the generated .idx."""
        entries = [(EKEY_C, 0, 0x5000, 750)]
        idx_data = build_idx_file(bucket=0, entries=entries)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "0000000001.idx")
            with open(path, "wb") as f:
                f.write(idx_data)

            from d2r_mod.casc import _build_index
            index = _build_index(tmpdir)

        assert EKEY_C in index
        archive_idx, offset, enc_size = index[EKEY_C]
        assert archive_idx == 0
        assert offset == 0x5000
        assert enc_size == 750

    def test_parseable_multiple_entries(self):
        """All entries should be found by the reader."""
        idx_data = build_idx_file(bucket=0, entries=TWO_ENTRIES)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "0000000001.idx")
            with open(path, "wb") as f:
                f.write(idx_data)

            from d2r_mod.casc import _build_index
            index = _build_index(tmpdir)

        assert EKEY_A in index
        assert EKEY_B in index

        # Verify EKEY_A
        a_idx, a_off, a_size = index[EKEY_A]
        assert a_idx == 0
        assert a_off == 0x1000
        assert a_size == 500

        # Verify EKEY_B
        b_idx, b_off, b_size = index[EKEY_B]
        assert b_idx == 1
        assert b_off == 0x2000
        assert b_size == 1000


class TestBuildIdxFileSingleEntry:
    """Detailed verification of a single-entry .idx file."""

    def test_entry_format(self):
        """Entry bytes at 0x28 should match our input exactly."""
        ekey = b"\xAA\xBB\xCC\xDD\xEE\xFF\x11\x22\x33"
        archive_idx = 2
        archive_offset = 0x12345
        enc_size = 9999

        idx = build_idx_file(bucket=0, entries=[(ekey, archive_idx, archive_offset, enc_size)])

        # Verify entry at 0x28
        stored_ekey = idx[0x28:0x28 + 9]
        assert stored_ekey == ekey

        # StorageOffset: 5 bytes BE = (archive_idx << 30) | archive_offset
        expected_storage = (archive_idx << 30) | archive_offset
        stored_storage = int.from_bytes(idx[0x31:0x36], "big")
        assert stored_storage == expected_storage

        # EncodedSize: 4 bytes LE
        stored_enc_size = struct.unpack_from("<I", idx, 0x36)[0]
        assert stored_enc_size == enc_size

    def test_archive_idx_39_roundtrip(self):
        """archive_idx=39 (realistic D2R value) should roundtrip through reader."""
        ekey = b"\xAA\xBB\xCC\xDD\xEE\xFF\x11\x22\x33"
        archive_idx = 39
        archive_offset = 0x2000000  # 32 MB
        enc_size = 12345

        idx_data = build_idx_file(bucket=0, entries=[(ekey, archive_idx, archive_offset, enc_size)])

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "0000000001.idx")
            with open(path, "wb") as f:
                f.write(idx_data)

            from d2r_mod.casc import _build_index
            index = _build_index(tmpdir)

        assert ekey in index
        r_idx, r_off, r_size = index[ekey]
        assert r_idx == 39
        assert r_off == 0x2000000
        assert r_size == 12345

    def test_data_block_size_is_18(self):
        """DataBlockSize should be 18 for one entry."""
        idx = build_idx_file(bucket=0, entries=SINGLE_ENTRY)
        data_block_size = struct.unpack_from("<I", idx, 0x20)[0]
        assert data_block_size == 18

    def test_header_block_size_is_16(self):
        """HeaderBlockSize should always be 16."""
        idx = build_idx_file(bucket=0, entries=SINGLE_ENTRY)
        header_block_size = struct.unpack_from("<I", idx, 0x00)[0]
        assert header_block_size == 16


class TestBuildIdxFileMultipleEntries:
    """Verification of multi-entry .idx files."""

    def test_data_block_size(self):
        """DataBlockSize should be num_entries * 18."""
        idx = build_idx_file(bucket=0, entries=TWO_ENTRIES)
        data_block_size = struct.unpack_from("<I", idx, 0x20)[0]
        assert data_block_size == 2 * 18

    def test_entries_contiguous(self):
        """Entries should be packed contiguously starting at 0x28."""
        idx = build_idx_file(bucket=0, entries=TWO_ENTRIES)

        # First entry at 0x28
        ekey1 = idx[0x28:0x28 + 9]
        assert ekey1 == EKEY_A

        # Second entry at 0x28 + 18
        ekey2 = idx[0x3A:0x3A + 9]
        assert ekey2 == EKEY_B

    def test_zero_padding_after_entries(self):
        """Bytes after entries should be all zeros."""
        idx = build_idx_file(bucket=0, entries=TWO_ENTRIES)
        entries_end = 0x28 + 2 * 18
        trailing = idx[entries_end:]
        assert trailing == b"\x00" * len(trailing)


class TestBuildIdxFileBucketIndex:
    """BucketIndex in V2 header must match the bucket parameter."""

    def test_bucket_0(self):
        idx = build_idx_file(bucket=0, entries=[])
        assert idx[0x0A] == 0

    def test_bucket_7(self):
        idx = build_idx_file(bucket=7, entries=[])
        assert idx[0x0A] == 7

    def test_bucket_15(self):
        idx = build_idx_file(bucket=15, entries=[])
        assert idx[0x0A] == 15

    def test_all_buckets(self):
        for b in range(16):
            idx = build_idx_file(bucket=b, entries=[])
            assert idx[0x0A] == b, f"Bucket {b}: header byte 0x0A = {idx[0x0A]}"


class TestBuildIdxFileValidation:
    """Input validation."""

    def test_invalid_bucket_negative(self):
        with pytest.raises(ValueError, match="Bucket index"):
            build_idx_file(bucket=-1, entries=[])

    def test_invalid_bucket_too_high(self):
        with pytest.raises(ValueError, match="Bucket index"):
            build_idx_file(bucket=16, entries=[])

    def test_invalid_ekey_length(self):
        with pytest.raises(ValueError, match="EKey must be 9 bytes"):
            build_idx_file(bucket=0, entries=[(b"\x01\x02\x03", 0, 0, 100)])

    def test_invalid_archive_offset_too_large(self):
        with pytest.raises(ValueError, match="30-bit limit"):
            build_idx_file(bucket=0, entries=[(EKEY_A, 0, 0x40000000, 100)])

    def test_max_archive_offset_ok(self):
        """Maximum valid offset (2^30 - 1) should work."""
        idx = build_idx_file(bucket=0, entries=[(EKEY_A, 0, 0x3FFFFFFF, 100)])
        assert len(idx) == IDX_FILE_SIZE

    def test_too_many_entries(self):
        entries = [(bytes(9), 0, 0, 100)] * (MAX_ENTRIES_PER_IDX + 1)
        with pytest.raises(ValueError, match="Too many entries"):
            build_idx_file(bucket=0, entries=entries)


# ── bucket_index tests ────────────────────────────────────────────────


class TestBucketIndex:
    """bucket_index function tests."""

    def test_all_zeros(self):
        assert bucket_index(b"\x00" * 9) == 0

    def test_returns_0_to_15(self):
        """Result should always be in [0, 15]."""
        import random
        rng = random.Random(42)
        for _ in range(1000):
            ekey = bytes(rng.randint(0, 255) for _ in range(9))
            bi = bucket_index(ekey)
            assert 0 <= bi <= 15

    def test_deterministic(self):
        ekey = b"\xDE\xAD\xBE\xEF\x01\x02\x03\x04\x05"
        assert bucket_index(ekey) == bucket_index(ekey)

    def test_different_ekeys_can_have_same_bucket(self):
        """Multiple EKeys may map to the same bucket."""
        # Just verify no crash; bucket collisions are expected
        b1 = bucket_index(EKEY_A)
        b2 = bucket_index(EKEY_B)
        assert 0 <= b1 <= 15
        assert 0 <= b2 <= 15


# ── write_new_idx_files tests ─────────────────────────────────────────


class TestWriteNewIdxFiles:
    """Integration tests for write_new_idx_files."""

    def test_creates_files(self):
        """Should create .idx files in the target directory."""
        entries = [(EKEY_A, 0, 0x1000, 500)]
        with tempfile.TemporaryDirectory() as tmpdir:
            created = write_new_idx_files(tmpdir, entries)
            assert len(created) >= 1
            for path in created:
                assert os.path.exists(path)
                assert path.endswith(".idx")

    def test_file_size(self):
        """Created files should be exactly 262,144 bytes."""
        entries = [(EKEY_A, 0, 0x1000, 500)]
        with tempfile.TemporaryDirectory() as tmpdir:
            created = write_new_idx_files(tmpdir, entries)
            for path in created:
                assert os.path.getsize(path) == IDX_FILE_SIZE

    def test_increments_suffix(self):
        """New file suffix should be one more than the highest existing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bi = bucket_index(EKEY_A)
            # Create a fake existing .idx file
            existing_name = f"{bi:02x}00000005.idx"
            with open(os.path.join(tmpdir, existing_name), "wb") as f:
                f.write(b"\x00" * IDX_FILE_SIZE)

            entries = [(EKEY_A, 0, 0x1000, 500)]
            created = write_new_idx_files(tmpdir, entries)

            assert len(created) == 1
            fname = os.path.basename(created[0])
            # Should be bucket_hex + "00000006" + .idx
            expected = f"{bi:02x}00000006.idx"
            assert fname == expected

    def test_starts_at_suffix_1_when_no_existing(self):
        """If no existing .idx for that bucket, suffix should be 1."""
        with tempfile.TemporaryDirectory() as tmpdir:
            entries = [(EKEY_A, 0, 0x1000, 500)]
            created = write_new_idx_files(tmpdir, entries)
            assert len(created) == 1
            fname = os.path.basename(created[0])
            bi = bucket_index(EKEY_A)
            expected = f"{bi:02x}00000001.idx"
            assert fname == expected

    def test_groups_by_bucket(self):
        """Entries for different buckets go in different .idx files."""
        # Find two EKeys that hash to different buckets
        ekeys_by_bucket: dict[int, bytes] = {}
        for i in range(256):
            ekey = bytes([i] + [0] * 8)
            bi = bucket_index(ekey)
            if bi not in ekeys_by_bucket:
                ekeys_by_bucket[bi] = ekey
            if len(ekeys_by_bucket) >= 2:
                break

        buckets = list(ekeys_by_bucket.keys())[:2]
        entries = [
            (ekeys_by_bucket[buckets[0]], 0, 0x1000, 500),
            (ekeys_by_bucket[buckets[1]], 0, 0x2000, 600),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            created = write_new_idx_files(tmpdir, entries)
            assert len(created) == 2
            # Each file should be for a different bucket
            file_buckets = set()
            for path in created:
                fname = os.path.basename(path)
                file_buckets.add(int(fname[:2], 16))
            assert len(file_buckets) == 2

    def test_parseable_by_reader(self):
        """Created files should be parseable by _build_index."""
        entries = [
            (EKEY_A, 0, 0x1000, 500),
            (EKEY_C, 0, 0x3000, 750),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            write_new_idx_files(tmpdir, entries)

            from d2r_mod.casc import _build_index
            index = _build_index(tmpdir)

        assert EKEY_A in index
        assert EKEY_C in index
        assert index[EKEY_A] == (0, 0x1000, 500)
        assert index[EKEY_C] == (0, 0x3000, 750)

    def test_empty_entries(self):
        """No entries should create no files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            created = write_new_idx_files(tmpdir, [])
            assert created == []


# ── Real .idx validation ──────────────────────────────────────────────

IDX_DIR = os.path.join(DEFAULT_GAME_DIR, "data", "data") if DEFAULT_GAME_DIR else ""


def _idx_available():
    return os.path.isdir(IDX_DIR) and len(glob.glob(os.path.join(IDX_DIR, "*.idx"))) > 0


@pytest.mark.skipif(not _idx_available(), reason="D2R .idx files not accessible")
class TestBuildIdxFileMatchesReal:
    """Verify our generated .idx structure matches real D2R .idx files."""

    def test_v2_header_matches_real(self):
        """V2 header fields should match a real .idx (except BucketIndex)."""
        # Read real header
        real_path = sorted(glob.glob(os.path.join(IDX_DIR, "*.idx")))[0]
        with open(real_path, "rb") as f:
            real_data = f.read(0x18)
        real_header = real_data[0x08:0x18]
        real_bucket = real_header[2]

        # Generate our header for same bucket
        idx = build_idx_file(bucket=real_bucket, entries=[])
        our_header = idx[0x08:0x18]

        assert our_header == real_header, (
            f"V2 header mismatch:\n"
            f"  real: {real_header.hex()}\n"
            f"  ours: {our_header.hex()}"
        )

    def test_header_hash_matches_real_computation(self):
        """Our header hash should use the same algorithm as verified real .idx files."""
        # Read a real .idx and verify our idx_header_hash matches
        real_path = sorted(glob.glob(os.path.join(IDX_DIR, "*.idx")))[0]
        with open(real_path, "rb") as f:
            real_data = f.read(0x18)
        real_hash = struct.unpack_from("<I", real_data, 0x04)[0]
        real_header = real_data[0x08:0x18]
        computed = idx_header_hash(real_header)
        assert computed == real_hash

        # Now verify our generated file uses the same computation
        idx = build_idx_file(bucket=0, entries=SINGLE_ENTRY)
        our_hash = struct.unpack_from("<I", idx, 0x04)[0]
        our_header = idx[0x08:0x18]
        assert our_hash == idx_header_hash(our_header)

    def test_structural_layout_matches_real(self):
        """Key structural offsets should match real .idx files."""
        real_path = sorted(glob.glob(os.path.join(IDX_DIR, "*.idx")))[0]
        with open(real_path, "rb") as f:
            real_data = f.read()
        assert len(real_data) == IDX_FILE_SIZE

        # HeaderBlockSize at 0x00
        real_hdr_size = struct.unpack_from("<I", real_data, 0x00)[0]
        assert real_hdr_size == 16

        # Our generated file should have the same structure
        idx = build_idx_file(bucket=0, entries=SINGLE_ENTRY)
        our_hdr_size = struct.unpack_from("<I", idx, 0x00)[0]
        assert our_hdr_size == real_hdr_size
