"""Tests for CASC BLTE encoder and archive entry builder (Task 4)."""

import hashlib
import os
import struct
import sys
import tempfile
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.slow

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from d2r_mod.casc_write import (
    CASCWriteError,
    append_to_archive,
    blte_encode,
    make_archive_entry,
)
from d2r_mod.casc import _decompress_blte, _build_index, DEFAULT_GAME_DIR


# ---------------------------------------------------------------------------
# BLTE Encoder Tests
# ---------------------------------------------------------------------------


class TestBLTEEncode:
    def test_blte_encode_roundtrip(self):
        """BLTE encode -> decode with existing reader should preserve content."""
        data = b'{"type": "test", "value": 42}'
        encoded = blte_encode(data)
        assert encoded[:4] == b'BLTE'
        decoded = _decompress_blte(encoded)
        assert decoded == data

    def test_blte_encode_uncompressed(self):
        """Uncompressed BLTE should roundtrip correctly."""
        data = b'small'
        encoded = blte_encode(data, compress=False)
        assert encoded[:4] == b'BLTE'
        decoded = _decompress_blte(encoded)
        assert decoded == data

    def test_blte_encode_empty_input(self):
        """Empty input should produce a valid BLTE container."""
        data = b''
        encoded = blte_encode(data)
        assert encoded[:4] == b'BLTE'
        decoded = _decompress_blte(encoded)
        assert decoded == data

    def test_blte_encode_empty_uncompressed(self):
        """Empty uncompressed input should roundtrip."""
        data = b''
        encoded = blte_encode(data, compress=False)
        decoded = _decompress_blte(encoded)
        assert decoded == data

    def test_blte_encode_large_data(self):
        """Large data should compress and roundtrip."""
        data = b'A' * 100_000
        encoded = blte_encode(data)
        assert len(encoded) < len(data)  # should compress well
        decoded = _decompress_blte(encoded)
        assert decoded == data

    def test_blte_header_size_is_zero(self):
        """Single-frame BLTE has header_size = 0."""
        encoded = blte_encode(b'test')
        header_size = struct.unpack_from('>I', encoded, 4)[0]
        assert header_size == 0

    def test_blte_compressed_mode_byte(self):
        """Compressed BLTE has mode byte 0x5A ('Z')."""
        encoded = blte_encode(b'test', compress=True)
        assert encoded[8] == 0x5A

    def test_blte_uncompressed_mode_byte(self):
        """Uncompressed BLTE has mode byte 0x4E ('N')."""
        encoded = blte_encode(b'test', compress=False)
        assert encoded[8] == 0x4E

    def test_blte_binary_data(self):
        """Binary data (all byte values) should roundtrip."""
        data = bytes(range(256)) * 10
        encoded = blte_encode(data)
        decoded = _decompress_blte(encoded)
        assert decoded == data


# ---------------------------------------------------------------------------
# Archive Entry Builder Tests
# ---------------------------------------------------------------------------


class TestMakeArchiveEntry:
    def test_make_archive_entry_format(self):
        """Archive entry header should match real CASC format."""
        data = b'test data'
        blte = blte_encode(data)
        ekey_9 = hashlib.md5(blte).digest()[:9]
        entry = make_archive_entry(blte, ekey_9)

        # First 16 bytes: EKey padded to 16 bytes, reversed
        expected_hash = (ekey_9 + b'\x00' * 7)[::-1]
        assert entry[:16] == expected_hash

        # Bytes 16-20: encoded size (LE)
        enc_size = struct.unpack_from('<I', entry, 16)[0]
        assert enc_size == len(entry)
        assert enc_size == 30 + len(blte)

        # Bytes 20-22: padding zeros
        assert entry[20:22] == b'\x00\x00'

        # Bytes 22-30: unknown (zeros)
        assert entry[22:30] == b'\x00' * 8

        # BLTE starts at offset 30
        assert entry[30:34] == b'BLTE'

    def test_make_archive_entry_ekey_recoverable(self):
        """Reversing header hash should recover the original EKey (first 9 bytes)."""
        data = b'some content'
        blte = blte_encode(data)
        ekey_9 = hashlib.md5(blte).digest()[:9]
        entry = make_archive_entry(blte, ekey_9)

        # Reverse the header hash, take first 9 bytes -> 9-byte EKey
        header_ekey = entry[:16][::-1][:9]
        assert header_ekey == ekey_9

    def test_make_archive_entry_total_length(self):
        """Total entry length = 30 (header) + len(blte_data)."""
        data = b'hello world'
        blte = blte_encode(data)
        ekey_9 = hashlib.md5(blte).digest()[:9]
        entry = make_archive_entry(blte, ekey_9)
        assert len(entry) == 30 + len(blte)

    def test_make_archive_entry_invalid_ekey_length(self):
        """Should reject EKey that is not exactly 9 bytes."""
        blte = blte_encode(b'data')
        with pytest.raises(CASCWriteError, match="9 bytes"):
            make_archive_entry(blte, b'\x00' * 8)
        with pytest.raises(CASCWriteError, match="9 bytes"):
            make_archive_entry(blte, b'\x00' * 16)

    def test_make_archive_entry_enc_size_field(self):
        """EncodedSize field should include the 30-byte header."""
        blte = blte_encode(b'x' * 500)
        ekey_9 = hashlib.md5(blte).digest()[:9]
        entry = make_archive_entry(blte, ekey_9)
        enc_size = struct.unpack_from('<I', entry, 16)[0]
        assert enc_size == 30 + len(blte)


