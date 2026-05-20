# D2R `.d2s` Save Format

Status: canonical public save-format reference for this repository.
Last updated: 2026-05-12.

Scope: Diablo II: Resurrected save version 105, including Reign of the
Warlock saves. Earlier save versions are not covered here.

Use this document as an engineering reference for the public tools. It records
only format details that are backed by the current parser/writer, public test
fixtures, or public-safe validation notes. When this document and the code
disagree, treat the code and tests as the source of truth.

`docs/save-format.md` is retained only for older links and points back here.

## Layout

The current writer treats the header as a stable 336-byte region followed by
marker-delimited sections. The body before the first item list is not a single
fixed-width blob; quests, waypoints, NPC-introduction bytes, stats, and skills
must be located by their section structure.

```text
0x000..0x14f  Header, 336 bytes
              Quests: "Woo!" marker, then difficulty quest blocks
              Waypoints: "WS" marker, then difficulty waypoint blocks
              NPC-introduction bytes, no confirmed marker
              Stats: "gf" marker, bit-packed stats, 0x1ff terminator
              Skills: "if" marker, 30 one-byte skill levels
              Character items: "JM" + u16 parent-item count + item records
              Dead-body items: "JM" + u16 parent-item count
              Corpse marker: "jf"
              Merc items: "JM" + u16 parent-item count + item records
              Iron golem: "kf" + u8 flag + optional JM-less item record
              Bridge: 01 00
              Followers: "lf" + u16 count + count * 116-byte payloads
              EOF
```

The `gf` bytes at follower-payload offsets `+92..+93` are payload data, not a
stats marker. Follower parsing must use the fixed payload length.

## Header

All multi-byte integer fields are little-endian unless stated otherwise.
Offsets are hexadecimal.

| Offset | Size | Field | Current handling |
| --- | ---: | --- | --- |
| `0x00..0x03` | u32 | Magic `0x55aa55aa` | Template validation checks this value. |
| `0x04..0x07` | u32 | Version | Version `105` is the current D2R/RotW value. |
| `0x08..0x0b` | u32 | File size | Recomputed before write. |
| `0x0c..0x0f` | u32 | Checksum | Recomputed before write with these bytes treated as zero. |
| `0x14` | u8 | Status flags | Bit 2 is hardcore; bit 3 is died. |
| `0x15` | u8 | Progression | `0x00` Normal, `0x05` Nightmare, `0x0f` Hell. |
| `0x18` | u8 | Class id | See class table below. |
| `0x1b` | u8 | Character level | Stored redundantly with the stats section level. |
| `0xa3..0xa6` | u32 | Merc name seed | Hireling-name RNG seed. |
| `0xa7..0xa8` | u16 | Merc status bitfield | Opaque. Preserve unless a writer intentionally owns it. |
| `0xa9..0xaa` | u16 | Merc id | `Hireling.txt` `Id` value. |
| `0xab..0xae` | u32 | Merc XP | XP or XP-adjacent value. |
| `0x12b..0x13a` | 16B | Character name | Null-padded ASCII. |

### Class Ids

```text
0 Amazon
1 Sorceress
2 Necromancer
3 Paladin
4 Barbarian
5 Druid
6 Assassin
7 Warlock
```

Warlock is a Reign of the Warlock class id and should be treated as version
105+ only.

### Status Byte

| Value | Meaning |
| --- | --- |
| `0x00` | Softcore, alive |
| `0x04` | Hardcore, alive |
| `0x08` | Softcore with died flag set |
| `0x0c` | Hardcore with died flag set; cannot join game |
| `0x24` | Observed hardcore chargen output; high bits are not fully decoded |

D2R v105 characters are implicitly expansion characters. Do not treat bit 3 as
an expansion bit; in current evidence it is the died flag.

### Merc And Difficulty Overlap

The public writer has to account for an overlapping header region:

- Softcore difficulty/act state uses `0xa8..0xaa` as a three-byte act tuple:
  `00 <act_index> 00`, where `act_index = difficulty * 5`.
- Merc id uses `0xa9..0xaa` as a little-endian `Hireling.txt` id.
- Hardcore output skips the softcore act tuple because writing it can corrupt
  the merc id.

When both difficulty and merc header data are written, merc data must be
written after difficulty handling, or the hardcore skip must be preserved.

## Body Sections

### Quests

The quest section starts with `Woo!` and then carries a six-byte header plus
three 96-byte difficulty blocks. Each difficulty block stores 48 quests as
two-byte records. The current quest writer uses `0x01` in the first byte for
quest complete and `0x10` in the second byte for reward collected.

### Waypoints

The waypoint section starts with `WS` and then carries an eight-byte header
followed by three 24-byte difficulty blocks. Each block has a two-byte intro,
a five-byte waypoint bitmask, and padding. The bitmask covers the 39
waypoints in act order.

