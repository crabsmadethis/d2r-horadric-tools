"""
D2R .tbl String Table Binary Format -- Investigation Gate
==========================================================

Confirmed format based on analysis of three vanilla D2R files:
  - string.tbl          (390570 bytes, 5391 entries)
  - expansionstring.tbl (173234 bytes, 2818 entries)
  - patchstring.tbl     ( 54879 bytes, 1216 entries)

HEADER (21 bytes):
  Offset  Size   Type       Field
  0x00    2      uint16 LE  CRC
  0x02    2      uint16 LE  NumElements     (number of used hash entries)
  0x04    4      uint32 LE  HashTableSize   (total hash table slots)
  0x08    1      uint8      Version         (always 1)
  0x09    4      uint32 LE  StringDataStart (absolute file offset)
  0x0D    4      uint32 LE  LoopCount       (num iterations during build)
  0x11    4      uint32 LE  FileSize        (total file size in bytes)

INDEX TABLE (NumElements * 2 bytes):
  Immediately follows header at offset 21.
  Each entry is a uint16 LE pointing to a hash table slot index.
  Provides ordered access to entries (insertion order).
  All indices are unique and point to used hash entries.

HASH TABLE (HashTableSize * 17 bytes):
  Immediately follows index table at offset 21 + NumElements * 2.
  Each entry is 17 bytes:

  Offset  Size   Type       Field
  +0      1      uint8      used         (0=empty, 1=occupied)
  +1      2      uint16 LE  index        (position in index table)
  +3      4      uint32 LE  hash_value   (hash % HashTableSize, original bucket)
  +7      4      uint32 LE  key_offset   (absolute file offset to key string)
  +11     4      uint32 LE  string_offset(absolute file offset to value string)
  +15     2      uint16 LE  string_length(length INCLUDING null terminator)

STRING DATA:
  Starts at StringDataStart (== 21 + NumElements*2 + HashTableSize*17).
  Contains null-terminated key/value pairs stored adjacently:
    key\\0value\\0
  All key_offset and string_offset values are ABSOLUTE file offsets
  (NOT relative to StringDataStart).

COLLISION RESOLUTION:
  Linear probing. When hash(key) % HashTableSize collides, the entry
  is placed at the next empty slot (wrapping around). The hash_value
  field stores the ORIGINAL bucket (hash % HashTableSize), not the
  actual position. This allows the lookup to verify it found the
  right chain.

HASH FUNCTION:
  Not yet identified (not standard Jenkins one-at-a-time). The stored
  hash_value is hash(key) % HashTableSize. The exact function does not
  need to be known for READING .tbl files (just iterate hash table),
  but will be needed for WRITING (Task 3 / ELF hash gate).
"""

import os
import struct
import pytest

# ── Paths ──────────────────────────────────────────────────────────────
VANILLA_DIR = os.path.join(os.path.dirname(__file__), "..", "vanilla", "data", "local", "lng", "eng")
TBL_FILES = {
    "string.tbl": os.path.join(VANILLA_DIR, "string.tbl"),
    "expansionstring.tbl": os.path.join(VANILLA_DIR, "expansionstring.tbl"),
    "patchstring.tbl": os.path.join(VANILLA_DIR, "patchstring.tbl"),
}

# ── Format constants ──────────────────────────────────────────────────
HEADER_SIZE = 21
HASH_ENTRY_SIZE = 17
INDEX_ENTRY_SIZE = 2
VERSION = 1


def parse_header(data: bytes) -> dict:
    """Parse a 21-byte .tbl header."""
    return {
        "crc": struct.unpack_from("<H", data, 0)[0],
        "num_elements": struct.unpack_from("<H", data, 2)[0],
        "hash_table_size": struct.unpack_from("<I", data, 4)[0],
        "version": data[8],
        "string_data_start": struct.unpack_from("<I", data, 9)[0],
        "loop_count": struct.unpack_from("<I", data, 0x0D)[0],
        "file_size": struct.unpack_from("<I", data, 0x11)[0],
    }


