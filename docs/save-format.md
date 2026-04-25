---
spec_version: 1.0
d2s_version_covered: 105
last_verified_commit: TBD-AT-MERGE
source_files:
  - d2r_chargen/build_lib.py
  - d2r_chargen/decoder.py
  - d2r_chargen/scanner.py
  - d2r_chargen/save.py
---

# D2R `.d2s` Save Format Reference

Reference for writing, reading, and modifying `.d2s` files for Diablo II: Resurrected (file version 105, game 1.4+). Imperative voice, tables for data, prose only for algorithms. All offsets are little-endian.

## Table of Contents

1. [Overview](#overview)
2. [File layout at a glance](#file-layout-at-a-glance)
3. [Header](#header)
4. [Attributes section (`gf`)](#attributes-section-gf)
5. [Skills section (`if`)](#skills-section-if)
6. [Items section (`JM`)](#items-section-jm)
7. [Mercenary items (`jf` / `kf`)](#mercenary-items-jf--kf)
8. [Iron golem (`kf`)](#iron-golem-kf)
9. [Checksum algorithm](#checksum-algorithm)
10. [Common operations](#common-operations)
11. [Reserved / unspecified](#reserved--unspecified)
12. [References](#references)

---

## Overview

A `.d2s` save file holds one Diablo II: Resurrected character, including header metadata, character attributes, skill points, items (in inventory / stash / equipped / cube / belt), the mercenary block (always present in v105), and the iron golem block (necromancer only). This document covers file version `99` (D2R 1.4+, the live game version on this codebase, parsed from `template.d2s` and verified against `d2r_chargen/scanner.py:scan_character_data`).

**Version note.** The on-disk file-version field at offset `0x04` is `105` (`0x69`) on this codebase — `version` and `file format version` are two different numbers in D2R. The `99` in the frontmatter refers to the structural format generation that public specs commonly cite (the format used since D2R 1.4); the `105` is the value the game writes and the scanner expects (`scanner.py:1335`).

**Endianness.** Little-endian throughout (x86 native). All multi-byte integer fields shown in tables below are LE unless explicitly noted.

**Bit packing.** Within bit-packed sections (attributes, skills, items), bits are written LSB-first inside each byte, then bytes accumulate forward. The `BitWriter` in `d2r_chargen/build_lib.py:136` is the reference implementation; `bits_at` in `scanner.py:41` is the inverse.

**Strings.** ASCII for the character name and merc name (not UTF-8). 4-character item type codes use a static Huffman tree (see `HUFFMAN` in `build_lib.py`).

## File layout at a glance

| Section | Marker | Width | Notes |
|---------|--------|-------|-------|
| Header | (none) | 0x00 .. start of `gf` | Fixed-offset fields. The block's end is determined by forward-scanning for `gf`, not a fixed boundary. See [Header](#header). |
| Attributes | `gf` | variable, terminated by 9-bit `0x1FF` | Character stats with `cB`-width packed encoding. See [Attributes section (`gf`)](#attributes-section-gf). |
| Skills | `if` | 32 bytes (2-byte marker + 30 skill points) | One byte per class skill slot. See [Skills section (`if`)](#skills-section-if). |
| Items | `JM` | 4-byte header + variable items | Player items (equipped, inventory, stash, cube, belt). See [Items section (`JM`)](#items-section-jm). |
| Mercenary block | `jf` then `JM` | variable | Always present in v105, even with no merc items. See [Mercenary items (`jf` / `kf`)](#mercenary-items-jf--kf). |
| Iron golem | `kf` | 1-byte presence flag + optional item | Necromancer-only. See [Iron golem (`kf`)](#iron-golem-kf). |
| End-of-file marker | `lf` | 4 bytes (`lf` + `u16` count, count typically 0) | Tail marker. The merc/golem block ENDS BEFORE this; `lf` is the file's last marker. |

The blocks appear in the file in the order shown.

## Header

### Layout

| Offset | Width | Field | Type | Notes |
|--------|-------|-------|------|-------|
| `0x00` | 4 | Signature | `u32` LE | `0xAA55AA55` |
| `0x04` | 4 | Version | `u32` LE | D2R 1.4+ (Reign of the Warlock) = `105`. (Some tools document `97`/`98`/`99` for legacy saves.) |
| `0x08` | 4 | File size | `u32` LE | Total bytes on disk. Updated by `write_d2s`. |
| `0x0C` | 4 | Checksum | `u32` LE | See [Checksum algorithm](#checksum-algorithm). |
| `0x10` | 4 | Active weapon set | `u32` LE | `0` = primary, `1` = secondary. |
| `0x14` | 1 | Status | `u8` bitfield | Bit 2 = hardcore, bit 3 = died (set for dead HC; harmless on SC), bit 5 = unknown. Others reserved. |
| `0x15` | 1 | Progression | `u8` | `0x00` Normal, `0x05` Nightmare, `0x0F` Hell. Other values reserved. |
| `0x16` | 2 | Reserved | `u16` | Do not write. |
| `0x18` | 1 | Class | `u8` | `0` Amazon … `7` Warlock. See class table below. |
| `0x19` | 2 | Reserved | `u16` | Do not write. |
| `0x1B` | 1 | Level | `u8` | 1–99. Mirrors stat 12 in attributes section. |
| `0x1C` | 4 | Reserved | `u32` | Do not write. |
| `0x20` | 4 | Last played | `u32` LE | Epoch seconds. |
| `0x24` | 4 | Reserved | `u32` | Do not write. |
| `0x28` | 64 | Hotkey skills | 16 × `u32` | One per F1–F12 + spares; `0xFFFFFFFF` = unset. |
| `0x68` | 4 | Left mouse skill | `u32` | Skill ID. |
| `0x6C` | 4 | Right mouse skill | `u32` | Skill ID. |
| `0x70` | 4 | Left mouse skill (alt) | `u32` | Switched-weapon left-click. |
| `0x74` | 4 | Right mouse skill (alt) | `u32` | Switched-weapon right-click. |
| `0x78` | 32 | Character menu appearance | `u8[32]` | Body part / colors as displayed on character select. |
| `0x98` | 1 | Difficulty (current) | `u8` | Active difficulty when last played. |
| `0x99` | 3 | Difficulty quest array | `u8[3]` | Per-difficulty active state. |
| `0xA3` | 4 | Mercenary name seed | `u32` LE | RNG seed for Hireling.NameFirst/NameLast picks. |
| `0xA7` | 2 | Mercenary status | `u16` LE | Observed values: 0, 1, 9, 15. Chargen writes 0. Semantics TBD. |
| `0xA9` | 2 | Mercenary Hireling.Id | `u16` LE | Index into Hireling.txt (class + element + difficulty composite). Max observed = 41. |
| `0xAB` | 4 | Mercenary experience | `u32` LE | XP accumulation. |
| `0xAF` | varies | Reserved / unknown | `u8[]` | Do not write. Extends to quest/waypoint markers. |
| `0x12B` | 16 | Character name | `ASCII` | NUL-terminated; raw byte range extends to 16 bytes regardless of name length. (Sits inside the reserved gap above — listed separately for visibility.) |
| `0x14E` | ~298 | Quest array (`Woo!`) | `u8[]` | Marker `Woo!` + sub-layout per difficulty. See `check_progression_consistency`. |
| `0x278` | ~80 | Waypoint array (`WS`) | `u8[]` | Marker `WS` + 24 bits × difficulty + headers. |
| `0x2C8` | varies | NPC intros | `u8[]` | Variable; ends before attributes section marker `gf`. |

**Note on byte range:** `scan_character_data` does NOT bind the header to a fixed end offset — it locates the attributes section by scanning forward for the `gf` marker. Public specs disagree on whether the header ends at `0x2FC` (765B) or `0x2FE` (767B); on this codebase the answer is "wherever `gf` is found" and the gap before `gf` is taken as NPC-intro / reserved padding.

**Status byte quick reference:**

| Value | Meaning |
|-------|---------|
| `0x00` | Softcore, alive |
| `0x04` | Hardcore, alive (correct HC status) |
| `0x08` | Softcore + died flag (harmless for SC; chargen template default) |
| `0x0C` | Hardcore + died — DEAD HC character, cannot join game |

**Class table:**

| ID | Class |
|----|-------|
| 0 | Amazon |
| 1 | Sorceress |
| 2 | Necromancer |
| 3 | Paladin |
| 4 | Barbarian |
| 5 | Druid |
| 6 | Assassin |
| 7 | Warlock (Reign of the Warlock expansion) |

### Invariants

- MUST: `signature == 0xAA55AA55` at offset `0x00`.
- MUST: `version == 105` for D2R 1.4+ (Reign of the Warlock).
- MUST: stored `file_size` at `0x08` equals `len(data)` after every write.
- MUST: stored `checksum` at `0x0C` equals `calc_checksum(data)` (see [Checksum algorithm](#checksum-algorithm)).
- MUST: name at `0x12B` is ASCII, NUL-terminated, ≤ 15 chars.
- MUST: `level` at `0x1B` matches stat ID 12 (`level`) in the attributes section.
- MUST NOT: set status byte bit 2 (HC) AND bit 3 (died) simultaneously — this produces a dead HC character that cannot join any game.
- MUST NOT: write to bytes marked Reserved — those bits' semantics are unknown and D2R may reject the file.
- MUST NOT: rebuild the header from scratch. Always start from a server-synced `.d2s` and edit in place (D2R rule 2).

### Worked example

The first 256 bytes of `d2r_chargen/data/template.d2s` (canonical empty character, Amazon level 1):

```
0000  55 aa 55 aa 69 00 00 00 a7 03 00 00 97 4a 28 09   U.U.i........J(.
0010  00 00 00 00 08 00 00 00 00 10 1e 01 00 00 00 00   ................
0020  a4 58 ca 69 ff ff ff ff ff ff 00 00 ff ff 00 00   .X.i............
0030  ff ff 00 00 ff ff 00 00 ff ff 00 00 ff ff 00 00   ................
0040  ff ff 00 00 ff ff 00 00 ff ff 00 00 ff ff 00 00   ................
0050  ff ff 00 00 ff ff 00 00 ff ff 00 00 ff ff 00 00   ................
0060  ff ff 00 00 ff ff 00 00 26 00 00 00 36 00 00 00   ........&...6...
0070  00 00 00 00 00 00 00 00 ff 01 01 01 01 16 ff 51   ...............Q
0080  02 02 ff ff ff ff ff ff ff 44 44 44 44 ff ff ff   .........DDDD...
0090  44 44 ff ff ff ff ff ff 00 80 00 99 f7 92 23 00   DD............#.
00a0  00 01 00 bf 19 2a 4d 01 00 0a 00 ae c3 c6 06 00   .....*M.........
00b0  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00   ................
00c0  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00   ................
00d0  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00   ................
00e0  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00   ................
00f0  00 00 00 00 00 00 00 00 03 00 00 39 6c 73 20 ff   ...........9ls .
```

Annotated field breakdown:

| Offset | Bytes | Decoded | Field |
|--------|-------|---------|-------|
| `0x00` | `55 aa 55 aa` | `0xAA55AA55` | Signature — valid |
| `0x04` | `69 00 00 00` | `105` | Version — D2R 1.4+ |
| `0x08` | `a7 03 00 00` | `935` bytes | File size (matches actual file length) |
| `0x0C` | `97 4a 28 09` | `0x09284A97` | Checksum |
| `0x10` | `00 00 00 00` | `0` | Active weapon set — primary |
| `0x14` | `08` | `0b00001000` | Status — bit 3 set (died flag; harmless on SC) |
| `0x15` | `00` | `0x00` | Progression — Normal |
| `0x18` | `00` | `0` | Class — Amazon |
| `0x1B` | `01` | `1` | Level |
| `0x20` | `a4 58 ca 69` | `1774868644` | Last played (epoch, ~2026-04-25) |
| `0xA3` | `bf 19 2a 4d` | `0x4D2A19BF` | Merc name seed |
| `0xA7` | `01 00` | `1` | Merc status field |
| `0xA9` | `0a 00` | `10` | Merc Hireling.Id (Act 2 Normal Offensive) |
| `0xAB` | `ae c3 c6 06` | `113853870` | Merc XP |
| `0x12B` | `54 65 6d 70 6c 61 74 65 00…` | `"Template"` | Character name, NUL-terminated |

Status byte `0x08` decoded: `bin = 00001000`. Bit 3 is the "died" flag. On a softcore character this flag is harmless (D2R ignores it). The character is NOT hardcore (bit 2 = 0). Chargen always starts from this template, which is why new SC builds have status `0x08`.

### Codebase

- Encode: `d2r_chargen/save.py` (header writes via `set_character_stats`, etc.)
- Decode: `d2r_chargen/scanner.py:scan_character_data` (line 1288), `decode_stats` (line 87)
- Validate: `d2r_chargen/scanner.py:check_progression_consistency` (line 1185)

## Attributes section (`gf`)

### Layout

The block starts with the 2-byte ASCII marker `gf` at a variable offset after the header. Locate it by forward-scanning from `0x2C8`. The `if` (skills) marker immediately follows — the stats section occupies the byte range `[gf+2, if)`.

**Per-stat encoding (character attributes — NOT item properties):**

The `gf` bitstream encodes character stats only. Each entry is:

| Field | Width | Notes |
|-------|-------|-------|
| `stat_id` | 9 bits | Index into `CHAR_STAT_DEFS` (16 known stats, IDs 0–15). `0x1FF` = terminator. |
| `value` | `cB` bits | Unsigned integer. `cB` varies by stat (see table below). No offset added. |

**Character stat definitions (all 16 stats, from `save.py:CHAR_STAT_DEFS`):**

| Stat ID | Name | `cB` bits | Notes |
|---------|------|-----------|-------|
| `0` | Strength | 10 | Base stat |
| `1` | Energy | 10 | Base stat |
| `2` | Dexterity | 10 | Base stat |
| `3` | Vitality | 10 | Base stat |
| `4` | StatPoints | 10 | Unspent stat points |
| `5` | SkillPoints | 8 | Unspent skill points |
| `6` | HP | 21 | Current HP × 256 (fixed-point; see below) |
| `7` | MaxHP | 21 | Max HP × 256 |
| `8` | Mana | 21 | Current Mana × 256 |
| `9` | MaxMana | 21 | Max Mana × 256 |
| `10` | Stamina | 21 | Current Stamina × 256 |
| `11` | MaxStamina | 21 | Max Stamina × 256 |
| `12` | Level | 7 | 1–99; MUST match header byte `0x1B` |
| `13` | Experience | 32 | Total XP |
| `14` | Gold | 25 | Carried gold |
| `15` | StashedGold | 25 | Stashed gold |

**Fixed-point stats (HP, Mana, Stamina — stat IDs 6–11):** values are stored multiplied by 256. To display: `stored_value >> 8`. To encode: `display_value * 256`. Example: 987 HP → stored as `987 × 256 = 252,672`.

**Bit order:** LSB-first within each byte (same as all other D2R bitstreams). Stat IDs may appear in any order; `save.py` writes them sorted by ID.

**Note on `sB`/`sA`/`sS`/`e` encoding:** Those fields from `item_stat_cost.py` apply to *item* properties inside `JM` item blocks (see [Items section (`JM`)](#items-section-jm)), NOT to the character `gf` section. The `gf` section is simpler: unsigned 9-bit ID + unsigned `cB`-bit value only.

### Invariants

- MUST: block starts with ASCII `gf` (`0x67 0x66`) followed immediately by the bitstream (no padding byte between marker and first stat).
- MUST: every stat list ends with a 9-bit `0x1FF` terminator.
- MUST: stat IDs in the `gf` block are character stat IDs (0–15 from `CHAR_STAT_DEFS`); item-only stats (`sB > 0` but `cB == 0`) MUST NOT appear here.
- MUST: `Level` (stat 12) value matches header byte `0x1B`; `set_character_stats` updates both.
- MUST: HP, Mana, Stamina (stat IDs 6–11) are stored × 256 (`>>8` to display). Storing raw display values (e.g. `987` instead of `252672`) produces a character with near-zero life bar.
- MUST: `StatPoints` (stat 4) and `SkillPoints` (stat 5) are always present in the encoded block even when zero; the game expects them.
- MUST: signed stats (sS=1) in item blocks round-trip with two's-complement sign extension — both `encode_property` and `decode_item_properties` now apply two's complement correctly (bug fixed in Task 5 fuzz session). This invariant applies to `JM` item properties, not `gf` character stats (which have no signed fields).
- MUST NOT: encode a stat ID not in `CHAR_STAT_DEFS` into the `gf` block.
- MUST NOT: add padding or alignment bytes between the `gf` marker and the bitstream, or between the terminator and the `if` marker; the stats section fills exactly `[gf+2, if)` bytes (zero-padded to byte boundary).

### Worked example

From `d2r_chargen/data/template.d2s` — a level-1 Amazon with base stats 25/25/25/25 (Str/Dex/Vit/En):

```
gf marker at file offset 0x341 (byte 833)

+0000  67 66 00 32 08 90 81 80 0c 06 64 60 00 20 03 1c   gf.2......d`. ..
+0010  00 c8 00 08 00 32 40 02 80 0c a0 00 20 03 2c 00   .....2@..... .,.
+0020  c8 00 0c 02 ff 01 00 00 00 00 00 00 00 00 00 69   ...............i
```

Bit-walk (bit positions are relative to byte 0x343, i.e. first byte after `gf` marker; LSB-first):

| Rel-bits | Stat ID | Name | `cB` | Raw value | Decoded |
|----------|---------|------|------|-----------|---------|
| 0–8 | `0x000` (9b) | — | — | — | stat_id = 0 (Strength) |
| 9–18 | — | Strength | 10 | `25` | 25 |
| 19–27 | `0x001` (9b) | — | — | — | stat_id = 1 (Energy) |
| 28–37 | — | Energy | 10 | `25` | 25 |
| 38–46 | `0x002` (9b) | — | — | — | stat_id = 2 (Dexterity) |
| 47–56 | — | Dexterity | 10 | `25` | 25 |
| 57–65 | `0x003` (9b) | — | — | — | stat_id = 3 (Vitality) |
| 66–75 | — | Vitality | 10 | `25` | 25 |
| 76–84 | `0x006` (9b) | — | — | — | stat_id = 6 (HP) |
| 85–105 | — | HP | 21 | `6400` | `6400 >> 8 = 25` HP displayed |
| 106–114 | `0x007` (9b) | — | — | — | stat_id = 7 (MaxHP) |
| 115–135 | — | MaxHP | 21 | `6400` | 25 HP max |
| 136–144 | `0x008` (9b) | — | — | — | stat_id = 8 (Mana) |
| 145–165 | — | Mana | 21 | `6400` | 25 Mana |
| 166–174 | `0x009` (9b) | — | — | — | stat_id = 9 (MaxMana) |
| 175–195 | — | MaxMana | 21 | `6400` | 25 Mana max |
| 196–204 | `0x00A` (9b) | — | — | — | stat_id = 10 (Stamina) |
| 205–225 | — | Stamina | 21 | `6400` | 25 Stamina |
| 226–234 | `0x00B` (9b) | — | — | — | stat_id = 11 (MaxStamina) |
| 235–255 | — | MaxStamina | 21 | `6400` | 25 Stamina max |
| 256–264 | `0x00C` (9b) | — | — | — | stat_id = 12 (Level) |
| 265–271 | — | Level | 7 | `1` | Level 1 |
| 272–280 | `0x1FF` (9b) | — | — | — | TERMINATOR |
```

Total bitstream: 281 bits of active data → 36 bytes minimum (padded to byte boundary with zero bits). The actual block size in `template.d2s` is 45 bytes (`[gf+2, if)` = `0x343`–`0x370`); the extra 9 bytes are zero-padding. `set_character_stats` preserves the original block length and pads with zeros rather than shrinking the block. The `if` marker follows immediately after the block.

### Codebase

- Encode: `d2r_chargen/build_lib.py:encode_property` (line 194), `encode_properties_terminated` (line 340)
- Decode: `d2r_chargen/decoder.py:decode_item_properties` (line 21), `d2r_chargen/scanner.py:decode_stats` (line 87)
- Validate: `d2r_chargen/scanner.py:validate_item_properties` (line 247)

## Skills section (`if`)

### Layout

| Offset | Width | Field | Notes |
|--------|-------|-------|-------|
| 0 | 2 | Marker `if` | ASCII `0x69 0x66`. |
| 2 | 30 | Skill points | `u8[30]` — one byte per class skill slot, value = points spent. |

Total: 32 bytes.

**Per-class skill ID ranges** (skill IDs index into `d2r_chargen/data/skills.py`; the 30 bytes correspond to that class's 30 skills in ID order):

| Class | Class code | First skill ID | Last skill ID | Count |
|-------|------------|----------------|---------------|-------|
| Amazon | `ama` | 6 | 35 | 30 |
| Sorceress | `sor` | 36 | 65 | 30 |
| Necromancer | `nec` | 66 | 95 | 30 |
| Paladin | `pal` | 96 | 125 | 30 |
| Barbarian | `bar` | 126 | 155 | 30 |
| Druid | `dru` | 221 | 250 | 30 |
| Assassin | `ass` | 251 | 280 | 30 |
| Warlock | `wlk` | 373 | 402 | 30 |

Byte index `i` in the 30-byte array (0-based) corresponds to `class_first_skill_id + i`. Skill IDs with gaps between classes (e.g. 156–220 between Barbarian and Druid, 281–372 between Assassin and Warlock) are global/monster skills and do not appear in the 30-byte block. (Verify exact ranges via `d2r_chargen/data/skills.py` — they may shift with mods.)

### Invariants

- MUST: marker is exactly `if` (`0x69 0x66`, 2 bytes ASCII).
- MUST: 30 skill bytes follow immediately after the marker, totaling 32 bytes for the whole block.
- MUST: byte index `i` corresponds to skill ID `(class_first_skill_id + i)` for the character's class (see table above).
- MUST: skill points sum ≤ available skill points at character level. Maximum available = `(level - 1) + 7` (one point per level past 1, plus up to 7 quest rewards across Normal/Nightmare/Hell difficulties).
- MUST NOT: write a value to a slot whose corresponding skill ID is not present in `SKILLS` for the character's class.
- MUST NOT: add padding between the skills block and the following `JM` items marker.

### Worked example

`template.d2s` — level-1 Amazon, no skill points spent. `if` marker at file offset `0x370` (immediately after the `gf` attributes block that ends at `0x36F`):

```
0x370  69 66 00 00 00 00 00 00 00 00 00 00 00 00 00 00  if..............
0x380  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  ................
```

Annotated:

| File offset | Bytes | Field |
|-------------|-------|-------|
| `0x370–0x371` | `69 66` | Marker `if` |
| `0x372–0x38F` | `00 × 30` | Skill points — all zero (no points spent on a level-1 character) |

For an Amazon, byte 0 (`0x372`) = points in Magic Arrow (skill ID 6), byte 1 (`0x373`) = Fire Arrow (7), … byte 29 (`0x38F`) = Lightning Fury (skill ID 35). All are `0x00` here.

### Codebase

- Encode: `d2r_chargen/save.py` (skill array writes)
- Decode: `d2r_chargen/scanner.py` (skills section parsing inside `scan_character_data`)
- Reference data: `d2r_chargen/data/skills.py`

## Items section (`JM`)

### Layout

#### Block header

| Offset | Width | Field | Notes |
|--------|-------|-------|-------|
| 0 | 2 | Marker `JM` | ASCII `0x4A 0x4D`. |
| 2 | 2 | Item count | `u16` LE — number of top-level items. Socketed sub-items (runes, gems) embedded after a parent are NOT counted here. |

The block header is followed immediately by `item_count` sequential item records, each bit-packed with LSB-first ordering.

#### Per-item bitstream

Every item starts with a 32-bit flag word. All positions below are bit offsets within the per-item bitstream, starting at 0.

**32-bit flags (bit positions within the item):**

| Bit | Meaning | Set by |
|-----|---------|--------|
| 4 | Identified | `build_item` — always set |
| 11 | Socketed | `build_item` when `socketed=True` |
| 16 | Ear item | `scanner.py` reads this; `build_item` never sets it |
| 21 | Simple item | `encode_socketed_rune` — set on runes/gems; no properties block |
| 22 | Ethereal | `build_item` when `ethereal=True` |
| 23 | Always-1 | `build_item` — must be set on every item |
| 24 | Personalized | `navigator` reads; `build_item` never sets it |
| 26 | Runeword | `build_item` when `runeword=True` |

All other bits are zero in `build_item`-generated items. The decoder reads only the bits listed above.

**Common fields after the 32-bit flag word:**

| Bits | Width | Field | Notes |
|------|-------|-------|-------|
| 32–34 | 3 | D2R ext | Always `5` (`0b101`). This is D2R's version marker. Verified: `w.write_bits(5, 3)` at line 707 of `build_lib.py`; scanner asserts `(item[4] & 7) == 5`. |
| 35–37 | 3 | `location` | `0` = in storage, `1` = equipped on character, `6` = socketed inside another item. |
| 38–41 | 4 | `bodyloc` | Body slot ID if `location=1`. Uses `BODYLOC` constants. `0` if not equipped. |
| 42–45 | 4 | `col` | Grid column (0-based). For socketed sub-items, encodes the socket slot index. |
| 46–48 | 3 | `row` | Grid row (0-based). |
| 49 | 1 | Unknown | Always `0`. |
| 50–52 | 3 | `storage` | Storage area: `0` = equipped/socketed, `1` = inventory, `2` = belt, `4` = cube, `5` = personal stash. |
| 53+ | variable | Type code | 4-character type code, Huffman-encoded. 3-char codes padded with a trailing space (e.g., `'amu '`). Width varies by code. |

**Simple items (bit 21 set):** the bitstream ends after the type code plus an 8-bit trailing field (value `2`, observed in all D2R v105 socketed sub-items). No quality, ID, property, or modifier blocks follow. Used for runes and gems inserted into sockets. See `encode_socketed_rune` (build_lib.py:908).

**Extended items (bit 21 clear):** the bitstream continues with the fields below after the type code.

#### Extended item fields (after type code, bit 21 clear)

| Field | Width | Notes |
|-------|-------|-------|
| `nr_in_sockets` | 3 bits | Count of socketed sub-items encoded AFTER this parent in the JM block. `len(rune_codes)` from the build call. |
| `item_id` | 32 bits | Unique item ID. Random 32-bit integer assigned at build time; `0xCAFEBABE` used in tests. |
| `ilvl` | 7 bits | Item level (1–99). |
| `quality` | 4 bits | Item quality (see quality table below). |
| `multi_pic` | 1 bit | `1` if item has multiple graphics variants (charms: `cm1/cm2/cm3`, jewels: `jew`). |
| `gfx_idx` | 3 bits | Only present when `multi_pic=1`. Graphics variant index. |
| `class_specific` | 1 bit | `1` if class-specific data follows. `build_item` always writes `0`; scanner skips 11 bits if set. |

#### Per-quality fields (immediately after `class_specific`)

| `quality` | Meaning | Extra fields |
|-----------|---------|--------------|
| 1 | Inferior | 3 bits: inferior_type |
| 2 | Normal | (none) |
| 3 | Superior | 3 bits: superior_type |
| 4 | Magic | 11-bit magic_prefix + 11-bit magic_suffix |
| 5 | Set | 12-bit set_id |
| 6 | Rare | 8-bit rare_first_name + 8-bit rare_last_name + 6 affix slots (each: 1-bit has_affix flag, then 11-bit affix_id if flag=1) |
| 7 | Unique | 12-bit unique_id |
| 8 | Crafted | Same layout as rare (quality 6) |

#### Fields after per-quality block

| Field | Condition | Width | Notes |
|-------|-----------|-------|-------|
| `runeword_id` | flags bit 26 set | 16 bits | D2R canonical form: low 12 bits = `runeword_id + 27` (legacy bias), high 4 bits = `5` (D2R version marker). Both the biased and unbiased forms are accepted for char-equipped items; canonical biased form is required for merc-equipped items. |
| Personalized name | flags bit 24 set | variable | 7-bit characters, NUL-terminated. `build_item` never sets bit 24; only present in player-personalized saves. |
| Book field | `base & 8` | 5 bits | Only for tomes (`tbk`, `ibk`). Value `0` = standard tome. |
| Extended body flag | always | 1 bit | `build_item` always writes `0`. If `1`, 96 additional bits follow (timestamp block). |
| `defense` | `base & 4` | 11 bits | Base defense value. Present for armor/shields. |
| `max_dur` | `base & 6` nonzero | 8 bits | Maximum durability. Present for weapons and armor. |
| `cur_dur` | `base & 6` AND `max_dur > 0` | 9 bits | Current durability. |
| Quantity presence flag | always | 1 bit | Set to `1` for stackable items (`base & 1`); `0` otherwise. `build_item` always writes this 1-bit flag for all extended items. |
| `quantity` | presence flag = 1 | 9 bits | Stack count. Default `200` when not explicitly set. |
| `num_sockets` | flags bit 11 set | 4 bits | Number of physical sockets in the item. Source: `build_lib.py:857`. (Note: `nr_in_sockets` above is a SEPARATE field — the count of sub-item records; `num_sockets` is the base-item socket capacity.) |
| `set_flags` | `quality == 5` | 5 bits | Bit mask indicating which set bonus property lists are present. Written immediately before the property mod list. |

**Base flags reference** (`base` value comes from `ITEM_BASES_FULL[type_code]['flags']`):

| Bit | Mask | Meaning |
|-----|------|---------|
| 0 | `& 1` | Stackable — quantity field present |
| 1+2 | `& 6` | Has durability (weapons, armor, shields) |
| 2 | `& 4` | Has defense (armor, shields) |
| 3 | `& 8` | Book item (tome) — 5-bit book field present |

#### Mod list (property list)

After all the fields above, the property mod list begins. Format is identical to the `gf` attributes section bitstream framing — 9-bit stat ID + variable-width value, terminated by `0x1FF` — but uses **item-property semantics**:

- Stat ID is looked up in `ITEM_STAT_COST` (not `CHAR_STAT_DEFS`).
- Value width = `sB` bits (from `item_stat_cost.py`), not `cB`.
- Values are offset by `sA` before encoding (except `e=3` charge stats, which use raw values).
- Signed stats (`sS=1`) use two's-complement encoding within the `sB`-bit field.

See `encode_property` (`build_lib.py:194`) and `decode_item_properties` (`decoder.py:21`).

**Runeword items have TWO terminated mod lists:**

1. List 1: base item magic properties (empty for a normal-quality base → single `0x1FF` terminator).
2. List 2: runeword bonus properties → actual stats + `0x1FF` terminator.

`build_item` writes list 1 as an empty terminator (`0x1FF`), then writes all runeword bonus properties in list 2.

#### Socketed sub-items

After a parent item is byte-aligned, each socketed rune or gem is encoded as a **separate simple item** immediately following the parent in the JM block:

- flags: bit 4 (identified) + bit 21 (simple) + bit 23 (always-1) — value `0x00A00010`.
- `location = 6` (socketed inside another item).
- `col = socket_index` (0-based slot position within the parent's sockets).
- After the Huffman type code: 8-bit trailing field, value `2`.
- Minimum size: 11 bytes. `encode_socketed_rune` adds extra padding bits when the Huffman code is short (e.g., `r27`/Ohm, `r29`/Sur produce only 10-byte items without the fix).

These sub-items are counted in the parent's `nr_in_sockets` field but NOT in the JM block header's item count.

### Invariants

- MUST: every `JM` block starts with ASCII marker `JM` (`0x4A 0x4D`); the following `u16` LE count = top-level items only (sub-items not counted).
- MUST: bit 23 is set on every item (both simple and extended).
- MUST: D2R ext bits (bits 32–34) = `5` (`0b101`) on every item. Scanner hard-error if violated.
- MUST: simple items (bit 21) have NO nr_in_sockets, item_id, quality, or property block.
- MUST: every extended item has at least one 9-bit `0x1FF` mod-list terminator.
- MUST: runeword items (bit 26) have exactly TWO `0x1FF` terminators — one ending the empty base-item list, one ending the runeword bonus list.
- MUST: unique items use a `unique_id` that exists in `UNIQUE_ITEMS` and whose `code` matches the item's `type_code` (`validate_unique_item`, build_lib.py:411). Violating this produces a crash or display-only item with no stats.
- MUST: set items use a `set_id` that exists in `SET_ITEMS` with matching `code` (`validate_set_item`).
- MUST: runeword items use a `runeword_id` that exists in `RUNEWORDS` and the base item's `categories` intersect the runeword's `bases` list (`validate_runeword`).
- MUST: socketed sub-items (location=6) are byte-aligned and at least 11 bytes long (padding fix in `encode_socketed_rune` lines 932–944).
- MUST: `runeword_id` is written in canonical biased form (low 12 bits = `id + 27`, high 4 bits = `5`) for merc-equipped items. Both biased and raw forms work for char-equipped items, but canonical is always preferred.
- MUST NOT: place a magic jewel (quality=4, location=6) as a socketed filler — D2R rejects saves with many items when magic jewels are in sockets. Merge filler stats into the parent item's properties instead (see `feedback_jewel_filler.md`).
- MUST: item property mod list uses `sB`/`sA`/`sS`/`e` encoding from `item_stat_cost.py` (item stats), distinct from the `gf` section's character-attribute `cB`-width unsigned encoding.
- MUST: extended items always include the 1-bit quantity presence flag, regardless of whether the item is stackable.

### Worked example

Normal amulet (`amu`) in personal stash, item_id=`0xCAFEBABE`, ilvl=50. Built with:

```python
build_item(type_code="amu", col=0, row=0, storage=5, quality=2, item_id=0xCAFEBABE, ilvl=50)
```

Raw bytes (18 bytes, LSB-first bit ordering):

```
10 00 80 00 05 00 f4 59 18 7c 75 fd 95 65 82 c8 fe 03
```

Bit-walk (all bit positions within the item bitstream, 0-indexed, LSB-first):

| Bits | Width | Field | Value | Notes |
|------|-------|-------|-------|-------|
| 0–31 | 32 | flags32 | `0x00800010` | bit 4=identified, bit 23=always-1; all others 0 |
| 32–34 | 3 | D2R ext | `5` (0b101) | D2R version marker |
| 35–37 | 3 | location | `0` | stored (not equipped) |
| 38–41 | 4 | bodyloc | `0` | not equipped |
| 42–45 | 4 | col | `0` | stash column 0 |
| 46–48 | 3 | row | `0` | stash row 0 |
| 49 | 1 | unknown | `0` | always 0 |
| 50–52 | 3 | storage | `5` | personal stash |
| 53–69 | 17 | type code | `'amu '` | Huffman-encoded (17 bits for this code) |
| 70–72 | 3 | nr_in_sockets | `0` | no socketed sub-items |
| 73–104 | 32 | item_id | `0xCAFEBABE` | unique item ID |
| 105–111 | 7 | ilvl | `50` | item level |
| 112–115 | 4 | quality | `2` | normal quality |
| 116 | 1 | multi_pic | `0` | single graphic |
| 117 | 1 | class_specific | `0` | no class data |
| 118 | 1 | ext_body | `0` | no timestamp block |
| 119 | 1 | qty presence | `1` | `amu` base_flags=1 (stackable misc) |
| 120–128 | 9 | quantity | `200` | default stack count |
| 129–137 | 9 | terminator | `0x1FF` | end of mod list |
| 138–143 | 6 | padding | `0` | zero-pad to byte boundary |

Total: 18 bytes. The amulet has `base_flags=1` (bit 0 set), so the quantity presence flag fires and encodes a default quantity of 200. No defense, no durability fields (bits 1–2 of base_flags are 0 for amulets).

Flags32 decoded bit-by-bit from `0x00800010`:

```
bit 31  (MSB) = 0
bit 26 (runeword)  = 0
bit 23 (always-1)  = 1  ← 0x00800000
bit 22 (ethereal)  = 0
bit 21 (simple)    = 0  ← extended item
bit 11 (socketed)  = 0
bit  4 (identified)= 1  ← 0x00000010
bits 0-3, 5-10, 12-20, 24-25, 27-31 = 0
```

### Codebase

- Encode: `d2r_chargen/build_lib.py:build_item` (line 502), `encode_socketed_rune` (line 908), `find_item_list` (line 952)
- Decode: `d2r_chargen/scanner.py:decode_item_header` (line 61), `navigate_item_structure` (line 130)
- Validate: `d2r_chargen/scanner.py:validate_item_properties` (line 247)

## Mercenary items (`jf` / `kf`)

### Layout

The merc block lives between the corpse (dead body) item list and the iron golem block. The tail of every `.d2s` file follows this fixed order:

```
JM[dead] | jf | JM[merc] | <merc items> | kf | <has_golem:1> | 01 00 | lf <lf_count:u16>
```

`jf` and `lf` are anchored from the end of the file (see scanner.py comment at line 556):
`rfind(lf)` → `rfind(kf, 0, lf)` → `rfind(JM, 0, kf)` → `rfind(jf, 0, JM)`.
Forward `find` from after `JM[char]` is unreliable — `jf`/`kf` byte sequences can appear inside item bitstreams.

| Segment | Width | Notes |
|---------|-------|-------|
| `JM` | 2 | Corpse (dead body) item list marker. Always count=0 in practice. |
| `<dead_count>` | 2 | `u16` LE — number of corpse items (always 0 in chargen-built saves). |
| `jf` | 2 | Start of mercenary block (always present, even when no merc). |
| `JM` | 2 | Begin merc item list. |
| `<merc_count>` | 2 | `u16` LE — number of merc items (0 when no merc, or positive). |
| `<items>` | varies | Each item uses the same bitstream layout as [Items section (`JM`)](#items-section-jm). |
| `kf` | 2 | End of mercenary block / start of iron golem block. |

The `jf` block is always present in every v105 save (D2R 1.4+).

#### `lf` marker (end of file)

After `kf` + golem bytes, the file ends with a 4-byte `lf` record:

| Segment | Width | Notes |
|---------|-------|-------|
| `01 00` | 2 | Constant; semantics unknown. Observed in every save. |
| `lf` | 2 | End-of-file marker. |
| `<lf_count>` | 2 | `u16` LE — historically called "merc hired flag". D2R writes `0` even with merc gear. Valid observed range: {0, 1}. |

**Canonical merc encoding (Rule 6):** When items are encoded directly in `JM[merc]` (equipment_mode: direct), the item's `col` field must equal `bodyloc` (not 0). For runeword merc items: low 12 bits of the runeword field = `runeword_id + 27`; high 4 bits = `5`.

**Merc fields in the header** (already covered in [Header](#header)): name seed at `0xA3`, status `0xA7`, `Hireling.Id` at `0xA9`, XP at `0xAB`.

### Invariants

- MUST: `jf` marker present in every save (D2R v105).
- MUST: corpse `JM` (count=0) immediately precedes `jf`.
- MUST: merc `JM` immediately follows `jf`.
- MUST: `kf` follows the merc item list with no gap (end of merc items is the byte before `kf`).
- MUST (canonical direct-mode): `col == bodyloc` (non-zero) for items in `JM[merc]`.
- MUST (canonical runeword bias): runeword field low12 = `runeword_id + 27`; high4 = `5`.
- MUST: `lf_count == 0` (D2R writes 0 even with merc gear; writing 1 causes silent rejection at game-enter).
- MUST NOT: write `lf_count > 1`.
- MUST: header merc fields at `0xA3..0xAE` match the merc items' implied class (if items present).

### Worked example

Fixture: `tests/fixtures/hexshade_lv98_haseen.d2s` — merc section (3 items), no golem.

```
Offset  Hex                                            ASCII
jf@79b  6a 66                                          jf
        4a 4d 03 00                                    JM count=3
        [item bitstreams — 0xf4 bytes total]
kf@897  6b 66                                          kf
        00                                             has_golem=0
        01 00                                          constant
lf@89c  6c 66 00 00                                    lf lf_count=0
```

Annotated tail (from `kf` to EOF, 9 bytes):

```
6b 66  00  01 00  6c 66  00 00
kf     \0  const  lf     lf_count=0
```

### Codebase

- Encode: `d2r_chargen/items.py:build_merc_item` (line 434), merc-specific builders (lines 469–620)
- Decode: `d2r_chargen/scanner.py:scan_character_data` (merc_jm anchoring, line 1326)

## Iron golem (`kf`)

### Layout

`kf` is both the terminator of the merc item block and the header of the iron golem block. The complete tail after the last merc item is:

| Segment | Width | Notes |
|---------|-------|-------|
| `kf` | 2 | Iron golem block marker (last block before `lf`/EOF). |
| `<has_golem>` | 1 | `0x01` if the necromancer has an iron golem, `0x00` otherwise. |
| `<item>` | varies | Present only when `has_golem == 0x01`. One item using the standard bitstream layout from [Items section (`JM`)](#items-section-jm). This is the **consumed weapon**, not the golem itself. |
| `01 00` | 2 | Constant (always `01 00`; semantics unknown). |
| `lf` | 2 | End-of-file marker (see `lf` in Mercenary section above). |
| `<lf_count>` | 2 | `u16` LE — always 0 in chargen writes. |

The iron golem feature is necromancer-only. For all other classes `has_golem` is `0x00` and no item follows.

### Invariants

- MUST: `kf` is the last structural marker in the file (immediately before the golem bytes and then `lf`).
- MUST: `has_golem` is `0x00` or `0x01`.
- MUST: when `has_golem == 0x01`, exactly one item follows (the consumed weapon).
- MUST NOT: write an iron-golem item for non-necromancer classes (D2R will reject the save).
- MUST: `kf..lf` gap does not exceed ~200 bytes (scanner flags gap > 200 as structural corruption).

### Worked example

Fixture: `tests/fixtures/hexshade_lv98_haseen.d2s` — no iron golem (non-necromancer).

```
kf region (9 bytes, kf@0x897 to EOF @0x8a0):

  Hex: 6b 66  00  01 00  6c 66  00 00
       ─────  ──  ─────  ─────  ─────
       kf     \0  const  lf     lf_count=0
              │
              └─ has_golem=0 (no golem)
```

For a necromancer with an active iron golem, the byte at `kf+2` is `0x01` and the consumed-weapon item bitstream follows immediately before the constant `01 00 lf lf_count` tail.

### Codebase

- Encode/decode: see iron golem markers in `d2r_chargen/save.py` and the `kf` block parsing in `d2r_chargen/scanner.py`.

## Checksum algorithm

The 32-bit checksum at offset `0x0C` is a rotate-left accumulator over the entire file with bytes `0x0C..0x0F` treated as zero during computation.

```python
def calc_checksum(data: bytes) -> int:
    cs = 0
    for i, b in enumerate(data):
        if 0x0C <= i <= 0x0F:
            b = 0
        cs = (((cs << 1) | (cs >> 31)) + b) & 0xFFFFFFFF
    return cs
```

After any edit:

1. Update file size at `0x08` (`u32` LE = `len(data)`).
2. Zero bytes `0x0C..0x0F`.
3. Recompute `calc_checksum(data)`.
4. Write the result back to `0x0C..0x0F` as `u32` LE.

`d2r_chargen/build_lib.py:write_d2s` (line 982) does all four steps in one call.

### Codebase

- Calculate: `d2r_chargen/build_lib.py:calc_checksum` (line 966)
- Write: `d2r_chargen/build_lib.py:write_d2s` (line 982)
- Verify: `d2r_chargen/scanner.py:calc_checksum` (line 99)

## Common operations

Each recipe lists the byte-level steps in order. Apply invariants from the relevant section as you go.

### Change class (header byte `0x18`)

1. Write target class ID (0–7) to `0x18`.
2. The character menu appearance block at `0x78..0x97` may need to be regenerated by the game; the chargen flow leaves it intact and lets D2R re-render.
3. Recompute checksum.

### Change difficulty progression (status byte `0x14` + progression byte `0x15`)

1. Set `0x15` to `0x00` (Normal), `0x05` (NM), or `0x0F` (Hell).
2. Update quest array at `0x14E` and waypoint array at `0x278` to reflect quest/WP completion through the new progression.
3. Recompute checksum.

### Add an item to the inventory / stash

1. Locate the items section: scan from `0x300` for `JM` marker (`build_lib.find_item_list`).
2. Insert the item bytes at the end of the existing item list, before the `jf` merc marker.
3. Increment the 16-bit item count at `JM + 2`.
4. Update file size at `0x08`.
5. Recompute checksum.

### Modify a stat in the attributes section

1. Locate the `gf` marker (forward scan from end of header).
2. Decode the property bitstream until you reach the target stat ID (or the `0x1FF` terminator).
3. Re-encode that stat (and shift any following bits if the bit-width changed — only happens for grouped stats).
4. Update file size and checksum if the section length changed.

### Recompute checksum after any edit

See [Checksum algorithm](#checksum-algorithm). Always update file size BEFORE checksum (the file-size field is part of the checksum input).

### Convert a SC character to HC

1. Status byte at `0x14`: set bit 2 (hardcore) → result depends on existing bits; verify against `feedback_hc_status_byte.md`. The chargen flow uses `status = 0x24` (bits 2 + 5 set; bit 5 = expansion-character indicator on this codebase).
2. Act byte at `0xA8`: set to `0x00` (HC act unlock — see memory `feedback_hc_act_byte.md`).
3. Preserve the merc-related bytes at `0xA9..0xAB` if a merc is hired (see memory `feedback_hc_flip_merc_preserve.md`).
4. Recompute checksum.

## Reserved / unspecified

Bytes / bit positions the codebase does not write. "Do not write — unknown semantics" is treated as an invariant.

| Range / position | Source of "reserved" classification |
|------------------|------------------------------------|
| `0x16..0x17` | Not read by `scan_character_data`; codebase does not write. |
| `0x19..0x1A` | Not read; reserved. |
| `0x1C..0x1F` | Not read; reserved. |
| `0x24..0x27` | Not read; reserved (likely additional play-time fields). |
| `0xA9..0xAA` | Reserved AFTER the act byte; preserved during HC flips because they encode merc Hireling.Id. |
| `0xAF..0xB0` | Reserved between map seed and merc-alive byte. |
| `0xBE..0x14D` | Mostly reserved/NPC-intro padding (144 bytes). |
| Item flag bits 0–3, 5–10, 12, 15, 18–20, 25, 28–31 | Not set by `build_item`; not tested by `decode_item_header`. |
| Item ext bits other than the 3-bit `0b101` constant | Reserved. |

Treat any bit not explicitly documented in another section as reserved.

## References

Public specs that cover earlier .d2s versions in detail. Cross-check carefully — none of these document D2R 1.4+ specifics (warlock class, expanded stash, item codes 401+, canonical merc encoding).

- [WalterCouto/D2CE — `d2s_File_Format.md`](https://github.com/WalterCouto/D2CE) — most thorough public spec, LoD-focused with partial v97/98 coverage.
- [krisives/d2s-format](https://github.com/krisives/d2s-format) — original canonical spec, versions 71–96.
- [dschu012/D2SLib](https://github.com/dschu012/D2SLib) — C# parser, D2R 1.15.
- [nokka/d2s](https://github.com/nokka/d2s) — Go parser.
