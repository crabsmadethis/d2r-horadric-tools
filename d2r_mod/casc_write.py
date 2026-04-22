"""CASC writer — BLTE encoder, archive entry builder, and .idx file builder.

Provides the full write pipeline for injecting new content into D2R's CASC:
1. BLTE encoding (blte_encode, make_archive_entry, append_to_archive)
2. .idx file creation (build_idx_file, write_new_idx_files, bucket_index)

.idx file layout (262,144 bytes fixed):
    [0x00] 4B LE: HeaderBlockSize (always 16 for V2)
    [0x04] 4B LE: HeaderBlockHash (hashlittle of 16-byte header, seed=0)
    [0x08] 16B:   V2 header (version, bucket, field sizes, segment size)
    [0x18] 8B:    Padding (zeros)
    [0x20] 4B LE: DataBlockSize (num_entries * 18)
    [0x24] 4B LE: DataBlockHash (hashlittle2 per-entry accumulation)
    [0x28] N*18B: Entries (EKey9 + StorageOffset5BE + EncodedSize4LE)
    [...] Zero-padded to 262,144 bytes total
"""

import glob
import hashlib
import os
import struct
import zlib

from d2r_mod.jenkins import idx_header_hash, idx_data_hash


class CASCWriteError(Exception):
    """Raised when a CASC write operation fails."""


# ---------------------------------------------------------------------------
# BLTE Encoder + Archive Entry Builder
# ---------------------------------------------------------------------------


def blte_encode(data: bytes, compress: bool = True) -> bytes:
    """Encode raw bytes into a single-frame BLTE container.

    Args:
        data: Raw file content to encode.
        compress: If True (default), use zlib compression (0x5A).
                  If False, store uncompressed (0x4E).

    Returns:
        BLTE container bytes: b'BLTE' + 4-byte header_size(0) + mode_byte + payload
    """
    if compress:
        payload = b'Z' + zlib.compress(data)
    else:
        payload = b'N' + data
    # Single-frame BLTE: header_size = 0 (big-endian)
    return b'BLTE' + struct.pack('>I', 0) + payload


def make_archive_entry(blte_data: bytes, ekey_9: bytes) -> bytes:
    """Build a 30-byte archive entry header + BLTE data.

    The 30-byte header format (verified empirically 2026-04-03):
        [0x00] 16B: EKey[:9] zero-padded to 16 bytes, then byte-reversed
        [0x10]  4B LE: EncodedSize = 30 + len(blte_data)
        [0x14]  2B: Padding (0x0000)
        [0x16]  8B: Unknown field (zeros — verified harmless)

    Args:
        blte_data: BLTE-encoded content (output of blte_encode).
        ekey_9: 9-byte truncated EKey (MD5[:9] of blte_data).

    Returns:
        Complete archive entry: 30-byte header + blte_data.

    Raises:
        CASCWriteError: If ekey_9 is not exactly 9 bytes.
    """
    if len(ekey_9) != 9:
        raise CASCWriteError(
            f"ekey_9 must be exactly 9 bytes, got {len(ekey_9)}"
        )

    header_hash = (ekey_9 + b'\x00' * 7)[::-1]  # padded + byte-reversed
    encoded_size = 30 + len(blte_data)

    header = (
        header_hash
        + struct.pack('<I', encoded_size)     # EncodedSize (LE)
        + b'\x00\x00'                         # padding
        + b'\x00' * 8                         # unknown field
    )
    assert len(header) == 30, f"Header must be 30 bytes, got {len(header)}"
    return header + blte_data


def append_to_archive(archive_path: str, entry_bytes: bytes) -> int:
    """Append an archive entry to a data.NNN file.

    Opens the file in append mode, writes the entry, flushes, and fsyncs
    to ensure durability on SD card storage.

    Args:
        archive_path: Path to the data.NNN archive file.
        entry_bytes: Complete entry (30-byte header + BLTE data).

    Returns:
        The byte offset where the entry was written (start of header).

    Raises:
        CASCWriteError: If the archive would exceed 1 GB (30-bit offset limit)
                        or if the write fails.
    """
    OFFSET_LIMIT = 0x3FFFFFFF  # 30-bit max = ~1 GB

    if not os.path.exists(archive_path):
        raise CASCWriteError(f"Archive not found: {archive_path}")

    offset = os.path.getsize(archive_path)

    if offset + len(entry_bytes) > OFFSET_LIMIT:
        raise CASCWriteError(
            f"Archive would exceed 30-bit offset limit: "
            f"current={offset}, entry={len(entry_bytes)}, "
            f"total={offset + len(entry_bytes)} > {OFFSET_LIMIT}"
        )

    with open(archive_path, 'ab') as f:
        written = f.write(entry_bytes)
        if written != len(entry_bytes):
            raise CASCWriteError(
                f"Short write: {written} of {len(entry_bytes)} bytes"
            )
        f.flush()
        os.fsync(f.fileno())

    # Verify: seek back and check BLTE magic at offset + 30
    with open(archive_path, 'rb') as f:
        f.seek(offset + 30)
        magic = f.read(4)
        if magic != b'BLTE':
            raise CASCWriteError(
                f"Post-write verification failed: expected BLTE magic at "
                f"offset {offset + 30}, got {magic!r}"
            )

    return offset


