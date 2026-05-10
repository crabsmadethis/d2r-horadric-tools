# D2R `.d2s` Save File Format

> **Status:** canonical public save-format reference. Last updated 2026-05-09;
> includes public-safe live findings from 2026-05-08. Cross-reference for
> `d2r_chargen/` parsers + writers. Compatibility links may still point to
> `docs/save-format.md`, but new format knowledge belongs here.
>
> **Scope:** D2R version 105 (Reign of the Warlock expansion). Pre-105 saves
> are out of scope.
>
> **Trust hierarchy:** code in `d2r_chargen/` > fixtures under
> `tests/fixtures/` > this doc > external/public specs. When in doubt,
> read the source.

---

## Top-level layout

```
+--------------------------------------------------------------+
| Header stable offsets (0x00..0x14F, 336 bytes)               |
+--------------------------------------------------------------+
| Quests   (Woo! marker + 3×96B difficulty blocks)             |
| Waypoints (WS marker + 3×24B difficulty blocks)              |
| NPC introductions (no specific marker — between WS and gf)   | [unconfirmed exact width]
| Stats    (`gf` marker + bit-packed stats list, 0x1FF term)   |
| Skills   (`if` marker + 30 skill bytes, 1 byte per slot)     |
| Char items   (`JM<u16:count>` + N item bitstreams)           |
| Dead body items  (`JM<u16:count>`, often count=0)            |
| Corpse marker   `jf`                                         |
| Merc items   (`JM<u16:count>` + N item bitstreams)           |
| Iron golem marker   `kf`                                     |
| Iron golem flag   u8 (`0` or `1`)                            |
| Iron golem item payload, if flag is `1` (variable length)     |
| Bridge   `\x01\x00` (constant 2 bytes)                       |
| Followers   `lf<u16:count>` [+ count × 116B payload]         |
| EOF                                                          |
+--------------------------------------------------------------+
```

The pre-`JM` region is not strictly fixed — Quests/Waypoints/Stats are
variable-length sections terminated by their own end-markers. The header field
table below covers the stable byte offsets currently used by the codebase; it
does not mean the whole pre-`gf` region has a fixed width.

---

## Header (0x00..0x14F, 336 bytes)

All multi-byte integers are little-endian unless noted. Offsets are given in
hex. "Confirmed" means the code reads or writes the offset directly; observed
raw values without decoded semantics stay raw until code or public-safe
fixtures prove more.

| Offset      | Size   | Field                          | Source / verification |
|-------------|--------|--------------------------------|-----------------------|
| `0x00..0x03`| u32    | Magic = `0x55AA55AA`           | `build_lib.py:741` (validate_template) |
| `0x04..0x07`| u32    | Version (105 for D2R RotW)     | format constant; not actively validated by chargen |
| `0x08..0x0B`| u32    | File size (LE u32, recomputed on write) | `build_lib.py:write_d2s` line 991 |
| `0x0C..0x0F`| u32    | Checksum (LE u32, zeroed during calc) | `build_lib.py:calc_checksum` lines 964-977 |
| `0x14`      | u8     | Status flags — bit 2 = hardcore, bit 3 = died | `scanner.py:577-582`, `save.py:444` |
| `0x15`      | u8     | Progression: `0x00` Normal, `0x05` NM, `0x0F` Hell | `save.py:443`, `importer.py:46-49` |
| `0x18`      | u8     | Class id (0=Amazon … 7=Warlock — see below) | `save.py:555`, `importer.py:43` |
| `0x1B`      | u8     | Character level (1..99)        | `save.py:206`, `importer.py:44` |
| `0xA3..0xA6`| u32    | Merc name seed (RNG for Hireling.NameFirst/NameLast) | `save.py:525` |
| `0xA7..0xA8`| u16    | Merc status bitfield (opaque; chargen writes 0) | `save.py:526`. Corpus/live values include at least `{0,1,3,5,9,10,11,13,15,16,18,21,50}`; preserve as raw until decoded. |
| `0xA9..0xAA`| u16    | `Hireling.txt` Id column (class+element+difficulty) | `save.py:527` |
| `0xAB..0xAE`| u32    | Merc XP (or XP-adjacent u32)   | `save.py:528` |
| `0xA8..0xAA`| 3 bytes| **(Aliased range)** Difficulty/act marker for SC chars: `[0x00, act_index, 0x00]` where `act_index = diff*5`. **Not written for HC.** Note this overlaps the merc-id u16; see § Merc/Difficulty overlap below. | `save.py:set_difficulty:436-453` |
| `0x12B..0x13A`| 16B  | Character name (null-padded ASCII) | `importer.py:88-91`, `save.py:557-561` |

