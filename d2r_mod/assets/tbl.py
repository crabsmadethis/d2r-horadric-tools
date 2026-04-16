"""
D2R .tbl string table parser.

Binary format (confirmed against vanilla D2R files):

  HEADER (21 bytes):
    0x00  uint16 LE  CRC
    0x02  uint16 LE  NumElements
    0x04  uint32 LE  HashTableSize
    0x08  uint8      Version (always 1)
    0x09  uint32 LE  StringDataStart (absolute file offset)
    0x0D  uint32 LE  LoopCount
    0x11  uint32 LE  FileSize

  INDEX TABLE (NumElements * 2 bytes):
    Starts at offset 21. uint16 LE entries pointing to hash table slots.

  HASH TABLE (HashTableSize * 17-byte entries):
    Starts at offset 21 + NumElements * 2.
    +0   uint8    used (0=empty, 1=occupied)
    +1   uint16   index
    +3   uint32   hash_value
    +7   uint32   key_offset   (ABSOLUTE file offset)
    +11  uint32   string_offset (ABSOLUTE file offset)
    +15  uint16   string_length (includes null terminator)

  STRING DATA:
    key\\0value\\0 pairs. All offsets are ABSOLUTE.
"""

import os
import struct

# ── Public constants ──────────────────────────────────────────────────────────

_HEADER_SIZE = 21
_HASH_ENTRY_SIZE = 17
_HAS_INDEX_TABLE = True


def _hash_table_start(num_elements: int) -> int:
    """Return the file offset where the hash table begins."""
    return _HEADER_SIZE + num_elements * 2


def _elf_hash(key: str) -> int:
    """Compute ELF hash for a .tbl key (case-sensitive).

    Verified 100% match against stored hash_value % HashTableSize across
    all three vanilla D2R .tbl files (string.tbl, expansionstring.tbl,
    patchstring.tbl, 9425 total entries).

    The stored hash_value field holds elf_hash(key) % HashTableSize (the
    original home bucket), NOT the raw 32-bit hash value.
    """
    h = 0
    for ch in key:
        h = (h << 4) + ord(ch)
        high = h & 0xF0000000
        if high:
            h ^= high >> 24
        h &= ~high
    return h & 0xFFFFFFFF


# ── Parser ────────────────────────────────────────────────────────────────────

def parse_tbl(data: bytes) -> dict[str, str]:
    """Parse .tbl binary data into a {key: value} dict.

    All strings are decoded as Latin-1. The dict is ordered by insertion
    order (index table order), matching the original file ordering.
    """
    if len(data) < _HEADER_SIZE:
        raise ValueError(f"Data too short for .tbl header: {len(data)} bytes")

    # Parse header
    num_elements = struct.unpack_from("<H", data, 0x02)[0]
    hash_table_size = struct.unpack_from("<I", data, 0x04)[0]
    str_data_start = struct.unpack_from("<I", data, 0x09)[0]

    ht_start = _hash_table_start(num_elements)

    # Structural invariant: hash table must end exactly where string data begins
    assert ht_start + hash_table_size * _HASH_ENTRY_SIZE == str_data_start, (
        f"Layout mismatch: hash_table_start={ht_start} + "
        f"hash_table_size={hash_table_size} * {_HASH_ENTRY_SIZE} = "
        f"{ht_start + hash_table_size * _HASH_ENTRY_SIZE} "
        f"!= str_data_start={str_data_start}"
    )

    # Iterate hash table in index-table order for deterministic output.
    # Build a list of (index, hash_slot_offset) pairs sorted by index value.
    entries: list[tuple[int, int]] = []  # (index_table_pos, hash_entry_offset)
    for slot in range(hash_table_size):
        off = ht_start + slot * _HASH_ENTRY_SIZE
        if not data[off]:  # used == 0 → empty slot
            continue
        idx = struct.unpack_from("<H", data, off + 1)[0]
        entries.append((idx, off))

    # Sort by index table position to preserve insertion order
    entries.sort(key=lambda x: x[0])

    result: dict[str, str] = {}
    for _idx, off in entries:
        key_offset = struct.unpack_from("<I", data, off + 7)[0]
        str_offset = struct.unpack_from("<I", data, off + 11)[0]
        str_length = struct.unpack_from("<H", data, off + 15)[0]

        # Read null-terminated key
        key_end = data.index(0, key_offset)
        key = data[key_offset:key_end].decode("latin-1")

        # Read value; string_length includes the null terminator
        value = data[str_offset:str_offset + str_length - 1].decode("latin-1")

        result[key] = value

    return result


# ── Helpers ──────────────────────────────────────────────────────────────────