### NPC Introductions

The bytes between the waypoint section and the `gf` stats marker are not
decoded. They have no confirmed marker and are not edited by chargen. Fixture
testing corrected an earlier assumption: the file contains only one `if`
marker in the relevant region, and that marker belongs to the skills section.

### Character Stats

The stats section starts with `gf`. It is a bit-packed list of character stat
entries:

```text
9-bit stat id
value bits for that stat
...
9-bit terminator 0x1ff
zero padding to the next byte boundary
```

The core stat ids currently owned by the character-stat writer are:

| Id | Name | Bits |
| ---: | --- | ---: |
| 0 | Strength | 10 |
| 1 | Energy | 10 |
| 2 | Dexterity | 10 |
| 3 | Vitality | 10 |
| 4 | StatPoints | 10 |
| 5 | SkillPoints | 8 |
| 6 | HP | 21 |
| 7 | MaxHP | 21 |
| 8 | Mana | 21 |
| 9 | MaxMana | 21 |
| 10 | Stamina | 21 |
| 11 | MaxStamina | 21 |
| 12 | Level | 7 |
| 13 | Experience | 32 |
| 14 | Gold | 25 |
| 15 | StashedGold | 25 |

HP, Mana, and Stamina values are stored multiplied by 256. Other stat ids use
metadata from `d2r_chargen/data/item_stat_cost.py`. Grouped stats with a
positive `np` value encode multiple values under one stat id.

### Skills

The skills section starts with `if` after the stats terminator. It contains
exactly 30 bytes, one byte per skill slot for the character class. Skill ids
are resolved from the class skill base plus the slot index.

### Item Lists

Item lists use `JM` followed by a little-endian u16 count. The count is the
number of parent item records. Socketed sub-items are separate item records
that follow their parent, but they do not increase the surrounding `JM` count.

The current body contains three `JM` lists in order:

1. Character items.
2. Dead-body items, usually count zero in generated output.
3. Merc items.

After the dead-body list, generated files carry a `jf` corpse marker before the
merc item list. Corpus saves prove that `jf` can be absent in some no-merc and
no-follower tails, so parsers must tolerate absence. Writers should preserve
`jf` when it is present and continue emitting it for new generated saves.

### Iron Golem

The iron golem section starts with `kf` and a one-byte flag:

```text
kf 00
kf 01 <JM-less item payload>
```

When the flag is one, the payload is encoded item data without a `JM` list
prefix. Most supported golems are one parent item record. Runeword golems use
the same JM-less block, but the parent is followed immediately by its socket
filler records:

```text
kf 01 <runeword parent> <socket filler 0> ... <socket filler n> 01 00 lf ...
```

Current support can preserve existing active golem payloads and write supported
generated normal, magic, ethereal, set, rare, crafted, socketed-normal, and
runeword golem items for Necromancers with Iron Golem available. Unique parent
payloads are supported only with explicit canonicalization opt-in because D2R
rewrites some bytes on save/exit. Runeword payloads have passed Offline
validation for Insight and Strength: D2R preserved the block length and filler
records while canonicalizing parent bytes. The public-writer Insight runeword
golem was visually confirmed with the expected aura. A magic single-parent
golem carrying `item_aura` Meditation has also joined, saved/exited, preserved
its golem payload, and been visually confirmed, so aura properties can also be
viable without a runeword.

Current scanner output splits golem payloads into record boundaries. The
validated runeword cases canonicalized only the parent record: Insight changed
parent-relative offsets `+20..+44`, Strength changed parent-relative offsets
`+23..+28`, and their socket filler records were byte-identical after
save/exit. The current unique opt-in fixture for The Gnasher changed only
parent-relative offsets `+20..+27`; keep unique payloads
canonicalization-aware rather than byte-preservation promises.

The bridge bytes `01 00` follow the iron-golem flag or item payload. Warlock
bound demons still use `kf 00`, then the bridge, then the `lf` follower block.

### Followers

The follower section starts with:

```text
lf <u16:follower_count> [follower_count * 116-byte payload]
```

For the currently documented follower kind, Warlock bound demon, D2R accepts
count zero or one. Manual validation rejected scanner-clean two-follower
variants. A valid follower count must match the number of complete 116-byte
payloads that follow.

## Item Encoding

The implementation details live in `d2r_chargen/build_lib.py`; this section
lists the invariants that public tools must preserve.

Bits are written least-significant-bit first inside each byte.

### Item Flags

Generated and scanned items use a 32-bit flag field at the start of each item
record.

| Bit | Meaning |
| ---: | --- |
| 4 | Identified |
| 11 | Socketed |
| 16 | Ear item |
| 21 | Simple item |
| 22 | Ethereal |
| 23 | Always set |
| 24 | Personalized |
| 26 | Runeword |