### Class id values

```
0 = Amazon
1 = Sorceress
2 = Necromancer
3 = Paladin
4 = Barbarian
5 = Druid
6 = Assassin
7 = Warlock      (Reign of the Warlock expansion — only valid in v105+)
```
Source: `d2r_chargen/config.py` `CLASS_DEFS` + `CLAUDE.md` quick reference.

### Status byte (0x14) full table

| Value | Meaning | Notes |
|-------|---------|-------|
| `0x00`| Softcore, alive | |
| `0x04`| **Hardcore, alive** | Correct HC status. |
| `0x08`| Softcore + died flag set | Harmless for SC; chargen template default. |
| `0x0C`| Hardcore + died = **DEAD HC**, cannot join game | Bug source for Malachar 2026-04-11. |
| `0x24`| HC chargen output | Observed output; the high nibble bits are not fully decoded. |

In D2R v105 every character is implicitly expansion. There is no
separate "expansion" bit (an earlier doc claimed bit 3 was that — it is the
died flag).

### Merc / Difficulty overlap

`save.py:set_difficulty` writes 3 bytes at `0xA8..0xAA` for SC chars
(act-byte trio). `save.py:set_merc_header` writes a u16 at `0xA9..0xAA`
(Hireling.Id). For HC characters chargen deliberately skips the act
trio (rule 446 in save.py) because writing those bytes for HC corrupts the
merc Hireling.Id. Order
matters: write merc header AFTER set_difficulty, or HC-skip the act
trio.

---

## Body sections (after header)

In on-disk order:

### 1. Quests — `Woo!` marker

- Marker: 4 bytes ASCII `Woo!` (b'\x57\x6f\x6f\x21')
- 6 byte header after marker (purpose unspecified; chargen writes none of it)
- 3 × 96B blocks: one per difficulty (Normal, NM, Hell)
- Each block: 48 quests × 2 bytes (6 acts × 8 quests; quest+reward bytes)
- Per-quest encoding: `0x01` first byte = quest complete; `0x10` second byte = reward collected
- Source: `save.py:set_all_quests:299-315`, `set_quests_granular:373-421`

### 2. Waypoints — `WS` marker

- Marker: 2 bytes `WS`
- 8 byte header (offset +0..+7 includes `02 01` constant)
- 3 × 24B blocks: one per difficulty
- Each block: 2 byte intro (`02 01`) + 5 byte bitmask + 17 byte padding
- Bitmask packing: 9+9+9+3+9 = 39 waypoints across 5 acts; bit i set = waypoint i revealed
- Source: `save.py:set_all_waypoints:254-269`, `set_waypoints_granular:324-370`

### 3. NPC introductions

- No dedicated ASCII marker; sits between the WS waypoint section and
  the `gf` stats marker.
- Verified via fixture-backed acceptance testing: only ONE `if`
  occurs in the file (at offset 880, the skills marker). Earlier
  speculation that there were two `if` markers (NPC + skills) was
  wrong.
- Width / contents [unconfirmed — chargen never edits this region].

### 4. Stats — `gf` marker

- Marker: 2 bytes `gf`
- Variable-length bit-packed stat list
- Per stat: 9 bit stat id, then `cB` bits of value (cB from `item_stat_cost.py`)
- Terminator: 9 bit value `0x1FF`
- Padding: zero bits to next byte boundary
- Stats stored ×256 internally for HP / Mana / Stamina (life_hp = stored / 256)
- Source: `save.py:set_character_stats:107-209`, `importer.py:_decode_character_stats:94-129`, `CHAR_STAT_DEFS:27-36`