# ---------------------------------------------------------------------------
# Real CASC Entry Validation
# ---------------------------------------------------------------------------


class TestArchiveEntryMatchesReal:
    """Compare our entry format against real entries in the D2R CASC."""

    CASC_DATA_DIR = os.path.join(DEFAULT_GAME_DIR, "data", "data") if DEFAULT_GAME_DIR else ""

    @pytest.fixture(autouse=True)
    def _check_casc_available(self):
        if not os.path.isdir(self.CASC_DATA_DIR):
            pytest.skip("D2R CASC not available at expected path")

    def test_archive_entry_matches_real(self):
        """Our header layout should match real CASC entry headers.

        Read a real entry, verify:
        - EKey padded+reversed at [0:16]
        - EncodedSize at [16:20] matches idx enc_size
        - BLTE magic at offset 30
        """
        index = _build_index(self.CASC_DATA_DIR)

        # Find an entry with non-zero offset (offset 0 entries may be special)
        real_ekey = None
        real_info = None
        for ekey, (archive_idx, offset, enc_size) in index.items():
            if offset > 0 and enc_size > 30:
                real_ekey = ekey
                real_info = (archive_idx, offset, enc_size)
                break

        assert real_ekey is not None, "No suitable real entry found"
        archive_idx, offset, enc_size = real_info

        # Read the 30-byte header from the real archive
        archive_path = os.path.join(
            self.CASC_DATA_DIR, f"data.{archive_idx:03d}"
        )
        with open(archive_path, 'rb') as f:
            f.seek(offset)
            real_header = f.read(30)

        assert len(real_header) == 30

        # Verify: header stores EKey padded to 16 bytes, reversed.
        header_reversed = real_header[:16][::-1]
        assert header_reversed[:9] == real_ekey, (
            f"EKey mismatch: header first 9={header_reversed[:9].hex()}, "
            f"expected={real_ekey.hex()}"
        )

        # Verify: encoded size at [16:20]
        real_enc_size = struct.unpack_from('<I', real_header, 16)[0]
        assert real_enc_size == enc_size, (
            f"EncSize mismatch: header={real_enc_size}, idx={enc_size}"
        )

        # Verify: BLTE magic at offset 30
        with open(archive_path, 'rb') as f:
            f.seek(offset + 30)
            blte_magic = f.read(4)
        assert blte_magic == b'BLTE', f"No BLTE magic at offset+30: {blte_magic!r}"

        # Now build our own entry with KNOWN data, and compare structure
        test_data = b'test comparison data'
        blte = blte_encode(test_data)
        ekey_9 = hashlib.md5(blte).digest()[:9]
        our_entry = make_archive_entry(blte, ekey_9)

        # Our header should have the same structural layout
        our_reversed = (ekey_9 + b'\x00' * 7)[::-1]
        assert our_entry[:16] == our_reversed
        our_enc_size = struct.unpack_from('<I', our_entry, 16)[0]
        assert our_enc_size == len(our_entry)
        assert our_entry[30:34] == b'BLTE'

    def test_real_entries_consistent_format(self):
        """Verify format consistency across multiple real entries.

        The archive header stores the 9-byte EKey padded to 16 bytes,
        then byte-reversed. We verify that the first 9 bytes of the
        reversed header match the .idx EKey, and bytes 9-15 are zeros.
        """
        index = _build_index(self.CASC_DATA_DIR)

        checked = 0
        for ekey, (archive_idx, offset, enc_size) in list(index.items())[:50]:
            if offset == 0:
                continue  # skip offset-0 entries

            archive_path = os.path.join(
                self.CASC_DATA_DIR, f"data.{archive_idx:03d}"
            )
            if not os.path.exists(archive_path):
                continue

            with open(archive_path, 'rb') as f:
                f.seek(offset)
                header = f.read(30)

            if len(header) < 30:
                continue

            # Header stores EKey padded+reversed. Reverse it back and check.
            header_reversed = header[:16][::-1]
            assert header_reversed[:9] == ekey, (
                f"Entry {ekey.hex()}: EKey mismatch in header"
            )
            # Bytes 9-15 should be zeros (padding)
            assert header_reversed[9:] == b'\x00' * 7, (
                f"Entry {ekey.hex()}: non-zero padding in header"
            )
            hdr_enc_size = struct.unpack_from('<I', header, 16)[0]
            assert hdr_enc_size == enc_size, (
                f"Entry {ekey.hex()}: enc_size mismatch "
                f"({hdr_enc_size} vs {enc_size})"
            )
            checked += 1

        assert checked >= 10, f"Only checked {checked} entries (need at least 10)"