def _next_prime(n: int) -> int:
    """Return the smallest prime >= n."""
    if n <= 2:
        return 2
    # Make candidate odd if even
    candidate = n if n % 2 != 0 else n + 1
    while True:
        if _is_prime(candidate):
            return candidate
        candidate += 2


def _is_prime(n: int) -> bool:
    """Simple primality test."""
    if n < 2:
        return False
    if n < 4:
        return True
    if n % 2 == 0 or n % 3 == 0:
        return False
    i = 5
    while i * i <= n:
        if n % i == 0 or n % (i + 2) == 0:
            return False
        i += 6
    return True


# ── Builder ──────────────────────────────────────────────────────────────────

def build_tbl(entries: dict[str, str]) -> bytes:
    """Build a .tbl binary from a {key: value} dict.

    All strings are encoded as Latin-1. The result round-trips through
    parse_tbl: ``parse_tbl(build_tbl(d)) == d``.
    """
    num_entries = len(entries)

    # Hash table sizing
    if num_entries == 0:
        hash_table_size = 1
    else:
        hash_table_size = _next_prime(max(int(num_entries * 1.5), 1))

    # Compute layout offsets
    str_data_start = _HEADER_SIZE + num_entries * 2 + hash_table_size * _HASH_ENTRY_SIZE

    # Build string data blob and record offsets
    str_blob = bytearray()
    # Each entry: (key_rel_offset, value_rel_offset, value_encoded_len_with_null)
    entry_info: list[tuple[str, int, int, int]] = []  # (key, key_abs, val_abs, val_len_with_null)

    for key, value in entries.items():
        key_bytes = key.encode("latin-1")
        value_bytes = value.encode("latin-1")

        key_rel = len(str_blob)
        str_blob.extend(key_bytes)
        str_blob.append(0)  # null terminator for key

        val_rel = len(str_blob)
        str_blob.extend(value_bytes)
        str_blob.append(0)  # null terminator for value

        key_abs = str_data_start + key_rel
        val_abs = str_data_start + val_rel
        val_len_with_null = len(value_bytes) + 1  # includes null

        entry_info.append((key, key_abs, val_abs, val_len_with_null))

    # Build hash table (linear probing)
    hash_table = bytearray(hash_table_size * _HASH_ENTRY_SIZE)  # all zeroes = all empty

    for idx, (key, key_abs, val_abs, val_len) in enumerate(entry_info):
        bucket = _elf_hash(key) % hash_table_size
        slot = bucket
        while True:
            off = slot * _HASH_ENTRY_SIZE
            if hash_table[off] == 0:  # empty slot
                break
            slot = (slot + 1) % hash_table_size
        off = slot * _HASH_ENTRY_SIZE
        hash_table[off] = 1  # used
        struct.pack_into("<H", hash_table, off + 1, idx)         # index
        struct.pack_into("<I", hash_table, off + 3, bucket)      # hash_value (original bucket)
        struct.pack_into("<I", hash_table, off + 7, key_abs)     # key_offset (ABSOLUTE)
        struct.pack_into("<I", hash_table, off + 11, val_abs)    # string_offset (ABSOLUTE)
        struct.pack_into("<H", hash_table, off + 15, val_len)    # string_length (incl null)

    # Build index table: sequential uint16 values (0, 1, 2, ...)
    index_table = bytearray(num_entries * 2)
    for i in range(num_entries):
        struct.pack_into("<H", index_table, i * 2, i)

    # Compute file size
    file_size = _HEADER_SIZE + len(index_table) + len(hash_table) + len(str_blob)

    # Build header (21 bytes)
    header = bytearray(_HEADER_SIZE)
    struct.pack_into("<H", header, 0x00, 0)                  # CRC = 0
    struct.pack_into("<H", header, 0x02, num_entries)         # NumElements
    struct.pack_into("<I", header, 0x04, hash_table_size)     # HashTableSize
    struct.pack_into("<B", header, 0x08, 1)                   # Version = 1
    struct.pack_into("<I", header, 0x09, str_data_start)      # StringDataStart
    struct.pack_into("<I", header, 0x0D, num_entries)         # LoopCount = NumElements
    struct.pack_into("<I", header, 0x11, file_size)           # FileSize

    return bytes(header + index_table + hash_table + str_blob)


# ── Patcher ──────────────────────────────────────────────────────────────────

def patch_tbl(base_path: str, overrides: dict[str, str], out_path: str) -> None:
    """Read a .tbl file, merge overrides, and write a new .tbl to out_path.

    Existing keys in overrides are replaced; new keys are added.
    """
    with open(base_path, "rb") as f:
        data = f.read()
    entries = parse_tbl(data)
    entries.update(overrides)
    result = build_tbl(entries)
    with open(out_path, "wb") as f:
        f.write(result)