# ---------------------------------------------------------------------------
# .idx File Builder
# ---------------------------------------------------------------------------


# .idx files are always exactly 256 KB
IDX_FILE_SIZE = 262144

# V2 header template (16 bytes) captured from real D2R .idx files.
# All fields are identical across all 16 buckets except byte 2 (BucketIndex).
#
# Byte layout:
#   [0] u16 LE: Version = 7
#   [2] u8:    BucketIndex (0x00-0x0F) — replaced per bucket
#   [3] u8:    ExtraBytes = 0
#   [4] u8:    EncodedSizeLength = 4
#   [5] u8:    StorageOffsetLength = 5
#   [6] u8:    EKeyLength = 9
#   [7] u8:    FileOffsetBits = 30
#   [8] u64 LE: SegmentSize = 0x000000FF_C0000000
_V2_HEADER_TEMPLATE = bytes([
    0x07, 0x00,  # Version 7
    0x00,        # BucketIndex (placeholder — overwritten)
    0x00,        # ExtraBytes
    0x04,        # EncodedSizeLength
    0x05,        # StorageOffsetLength
    0x09,        # EKeyLength
    0x1E,        # FileOffsetBits (30)
    0x00, 0x00, 0x00, 0xC0, 0xFF, 0x00, 0x00, 0x00,  # SegmentSize
])

# Maximum entries that fit in a single .idx file:
# (262144 - 0x28) / 18 = 14561
MAX_ENTRIES_PER_IDX = (IDX_FILE_SIZE - 0x28) // 18

# 30-bit archive offset limit (1 GB)
MAX_ARCHIVE_OFFSET = (1 << 30) - 1


def bucket_index(ekey_9: bytes) -> int:
    """Compute the bucket index for a 9-byte EKey.

    XORs all bytes, then folds the result into a 4-bit value (0-15).
    This matches the CASC bucket assignment convention.

    Args:
        ekey_9: 9-byte truncated EKey (MD5[:9] of BLTE data).

    Returns:
        Bucket index in range [0, 15].
    """
    i = 0
    for b in ekey_9:
        i ^= b
    return (i & 0x0F) ^ (i >> 4)


