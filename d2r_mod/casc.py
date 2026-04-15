"""Pure Python CASC reader for D2R. Extracts moddable files to vanilla/."""

import glob
import os
import struct
import sys
import zlib

# TVFS tree can be 21 levels deep with many siblings
sys.setrecursionlimit(5000)


from d2r_mod.build import DEFAULT_GAME_DIR

# TVFS uses LOWERCASE_MANIFEST; restore original D2R casing for pipeline compat
_FILENAME_CASING = {
    "uniqueitems.txt": "UniqueItems.txt",
    "setitems.txt": "SetItems.txt",
    "skills.txt": "Skills.txt",
    "runes.txt": "Runes.txt",
    "weapons.txt": "Weapons.txt",
    "armor.txt": "Armor.txt",
    "misc.txt": "Misc.txt",
    "itemstatcost.txt": "ItemStatCost.txt",
    "monstats.txt": "MonStats.txt",
    "treasureclassex.txt": "TreasureClassEx.txt",
    "levels.txt": "Levels.txt",
    "experience.txt": "Experience.txt",
    "properties.txt": "Properties.txt",
    "missiles.txt": "Missiles.txt",
    "difficultylevels.txt": "DifficultyLevels.txt",
    "charstats.txt": "CharStats.txt",
    "hireling.txt": "Hireling.txt",
    "monstats2.txt": "MonStats2.txt",
    "itemtypes.txt": "ItemTypes.txt",
    "gems.txt": "Gems.txt",
    "cubemain.txt": "CubeMain.txt",
    "magicprefix.txt": "MagicPrefix.txt",
    "magicsuffix.txt": "MagicSuffix.txt",
    "automagic.txt": "AutoMagic.txt",
    "superuniques.txt": "SuperUniques.txt",
    "monprop.txt": "MonProp.txt",
    "montype.txt": "MonType.txt",
    "monai.txt": "MonAI.txt",
    "npc.txt": "NPC.txt",
    "objmode.txt": "ObjMode.txt",
    "overlay.txt": "Overlay.txt",
    "pettype.txt": "PetType.txt",
    "playerclass.txt": "PlayerClass.txt",
    "plrmode.txt": "PlrMode.txt",
    "skilldesc.txt": "SkillDesc.txt",
    "states.txt": "States.txt",
    "sets.txt": "Sets.txt",
    "setitems.txt": "SetItems.txt",
    "wanderingmon.txt": "WanderingMon.txt",
    "monseq.txt": "MonSeq.txt",
    "monsounds.txt": "MonSounds.txt",
    "monumod.txt": "MonUMod.txt",
    "soundenviron.txt": "SoundEnviron.txt",
    "sounds.txt": "Sounds.txt",
    "objects.txt": "Objects.txt",
    "objgroup.txt": "ObjGroup.txt",
    "objpreset.txt": "ObjPreset.txt",
    "objtype.txt": "ObjType.txt",
    "shrines.txt": "Shrines.txt",
    "belts.txt": "Belts.txt",
    "gamble.txt": "Gamble.txt",
    "colors.txt": "Colors.txt",
    "compcode.txt": "CompCode.txt",
    "composit.txt": "Composit.txt",
    "elemtypes.txt": "ElemTypes.txt",
    "events.txt": "Events.txt",
    "bodylocs.txt": "BodyLocs.txt",
    "storepage.txt": "StorePage.txt",
    "inventory.txt": "Inventory.txt",
    "lowqualityitems.txt": "LowQualityItems.txt",
    "rareprefix.txt": "RarePrefix.txt",
    "raresuffix.txt": "RareSuffix.txt",
    "qualityitems.txt": "QualityItems.txt",
    "books.txt": "Books.txt",
    "monplace.txt": "MonPlace.txt",
    "lvlmaze.txt": "LvlMaze.txt",
    "lvlprest.txt": "LvlPrest.txt",
    "lvlsub.txt": "LvlSub.txt",
    "lvltypes.txt": "LvlTypes.txt",
    "lvlwarp.txt": "LvlWarp.txt",
}


