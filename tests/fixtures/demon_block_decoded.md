# Bound Demon Save Block — Field-by-field decode

**Source:** Diff between Fixture A (pre-rebind, monster unknown) and Fixture B (post-rebind, fallen). Both 116 bytes long, captured from live Marrowbind.d2s saves on 2026-04-25.

**Layout:** byte-aligned offsets from the start of the post-`lf<count>` payload (i.e. the byte that follows the 2-byte `lf` marker + 2-byte `follower_count` u16).

| Offset | Size | A value | B value | Diff? | Interpretation |
|--------|------|---------|---------|-------|----------------|
| +0  | u16 | 0x0018 (24)   | 0x0018 (24)   | same | Section/follower-kind tag — invariant across binds. Likely "bound demon" type marker. |
| +2  | u16 | 2             | 1             | diff | Rebind generation counter, OR follower index. Decremented? Investigate. |
| +4  | u16 | 42            | 20            | diff | **Monster hcIdx.** B=20=`fallen2` matches user's "I bound a fallen" (vanilla MonStats.txt row 22). |
| +6  | u32 | 0x000A5BDA (678874) | 0x0018281B (1583131) | diff | **Monster random seed** (4-byte LE). Same role as merc seed at header 0xA8. Re-rolls every bind. |
| +10 | u16 | 0x0010 (16)   | 0x0010 (16)   | same | Invariant — likely follower flags or fixed alignment marker. |
| +12 | u32 | 0x00000302    | 0x00000302    | same | Invariant — bind level encoding? 0x0302 = 770. Could be `(skill_level << 8) \| bind_demon_par_index` or similar. |
| +16 | u32 | 0             | 0             | same | Reserved / padding. |
| +20 | u32 | 3             | 3             | same | Invariant — likely affix count (3 mandatory affixes at lvl 15+: Strong/Fast/Spectral). |
| +24 | u32 | 107           | 2             | diff | Monster-derived runtime stat — possibly **current HP** or current resource, or a monster-specific param (fallen has different base than whatever A was). |
| +28 | u32 | 87            | 85            | diff | Monster-derived runtime stat — slightly different scale. Possibly XP-to-next or attack rating. |
| +32..+43 | 12B | zeros | zeros | same | Reserved / padding block. |
| +44 | u32 | 100           | 100           | same | Invariant — likely **HP percent** (full health ⇒ 100). Will probably change in a damaged-demon fixture (Phase 0.3). |
| +48 | u32 | 100           | 100           | same | Invariant — paired with +44. **Mana/MP percent** OR max-HP-cap normalized to 100. |
| +52 | u32 | 7             | 7             | same | **Persisted bind metadata**. Completed binds have repeatedly saved `7`; this is not the effective Bind Demon skill level. |
| +56 | u32 | 2             | 2             | same | Invariant — possibly tier counter. |
| +60 | u32 | 3             | 3             | same | Invariant — possibly affix-tier count (3 = Strong/Fast/Spectral active at this skill level). |
| +64..+71 | 8B | zeros | `00 00 00 00 00 01 00 01` | diff | Bitfield — turned ON in B. Possibly affix-applied flags or champion-rolled flags. |
| +72..+79 | 8B | zeros | `01 00 00 00 00 00 00 00` | diff | Bitfield — bit 0 of byte 0 set in B. Possibly status/state byte. |
| +80..+86 | 7B | `1b 1e 05 1c 06 00 00` | `19 06 05 1b 1e 00 00` | diff | **Affix indices** (refer to MonUMod.txt). Both contain `5` (Strong), `1B` (Spectral Hit), `1E` (Aura Enchanted) — the par2/par3/par4/par5 mandatory affixes from Skills.txt:384. The 6th/7th bytes are extra MonUMod slots that are zero in these old fixtures. Order is roll order, not declaration order. |
| +87 | 1B | zero | zero | same | Padding. |
| +88 | u32 | 0xFED42200    | 0x03B8C400    | diff | Looks like a checksum or hash. Both have a non-zero high-entropy value. |
| +92..+93 | 2B | `gf`         | `gf`         | same | Embedded payload data, not a section delimiter. Live 2026-05-08 rewrites kept the save ending immediately after the 116-byte demon payload, so decoders must not split on these bytes. |
| +94 | u8  | 0x06          | 0x06          | same | Byte after `gf`. In vanilla D2 this is `has_golem` (0/1). Here it's 6 — **NOT a vanilla golem flag**. Could be a count, a follower-state byte, or a RotW-specific opcode. |
| +95..+115 | 21B | `16 8c df 06 0e d0 7f c3 0d 30 d0 02 00 00 68 20 34 be 01 f0 1f` | `d0 29 48 00 0e a0 53 90 00 30 c0 02 00 00 68 80 3d 51 00 f0 1f` | diff | Encoded payload after `gf`. Last 2 bytes (`f0 1f`) match → likely a fixed terminator. The middle is variable. Could be golem item (encoded `JM`-less), a second follower record, or a hash. |

## High-confidence interpretations (will drive Phase 1.2 parsers)

- `+4 u16` → **monster_hcidx** (matches MonStats.txt row index)
- `+6 u32` → **monster_seed** (4-byte LE random instance seed)
- `+52 u32` → **bind_demon_level** / persisted bind metadata (not effective skill level)
- `+80..+86` → **affix_indices** (7 bytes, MonUMod.txt indices)
- `+92..+93` → embedded ASCII `gf` payload bytes, not a structural marker

## Medium-confidence (need more fixtures)

- `+2 u16` → **bind_generation** counter (incremented each rebind, OR decremented)
- `+44 u32` → **hp_percent** (current HP %, would change with a damaged-demon fixture)
- `+48 u32` → **mp_percent** OR **max_hp_normalized** (to be confirmed with damage test)

## Open questions (Phase 0.3 + Phase 1.2 will resolve)

- `+24 u32` and `+28 u32` change between binds — what aspect of the monster do they encode? Likely runtime stats (HP/AR/level) — needs damaged-demon fixture or known-monster-stats cross-reference.
- `+64..+79` bitfields — what triggers them? Champion roll? Paragon? Affix-application stages?
- `+88 u32` — is it a hash of the preceding bytes, or independent runtime data?
- `+95..+115` post-embedded-`gf` payload — RotW-specific/runtime data until proven otherwise.

## Confirmed invariants for the writer

The plan's Phase 3.1 (round-trip preserve) only needs to copy bytes verbatim — none of this needs reconstruction. Phase 3.2 (build from YAML template) just splices a fixture's block into a new save, so the field meanings above are reference, not requirements for v1.

## Cross-reference

- Skills.txt:384 (Bind Demon) — par2..par5 affix indices: `(lvl>=5)?5:0`, `(lvl>=10)?6:0`, `(lvl>=15)?27:0`, `(lvl>=20)?30:0`. Later natural-bind tests confirmed these threshold affixes derive from effective Bind Demon level, while payload `+52` remains bind metadata rather than the current effective level.
- monpet.txt — `bindchancecalc` is fixture-irrelevant (only affects whether the bind succeeds, not what's stored).
- MonUMod.txt — affix index → name mapping (Phase 1.3 builds the lookup table).