def build_idx_file(
    bucket: int,
    entries: list[tuple[bytes, int, int, int]],
) -> bytes:
    """Build a complete .idx file for the given bucket.

    Args:
        bucket:  Bucket index (0-15). Must match the intended filename prefix.
        entries: List of (ekey_9, archive_idx, archive_offset, enc_size) tuples.
                 - ekey_9: 9-byte EKey (MD5[:9] of BLTE data)
                 - archive_idx: data.NNN archive number (0-39+)
                 - archive_offset: byte offset within the archive file
                 - enc_size: full encoded size INCLUDING 30-byte header

    Returns:
        Exactly 262,144 bytes — a valid .idx file, zero-padded.

    Raises:
        ValueError: If entries exceed capacity, bucket out of range,
                    or any entry has invalid parameters.
    """
    if not 0 <= bucket <= 15:
        raise ValueError(f"Bucket index must be 0-15, got {bucket}")
    if len(entries) > MAX_ENTRIES_PER_IDX:
        raise ValueError(
            f"Too many entries: {len(entries)} > {MAX_ENTRIES_PER_IDX}"
        )

    # --- Build V2 header (16 bytes) with correct BucketIndex ---
    v2_header = bytearray(_V2_HEADER_TEMPLATE)
    v2_header[2] = bucket
    v2_header = bytes(v2_header)

    # --- Build data block (entries) ---
    data_block = bytearray()
    for ekey_9, archive_idx, archive_offset, enc_size in entries:
        if len(ekey_9) != 9:
            raise ValueError(
                f"EKey must be 9 bytes, got {len(ekey_9)}"
            )
        if archive_offset > MAX_ARCHIVE_OFFSET:
            raise ValueError(
                f"Archive offset 0x{archive_offset:x} exceeds 30-bit limit"
            )
        if archive_idx < 0 or archive_idx > 0x3FF:
            raise ValueError(
                f"Archive index {archive_idx} out of 10-bit range (0-1023)"
            )

        # 9-byte EKey
        data_block.extend(ekey_9)

        # 5-byte BE StorageOffset = (archive_idx << 30) | archive_offset
        storage_offset = (archive_idx << 30) | archive_offset
        data_block.extend(storage_offset.to_bytes(5, "big"))

        # 4-byte LE EncodedSize
        data_block.extend(struct.pack("<I", enc_size))

    data_block = bytes(data_block)
    data_block_size = len(data_block)

    # --- Compute hashes ---
    header_hash = idx_header_hash(v2_header)
    data_hash = idx_data_hash(data_block, entry_length=18) if data_block else 0

    # --- Assemble the full .idx file ---
    buf = bytearray(IDX_FILE_SIZE)  # zero-initialized

    # Header guard block (offset 0x00)
    struct.pack_into("<I", buf, 0x00, 16)            # HeaderBlockSize
    struct.pack_into("<I", buf, 0x04, header_hash)    # HeaderBlockHash
    buf[0x08:0x18] = v2_header                        # V2 header (16 bytes)

    # Padding at 0x18..0x1F is already zeros

    # Data guard block (offset 0x20)
    struct.pack_into("<I", buf, 0x20, data_block_size)  # DataBlockSize
    struct.pack_into("<I", buf, 0x24, data_hash)        # DataBlockHash
    buf[0x28:0x28 + data_block_size] = data_block       # Entry data

    # Rest is already zeros (zero-padded to 262,144 bytes)
    return bytes(buf)


def _read_idx_entries(idx_path: str) -> list[tuple[bytes, int, int, int]]:
    """Read all entries from an existing .idx file.

    Returns:
        List of (ekey_9, archive_idx, archive_offset, enc_size) tuples.
    """
    with open(idx_path, "rb") as f:
        data = f.read()

    if len(data) < 0x28:
        return []

    data_block_size = struct.unpack_from("<I", data, 0x20)[0]
    entry_count = data_block_size // 18
    entries = []

    for i in range(entry_count):
        off = 0x28 + i * 18
        ekey_9 = data[off:off + 9]
        storage_offset = int.from_bytes(data[off + 9:off + 14], "big")
        archive_idx = storage_offset >> 30
        archive_offset = storage_offset & 0x3FFFFFFF
        enc_size = struct.unpack_from("<I", data, off + 14)[0]
        entries.append((ekey_9, archive_idx, archive_offset, enc_size))

    return entries


def write_new_idx_files(
    data_dir: str,
    entries: list[tuple[bytes, int, int, int]],
    backup: bool = True,
) -> list[str]:
    """Create new .idx files that MERGE new entries with existing ones.

    D2R uses "highest version per bucket" — only the .idx with the highest
    suffix for each bucket prefix is loaded. So new files MUST include all
    existing entries from the current highest-version .idx, plus our new ones.

    Groups entries by bucket_index(ekey_9), then for each bucket:
    - Finds the highest existing .idx for that bucket
    - Reads ALL existing entries from it
    - Merges new entries (deduplicating by EKey, new wins)
    - Creates a new file with suffix + 1 containing ALL entries
    - Backs up the old .idx file

    Args:
        data_dir: Path to D2R's data/data directory containing .idx files.
        entries:  List of (ekey_9, archive_idx, archive_offset, enc_size).
        backup:   If True, backup old .idx files before replacing.

    Returns:
        List of absolute paths to created .idx files.

    Raises:
        ValueError: If any entry has invalid parameters.
        OSError: If file creation fails.
    """
    # Group new entries by bucket
    buckets: dict[int, list[tuple[bytes, int, int, int]]] = {}
    for entry in entries:
        ekey_9 = entry[0]
        bi = bucket_index(ekey_9)
        buckets.setdefault(bi, []).append(entry)

    # Find highest existing .idx file per bucket
    existing_idx = sorted(glob.glob(os.path.join(data_dir, "*.idx")))
    max_suffix: dict[int, int] = {}
    max_path: dict[int, str] = {}
    for path in existing_idx:
        fname = os.path.basename(path)
        # Filename format: BBVVVVVVVV.idx (2 hex bucket + 8 hex suffix)
        if len(fname) != 14 or not fname.endswith(".idx"):
            continue
        try:
            file_bucket = int(fname[:2], 16)
            file_suffix = int(fname[2:10], 16)
        except ValueError:
            continue
        if file_bucket not in max_suffix or file_suffix > max_suffix[file_bucket]:
            max_suffix[file_bucket] = file_suffix
            max_path[file_bucket] = path

    created_files = []
    for bi, new_entries in sorted(buckets.items()):
        # Read existing entries from the current highest .idx for this bucket
        existing_entries = []
        if bi in max_path:
            existing_entries = _read_idx_entries(max_path[bi])

        # Merge: existing + new, deduplicate by EKey (new wins)
        merged = {}
        for entry in existing_entries:
            merged[entry[0]] = entry  # key = ekey_9
        for entry in new_entries:
            merged[entry[0]] = entry  # overwrite if exists

        all_entries = list(merged.values())

        if len(all_entries) > MAX_ENTRIES_PER_IDX:
            raise CASCWriteError(
                f"Bucket {bi}: merged entries ({len(all_entries)}) exceed "
                f"max capacity ({MAX_ENTRIES_PER_IDX})"
            )

        # Determine new suffix
        current_max = max_suffix.get(bi, 0)
        new_suffix = current_max + 1

        # Build filename: bucket as 2-char hex, suffix as 8-char hex
        filename = f"{bi:02x}{new_suffix:08x}.idx"
        filepath = os.path.join(data_dir, filename)

        # Backup the old .idx file if requested
        if backup and bi in max_path:
            import shutil
            old_path = max_path[bi]
            shutil.copy2(old_path, old_path + ".pre_inject_bak")

        # Build and write the merged .idx file
        idx_data = build_idx_file(bi, all_entries)

        with open(filepath, "wb") as f:
            f.write(idx_data)
            f.flush()
            os.fsync(f.fileno())

        created_files.append(filepath)

    return created_files