# ---------------------------------------------------------------------------
# Archive Append Tests
# ---------------------------------------------------------------------------


class TestAppendToArchive:
    def test_append_to_archive(self, tmp_path):
        """Append should write entry at the end and return correct offset."""
        archive = tmp_path / "data.039"
        # Create a fake archive with some pre-existing data
        pre_data = b'\x00' * 100
        archive.write_bytes(pre_data)

        data = b'test append data'
        blte = blte_encode(data)
        ekey_9 = hashlib.md5(blte).digest()[:9]
        entry = make_archive_entry(blte, ekey_9)

        offset = append_to_archive(str(archive), entry)
        assert offset == 100  # appended after pre-existing data

        # Verify the entry was written correctly
        content = archive.read_bytes()
        assert len(content) == 100 + len(entry)
        assert content[100:130] == entry[:30]  # header
        assert content[130:134] == b'BLTE'     # BLTE magic

    def test_append_with_fsync(self, tmp_path):
        """Verify that fsync is called during append."""
        archive = tmp_path / "data.039"
        archive.write_bytes(b'\x00' * 50)

        data = b'fsync test'
        blte = blte_encode(data)
        ekey_9 = hashlib.md5(blte).digest()[:9]
        entry = make_archive_entry(blte, ekey_9)

        # Patch os.fsync to verify it's called
        with patch('d2r_mod.casc_write.os.fsync') as mock_fsync:
            offset = append_to_archive(str(archive), entry)
            assert mock_fsync.called, "os.fsync was not called"
            # fsync should be called with the file descriptor
            args = mock_fsync.call_args[0]
            assert isinstance(args[0], int), "fsync arg should be an fd (int)"

    def test_append_returns_correct_offset(self, tmp_path):
        """Multiple appends should return increasing offsets."""
        archive = tmp_path / "data.039"
        archive.write_bytes(b'')  # empty archive

        offsets = []
        for i in range(3):
            data = f'entry {i}'.encode()
            blte = blte_encode(data)
            ekey_9 = hashlib.md5(blte).digest()[:9]
            entry = make_archive_entry(blte, ekey_9)
            offset = append_to_archive(str(archive), entry)
            offsets.append((offset, len(entry)))

        # Each offset should be after the previous entry
        assert offsets[0][0] == 0
        assert offsets[1][0] == offsets[0][0] + offsets[0][1]
        assert offsets[2][0] == offsets[1][0] + offsets[1][1]

    def test_append_nonexistent_archive(self, tmp_path):
        """Should raise CASCWriteError for missing archive."""
        fake_path = str(tmp_path / "nonexistent.dat")
        blte = blte_encode(b'data')
        ekey_9 = hashlib.md5(blte).digest()[:9]
        entry = make_archive_entry(blte, ekey_9)

        with pytest.raises(CASCWriteError, match="not found"):
            append_to_archive(fake_path, entry)

    def test_append_offset_limit(self, tmp_path):
        """Should reject append that would exceed 30-bit offset limit."""
        archive = tmp_path / "data.039"
        # Create a file right at the limit
        archive.write_bytes(b'')

        blte = blte_encode(b'data')
        ekey_9 = hashlib.md5(blte).digest()[:9]
        entry = make_archive_entry(blte, ekey_9)

        # Pretend the file is already at the limit
        with patch('d2r_mod.casc_write.os.path.getsize', return_value=0x3FFFFFFF):
            with pytest.raises(CASCWriteError, match="offset limit"):
                append_to_archive(str(archive), entry)

    def test_append_entry_readable_after_write(self, tmp_path):
        """After appending, the entry should be readable and decompressible."""
        archive = tmp_path / "data.039"
        archive.write_bytes(b'\x00' * 200)

        original_data = b'{"health_ball": {"x": 600}}'
        blte = blte_encode(original_data)
        ekey_9 = hashlib.md5(blte).digest()[:9]
        entry = make_archive_entry(blte, ekey_9)

        offset = append_to_archive(str(archive), entry)

        # Read back and decompress
        with open(str(archive), 'rb') as f:
            f.seek(offset + 30)  # skip header
            blte_readback = f.read(len(entry) - 30)

        decoded = _decompress_blte(blte_readback)
        assert decoded == original_data


# ---------------------------------------------------------------------------
# CASCWriteError Tests
# ---------------------------------------------------------------------------


class TestCASCWriteError:
    def test_exception_is_exception(self):
        """CASCWriteError should be a proper exception."""
        with pytest.raises(CASCWriteError):
            raise CASCWriteError("test error")

    def test_exception_message(self):
        """CASCWriteError should carry a message."""
        try:
            raise CASCWriteError("something went wrong")
        except CASCWriteError as e:
            assert "something went wrong" in str(e)
