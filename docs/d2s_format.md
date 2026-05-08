# D2R `.d2s` Save File Format

> **Status:** living document. Last updated 2026-04-25. Cross-reference
> for `d2r_chargen/` parsers + writers. When fields are added or
> reinterpreted, update both this doc and the associated memory file
> (`<agent memory dir>/reference_*.md`).
>
> **Scope:** D2R version 105 (Reign of the Warlock expansion) on this
> Steam Deck install. PC version. Pre-105 saves are out of scope.
>
> **Trust hierarchy:** code in `d2r_chargen/` > fixtures under
> `tests/fixtures/` > this doc > memory files > everything else. When
> in doubt, read the source.

---

## Top-level layout

```
+--------------------------------------------------------------+
| Header (0x00..0x14F, 336 bytes — fixed-size)                 |
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
| Iron golem flag   u8 (always 0 in current chargen output)    |
| Bridge   `\x01\x00` (constant 2 bytes)                       |
| Followers   `lf<u16:count>` [+ count × 116B payload]         |
| EOF                                                          |
+--------------------------------------------------------------+
```

The pre-`JM` region is not strictly fixed — Quests/Waypoints/Stats are
variable-length sections terminated by their own end-markers. The
header up to 0x14F is the only region with stable byte offsets.

---

## Header (0x00..0x14F, 336 bytes)

All multi-byte integers are little-endian unless noted. Offsets given
in hex. "Confirmed" = code reads/writes the offset directly; "memory" =
backed by a memory file but not currently exercised by `d2r_chargen/`.

| Offset      | Size   | Field                          | Source / verification |
|-------------|--------|--------------------------------|-----------------------|
| `0x00..0x03`| u32    | Magic = `0x55AA55AA`           | `build_lib.py:741` (validate_template) |
| `0x04..0x07`| u32    | Version (105 for D2R RotW)     | format constant; not actively validated by chargen |
| `0x08..0x0B`| u32    | File size (LE u32, recomputed on write) | `build_lib.py:write_d2s` line 991 |
| `0x0C..0x0F`| u32    | Checksum (LE u32, zeroed during calc) | `build_lib.py:calc_checksum` lines 964-977 |
| `0x14`      | u8     | Status flags — bit 2 = hardcore, bit 3 = died | `scanner.py:577-582`, `save.py:444`, memory `reference_d2s_binary.md` |
| `0x15`      | u8     | Progression: `0x00` Normal, `0x05` NM, `0x0F` Hell | `save.py:443`, `importer.py:46-49` |
| `0x18`      | u8     | Class id (0=Amazon … 7=Warlock — see below) | `save.py:555`, `importer.py:43` |
| `0x1B`      | u8     | Character level (1..99)        | `save.py:206`, `importer.py:44` |
| `0xA3..0xA6`| u32    | Merc name seed (RNG for Hireling.NameFirst/NameLast) | `save.py:525`, memory `reference_merc_d2s_offsets.md` |
| `0xA7..0xA8`| u16    | Merc status bitfield (opaque; chargen writes 0) | `save.py:526`. Live values seen: `{0,1,9,15}`. Semantics TBD. |
| `0xA9..0xAA`| u16    | `Hireling.txt` Id column (class+element+difficulty) | `save.py:527`, memory `reference_merc_d2s_offsets.md` |
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
| `0x24`| HC chargen output (status byte from Marrowbind HC flip) | feedback `feedback_hc_status_byte.md`. The high nibble bits are not fully decoded. |

In D2R v105 every character is implicitly expansion. There is no
separate "expansion" bit (an earlier doc claimed bit 3 was that — it's
the died flag). See `reference_d2s_binary.md` for the corrected
analysis.

### Merc / Difficulty overlap

`save.py:set_difficulty` writes 3 bytes at `0xA8..0xAA` for SC chars
(act-byte trio). `save.py:set_merc_header` writes a u16 at `0xA9..0xAA`
(Hireling.Id). For HC characters chargen deliberately skips the act
trio (rule 446 in save.py) — `feedback_hc_act_byte.md` documents that
writing those bytes for HC corrupts the merc Hireling.Id. Order
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
- Verified via `tests/fixtures/tempest.d2s` 2026-04-25: only ONE `if`
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
(the `cB` and `vS` columns). See `feedback_grouped_stats.md` for the
"grouped stats" pitfall (stats with `np>0` encode multiple values
under one stat id).

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
  (col=bodyloc, biased runeword id, lf_count=0)