# ---------------------------------------------------------------------------
# Injection Orchestrator
# ---------------------------------------------------------------------------


def _find_writable_archive(data_dir: str) -> tuple[str, int]:
    """Find the highest-numbered data.NNN that is under 1 GB.

    Returns:
        (archive_path, archive_idx)
    """
    archives = sorted(glob.glob(os.path.join(data_dir, "data.*")))
    # Filter to data.NNN (numeric extension)
    valid = []
    for p in archives:
        ext = p.rsplit(".", 1)[-1]
        if ext.isdigit():
            valid.append((p, int(ext)))

    if not valid:
        raise CASCWriteError("No data.NNN archives found")

    # Start from highest, find one under 1 GB
    for path, idx in reversed(valid):
        size = os.path.getsize(path)
        if size < MAX_ARCHIVE_OFFSET:
            return path, idx

    raise CASCWriteError("All archives are at 1 GB limit")


def _update_build_config(
    game_dir: str,
    key: str,
    new_values: list[str],
) -> str:
    """Update a key in the build config and handle Build Key renaming.

    Modifies the build config file, computes its new MD5, renames the file
    to match the new MD5, and updates .build.info.

    Args:
        game_dir: D2R installation directory.
        key: Config key to update (e.g., "vfs-2").
        new_values: New values for the key.

    Returns:
        New build key (MD5 of updated config).
    """
    from d2r_mod.casc import _parse_build_info

    old_build_key = _parse_build_info(game_dir)
    config_dir = os.path.join(game_dir, "data", "config")
    old_path = os.path.join(
        config_dir, old_build_key[:2], old_build_key[2:4], old_build_key,
    )

    # Read and update config
    with open(old_path, "r") as f:
        lines = f.readlines()

    # Keys that reference CDN-only data not available locally.
    # Keeping these causes TACT Error Code 1 on startup.
    _STRIP_KEYS = {"patch-config", "patch", "patch-size", "patch-index",
                   "patch-index-size"}

    new_lines = []
    key_found = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(f"{key} =") or stripped.startswith(f"{key}="):
            new_lines.append(f"{key} = {' '.join(new_values)}\n")
            key_found = True
        elif any(stripped.startswith(f"{sk} =") or stripped.startswith(f"{sk}=")
                 for sk in _STRIP_KEYS):
            continue  # strip CDN-only keys
        else:
            new_lines.append(line)

    if not key_found:
        raise CASCWriteError(
            f"Key '{key}' not found in build config at {old_path}"
        )

    new_content = "".join(new_lines)

    # Compute new Build Key (MD5 of file contents)
    new_build_key = hashlib.md5(new_content.encode("utf-8")).hexdigest()

    # Write new config file at the new path
    new_dir = os.path.join(config_dir, new_build_key[:2], new_build_key[2:4])
    os.makedirs(new_dir, exist_ok=True)
    new_path = os.path.join(new_dir, new_build_key)
    with open(new_path, "w") as f:
        f.write(new_content)
        f.flush()
        os.fsync(f.fileno())

    # Update .build.info
    build_info_path = os.path.join(game_dir, ".build.info")
    with open(build_info_path, "r") as f:
        info_lines = f.readlines()

    # Replace Build Key in the data row (line 2)
    headers = [h.split("!")[0] for h in info_lines[0].strip().split("|")]
    values = info_lines[1].strip().split("|")
    for i, h in enumerate(headers):
        if h == "Build Key":
            values[i] = new_build_key
            break

    info_lines[1] = "|".join(values) + "\n"
    with open(build_info_path, "w") as f:
        f.writelines(info_lines)
        f.flush()
        os.fsync(f.fileno())

    return new_build_key


