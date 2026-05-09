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
| `+4..+5` | `monster_hcidx` | proven live: changing to `20` changed model to Fallen and persisted |
| `+6..+9` | monster seed | likely arbitrary u32, needs mutation test |
| `+52..+55` | Bind Demon level | persists live; no visible difference in first level-only test |
| `+80..+84` | five MonUMod affix bytes | proven live: controls visible extra affix list and persists |
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
- The first edited-payload batch loaded and saved cleanly. D2R preserved all
  intentional edits and changed only volatile bytes `+89..+91` in four of five
  probes.
- Zeroing the five MonUMod bytes removed visible extra affixes, while the demon
  and lightning immunity remained. Treat lightning immunity as monster-specific
  for this `hcidx=347` demon, not a MonUMod byte.
- The second edited-payload batch loaded and saved cleanly. Cold Enchanted and
  Stone Skin showed visibly; Lightning Enchanted byte `03` persisted but did
  not show as a visible Lightning Enchanted label for this bound demon.
- The first real chargen YAML override probe, `demexp`, loaded live with the
  requested Fallen model and visible Extra Strong plus Extra Fast affixes. After
  save-and-exit, D2R preserved `monster_hcidx=20`, `monster_seed=0x0018AB90`,
  `bind_demon_lv=20`, and affix bytes `05 06 00 00 00`; only volatile payload
  bytes `+89..+91` changed.

## Robust Support Shape

Implement demon support in tiers:

| Tier | YAML | Meaning | Promotion gate |
| --- | --- | --- | --- |
| 1 | `template: NAME` | Copy a known 116-byte payload | Already supported |
| 2 | `template: NAME` plus safe field overrides | Edit only proven fields like affixes or bind level | Each edited field survives live reload/save |
| 3 | `monster_hcidx`/`monster` with template-derived runtime fields | Change monster identity while borrowing the rest of a compatible template | Live test proves model/properties follow the edited monster and save persists |
| 4 | fully synthesized payload | Build all 116 bytes without a template | Only after unknown fields are decoded or proven ignorable |

Tier 2 and Tier 3 are implemented as experimental template-derived YAML
overrides. Keep fully synthesized payloads blocked until the remaining runtime
slices are decoded or proven ignorable across more monster families.

## Question Status

### Q1: Do the five affix bytes control visible properties?

Status: answered for template-derived payload edits.

Answered finding:

- `demclone`, `demauras`, and `demblank` proved that `+80..+84` is authorable
  and controls the persisted MonUMod list. Zeroing those bytes removed visible
  extra affixes while the demon and monster-specific lightning immunity
  remained.

Residual risk:

- The five bytes do not cover every visible property. The `bindtank` demon kept
  Aura Enchanted, Spectral Hit, and lightning immunity through some other
  source.

### Q2: Does `monster_hcidx` control demon identity by itself?

Status: answered for the tested template-derived override.

Answered finding:

- `demfalln` changed the visible model to a Fallen, joined, saved, and retained
  `monster_hcidx=20`. D2R changed only volatile bytes `+89..+91`.

Residual risk:

- This does not prove fully synthesized payloads. It proves a practical Tier 3
  override when the rest of the 116-byte payload comes from a compatible live
  template.

### Q3: Does Bind Demon level affect persisted properties?

Status: partially answered.

Answered finding:

- `demlvl` joined, saved, and retained `bind_demon_level=20`.

Still open:

- The user observed no visible difference in the first level-only test, so
  `+52` should remain persistent metadata until a skill-level matrix proves
  visible behavior.

Next proof method:

- Test a small level matrix against the same monster and affix baseline, then
  diff only the 116-byte payload and visible property report.

### Q4: Can we keep collecting natural high-property captures?

Status: still open and useful.

Next proof method:

- Use `demonlab` as the clean no-bound-demon tank for natural captures. Each
  capture should record visible properties, save/reload stability, and a
  public-safe payload-field summary without publishing private save data.

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

## Completed Test Batch

The first batch was intentionally letter-only and is now answered evidence:

| Character | Purpose |
| --- | --- |
| `demonlab` | clean tank for new natural demon captures |
| `demclone` | unmodified high-property clone control |
| `demauras` | affix list changed to include Spectral Hit and Aura Enchanted |
| `demblank` | affix list zeroed |
| `demfalln` | monster id changed to known Fallen id `20` |
| `demlvl` | bind level changed to `20` |

Keep these as disposable evidence references. They are not production-safe
chargen outputs.

## Second Test Batch

Status: complete.

| Character | Purpose |
| --- | --- |
| `demfallz` | Fallen model with all five affix bytes zeroed |
| `demlite` | original model with only Lightning Enchanted |
| `demcold` | original model with only Cold Enchanted |
| `demstone` | original model with only Stone Skin |
| `demmulti` | original model with Multiple Shots, Teleportation, Lightning Enchanted, Cold Enchanted, Stone Skin |

Results:

- `demfallz`: loaded as Fallen with no affix.
- `demlite`: loaded as lightning immune, but not visibly Lightning Enchanted.
- `demcold`: loaded as Cold Enchanted.
- `demstone`: loaded as Stone Skin.
- `demmulti`: loaded and saved without canonicalizing the five authored affix
  bytes, but did not visibly show Lightning Enchanted.

All five rewritten saves retained `follower_count=1`, exactly 116 payload
bytes, valid checksums, and the authored affix bytes. Save/quit changed only
volatile bytes `+89..+91`, except `demlite`, which was byte-stable.

Conclusions:

- Single-affix Cold Enchanted and Stone Skin work and persist.
- Byte `03` persists as Lightning Enchanted but does not necessarily display as
  Lightning Enchanted for this bound demon.
- Five authored affix bytes can include less common affixes without join
  failure or canonicalization.

## Experimental YAML Override Result

Status: live-positive for the Tier 2/Tier 3 template-derived path.

`demexp` was generated through normal chargen YAML:

```yaml
bound_demon:
  template: demclone
  monster_hcidx: 20
  bind_level: 20
  affixes:
    - Extra Strong
    - Extra Fast
```

The generated save appeared in Offline, joined game, and spawned a Fallen-style
bound demon with the requested visible affixes. Post-save scanner output was
checksum-clean with `follower_count=1` and exactly 116 follower payload bytes.
The post-save payload retained the authored identity and affix fields, with the
only payload diff at known volatile bytes `+89..+91`.

## Experimental YAML Mode

Template-derived overrides are implemented:

```yaml
bound_demon:
  template: demclone
  monster_hcidx: 20
  affixes: [Extra Strong, Extra Fast]
  bind_level: 20
```

This is not full synthesis yet, but it covers practical "pick a known template
base, then author monster/properties" chargen. The first YAML-path live probe
is `demexp`, which appeared in Offline, joined game, spawned a Fallen-style
bound demon with the requested affixes, and saved back with only known volatile
payload bytes changed.

## Next YAML Live Batch

Status: staged for live Offline testing.

These probes are generated through the normal YAML chargen path and should be
tested one at a time, saving and exiting after each:

| Character | Expected live question |
| --- | --- |
| `demynul` | Fallen-style demon with no visible extra affixes |
| `demycol` | Fallen-style demon with Cold Enchanted |
| `demysto` | Fallen-style demon with Stone Skin |
| `demyfur` | Fallen-style demon with five authored affixes |
| `demyaur` | Whether Spectral Hit and Aura Enchanted display from authored bytes |
| `demysee` | Whether an authored non-template monster seed persists |