Core stat ids + bit widths (from `CHAR_STAT_DEFS`):

| id  | name           | bits |
|-----|----------------|------|
| 0   | Strength       | 10   |
| 1   | Energy         | 10   |
| 2   | Dexterity      | 10   |
| 3   | Vitality       | 10   |
| 4   | StatPoints     | 10   |
| 5   | SkillPoints    | 8    |
| 6   | HP (current)   | 21   |
| 7   | MaxHP          | 21   |
| 8   | Mana           | 21   |
| 9   | MaxMana        | 21   |
| 10  | Stamina        | 21   |
| 11  | MaxStamina     | 21   |
| 12  | Level          | 7    |
| 13  | Experience     | 32   |
| 14  | Gold           | 25   |
| 15  | StashedGold    | 25   |

Stats outside this set use bit widths from `data/item_stat_cost.py`
(the `cB` and `vS` columns). For grouped stats, `np>0` means multiple values
encode under one stat id.

### 5. Skills — `if` marker (after stats)

- Marker: 2 bytes `if`
- Fixed 30 byte payload — one byte per skill slot
- Skill id resolution: `class_skill_base + slot_index` (per class, see `data/skills.py`)
- Each byte = level 0..255 (typically capped at 20 + plus skills)
- Source: `save.py:set_skills:424-433`, `importer.py:_decode_skills:132-154`

### 6. Character items — `JM<u16:count>`

- Marker: 2 bytes `JM`
- u16 LE count = parent items only (NOT socket fillers — see § Item encoding)
- Variable-length item bitstreams follow, count items
- Source: `save.py:rebuild_items:603-642`, `importer.py:_decode_items:166-219`

### 7. Dead body items — `JM<u16:count>`

- Marker: another `JM` immediately after the last char item
- Almost always count=0 (no dead-body items)
- chargen always writes `JM 00 00`

### 8. Corpse marker — `jf`

- Marker: 2 bytes `jf`
- Comes after the dead-body JM section
- No payload of its own

### 9. Merc items — `JM<u16:count>`

- Marker: 2 bytes `JM`
- u16 LE count = parent items the merc has equipped
- Always present even when merc has no items (count=0)
- See CLAUDE.md rule 6: merc items must use D2R canonical encoding
  (col=bodyloc, biased runeword id). The later `lf` field is the follower
  count, not a merc flag.
- Source: `save.py:rebuild_items:644-645,690-691`, `importer.py:220-241`

### 10. Iron golem marker — `kf`

- Marker: 2 bytes `kf`
- Followed by u8 has_golem flag (0 or 1)
- If flag=1: a single golem item (JM-less item bitstream, encoded same as char items but without the JM count prefix)
- Current chargen can preserve existing golem payloads and write supported
  generated normal/magic golem items for Necromancers. Unsupported item
  families must stay rejected until manual validation proves them.

### 11. Bridge — constant `\x01\x00`

- 2 bytes immediately after the iron-golem flag byte
- Has been `\x01\x00` in every D2R v105 save examined — purpose unknown
- chargen writes it unconditionally (`save.py:698`)
- When `has_golem=0`, combined with the preceding `kf 00`, this is the 5-byte
  gap from `kf` to `lf`: `kf 00 01 00` + `lf`. When `has_golem=1`, the
  variable-length golem item payload sits between the flag and this bridge.

### 12. Followers — `lf<u16:count>` (+ optional payload)

- Marker: 2 bytes `lf`
- u16 LE `follower_count`
- If `follower_count >= 1`: `follower_count × 116B` payload follows (see § Follower section)
- Source: `save.py:rebuild_items:699-700`, `d2r_chargen/follower_block.py`

### 13. EOF

In the current follower fixture pair, the file ends immediately
after the follower block (no extra trailing bytes). The `gf` ASCII at
offset +92 of the demon payload is **payload data**, not a section
marker. Phase 0.4 confirmed no separate post-payload golem section in
warlock + bound-demon saves — see `lf_count_acceptance_test.md`.