def inject_files(
    game_dir: str,
    file_map: dict[str, bytes],
) -> dict:
    """Inject files into D2R's CASC archive via per-file ekey hijacking.

    For each virtual_path -> raw_content:
    1. Look up the vanilla ekey from the TVFS CFT entry
    2. BLTE-encode our custom content
    3. Create an archive entry using the VANILLA ekey (so the CASC client
       header check passes) but containing our custom BLTE payload
    4. Add an idx entry: vanilla_ekey -> our archive location

    The TVFS and build config are NOT modified. D2R follows its normal
    resolution chain (vfs-1 -> vfs-2 -> file ekeys) and the idx redirect
    delivers our custom content transparently.

    Args:
        game_dir: D2R installation directory.
        file_map: {virtual_path: raw_file_bytes}

    Returns:
        dict with injection results.
    """
    from d2r_mod.casc import (
        _parse_build_config,
        _build_index,
        _read_blte,
        _parse_tvfs,
    )
    from d2r_mod.casc_tvfs import locate_cft_entries

    data_dir = os.path.join(game_dir, "data", "data")

    # --- Step 0: Read current CASC state ---
    config = _parse_build_config(game_dir)
    index = _build_index(data_dir)

    # Follow vfs-1 -> "data" -> vanilla vfs-2 ekey to find the TVFS
    # that D2R actually uses (not the build config, which may be stale)
    vfs1_ekey9 = bytes.fromhex(config["vfs-1"][1])[:9]
    vfs1_data = _read_blte(data_dir, *index[vfs1_ekey9])
    vfs1_entries = _parse_tvfs(vfs1_data)
    vanilla_vfs2_ekey9 = vfs1_entries.get("data")
    if vanilla_vfs2_ekey9 is None:
        raise CASCWriteError("'data' entry not found in vfs-1")

    # Load vanilla TVFS manifest (read-only — we don't modify it)
    tvfs_data = _read_blte(data_dir, *index[vanilla_vfs2_ekey9])

    # --- Step 1: Locate CFT entries to read vanilla ekeys ---
    target_paths = list(file_map.keys())
    cft_offsets = locate_cft_entries(tvfs_data, target_paths)

    missing = set(p.lower() for p in target_paths) - set(cft_offsets.keys())
    if missing:
        raise CASCWriteError(
            f"Paths not found in TVFS: {', '.join(sorted(missing))}"
        )

    # --- Step 2: Find writable archive ---
    archive_path, archive_idx = _find_writable_archive(data_dir)

    # --- Step 3: For each file, hijack the vanilla ekey ---
    idx_entries = []
    results = []

    for vpath, raw_content in file_map.items():
        # Read vanilla ekey from CFT entry (bytes 0-8)
        cft_off = cft_offsets[vpath.lower()]
        vanilla_ekey9 = bytes(tvfs_data[cft_off:cft_off + 9])

        # BLTE-encode our custom content
        blte = blte_encode(raw_content)

        # Create archive entry with VANILLA ekey but OUR blte payload
        entry = make_archive_entry(blte, vanilla_ekey9)
        offset = append_to_archive(archive_path, entry)
        enc_size = len(entry)

        # idx maps vanilla ekey -> our archive location
        idx_entries.append((vanilla_ekey9, archive_idx, offset, enc_size))
        results.append({
            "path": vpath,
            "ekey": vanilla_ekey9.hex(),
            "archive_idx": archive_idx,
            "offset": offset,
            "enc_size": enc_size,
        })

    # --- Step 4: Write new .idx files ---
    idx_files = write_new_idx_files(data_dir, idx_entries)

    return {
        "injected": results,
        "idx_files": idx_files,
    }