def _parse_build_info(game_dir: str) -> str:
    """Read .build.info and return the build key (hex hash)."""
    path = os.path.join(game_dir, ".build.info")
    with open(path, "r") as f:
        lines = f.read().strip().split("\n")
    # Header line: "Branch!STRING:0|Active!DEC:1|Build Key!HEX:16"
    headers = [h.split("!")[0] for h in lines[0].split("|")]
    values = lines[1].split("|")
    for h, v in zip(headers, values):
        if h == "Build Key":
            return v.strip()
    raise ValueError(f"Build Key not found in {path}")


def _parse_build_config(game_dir: str) -> dict[str, list[str]]:
    """Read the build config file. Returns {key: [values]}."""
    build_key = _parse_build_info(game_dir)
    config_path = os.path.join(
        game_dir, "data", "config",
        build_key[:2], build_key[2:4], build_key,
    )
    result = {}
    with open(config_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, val = line.partition("=")
            result[key.strip()] = val.strip().split()
    return result


def _build_index(data_dir: str) -> dict[bytes, tuple[int, int, int]]:
    """Parse all .idx files. Returns {ekey_9: (archive_idx, offset, enc_size)}."""
    index = {}
    idx_files = sorted(glob.glob(os.path.join(data_dir, "*.idx")))
    for idx_path in idx_files:
        with open(idx_path, "rb") as f:
            data = f.read()
        if len(data) < 0x28:
            continue
        # Data block starts at 0x20
        data_block_len = struct.unpack_from("<I", data, 0x20)[0]
        entries_start = 0x28
        entry_size = 18  # 9 (ekey) + 5 (offset) + 4 (size)
        num_entries = data_block_len // entry_size
        for i in range(num_entries):
            off = entries_start + i * entry_size
            if off + entry_size > len(data):
                break
            ekey = data[off:off + 9]
            storage_offset = int.from_bytes(data[off + 9:off + 14], "big")
            enc_size = struct.unpack_from("<I", data, off + 14)[0]
            archive_idx = storage_offset >> 30
            archive_offset = storage_offset & 0x3FFFFFFF
            # Only keep if not already present (first seen wins)
            if ekey not in index:
                index[ekey] = (archive_idx, archive_offset, enc_size)
    return index


def _decompress_blte(data: bytes) -> bytes:
    """Decompress a BLTE container. Input starts at BLTE magic."""
    if data[:4] != b"BLTE":
        raise ValueError("Not a BLTE block")

    header_size = struct.unpack_from(">I", data, 4)[0]

    if header_size == 0:
        # Single frame
        if len(data) < 9:
            raise ValueError("BLTE block too short")
        enc = data[8]
        payload = data[9:]
        if enc == 0x4E:  # N = uncompressed
            return payload
        elif enc == 0x5A:  # Z = zlib
            return zlib.decompress(payload)
        else:
            raise ValueError(f"Unknown BLTE encoding: 0x{enc:02x}")

    # Multi-frame
    table_start = 8
    chunk_count = struct.unpack_from(">I", data, table_start)[0] & 0x00FFFFFF
    entries_start = table_start + 4
    # Chunk data starts right after the chunk table entries
    chunks_data_start = entries_start + chunk_count * 24

    result = bytearray()
    pos = chunks_data_start
    for i in range(chunk_count):
        entry_off = entries_start + i * 24
        comp_size = struct.unpack_from(">I", data, entry_off)[0]
        pos_end = pos + comp_size
        if pos_end > len(data):
            raise ValueError(f"BLTE frame {i} extends beyond data")
        enc = data[pos]
        payload = data[pos + 1:pos_end]
        if enc == 0x4E:  # N
            result.extend(payload)
        elif enc == 0x5A:  # Z
            result.extend(zlib.decompress(payload))
        elif enc == 0x45:  # E = encrypted, skip
            pass
        else:
            raise ValueError(f"Unknown BLTE encoding: 0x{enc:02x}")
        pos = pos_end

    return bytes(result)


def _read_blte(data_dir: str, archive_idx: int, offset: int, enc_size: int) -> bytes:
    """Read and decompress a BLTE block from a data archive file."""
    archive_path = os.path.join(data_dir, f"data.{archive_idx:03d}")
    with open(archive_path, "rb") as f:
        # Skip the 30-byte entry header to reach BLTE magic
        f.seek(offset + 30)
        blte_data = f.read(enc_size - 30)
    return _decompress_blte(blte_data)


def _parse_tvfs(data: bytes) -> dict[str, bytes]:
    """Parse a TVFS manifest. Returns {path: ekey_9_bytes}."""
    if data[:4] != b"TVFS":
        raise ValueError("Not a TVFS block")

    ekey_size = data[6]
    flags = struct.unpack_from(">I", data, 8)[0]
    path_table_offset = struct.unpack_from(">I", data, 0x0C)[0]
    path_table_size = struct.unpack_from(">I", data, 0x10)[0]
    vfs_table_offset = struct.unpack_from(">I", data, 0x14)[0]
    cft_table_offset = struct.unpack_from(">I", data, 0x1C)[0]
    cft_table_size = struct.unpack_from(">I", data, 0x20)[0]

    # Compute CFT offset size
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
            # Optional pre-separator
            has_pre_sep = False
            if ptr < end and data[ptr] == 0x00:
                has_pre_sep = True
                ptr += 1

            if ptr >= end:
                break

            # Check for node value marker (0xFF) before name
            # In the TVFS format, 0xFF can appear directly without a name
            name = ""
            if data[ptr] != 0xFF:
                # Name length + name
                name_len = data[ptr]
                ptr += 1
                if name_len > 0:
                    name = data[ptr:ptr + name_len].decode(
                        "ascii", errors="replace"
                    )
                    ptr += name_len

            # Build path
            if has_pre_sep and prefix and not prefix.endswith("/"):
                full_path = prefix + "/" + name
            else:
                full_path = prefix + name

            # Optional post-separator
            if ptr < end and data[ptr] == 0x00:
                full_path += "/"
                ptr += 1

            # Node value (required if 0xFF marker present)
            if ptr < end and data[ptr] == 0xFF:
                ptr += 1
                node_value = struct.unpack_from(">I", data, ptr)[0]
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
                    if abs_vfs < len(data):
                        span_count = data[abs_vfs]
                        if span_count >= 1 and span_count <= 224:
                            span_start = abs_vfs + 1
                            # Read first span's CFT offset
                            cft_off_raw = data[
                                span_start + 8:
                                span_start + 8 + cft_offs_size
                            ]
                            cft_off = int.from_bytes(cft_off_raw, "big")
                            abs_cft = cft_table_offset + cft_off
                            if abs_cft + ekey_size <= len(data):
                                ekey = data[abs_cft:abs_cft + ekey_size]
                                # Strip trailing slashes from path
                                clean_path = full_path.strip("/")
                                if clean_path:
                                    result[clean_path] = ekey

    walk_path_table(
        path_table_offset,
        path_table_offset + path_table_size,
        "",
    )
    return result


def _restore_casing(path: str) -> str:
    """Restore original D2R filename casing for a TVFS path."""
    dirname = os.path.dirname(path)
    basename = os.path.basename(path)
    restored = _FILENAME_CASING.get(basename.lower(), basename)
    return os.path.join(dirname, restored) if dirname else restored


def extract_vanilla(
    game_dir: str = DEFAULT_GAME_DIR,
    output_dir: str = "vanilla",
    extensions: set[str] | None = {".txt", ".tbl", ".json"},
    prefix_filter: set[str] | None = {
        "data/global/excel/", "data/global/string/", "data/global/ui/",
    },
    verbose: bool = True,
) -> dict[str, str]:
    """Extract moddable files from CASC archive.

    Returns {relative_path: absolute_output_path} for extracted files.
    """
    data_dir = os.path.join(game_dir, "data", "data")

    # Step 1: Parse build config
    if verbose:
        print("Reading build config...")
    config = _parse_build_config(game_dir)

    # Step 2: Build index from all .idx files
    if verbose:
        print("Building index from .idx files...")
    index = _build_index(data_dir)
    if verbose:
        print(f"  {len(index)} entries indexed")

    # Step 3: Load vfs-2 TVFS manifest
    # Config line: "vfs-2 = CKey EKey" — second hash is the EKey
    vfs2_ekey_hex = config["vfs-2"][1]
    vfs2_ekey9 = bytes.fromhex(vfs2_ekey_hex)[:9]

    if vfs2_ekey9 not in index:
        raise ValueError(f"vfs-2 EKey {vfs2_ekey_hex} not found in index")

    archive_idx, offset, enc_size = index[vfs2_ekey9]
    if verbose:
        print(f"Loading vfs-2 from data.{archive_idx:03d} @ 0x{offset:x}...")
    vfs2_data = _read_blte(data_dir, archive_idx, offset, enc_size)
    if verbose:
        print(f"  vfs-2: {len(vfs2_data)} bytes decompressed")

    # Step 4: Parse TVFS tree
    if verbose:
        print("Parsing TVFS path table...")
    file_map = _parse_tvfs(vfs2_data)
    if verbose:
        print(f"  {len(file_map)} files in manifest")

    # Step 5: Filter and extract
    extracted = {}
    skipped = 0
    errors = 0

    for tvfs_path, ekey in sorted(file_map.items()):
        # Extension filter
        if extensions:
            ext = os.path.splitext(tvfs_path)[1].lower()
            if ext not in extensions:
                continue

        # Prefix filter
        if prefix_filter:
            if not any(tvfs_path.startswith(p) for p in prefix_filter):
                continue

        # Restore casing
        out_path = _restore_casing(tvfs_path)

        # Look up in index
        if ekey not in index:
            if verbose:
                print(f"  SKIP {tvfs_path}: EKey not in index")
            skipped += 1
            continue

        a_idx, a_off, a_size = index[ekey]
        abs_out = os.path.join(output_dir, out_path)

        try:
            file_data = _read_blte(data_dir, a_idx, a_off, a_size)
            os.makedirs(os.path.dirname(abs_out), exist_ok=True)
            with open(abs_out, "wb") as f:
                f.write(file_data)
            extracted[out_path] = abs_out
            if verbose:
                print(f"  {out_path} ({len(file_data)} bytes)")
        except Exception as e:
            if verbose:
                print(f"  ERROR {tvfs_path}: {e}")
            errors += 1

    if verbose:
        print(f"\nExtracted {len(extracted)} files, {skipped} skipped, {errors} errors")

    return extracted


def extract_single(
    game_dir: str, tvfs_path: str,
) -> bytes | None:
    """Extract a single file by its TVFS path. Returns bytes or None."""
    data_dir = os.path.join(game_dir, "data", "data")
    config = _parse_build_config(game_dir)
    index = _build_index(data_dir)

    vfs2_ekey9 = bytes.fromhex(config["vfs-2"][1])[:9]
    if vfs2_ekey9 not in index:
        return None

    a_idx, a_off, a_size = index[vfs2_ekey9]
    vfs2_data = _read_blte(data_dir, a_idx, a_off, a_size)
    file_map = _parse_tvfs(vfs2_data)

    ekey = file_map.get(tvfs_path)
    if ekey is None:
        return None
    if ekey not in index:
        return None

    a_idx, a_off, a_size = index[ekey]
    return _read_blte(data_dir, a_idx, a_off, a_size)