- Source: `save.py:rebuild_items:644-645,690-691`, `importer.py:220-241`

### 10. Iron golem marker — `kf`

- Marker: 2 bytes `kf`
- Followed by u8 has_golem flag (0 or 1)
- If flag=1: a single golem item (JM-less item bitstream, encoded same as char items but without the JM count prefix)
- chargen always writes `kf 00` (no iron golem) — `save.py:697-698`

### 11. Bridge — constant `\x01\x00`

- 2 bytes immediately after the iron-golem flag byte
- Has been `\x01\x00` in every D2R v105 save examined — purpose unknown
- chargen writes it unconditionally (`save.py:698`)
- Combined with the preceding `kf 00`, this is the 5-byte gap from
  `kf` to `lf`: `kf 00 01 00` + `lf`. Verified across 19 saves
  (`scanner.py:884-887`).

### 12. Followers — `lf<u16:count>` (+ optional payload)

- Marker: 2 bytes `lf`
- u16 LE `follower_count`
- If `follower_count >= 1`: `follower_count × 116B` payload follows (see § Follower section)
- Source: `save.py:rebuild_items:699-700`, `d2r_chargen/follower_block.py`

### 13. EOF

In all current Marrowbind/Tempest saves the file ends immediately
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

For the only currently-known follower kind (warlock bound demon), live D2R
accepts N=0 or N=1. On 2026-05-08, D2R rejected two scanner-clean N=2 probes:
one with the same 116-byte payload duplicated and one with two different known
116-byte payloads. Both failed to join game and neither save was rewritten.

### Demon payload (116 bytes)

High-confidence fields parsed by `d2r_chargen/follower_block.py`:

| Offset (rel) | Size | Field             | Notes |
|--------------|------|-------------------|-------|
| `+0`         | u16  | section/follower-kind tag | invariant `0x0018` across binds; likely "bound demon" type marker |
| `+4`         | u16  | `monster_hcidx`   | MonStats.txt row index (e.g. `20` = `fallen2`) |
| `+6`         | u32  | `monster_seed`    | random instance seed; rerolls every bind |
| `+52`        | u32  | `bind_demon_level`| player's Bind Demon skill level at bind time |
| `+80..+84`   | 5B   | `affix_indices`   | MonUMod.txt indices, raw bytes (NOT a u32) |
| `+92..+93`   | 2B   | ASCII `gf`        | **DATA, not a section marker.** Same byte position in both fixtures. The decoder must use a fixed 116B length, not a `gf`-terminated slice. |

Per-byte decode of all 116 bytes (including medium and
low-confidence fields like `+24/+28` runtime stats and
`+64..+79` bitfields) is in `tests/fixtures/demon_block_decoded.md`.
Do **not** duplicate that table here — it changes as new fixtures
arrive.

2026-05-08 live check: `probewldemon` loaded with the copied bound demon
visible. D2R rewrote the save on exit and preserved `follower_count=1` with
exactly 116 trailing payload bytes; the embedded `gf` remained data inside the
payload, not a new section marker.

2026-05-08 live check: `probewlalt` loaded with a different known 116-byte
payload (`tests/fixtures/demon_block_a.bin`) and spawned a demon. After
save-and-quit, D2R preserved `follower_count=1`, the 116-byte payload length,
and the high-confidence identity fields, but rewrote payload bytes `+89..+91`
and `+95..+97`. Treat those bytes as runtime/hash-like until further fixtures
pin them down.

A second `probewlalt` reload/save on 2026-05-08 kept the demon and the same
116-byte payload shape. Bytes `+95..+97` stayed stable after the first rewrite,
while `+89..+91` changed again. Treat `+89..+91` as volatile runtime/hash bytes.

A third reload/save again kept the demon and the valid block shape. Bytes
`+95..+97` stayed stable and `+89..+91` changed to `00 00 00`.

### Cross-class behavior