---

## Follower section (Discovered 2026-04-25)

Documents work from the `feat/follower-block` branch (commits
`affedc1` through `5fc1ce7`).

Wire format:

```
'l' 'f' <u16:follower_count> [follower_count × 116B payload]
```

### Acceptance rule (Phase 0.4)

```
follower_count == N  ⇒  exactly N × 116 bytes of payload must follow
```

Mismatch produces silent rejection: D2R returns "FAILED TO JOIN GAME"
with no log message and no cache files written. Verified by
`scripts/dev/forge_lf_test.py` 2026-04-25 — full results in
`tests/fixtures/lf_count_acceptance_test.md`.

For the only currently-known follower kind (Warlock bound demon), D2R accepts
N=0 or N=1. Manual validation rejected two scanner-clean N=2 variants: one with
the same 116-byte payload duplicated and one with two different known 116-byte
payloads. Both failed to join game and neither save was rewritten.

### Demon payload (116 bytes)

High-confidence fields parsed by `d2r_chargen/follower_block.py`:

| Offset (rel) | Size | Field             | Notes |
|--------------|------|-------------------|-------|
| `+0`         | u16  | section/follower-kind tag | invariant `0x0018` across binds; likely "bound demon" type marker |
| `+4`         | u16  | `monster_hcidx`   | MonStats.txt row index (e.g. `20` = `fallen2`) |
| `+6`         | u32  | `monster_seed`    | random instance seed; rerolls every bind |
| `+52`        | u32  | `bind_demon_level`| persisted bind metadata; not the effective Bind Demon skill level |
| `+80..+84`   | 5B   | `affix_indices`   | MonUMod.txt indices, raw bytes (NOT a u32) |
| `+92..+93`   | 2B   | ASCII `gf`        | **DATA, not a section marker.** Same byte position in both fixtures. The decoder must use a fixed 116B length, not a `gf`-terminated slice. |

Per-byte decode of all 116 bytes (including medium and
low-confidence fields like `+24/+28` runtime stats and
`+64..+79` bitfields) is in `tests/fixtures/demon_block_decoded.md`.
Do **not** duplicate that table here — it changes as new fixtures
arrive.

Manual validation confirmed that copied 116-byte bound-demon payloads remain
visible and preserve `follower_count=1` after save/exit. The embedded `gf`
bytes remain data inside the payload, not a new section marker.

Repeated reload/save checks show that payload bytes `+89..+91` are volatile.
They can change to or from `00 00 00`, so zero is not a canonical endpoint.
High-confidence identity fields persisted across the same checks.

A high-property capture showed visible properties that were not all present in
the five decoded MonUMod bytes at `+80..+84`. That means some visible
properties are monster-specific, stored in other payload bytes, or omitted from
the persisted bound-demon affix list.

Targeted template-derived edits to high-confidence fields are accepted and
preserved: zeroing the five MonUMod bytes removes visible extra affixes,
changing `monster_hcidx` can change the visible model, and changing
`bind_demon_level` persists, but natural live binds at hard skill levels 1, 5,
10, and 20 all saved this field as `7`; do not treat it as the effective skill
level.
Cold Enchanted and Stone Skin have positive single-affix evidence. Lightning
Enchanted byte `03` can persist without necessarily displaying as a Lightning
Enchanted label for the tested bound demon.

Experimental chargen support now allows template-derived overrides for
`monster_hcidx`, `monster_seed`, `bind_level` / `bind_demon_level`, and up to
five MonUMod affixes. This is not full synthesis: the unknown runtime slices
still come from a live template payload.

### Cross-class behavior

Fixture-backed validation found D2R can load a non-Warlock save carrying a
structurally valid Warlock follower block without rejecting the file. It does
not instantiate the borrowed demon for that class; on save/exit, D2R strips the
follower block back to `follower_count=0`.

---

## Iron golem section (when present)

