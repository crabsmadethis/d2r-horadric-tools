"""Jenkins hashlittle / hashlittle2 — Pure Python port of Bob Jenkins' lookup3.c.

Used by Blizzard's CASC V2 .idx files for block hash verification and
computation. This is the standard Jenkins "hashlittle" hash for
little-endian platforms.

References:
  - Original C: http://burtleburtle.net/bob/c/lookup3.c
  - CascLib:    https://github.com/ladislav-zezula/CascLib
  - CascLib uses hashlittle for header blocks (CaptureGuardedBlock1)
    and hashlittle2 entry-by-entry for data blocks (CaptureGuardedBlock2)

Algorithm summary:
  - Internal state: three 32-bit words (a, b, c)
  - Initialized from 0xdeadbeef + length + seed(s)
  - Input consumed in 12-byte chunks via mix()
  - Remaining 1-12 bytes added to (a, b, c) as little-endian
  - final() avalanche produces output in c (and b for hashlittle2)
"""

MASK32 = 0xFFFFFFFF


def _rot(x: int, k: int) -> int:
    """32-bit left rotation."""
    return ((x << k) | (x >> (32 - k))) & MASK32


def _mix(a: int, b: int, c: int) -> tuple[int, int, int]:
    """Jenkins mix — thoroughly mixes three 32-bit values.

    Every bit of (a, b, c) affects every bit of (a, b, c) after mixing.
    """
    a = (a - c) & MASK32; a ^= _rot(c,  4); c = (c + b) & MASK32
    b = (b - a) & MASK32; b ^= _rot(a,  6); a = (a + c) & MASK32
    c = (c - b) & MASK32; c ^= _rot(b,  8); b = (b + a) & MASK32
    a = (a - c) & MASK32; a ^= _rot(c, 16); c = (c + b) & MASK32
    b = (b - a) & MASK32; b ^= _rot(a, 19); a = (a + c) & MASK32
    c = (c - b) & MASK32; c ^= _rot(b,  4); b = (b + a) & MASK32
    return a, b, c


def _final(a: int, b: int, c: int) -> tuple[int, int, int]:
    """Jenkins final — avalanche mixing for the last partial block."""
    c ^= b; c = (c - _rot(b, 14)) & MASK32
    a ^= c; a = (a - _rot(c, 11)) & MASK32
    b ^= a; b = (b - _rot(a, 25)) & MASK32
    c ^= b; c = (c - _rot(b, 16)) & MASK32
    a ^= c; a = (a - _rot(c,  4)) & MASK32
    b ^= a; b = (b - _rot(a, 14)) & MASK32
    c ^= b; c = (c - _rot(b, 24)) & MASK32
    return a, b, c


def _add_le32(k: bytes, i: int, count: int) -> int:
    """Read up to 4 bytes from k[i:] as little-endian uint32, zero-padded."""
    val = 0
    for j in range(min(count, 4)):
        val |= k[i + j] << (8 * j)
    return val


def hashlittle(key: bytes, initval: int = 0) -> int:
    """Jenkins hashlittle — returns a single 32-bit hash.

    This is the standard Jenkins one-at-a-time hash for little-endian
    platforms, processing input as a byte stream.

    Args:
        key:     Bytes to hash.
        initval: 32-bit seed value (default 0).

    Returns:
        32-bit hash value (unsigned).
    """
    length = len(key)
    a = b = c = (0xdeadbeef + length + initval) & MASK32

    i = 0
    while length > 12:
        a = (a + key[i+0] + (key[i+1] << 8) + (key[i+2] << 16) + (key[i+3] << 24)) & MASK32
        b = (b + key[i+4] + (key[i+5] << 8) + (key[i+6] << 16) + (key[i+7] << 24)) & MASK32
        c = (c + key[i+8] + (key[i+9] << 8) + (key[i+10] << 16) + (key[i+11] << 24)) & MASK32
        a, b, c = _mix(a, b, c)
        length -= 12
        i += 12

    # Handle remaining 1-12 bytes (switch-fallthrough from C)
    if length >= 12: c = (c + (key[i+11] << 24)) & MASK32
    if length >= 11: c = (c + (key[i+10] << 16)) & MASK32
    if length >= 10: c = (c + (key[i+9]  <<  8)) & MASK32
    if length >=  9: c = (c + key[i+8]) & MASK32
    if length >=  8: b = (b + (key[i+7]  << 24)) & MASK32
    if length >=  7: b = (b + (key[i+6]  << 16)) & MASK32
    if length >=  6: b = (b + (key[i+5]  <<  8)) & MASK32
    if length >=  5: b = (b + key[i+4]) & MASK32
    if length >=  4: a = (a + (key[i+3]  << 24)) & MASK32
    if length >=  3: a = (a + (key[i+2]  << 16)) & MASK32
    if length >=  2: a = (a + (key[i+1]  <<  8)) & MASK32
    if length >=  1: a = (a + key[i+0]) & MASK32
    if length == 0:
        return c

    a, b, c = _final(a, b, c)
    return c