def parse_hash_entry(data: bytes, offset: int) -> dict:
    """Parse a single 17-byte hash table entry."""
    return {
        "used": data[offset],
        "index": struct.unpack_from("<H", data, offset + 1)[0],
        "hash_value": struct.unpack_from("<I", data, offset + 3)[0],
        "key_offset": struct.unpack_from("<I", data, offset + 7)[0],
        "string_offset": struct.unpack_from("<I", data, offset + 11)[0],
        "string_length": struct.unpack_from("<H", data, offset + 15)[0],
    }


def read_cstring(data: bytes, offset: int) -> str:
    """Read a null-terminated string from data at offset."""
    end = data.index(0, offset)
    return data[offset:end].decode("utf-8", errors="replace")


# ── Fixtures ──────────────────────────────────────────────────────────
@pytest.fixture(params=list(TBL_FILES.keys()), ids=list(TBL_FILES.keys()))
def tbl_data(request):
    """Load a vanilla .tbl file, return (name, raw_bytes)."""
    name = request.param
    path = TBL_FILES[name]
    if not os.path.exists(path):
        pytest.skip(f"Vanilla file not found: {path}")
    with open(path, "rb") as f:
        return name, f.read()


# ── Header tests ──────────────────────────────────────────────────────
class TestHeader:
    def test_version_is_1(self, tbl_data):
        name, data = tbl_data
        hdr = parse_header(data)
        assert hdr["version"] == VERSION, f"{name}: version={hdr['version']}"

    def test_file_size_matches(self, tbl_data):
        name, data = tbl_data
        hdr = parse_header(data)
        assert hdr["file_size"] == len(data), (
            f"{name}: stored={hdr['file_size']} actual={len(data)}"
        )

    def test_string_data_start_formula(self, tbl_data):
        """StringDataStart == HEADER + IndexTable + HashTable."""
        name, data = tbl_data
        hdr = parse_header(data)
        expected = (
            HEADER_SIZE
            + hdr["num_elements"] * INDEX_ENTRY_SIZE
            + hdr["hash_table_size"] * HASH_ENTRY_SIZE
        )
        assert hdr["string_data_start"] == expected, (
            f"{name}: StringDataStart={hdr['string_data_start']} expected={expected}"
        )


# ── Index table tests ─────────────────────────────────────────────────
class TestIndexTable:
    def test_all_indices_unique(self, tbl_data):
        name, data = tbl_data
        hdr = parse_header(data)
        indices = []
        for i in range(hdr["num_elements"]):
            idx = struct.unpack_from("<H", data, HEADER_SIZE + i * 2)[0]
            indices.append(idx)
        assert len(set(indices)) == len(indices), f"{name}: duplicate indices"

    def test_all_indices_point_to_used_entries(self, tbl_data):
        name, data = tbl_data
        hdr = parse_header(data)
        hash_table_start = HEADER_SIZE + hdr["num_elements"] * INDEX_ENTRY_SIZE

        for i in range(hdr["num_elements"]):
            idx = struct.unpack_from("<H", data, HEADER_SIZE + i * 2)[0]
            assert idx < hdr["hash_table_size"], (
                f"{name}: index[{i}]={idx} >= HashTableSize={hdr['hash_table_size']}"
            )
            entry_off = hash_table_start + idx * HASH_ENTRY_SIZE
            assert data[entry_off] == 1, (
                f"{name}: index[{i}]={idx} points to unused entry"
            )

    def test_index_field_matches_position(self, tbl_data):
        """The 'index' field in each hash entry equals its position in
        the index table that points to it."""
        name, data = tbl_data
        hdr = parse_header(data)
        hash_table_start = HEADER_SIZE + hdr["num_elements"] * INDEX_ENTRY_SIZE

        # Build reverse map: hash_slot -> index_table_position
        slot_to_pos = {}
        for i in range(hdr["num_elements"]):
            slot = struct.unpack_from("<H", data, HEADER_SIZE + i * 2)[0]
            slot_to_pos[slot] = i

        for slot in range(hdr["hash_table_size"]):
            entry_off = hash_table_start + slot * HASH_ENTRY_SIZE
            if not data[entry_off]:
                continue
            entry = parse_hash_entry(data, entry_off)
            assert slot in slot_to_pos, (
                f"{name}: used entry at slot {slot} not referenced by index table"
            )
            assert entry["index"] == slot_to_pos[slot], (
                f"{name}: slot {slot} index field={entry['index']} "
                f"expected={slot_to_pos[slot]}"
            )