### Common Item Fields

After the flags, item records include:

| Bit range | Field |
| --- | --- |
| `32..34` | D2R extension/version bits; current generated value is `5` |
| `35..37` | Location |
| `38..41` | Body location |
| `42..45` | Grid column, or socket index for socket fillers |
| `46..48` | Grid row |
| `49` | Unknown raw bit; generated items write zero |
| `50..52` | Storage |
| `53+` | Huffman-encoded item type code |

Storage values used by the public tools:

```text
0 equipped or socketed
1 inventory
2 belt
4 cube
5 personal stash
```

Three-character item codes are padded to four characters before encoding.
Simple items stop after the type code plus the observed trailing field used by
generated socket fillers. Extended items continue with item identity, item
level, quality-specific data, optional runeword/personalization/base fields,
and one or more property lists.

### Quality Payloads

| Quality | Payload |
| ---: | --- |
| 1 | Inferior type |
| 2 | None |
| 3 | Superior type |
| 4 | Magic prefix and suffix |
| 5 | Set item id |
| 6 | Rare names and affix slots |
| 7 | Unique item id |
| 8 | Crafted rare-style names and affix slots |

### Property Lists

Item property lists have the same frame shape as character stats: 9-bit stat
id, stat-specific value bits, and a `0x1ff` terminator. Their metadata comes
from `item_stat_cost.py`, not the character-stat table.

Important differences from character stats:

- Item values use `sB` as the value width.
- Values are adjusted by `sA`, except for charge-style `e=3` stats.
- Signed stats (`sS=1`) use two's-complement encoding inside the `sB` field.
- Runeword items carry two terminated property lists: base-item properties,
  then runeword bonus properties.
- Merc runewords use the canonical biased id form: low 12 bits are
  `runeword_id + 27`; high 4 bits are `5`.

### Socketed Sub-Items

Socket fillers are item records with `location=6` and `col=socket_index`.
They are byte-aligned after the parent item, count toward the parent's
`nr_in_sockets`, and do not count toward the surrounding `JM` parent count.
Generated simple socket fillers should be at least 11 bytes after padding;
shorter fillers are a known rejection risk.

## Bound-Demon Follower Payload

The only currently documented 116-byte follower payload is the Warlock bound
demon payload. The public parser exposes these high-confidence fields:

| Relative offset | Size | Field |
| --- | ---: | --- |
| `+0` | u16 | Follower-kind tag; observed invariant `0x0018` |
| `+4` | u16 | `monster_hcidx`; zero-based `MonStats.txt` row index |
| `+6` | u32 | Monster seed |
| `+52` | u32 | Bind Demon metadata; not the effective skill level |
| `+80..+86` | 7B | MonUMod affix indices |
| `+92..+93` | 2B | Embedded ASCII `gf` payload bytes |

The `monster_hcidx` field uses the zero-based row index in `MonStats.txt`; it
does not use the separate `*hcIdx` column. A known example is Black Lancer
`cr_lancer9`, which uses payload value `724`.

The seven affix bytes at `+80..+86` are raw `MonUMod.txt` indices. They are not
a u32. Natural over-cap validation showed that the vector is seven bytes, not
five; `+85/+86` can carry overflow affixes.

`+52` is persisted bind metadata. Live binds at hard skill levels 1, 5, 10,
15, and 20 all saved this field as `7`, so it must not be used as the
effective Bind Demon skill level. Player-facing generation derives
skill-granted affixes from the effective skill level instead.

### Bound-Demon Authoring Rules

Current public generation is template-derived. A local template provides the
unknown runtime slices and seed state. The public writer may override
high-confidence fields such as monster row, bind metadata, and affix bytes
when that target has validation behind it. This is not template-free synthesis.
`template_path` may point either at a `.d2s` file with one bound-demon follower
or at an extracted raw 116-byte payload produced by
`tools/d2s_demon_template_inspect.py --extract-payload`.

Known stable rules:

- Preserve the fixed 116-byte payload length for known bound-demon records.
- Preserve the embedded `gf` bytes as payload data.
- Preserve template `monster_seed` by default. Same-row/same-affix seed
  evidence shows seed changes can change the visible generated name and may
  change Aura Enchanted flavor, so seed/name/aura authoring remains
  unsupported unless a named validated package owns those fields.
- Treat `+89..+91` as volatile runtime bytes.
- Preserve `+94 == 06` for known 116-byte payloads until variable-length
  follower records are decoded.
- Treat `+114/+115 == f0 1f` as a same-model Fallen terminator unless a future
  original capture proves a broader rule.