Phase 0.4 found D2R loads non-warlock saves carrying a follower block
without rejection (a Sorceress save with a borrowed Marrowbind demon
payload entered the game cleanly). The 2026-05-08 `probesorc` live check
confirmed D2R does NOT class-gate the follower block at file load, but it also
does not instantiate the borrowed demon for Sorceress. On save-and-quit, D2R
stripped the follower block back to `follower_count=0`.

---

## Iron golem section (when present)

Conditionally written as `kf <u8:has_golem> [golem_item]`. In every
D2R v105 save examined before the live probe, chargen wrote `kf 00` (no iron
golem). Saves that come from in-game with an active iron golem (Necromancer Iron
Golem skill) carry `kf 01` followed by a JM-less item bitstream. The 2026-05-08
`probenecro` capture wrote `kf 01`, had `kf_to_lf_gap=58`, and carried 55 bytes
of golem item payload before `lf`. A fresh reload preserved the in-game Iron
Golem and kept the same 55-byte payload
(`sha1=2f582d487d12a70b8c5cdc1da3e371b2c302c390`) after save-and-quit.
A second reload showed the golem again and left the on-disk save unchanged.
Recasting Iron Golem from a different item produced `kf_to_lf_gap=29` with a
26-byte golem payload
(`sha1=2b0cddc4fb4d6f53db12fa589571c864e8e40e61`), confirming the section
contains a variable-length encoded item rather than a fixed-size golem record.
Reloading that second golem preserved the length but changed only payload byte
`+1` from `0x20` to `0x00`, suggesting a runtime/state bit near the start of
the golem item encoding.
A subsequent reload/save preserved the canonicalized 26-byte payload
byte-for-byte.