# ── Hash table tests ──────────────────────────────────────────────────
class TestHashTable:
    def test_entry_size_is_17(self, tbl_data):
        """Verify the 17-byte entry size by checking the formula."""
        name, data = tbl_data
        hdr = parse_header(data)
        hash_table_start = HEADER_SIZE + hdr["num_elements"] * INDEX_ENTRY_SIZE
        hash_table_bytes = hdr["string_data_start"] - hash_table_start
        assert hash_table_bytes == hdr["hash_table_size"] * HASH_ENTRY_SIZE

    def test_used_count_equals_num_elements(self, tbl_data):
        name, data = tbl_data
        hdr = parse_header(data)
        hash_table_start = HEADER_SIZE + hdr["num_elements"] * INDEX_ENTRY_SIZE

        used = 0
        for i in range(hdr["hash_table_size"]):
            if data[hash_table_start + i * HASH_ENTRY_SIZE]:
                used += 1

        assert used == hdr["num_elements"], (
            f"{name}: used={used} NumElements={hdr['num_elements']}"
        )

    def test_hash_value_within_table_range(self, tbl_data):
        """hash_value must be in [0, HashTableSize)."""
        name, data = tbl_data
        hdr = parse_header(data)
        hash_table_start = HEADER_SIZE + hdr["num_elements"] * INDEX_ENTRY_SIZE

        for i in range(hdr["hash_table_size"]):
            off = hash_table_start + i * HASH_ENTRY_SIZE
            if not data[off]:
                continue
            entry = parse_hash_entry(data, off)
            assert entry["hash_value"] < hdr["hash_table_size"], (
                f"{name}: entry[{i}] hash_value={entry['hash_value']} "
                f">= HashTableSize={hdr['hash_table_size']}"
            )

    def test_linear_probing_chain(self, tbl_data):
        """For displaced entries (position != hash_value), all slots from
        hash_value to position must be occupied (linear probing)."""
        name, data = tbl_data
        hdr = parse_header(data)
        hash_table_start = HEADER_SIZE + hdr["num_elements"] * INDEX_ENTRY_SIZE
        ht_size = hdr["hash_table_size"]

        for i in range(ht_size):
            off = hash_table_start + i * HASH_ENTRY_SIZE
            if not data[off]:
                continue
            entry = parse_hash_entry(data, off)
            if entry["hash_value"] == i:
                continue  # at home bucket

            # Walk from home bucket to current position; all must be used
            pos = entry["hash_value"]
            while pos != i:
                check_off = hash_table_start + pos * HASH_ENTRY_SIZE
                assert data[check_off], (
                    f"{name}: linear probe gap at slot {pos} "
                    f"(entry {i}, home={entry['hash_value']})"
                )
                pos = (pos + 1) % ht_size