- Keep source affixes separate from skill-granted affixes in YAML semantics.
- Fanaticism is source/aura-flavor input; it is not a Bind Demon threshold
  affix by itself.

Known accepted examples are target-specific, not universal model-synthesis
proofs:

- Council Member row `347` worked from the current clean Fallen shell with
  `monster_hcidx` only.
- Black Lancer row `724` worked from the current clean Fallen shell with
  `monster_hcidx` only for an empty-affix payload.
- Visible source-style labels on Black Lancer required compatible template
  context.
- Fanaticism plus Aura Enchanted exposed the visible aura path only for the
  documented support set.

## Iron Golem And Bound Demon Interaction

Current evidence covers normal single-class cases:

- Necromancer Iron Golem saves use `kf 01` plus a JM-less item payload.
- Warlock bound-demon saves use `kf 00`, bridge `01 00`, and `lf 01` with a
  bound-demon payload.
- A non-Warlock save can carry a structurally valid Warlock follower block
  without immediate rejection, but D2R does not instantiate the borrowed demon
  and strips it back to `follower_count=0` on save/exit.
- Cross-class Iron Golem acceptance is not supported; the public writer keeps
  generated `iron_golem:` authoring on the Necromancer-only path.

Combined `kf 01` plus bound-demon authoring remains unsupported.

## Checksum And Write Invariants

After any edit, the writer must:

1. Write the byte length at `0x08..0x0b`.
2. Compute the checksum over the whole file with `0x0c..0x0f` treated as zero.
3. Write the checksum at `0x0c..0x0f`.
4. Scan the result before promotion.

Reference checksum:

```python
def calc_checksum(data: bytes) -> int:
    cs = 0
    for i, b in enumerate(data):
        if 0x0C <= i <= 0x0F:
            b = 0
        cs = (((cs << 1) | (cs >> 31)) + b) & 0xFFFFFFFF
    return cs
```

Scanner hard errors block deployment unless there is bit-level proof that the
scanner is wrong.

## Operational Rules For Save Editing

These are format-safety rules, not project-management notes:

- Start from an existing valid `.d2s`; do not rebuild a save from scratch.
- Write to staging first, then scan, then promote only the scanned output.
- Back up the target save family before touching local saves.
- Edit one risky area at a time.
- Fully exit and relaunch D2R after file changes; character select does not
  reliably reload save files.
- Keep the embedded character name and filename aligned when staging test
  saves.
- Prefer short letter-only character names for manual visibility checks.
- Preserve follower blocks on item rebuild unless the operation intentionally
  removes the follower.
- Do not zero `0xa8..0xaa` while flipping softcore/hardcore state; that can
  corrupt merc id bytes.
- Generated unique and set items need encoded stat properties; an item id alone
  can produce the right displayed name with zero stats.
- Non-simple socket fillers remain a rejection risk; merge filler stats into
  the parent unless the specific filler shape has been validated.
- Stat 188 (`skill_tab`) stores `(class << 3) | tab_within_class`, not a global
  tab index.

## Remaining Raw Fields

Preserve these bytes unless a future public-safe fixture, code change, or
manual validation result narrows their meaning.

| Region | Current status |
| --- | --- |
| NPC-introduction bytes | Undecoded bytes between waypoints and stats. |
| Header `0xa7..0xa8` | Opaque merc status bitfield. Observed values include `0`, `1`, `3`, `5`, `9`, `10`, `11`, `13`, `15`, `16`, `18`, `21`, and `50`. |
| Header version | Version 105 is current; pre-105 behavior is out of scope. |
| Demon `+24..+31` | Runtime stats or monster-derived constants; not decoded. |
| Demon `+44/+48` | Writer-controllable player-count-shaped percent fields for one row-20 shell. Matched p1/p4/p8 captures produced `0`, `150`, and `350`, but healthy runtime replays and isolates did not prove these bytes control visible HP, damage, AR, defense, or survivability by themselves. |
| Demon `+64..+79` | Bitfield/context slice; source-affix activation evidence exists, but individual bits are not decoded. |
| Demon `+88..+91` | Volatile/runtime-like bytes; copied values can be rewritten and should not be authored. |
| Demon `+94..+115` | Post-`gf` payload bytes. Some subranges are health-like or context-like, but current isolates do not prove a standalone visible-strength control. |

## Code And Fixture Cross-References

Use these files before changing writer behavior:

- `d2r_chargen/save.py`
- `d2r_chargen/build_lib.py`
- `d2r_chargen/importer.py`
- `d2r_chargen/scanner.py`
- `d2r_chargen/follower_block.py`
- `d2r_chargen/data/item_stat_cost.py`
- `d2r_chargen/data/monumod_affixes.py`
- `tests/fixtures/demon_block_decoded.md`
- `tests/fixtures/lf_count_acceptance_test.md`