For warlocks with bound demons: `kf 00` is still written, the bridge
`\x01\x00` follows, and the `lf` follower block carries the demon.
**The `gf` ASCII at offset +92 of the demon payload is unrelated to
the iron golem section.** [unconfirmed: whether D2R ever writes both
an iron golem and a bound demon for the same character — RotW gives
the bound-demon skill only to warlocks, who don't have iron golem.]

---

## Item encoding (overview)

Full bitstream spec lives in `d2r_chargen/build_lib.py` (`build_item`,
`encode_socketed_rune`, `BitWriter`). High level:

- 14 byte fixed header (`JM` magic + flags u32 + per-item header bits)
- Variable bitstream: type code, ilvl, quality, uid, gem/rune id,
  socket count, properties (per `item_stat_cost.py` cB/vS encoding),
  property terminator `0x1FF`
- **Storage location** (bits 35-37 of the bitstream): `0=equipped
  1=inventory 2=belt 4=cube 5=personal_stash 6=socket_filler`
- Socket fillers (`location == 6`) are NOT counted in the JM u16 count
  — only parent items are. See `save.py:rebuild_items:629-636` for
  the count_parents() helper, and CLAUDE.md rule 8 + 15 for filler
  pitfalls.

### Item flags (u32 at item start)

| Bit | Meaning           | Notes |
|-----|-------------------|-------|
| 11  | Socketed          | Item has sockets (filled or empty) |
| 21  | Simple item       | No properties bitstream (rune, gem, etc.) |
| 22  | Ethereal          | |
| 26  | Runeword          | Item carries runeword data |

Source: `importer.py:254-258`.

---

## Common pitfalls

Pulled from CLAUDE.md rules + memory feedback files. Read those
sources for full context — this is just the index.

- **Rule 1:** never hallucinate UIDs / item codes / binary values. Read `data/unique_items.py` etc.
- **Rule 2:** never rebuild a `.d2s` from scratch. Header has interdependent fields. Always start from a server-synced template.
- **Rule 3:** always backup before write. `shutil.copy2(path, path + '.pre_X_bak')`.
- **Rule 4:** run `/d2rdoctor` after every edit phase, not at the end.
- **Rule 5:** verify checksums match after writing. `stored == calc_checksum(result)`.
- **Rule 6:** merc items need canonical encoding in JM[merc] (col=bodyloc, biased runeword id, lf_count=0). Use `equipment_mode: direct` in YAML.
- **Rule 8:** items must include stat properties — empty unique = wrong-name with zero stats.
- **Rule 10:** write to temp, scan, verify, then overwrite the live file.
- **Rule 12:** edit incrementally. Don't combine stats + skills + items + stash in one shot.
- **Rule 17:** scanner hard errors are deployment blockers — do not classify as false positives without bit-level proof. (`feedback_scanner_hard_errors.md`.)
- **Rule 21 (NEW 2026-04-25):** preserve the follower block on rebuild. `save.py:rebuild_items` defaults to `preserve_followers=True`. Stripping it silently kills a warlock's bound demon.
- **Character-select visibility needs more than a clean `.d2s`** — a Bazzite
  live-test session on 2026-05-08 found staged probe saves that scanned cleanly
  but did not appear in Offline. Adding copied companions (`.ctl`, `.key`,
  `.map`, `.ma0`) and matching the throwaway character's SC/HC status category
  was still insufficient. Same-install letter-only clones appeared, while names
  containing the digit `2` did not. Use letter-only embedded names and matching
  file basenames before treating an invisible probe as a payload rejection; the
  renamed `probe...` saves appeared in Offline.
- **Stats can't be 0** where class minimum applies — Dex / Energy at 0 produces `Error:7`. (`feedback_stats_nonzero.md`.)
- **Non-simple socketed fillers are broken** — magic jewels (quality=4, location=6) cause "FAILED TO JOIN GAME" with a full save. Merge filler stats into the parent. (`feedback_jewel_filler.md`.)
- **HC flip preserves merc bytes** — `feedback_hc_flip_merc_preserve.md`: don't zero `0xA8..0xAA` when flipping SC→HC, or merc Hireling.Id is destroyed.
- **stat 188 (skill_tab) param** uses `(class<<3)|tab_within_class` on disk, NOT global tab index. (`reference_skill_tab_encoding.md`.)
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

### Memory files (`<agent memory dir>/`)
- `reference_d2s_binary.md` — status byte + name offset notes
- `reference_merc_d2s_offsets.md` — merc disk layout 0xA3..0xAE
- `reference_skill_tab_encoding.md` — stat 188 binary encoding
- `feedback_grouped_stats.md` — np>0 stat encoding pitfall
- `feedback_jewel_filler.md` — non-simple filler ban
- `feedback_hc_status_byte.md` — chargen HC flip
- `feedback_scanner_hard_errors.md` — never-dismiss-as-false-positive

### Plans
- `docs/superpowers/plans/2026-04-25-bound-demon-save-block.md` — the plan that produced this doc

---

## Open questions

These are unresolved as of 2026-04-25. Updating them is encouraged when
new fixtures land.

1. **Demon payload `+24..+31`** — runtime stats vs monster-derived
   constants? Need a damaged-demon fixture (Phase 0.3 not done) to
   distinguish current-HP from monster-base. See
   `demon_block_decoded.md` open questions section.
2. **Demon payload `+64..+79` bitfields** — what triggers them? Champion
   roll, paragon, affix-application stage? Both fixtures differ in
   these bytes despite both being lvl-7 fallen-class binds.
3. **Demon payload `+88` u32** — looks like a checksum or hash. Is it
   over the preceding 88 bytes, or independent runtime data?
4. **Demon payload `+95..+115`** — variable post-`gf` payload. Last
   2 bytes `f0 1f` match across fixtures (likely terminator); middle
   bytes vary. Could be a second follower record, a hash, or
   golem-style item data. RotW-specific or repurposed.
5. **`gf` ASCII at +92 of demon payload** — is it ever a real section
   marker, or always payload data? Current code treats it as data
   exclusively; Phase 0.4 saw no post-payload golem section.
6. **NPC introduction region** — the bytes between the `WS`
   waypoint section and the `gf` stats marker have not been decoded.
   chargen does not edit them; `validate_template` does not check
   them. Decode if a future feature needs to manipulate NPC dialog
   state.
7. **Cross-class follower block** — D2R loads non-warlock saves with a
   follower block but does the demon actually spawn in-game for a
   non-warlock? Out of scope for v1. Smoke test on Sorc + borrowed
   demon if/when needed.
8. **Header `0xA7..0xA8` u16 (merc status bitfield)** — observed values
   `{0, 1, 9, 15}` across saves; chargen writes 0. Semantics unknown.
   Could be (active/dismissed/dead) flags or RNG cache.
9. **Header version `0x04..0x07`** — chargen does not validate or
   write this. v105 = D2R RotW. Pre-105 saves are out of scope but the
   format constant is unverified for v100..v104.