# ── String data tests ─────────────────────────────────────────────────
class TestStringData:
    def test_all_keys_valid_ascii(self, tbl_data):
        """Every key must be printable ASCII."""
        name, data = tbl_data
        hdr = parse_header(data)
        hash_table_start = HEADER_SIZE + hdr["num_elements"] * INDEX_ENTRY_SIZE

        for i in range(hdr["hash_table_size"]):
            off = hash_table_start + i * HASH_ENTRY_SIZE
            if not data[off]:
                continue
            entry = parse_hash_entry(data, off)
            key = read_cstring(data, entry["key_offset"])
            assert len(key) > 0, f"{name}: empty key at slot {i}"
            assert all(32 <= ord(c) < 127 for c in key), (
                f"{name}: non-ASCII key at slot {i}: {key!r}"
            )

    def test_all_strings_valid_utf8(self, tbl_data):
        """Every string value must decode as valid UTF-8."""
        name, data = tbl_data
        hdr = parse_header(data)
        hash_table_start = HEADER_SIZE + hdr["num_elements"] * INDEX_ENTRY_SIZE

        for i in range(hdr["hash_table_size"]):
            off = hash_table_start + i * HASH_ENTRY_SIZE
            if not data[off]:
                continue
            entry = parse_hash_entry(data, off)
            end = data.index(0, entry["string_offset"])
            # strict decode -- raises on invalid UTF-8
            data[entry["string_offset"]:end].decode("utf-8")

    def test_offsets_are_absolute(self, tbl_data):
        """All key/string offsets must be >= StringDataStart and < FileSize."""
        name, data = tbl_data
        hdr = parse_header(data)
        hash_table_start = HEADER_SIZE + hdr["num_elements"] * INDEX_ENTRY_SIZE

        for i in range(hdr["hash_table_size"]):
            off = hash_table_start + i * HASH_ENTRY_SIZE
            if not data[off]:
                continue
            entry = parse_hash_entry(data, off)
            assert entry["key_offset"] >= hdr["string_data_start"], (
                f"{name}: key_offset {entry['key_offset']} < "
                f"StringDataStart {hdr['string_data_start']}"
            )
            assert entry["string_offset"] >= hdr["string_data_start"], (
                f"{name}: string_offset {entry['string_offset']} < "
                f"StringDataStart {hdr['string_data_start']}"
            )
            assert entry["key_offset"] < hdr["file_size"]
            assert entry["string_offset"] < hdr["file_size"]

    def test_key_string_adjacent(self, tbl_data):
        """key and value are stored adjacently: key\\0value\\0."""
        name, data = tbl_data
        hdr = parse_header(data)
        hash_table_start = HEADER_SIZE + hdr["num_elements"] * INDEX_ENTRY_SIZE

        for i in range(hdr["hash_table_size"]):
            off = hash_table_start + i * HASH_ENTRY_SIZE
            if not data[off]:
                continue
            entry = parse_hash_entry(data, off)
            key_end = data.index(0, entry["key_offset"])
            expected_str_off = key_end + 1
            assert entry["string_offset"] == expected_str_off, (
                f"{name}: slot {i} key ends at {key_end}, "
                f"string_offset={entry['string_offset']} expected={expected_str_off}"
            )

    def test_string_length_includes_null(self, tbl_data):
        """string_length == len(value_bytes) + 1 (includes null terminator)."""
        name, data = tbl_data
        hdr = parse_header(data)
        hash_table_start = HEADER_SIZE + hdr["num_elements"] * INDEX_ENTRY_SIZE

        for i in range(hdr["hash_table_size"]):
            off = hash_table_start + i * HASH_ENTRY_SIZE
            if not data[off]:
                continue
            entry = parse_hash_entry(data, off)
            str_end = data.index(0, entry["string_offset"])
            actual_with_null = str_end - entry["string_offset"] + 1
            assert entry["string_length"] == actual_with_null, (
                f"{name}: slot {i} string_length={entry['string_length']} "
                f"actual_with_null={actual_with_null}"
            )