def hashlittle2(key: bytes, pc: int = 0, pb: int = 0) -> tuple[int, int]:
    """Jenkins hashlittle2 — returns two 32-bit hashes.

    Identical to hashlittle except it takes two seeds and returns two
    hash values, giving 64 bits of output for the price of one pass.

    Args:
        key: Bytes to hash.
        pc:  Primary seed / receives primary hash (better mixed).
        pb:  Secondary seed / receives secondary hash.

    Returns:
        (pc, pb) — two 32-bit hash values (unsigned).
    """
    length = len(key)
    a = b = c = (0xdeadbeef + length + pc) & MASK32
    c = (c + pb) & MASK32

    i = 0
    while length > 12:
        a = (a + key[i+0] + (key[i+1] << 8) + (key[i+2] << 16) + (key[i+3] << 24)) & MASK32
        b = (b + key[i+4] + (key[i+5] << 8) + (key[i+6] << 16) + (key[i+7] << 24)) & MASK32
        c = (c + key[i+8] + (key[i+9] << 8) + (key[i+10] << 16) + (key[i+11] << 24)) & MASK32
        a, b, c = _mix(a, b, c)
        length -= 12
        i += 12

    # Handle remaining 1-12 bytes
    if length >= 12: c = (c + (key[i+11] << 24)) & MASK32
    if length >= 11: c = (c + (key[i+10] << 16)) & MASK32
    if length >= 10: c = (c + (key[i+9]  <<  8)) & MASK32
    if length >=  9: c = (c + key[i+8]) & MASK32
    if length >=  8: b = (b + (key[i+7]  << 24)) & MASK32
    if length >=  7: b = (b + (key[i+6]  << 16)) & MASK32
    if length >=  6: b = (b + (key[i+5]  <<  8)) & MASK32
    if length >=  5: b = (b + key[i+4]) & MASK32
    if length >=  4: a = (a + (key[i+3]  << 24)) & MASK32
    if length >=  3: a = (a + (key[i+2]  << 16)) & MASK32
    if length >=  2: a = (a + (key[i+1]  <<  8)) & MASK32
    if length >=  1: a = (a + key[i+0]) & MASK32
    if length == 0:
        return c, b

    a, b, c = _final(a, b, c)
    return c, b


# === CASC V2 .idx block hash functions ===
#
# A V2 .idx file has two "guarded blocks," each prefixed by an 8-byte
# FILE_INDEX_GUARDED_BLOCK struct:
#
#   [0x00] u32 LE: BlockSize    (size of content following this header)
#   [0x04] u32 LE: BlockHash    (hash of content bytes)
#
# Block 1: Header (offset 0x00)
#   Content: 16-byte FILE_INDEX_HEADER_V2 at offset 0x08
#   Hash:    hashlittle(content, size, 0)           — CaptureGuardedBlock1
#
# Block 2: Data entries (offset 0x20)
#   Content: N entries of (EKey + StorageOffset + EncodedSize) at offset 0x28
#   Hash:    hashlittle2 called per-entry with running state — CaptureGuardedBlock2
#            (HashHigh=0, HashLow=0 initially; HashHigh compared to BlockHash)


def idx_header_hash(header_bytes: bytes) -> int:
    """Compute the HeaderBlockHash for a V2 .idx file.

    CascLib's CaptureGuardedBlock1: hashlittle(data, size, 0).

    Args:
        header_bytes: The 16-byte V2 header content (offset 0x08..0x17).

    Returns:
        32-bit hash matching the value stored at offset 0x04.
    """
    return hashlittle(header_bytes, initval=0)


def idx_data_hash(data_block: bytes, entry_length: int = 18) -> int:
    """Compute the DataBlockHash for a V2 .idx file.

    CascLib's CaptureGuardedBlock2 "Blizzard Downloader" method:
    hashlittle2 called once per entry with accumulating (pc, pb) state.
    The primary hash (pc = HashHigh) is compared to the stored BlockHash.

    Args:
        data_block:   Entry bytes (offset 0x28 to 0x28 + DataBlockLength).
        entry_length: Bytes per entry (default 18 for D2R: 9 EKey + 5 offset + 4 size).

    Returns:
        32-bit hash matching the value stored at offset 0x24.
    """
    entry_count = len(data_block) // entry_length
    pc = 0  # HashHigh
    pb = 0  # HashLow

    for i in range(entry_count):
        start = i * entry_length
        entry = data_block[start:start + entry_length]
        pc, pb = hashlittle2(entry, pc=pc, pb=pb)

    return pc
