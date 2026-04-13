"""TVFS CFT locator and patcher for CASC writer.

Walks the TVFS path table to locate CFT entries by virtual path,
and patches CFT entries in-place (first 13 bytes: 9 EKey + 4 BE EncodedSize).

Does NOT modify casc.py. Uses the same TVFS parsing algorithm but returns
CFT byte offsets instead of EKey values.
"""

import struct
import sys

# TVFS tree can be 21 levels deep with many siblings
sys.setrecursionlimit(5000)


def locate_cft_entries(
    tvfs_data: bytes, target_paths: list[str]
) -> dict[str, int]:
    """Walk the TVFS path table and return CFT offsets for requested paths.

    Args:
        tvfs_data: Raw TVFS manifest bytes (starts with b"TVFS").
        target_paths: List of virtual paths to locate. Normalized to
            lowercase internally (TVFS uses LOWERCASE_MANIFEST).

    Returns:
        {lowercase_path: absolute_byte_offset_in_tvfs_data} for each
        found path. Missing paths are silently excluded.
    """
    if tvfs_data[:4] != b"TVFS":
        raise ValueError("Not a TVFS block")

    # Build lookup set (lowercase)
    targets = {p.lower() for p in target_paths}
    if not targets:
        return {}

    ekey_size = tvfs_data[6]
    path_table_offset = struct.unpack_from(">I", tvfs_data, 0x0C)[0]
    path_table_size = struct.unpack_from(">I", tvfs_data, 0x10)[0]
    vfs_table_offset = struct.unpack_from(">I", tvfs_data, 0x14)[0]
    cft_table_offset = struct.unpack_from(">I", tvfs_data, 0x1C)[0]
    cft_table_size = struct.unpack_from(">I", tvfs_data, 0x20)[0]

    # Compute CFT offset size (how many bytes encode a CFT table index)
    if cft_table_size <= 0xFF:
        cft_offs_size = 1
    elif cft_table_size <= 0xFFFF:
        cft_offs_size = 2
    elif cft_table_size <= 0xFFFFFF:
        cft_offs_size = 3
    else:
        cft_offs_size = 4

    FOLDER_BIT = 0x80000000
    result = {}

    def walk_path_table(start: int, end: int, prefix: str):
        ptr = start
        while ptr < end:
            # Early exit: found all targets
            if len(result) == len(targets):
                return

            # Optional pre-separator
            has_pre_sep = False
            if ptr < end and tvfs_data[ptr] == 0x00:
                has_pre_sep = True
                ptr += 1

            if ptr >= end:
                break

            # Name segment
            name = ""
            if tvfs_data[ptr] != 0xFF:
                name_len = tvfs_data[ptr]
                ptr += 1
                if name_len > 0:
                    name = tvfs_data[ptr:ptr + name_len].decode(
                        "ascii", errors="replace"
                    )
                    ptr += name_len

            # Build path
            if has_pre_sep and prefix and not prefix.endswith("/"):
                full_path = prefix + "/" + name
            else:
                full_path = prefix + name

            # Optional post-separator
            if ptr < end and tvfs_data[ptr] == 0x00:
                full_path += "/"
                ptr += 1

            # Node value
            if ptr < end and tvfs_data[ptr] == 0xFF:
                ptr += 1
                node_value = struct.unpack_from(">I", tvfs_data, ptr)[0]
                ptr += 4

                if node_value & FOLDER_BIT:
                    # Directory: recurse into children
                    child_data_len = (node_value & 0x7FFFFFFF) - 4
                    child_end = ptr + child_data_len
                    walk_path_table(ptr, min(child_end, end), full_path)
                    ptr = child_end
                else:
                    # File: node_value = VFS table offset
                    vfs_off = node_value
                    abs_vfs = vfs_table_offset + vfs_off
                    if abs_vfs < len(tvfs_data):
                        span_count = tvfs_data[abs_vfs]
                        if 1 <= span_count <= 224:
                            span_start = abs_vfs + 1
                            # Read first span's CFT offset
                            cft_off_raw = tvfs_data[
                                span_start + 8:
                                span_start + 8 + cft_offs_size
                            ]
                            cft_off = int.from_bytes(cft_off_raw, "big")
                            abs_cft = cft_table_offset + cft_off

                            if abs_cft + ekey_size <= len(tvfs_data):
                                clean_path = full_path.strip("/")
                                if clean_path in targets:
                                    result[clean_path] = abs_cft

    walk_path_table(
        path_table_offset,
        path_table_offset + path_table_size,
        "",
    )
    return result


def patch_cft_entry(
    tvfs_data: bytearray,
    cft_offset: int,
    new_ekey: bytes,
    encoded_size: int,
    content_size: int,
    new_ckey: bytes,
) -> None:
    """Overwrite a CFT entry in-place.

    CFT entry layout (35 bytes, verified empirically 2026-04-03):
        bytes 0-8:   EKey (9 bytes, MD5[:9] of BLTE data)
        bytes 9-12:  EncodedSize (4 bytes BE, BLTE size without 30-byte header)
        bytes 13-17: ContentSize (5 bytes BE, decompressed file size)
        bytes 18-33: CKey (16 bytes, full MD5 of decompressed content)
        byte  34:    Padding (0x00, untouched)

    D2R validates CKey against decompressed content. If CKey doesn't match,
    the file is silently ignored and the original is used instead.

    Args:
        tvfs_data: Mutable TVFS data (bytearray).
        cft_offset: Absolute byte offset of the CFT entry in tvfs_data.
        new_ekey: 9-byte EKey (MD5[:9] of the new BLTE data).
        encoded_size: BLTE container size (excluding 30-byte archive header).
        content_size: Decompressed file size in bytes.
        new_ckey: Full 16-byte MD5 of the decompressed content.
    """
    if len(new_ekey) != 9:
        raise ValueError(f"EKey must be 9 bytes, got {len(new_ekey)}")
    if len(new_ckey) != 16:
        raise ValueError(f"CKey must be 16 bytes, got {len(new_ckey)}")
    if not isinstance(tvfs_data, bytearray):
        raise TypeError("tvfs_data must be a bytearray")

    # Write 9-byte EKey
    tvfs_data[cft_offset:cft_offset + 9] = new_ekey
    # Write 4-byte BE EncodedSize
    struct.pack_into(">I", tvfs_data, cft_offset + 9, encoded_size)
    # Write 5-byte BE ContentSize
    tvfs_data[cft_offset + 13:cft_offset + 18] = content_size.to_bytes(5, "big")
    # Write 16-byte CKey (full MD5 of decompressed content)
    tvfs_data[cft_offset + 18:cft_offset + 34] = new_ckey