# ── Known-value spot checks ──────────────────────────────────────────
class TestKnownValues:
    """Spot-check specific entries to catch format regressions."""

    def _lookup(self, data: bytes, target_key: str) -> dict | None:
        """Find a hash entry by key name."""
        hdr = parse_header(data)
        hash_table_start = HEADER_SIZE + hdr["num_elements"] * INDEX_ENTRY_SIZE
        for i in range(hdr["hash_table_size"]):
            off = hash_table_start + i * HASH_ENTRY_SIZE
            if not data[off]:
                continue
            entry = parse_hash_entry(data, off)
            key = read_cstring(data, entry["key_offset"])
            if key == target_key:
                return entry
        return None

    def test_string_tbl_quarterstaff(self):
        """string.tbl must contain key '8ls' -> 'Quarterstaff'."""
        path = TBL_FILES["string.tbl"]
        if not os.path.exists(path):
            pytest.skip("Vanilla file not found")
        with open(path, "rb") as f:
            data = f.read()
        entry = self._lookup(data, "8ls")
        assert entry is not None, "Key '8ls' not found"
        value = read_cstring(data, entry["string_offset"])
        assert value == "Quarterstaff"

    def test_string_tbl_faithful(self):
        """string.tbl must contain key 'Faithful' -> 'Faithful'."""
        path = TBL_FILES["string.tbl"]
        if not os.path.exists(path):
            pytest.skip("Vanilla file not found")
        with open(path, "rb") as f:
            data = f.read()
        entry = self._lookup(data, "Faithful")
        assert entry is not None, "Key 'Faithful' not found"
        value = read_cstring(data, entry["string_offset"])
        assert value == "Faithful"

    def test_string_tbl_gothic_bow(self):
        """string.tbl must contain key '8lw' -> 'Gothic Bow'."""
        path = TBL_FILES["string.tbl"]
        if not os.path.exists(path):
            pytest.skip("Vanilla file not found")
        with open(path, "rb") as f:
            data = f.read()
        entry = self._lookup(data, "8lw")
        assert entry is not None, "Key '8lw' not found"
        value = read_cstring(data, entry["string_offset"])
        assert value == "Gothic Bow"

    def test_header_values_string_tbl(self):
        """Lock in exact header values for string.tbl."""
        path = TBL_FILES["string.tbl"]
        if not os.path.exists(path):
            pytest.skip("Vanilla file not found")
        with open(path, "rb") as f:
            data = f.read()
        hdr = parse_header(data)
        assert hdr["crc"] == 0xFE2B
        assert hdr["num_elements"] == 5391
        assert hdr["hash_table_size"] == 5393
        assert hdr["version"] == 1
        assert hdr["string_data_start"] == 102484
        assert hdr["file_size"] == 390570

    def test_header_values_expansionstring_tbl(self):
        """Lock in exact header values for expansionstring.tbl."""
        path = TBL_FILES["expansionstring.tbl"]
        if not os.path.exists(path):
            pytest.skip("Vanilla file not found")
        with open(path, "rb") as f:
            data = f.read()
        hdr = parse_header(data)
        assert hdr["crc"] == 0xCB2F
        assert hdr["num_elements"] == 2818
        assert hdr["hash_table_size"] == 2819
        assert hdr["version"] == 1
        assert hdr["string_data_start"] == 53580
        assert hdr["file_size"] == 173234

    def test_header_values_patchstring_tbl(self):
        """Lock in exact header values for patchstring.tbl."""
        path = TBL_FILES["patchstring.tbl"]
        if not os.path.exists(path):
            pytest.skip("Vanilla file not found")
        with open(path, "rb") as f:
            data = f.read()
        hdr = parse_header(data)
        assert hdr["crc"] == 0xE65C
        assert hdr["num_elements"] == 1216
        assert hdr["hash_table_size"] == 1217
        assert hdr["version"] == 1
        assert hdr["string_data_start"] == 23142
        assert hdr["file_size"] == 54879


# ── Full parse count test ─────────────────────────────────────────────
class TestFullParse:
    """The ultimate validation: parse 100% of entries from all files."""

    @pytest.mark.parametrize("filename", list(TBL_FILES.keys()))
    def test_parse_all_entries(self, filename):
        """Parse every entry and verify key+value are readable."""
        path = TBL_FILES[filename]
        if not os.path.exists(path):
            pytest.skip(f"Vanilla file not found: {path}")
        with open(path, "rb") as f:
            data = f.read()

        hdr = parse_header(data)
        hash_table_start = HEADER_SIZE + hdr["num_elements"] * INDEX_ENTRY_SIZE
        parsed = 0

        for i in range(hdr["hash_table_size"]):
            off = hash_table_start + i * HASH_ENTRY_SIZE
            if not data[off]:
                continue
            entry = parse_hash_entry(data, off)

            # Must be able to read key and value
            key = read_cstring(data, entry["key_offset"])
            value = read_cstring(data, entry["string_offset"])
            assert len(key) > 0
            parsed += 1

        assert parsed == hdr["num_elements"], (
            f"{filename}: parsed {parsed}/{hdr['num_elements']}"
        )