Conditionally written as `kf <u8:has_golem> [golem_item]`. In every
D2R v105 save examined before manual validation, chargen wrote `kf 00` (no iron
golem). Saves that come from in-game with an active iron golem (Necromancer Iron
Golem skill) carry `kf 01` followed by a JM-less item bitstream. Captures with
active golems showed variable-length payloads, confirming the section contains
encoded item data rather than a fixed-size golem record. Recasting replaces the
existing golem payload instead of appending another one.

Rebuild tests preserved active golem payloads through the
`kf 01 <item> 01 00 lf 00 00` tail. Generated normal and magic Iron Golem items
are supported for Necromancers with `IronGolem >= 1`. Broader item families
need canonicalization-aware tests before they become part of the stable public
YAML contract.

For warlocks with bound demons: `kf 00` is still written, the bridge
`\x01\x00` follows, and the `lf` follower block carries the demon.
**The `gf` ASCII at offset +92 of the demon payload is unrelated to
the iron golem section.** [unconfirmed: whether D2R ever writes both
an iron golem and a bound demon for the same character — RotW gives
the bound-demon skill only to warlocks, who don't have iron golem.]

---

## Item encoding (overview)

Full bitstream spec lives in `d2r_chargen/build_lib.py` (`build_item`,
`encode_socketed_rune`, `BitWriter`). Bits are written LSB-first inside each
byte, then bytes accumulate forward. The scanner hard-errors when item records
violate the structural invariants below.

Every `JM` block stores a `u16` parent-item count after the marker. Socketed
sub-items (`location == 6`) are encoded as item records immediately after their
parent, but are not included in the `JM` count. See
`save.py:rebuild_items:629-636` for the `count_parents()` helper.

### Item flags (u32 at item start)

| Bit | Meaning           | Notes |
|-----|-------------------|-------|
| 4   | Identified        | `build_item` sets this on generated items |
| 11  | Socketed          | Item has sockets (filled or empty) |
| 16  | Ear item          | Scanner reads this; `build_item` does not set it |
| 21  | Simple item       | No properties bitstream (rune, gem, etc.) |
| 22  | Ethereal          | |
| 23  | Always-1          | Must be set on every item |
| 24  | Personalized      | Personalized name follows when set |
| 26  | Runeword          | Item carries runeword data |

Source: `importer.py:254-258`.

### Common item fields after flags

Bit positions are relative to the start of the item bitstream.

| Bits | Width | Field | Notes |
|------|-------|-------|-------|
| `32..34` | 3 | D2R ext/version bits | Must be `5` (`0b101`) |
| `35..37` | 3 | `location` | `0` in storage, `1` equipped, `6` socketed inside another item |
| `38..41` | 4 | `bodyloc` | Body slot when equipped; `0` otherwise |
| `42..45` | 4 | `col` | Grid column, or socket index for sub-items |
| `46..48` | 3 | `row` | Grid row |
| `49` | 1 | raw unknown bit | Generated items write `0` |
| `50..52` | 3 | `storage` | `0` equipped/socketed, `1` inventory, `2` belt, `4` cube, `5` personal stash |
| `53+` | variable | type code | 4-character item code, Huffman encoded; 3-char codes are padded with a space |

Simple items (`flags bit 21`) stop after the type code plus the observed
8-bit trailing field used by generated socket fillers. Extended items continue
with item id, item level, quality fields, durability/quantity/socket fields,
and one or more property lists.

### Extended item fields

After the type code, extended items carry:

- `nr_in_sockets` (3 bits): number of socketed sub-item records after this
  parent.
- `item_id` (32 bits): generated/random item identity.
- `ilvl` (7 bits): item level.
- `quality` (4 bits): `1=inferior`, `2=normal`, `3=superior`, `4=magic`,
  `5=set`, `6=rare`, `7=unique`, `8=crafted`.
- `multi_pic` plus optional `gfx_idx`: graphic variant selector.
- `class_specific`: if set in a source save, scanner treats the following raw
  class-specific bits as part of the item. Generated items write `0`.

Quality-specific data follows this core header:

| Quality | Extra payload |
|---------|---------------|
| Inferior | 3-bit inferior type |
| Normal | none |
| Superior | 3-bit superior type |
| Magic | 11-bit prefix + 11-bit suffix |
| Set | 12-bit set id |
| Rare | 8-bit first name + 8-bit last name + up to 6 affix slots |
| Unique | 12-bit unique id |
| Crafted | Rare-style name and affix layout |

After the quality-specific fields, optional payloads appear according to item
flags and base flags: runeword id, personalized name, tome/book field,
defense, durability, quantity, socket count, and set-bonus flags. Keep unknown
bits raw unless the codebase decodes them.

### Item property lists

Item property lists use the same framing shape as the `gf` character-stat
section — 9-bit stat id plus a variable-width value, terminated by `0x1FF` —
but the semantics come from `item_stat_cost.py`, not `CHAR_STAT_DEFS`.

- Value width is `sB`, not character-stat `cB`.
- Values are adjusted by `sA` except for charge-style `e=3` stats.
- Signed stats (`sS=1`) use two's-complement encoding within the `sB` field.
- Runeword items carry two terminated lists: base-item properties, then
  runeword bonus properties.
- Merc runewords should use the canonical biased id form:
  low 12 bits = `runeword_id + 27`, high 4 bits = `5`.

### Socketed sub-items

Socket fillers are separate simple item records with `location=6` and
`col=socket_index`, byte-aligned after the parent. They count toward the
parent's `nr_in_sockets`, not the surrounding `JM` block count. Generated
socket fillers must be at least 11 bytes after padding; shorter fillers are a
known rejection risk.

---

## Checksum and write invariants

After any edit:

1. Update file size at `0x08` (`u32` LE = `len(data)`).
2. Treat bytes `0x0C..0x0F` as zero while computing the checksum.
3. Recompute the rotate-left accumulator over the full file.
4. Write the checksum back to `0x0C..0x0F` as `u32` LE.

Reference implementation:

```python
def calc_checksum(data: bytes) -> int:
    cs = 0
    for i, b in enumerate(data):
        if 0x0C <= i <= 0x0F:
            b = 0
        cs = (((cs << 1) | (cs >> 31)) + b) & 0xFFFFFFFF
    return cs
```

`d2r_chargen/build_lib.py:write_d2s` performs the size and checksum update.
Scanner hard errors block local deployment unless bit-level evidence proves the
scanner is wrong.

---

## Common pitfalls

Pulled from `CLAUDE.md`, fixture notes, and public-safe live findings. Read
those sources for full context — this is just the index.

- **Rule 1:** never hallucinate UIDs / item codes / binary values. Read `data/unique_items.py` etc.
- **Rule 2:** never rebuild a `.d2s` from scratch. Header has interdependent fields. Always start from an existing valid template.
- **Rule 3:** always backup before write. `shutil.copy2(path, path + '.pre_X_bak')`.
- **Rule 4:** run `d2r-chargen scan <name>` after every edit phase, not at the end.
- **Rule 5:** verify checksums match after writing. `stored == calc_checksum(result)`.
- **Rule 6:** merc items need canonical encoding in JM[merc] (col=bodyloc, biased runeword id). Use `equipment_mode: direct` in YAML. The trailing `lf` field is the follower count, not a merc-hired flag.
- **Rule 8:** items must include stat properties — empty unique = wrong-name with zero stats.
- **Rule 10:** write to temp, scan, verify, then overwrite the live file.
- **Rule 12:** edit incrementally. Don't combine stats + skills + items + stash in one shot.
- **Rule 17:** scanner hard errors are deployment blockers — do not classify as false positives without bit-level proof.
- **Rule 21 (NEW 2026-04-25):** preserve the follower block on rebuild. `save.py:rebuild_items` defaults to `preserve_followers=True`. Stripping it silently kills a warlock's bound demon.
- **Character-select visibility needs more than a clean `.d2s`** — manual
  validation showed that companion files, softcore/hardcore category, embedded
  character name, and filename can all affect whether a staged save appears in
  Offline. Use short letter-only embedded names and matching file basenames
  before treating an invisible save as a payload rejection.
- **Stats can't be 0** where class minimum applies — Dex / Energy at 0 produces `Error:7`.
- **Non-simple socketed fillers are broken** — magic jewels (quality=4, location=6) cause "FAILED TO JOIN GAME" with a full save. Merge filler stats into the parent.
- **HC flip preserves merc bytes** — don't zero `0xA8..0xAA` when flipping SC→HC, or merc Hireling.Id is destroyed.
- **stat 188 (skill_tab) param** uses `(class<<3)|tab_within_class` on disk, NOT global tab index.
- **D2R caches saves at session startup** (rule 7) — character-select reload doesn't reread files. User must fully restart D2R.

---

## Cross-references

### Code (current)
- `d2r_chargen/follower_block.py` — follower block parser; field offset constants
- `d2r_chargen/data/monumod_affixes.py` — affix index → name lookup (Phase 1.3)
- `d2r_chargen/scanner.py` — full save scanner; BOUND DEMON section at lines 889-897
- `d2r_chargen/save.py:rebuild_items` (line 579) — main writer; preserves follower block by default
- `d2r_chargen/save.py:set_character_stats` (line 107) — stats section writer
- `d2r_chargen/save.py:set_difficulty` (line 436) — progression byte + act trio writer
- `d2r_chargen/save.py:set_merc_header` (line 500) — merc header writer (0xA3..0xAE)
- `d2r_chargen/build_lib.py:calc_checksum` (line 964) — D2S rotate-left-accumulate checksum
- `d2r_chargen/build_lib.py:write_d2s` (line 980) — file write with size + checksum update
- `d2r_chargen/importer.py` — read-side: `.d2s` → YAML-compatible dict

### Fixtures
- `tests/fixtures/demon_block_a.bin` (pre-rebind)
- `tests/fixtures/demon_block_b.bin` (post-rebind to fallen)
- `tests/fixtures/demon_block_decoded.md` — full Phase 0 decode notes (source of truth for demon payload field meanings)
- `tests/fixtures/lf_count_acceptance_test.md` — Phase 0.4 acceptance findings
- `tests/fixtures/marrowbind_demon_b.d2s` — full warlock save with bound demon
- `tests/fixtures/tempest.d2s` — non-warlock baseline (Sorc lv99 HC, no follower)

### Historical notes
- The original bound-demon planning note is not part of this public repo
  snapshot. Treat this document, public fixture notes, and current code as the
  canonical public references.

---

## Remaining unknown raw fields

These fields remain intentionally raw. Preserve their bytes unless a future
public-safe fixture or manual validation gives bit-level evidence for a narrower
meaning.

1. **Demon payload `+24..+31`** — runtime stats vs monster-derived
   constants is still undecoded. A damaged-demon fixture may distinguish
   current HP from monster-base data. See `demon_block_decoded.md` open
   questions section.
2. **Demon payload `+64..+79` bitfields** — what triggers them? Champion
   roll, paragon, affix-application stage? Both fixtures differ in
   these bytes despite both being lvl-7 fallen-class binds.
3. **Demon payload `+88..+91`** — volatile/runtime-like bytes. Multiple
   2026-05-08 no-combat reloads changed `+89..+91`; whether the four-byte
   range is a checksum, hash, seed, or independent runtime data is unknown.
4. **Demon payload `+95..+115`** — variable data after the embedded `gf`
   payload bytes. The embedded `gf` at `+92..+93` is confirmed payload data,
   not a structural marker; the meaning of `+95..+115` is still raw.
5. **NPC introduction region** — the bytes between the `WS`
   waypoint section and the `gf` stats marker have not been decoded.
   chargen does not edit them; `validate_template` does not check
   them. Decode if a future feature needs to manipulate NPC dialog
   state.
6. **Header `0xA7..0xA8` u16 (merc status bitfield)** — corpus/live values
   include at least `{0,1,3,5,9,10,11,13,15,16,18,21,50}`; chargen writes 0.
   The field remains opaque and should be preserved as a raw u16 unless a
   targeted merc-state experiment proves specific bits.
7. **Header version `0x04..0x07`** — chargen does not validate or
   write this. v105 = D2R RotW. Pre-105 saves are out of scope but the
   format constant is unverified for v100..v104.
