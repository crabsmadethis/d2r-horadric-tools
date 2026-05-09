# Bound Demon Chargen Roadmap

Status: research plan for moving from template cloning to robust Reign of the
Warlock bound-demon generation.

## Goal

Support this kind of YAML without relying on a copied live fixture for every
case:

```yaml
bound_demon:
  monster: fallen
  affixes:
    - Extra Strong
    - Extra Fast
    - Spectral Hit
  bind_level: 20
```

The safe v1 remains template cloning:

```yaml
bound_demon:
  template: marrowbind_demon_b
```

The robust target is not just "write five bytes." The 2026-05-08 `bindtank`
capture proved a demon can visibly retain Aura Enchanted, Spectral Hit, and
lightning immunity even when those properties are absent from the five decoded
MonUMod bytes at payload `+80..+84`.

## Current Evidence

High-confidence payload fields:

| Offset | Meaning | Writer confidence |
| --- | --- | --- |
| `+0..+1` | follower kind tag `0x0018` | fixed |
| `+4..+5` | `monster_hcidx` | needs mutation test |
| `+6..+9` | monster seed | likely arbitrary u32, needs mutation test |
| `+52..+55` | Bind Demon level | needs mutation test |
| `+80..+84` | five MonUMod affix bytes | needs mutation test |
| `+89..+91` | volatile runtime bytes | do not author; D2R rewrites |
| `+92..+93` | embedded `gf` payload data | fixed data, not a section |

Live facts:

- D2R accepts one Warlock bound-demon payload of exactly 116 bytes.
- D2R rejected two valid-looking `follower_count=2` saves at game join.
- `probewldemon`, `probewlalt`, and `bindtank` all survived no-combat
  reload/save with stable identity fields.
- The repeated volatile field is `+89..+91`; it can change to or from
  `00 00 00`, so zero is not a canonical endpoint.
- The `bindtank` high-property demon decoded to affixes `05 09 07 19 06`
  while in-game still showed Aura Enchanted, Spectral Hit, and lightning
  immunity after reload.

## Robust Support Shape

Implement demon support in tiers:

| Tier | YAML | Meaning | Promotion gate |
| --- | --- | --- | --- |
| 1 | `template: NAME` | Copy a known 116-byte payload | Already supported |
| 2 | `template: NAME` plus safe field overrides | Edit only proven fields like affixes or bind level | Each edited field survives live reload/save |
| 3 | `monster_hcidx`/`monster` with template-derived runtime fields | Change monster identity while borrowing the rest of a compatible template | Live test proves model/properties follow the edited monster and save persists |
| 4 | fully synthesized payload | Build all 116 bytes without a template | Only after unknown fields are decoded or proven ignorable |

Do not expose a normal `bound_demon: {monster, affixes}` writer until Tier 2
and Tier 3 tests are boring: visible demon, join succeeds, save/quit persists,
reload shows expected model/properties, and the scanner diff shows only known
volatile bytes changed.

## Questions To Answer

### Q1: Do the five affix bytes control visible properties?

Test with the same `bindtank` high-property payload and only change
`+80..+84`.

Characters:

- `demclone`: unmodified cloned control.
- `demauras`: affixes changed to `05 09 07 1b 1e`
  (Extra Strong, Fire Enchanted, Cursed, Spectral Hit, Aura Enchanted).
- `demblank`: affixes changed to `00 00 00 00 00`.

Expected signal:

- If `demblank` still shows the same properties, visible properties are mostly
  elsewhere or implicit.
- If `demauras` changes the tooltip/display and persists, Tier 2 affix editing
  is viable.
- If D2R rewrites the five bytes back, the affix list is derived/canonicalized.

### Q2: Does `monster_hcidx` control demon identity by itself?

Character:

- `demfalln`: same high-property payload, but `monster_hcidx=20`
  (`fallen2` in the existing fixture notes).

Expected signal:

- If the demon becomes a Fallen and persists, Tier 3 monster identity editing
  is plausible.
- If it keeps the original model or fails to join, other runtime/tail fields
  are coupled to the monster.

### Q3: Does Bind Demon level affect persisted properties?

Character:

- `demlvl`: same high-property payload, but `bind_demon_level=20`.

Expected signal:

- If D2R rewrites `+52` or visible properties do not change, the field is
  mostly historical display/state.
- If properties change and persist, the level participates in runtime
  reconstruction.

### Q4: Can we keep collecting natural high-property captures?

Character:

- `demonlab`: clean no-bound-demon tank for binding fresh monsters without
  overwriting `bindtank`.

Expected signal:

- Each natural capture gives a real payload where visible properties are known.
  These are the best fixtures for decoding the unknown slices and any
  non-MonUMod properties.

## Live Test Protocol

For each probe character:

1. Confirm it appears in Offline.
2. Join game.
3. Observe whether a demon appears.
4. Record visible model and properties.
5. Save and exit without fighting.
6. Tell Codex the result.

Codex then pulls the save, runs:

```bash
python3 tools/d2s_corpus_scan.py <save>
python3 tools/d2s_demon_payload_diff.py <pre> <post>
D2R_SAVES=<capture-dir> python3 -m d2r_chargen scan <name>
```

Promotion criteria for a field:

- join succeeds
- demon appears
- expected visible behavior is observed
- post-save checksum is valid
- follower payload is still exactly 116 bytes
- reload/save changes only known volatile bytes, or the new canonicalized bytes
  are documented and repeatable

## Current Test Batch

The first batch is intentionally letter-only:

| Character | Purpose |
| --- | --- |
| `demonlab` | clean tank for new natural demon captures |
| `demclone` | unmodified high-property clone control |
| `demauras` | affix list changed to include Spectral Hit and Aura Enchanted |
| `demblank` | affix list zeroed |
| `demfalln` | monster id changed to known Fallen id `20` |
| `demlvl` | bind level changed to `20` |

Keep these as disposable live probes. They are evidence generators, not
production-safe chargen outputs.
