# D2S Follower Stats and Chargen Integration Plan

Status: follow-up plan after the 2026-05-08 live D2S probe session.

Goal: turn the live findings about bound demons and Iron Golems into safe,
testable chargen features without pretending we understand fields that are
still runtime state.

## Current Understanding

### Bound Demon

The bound demon is stored after the `lf<u16:follower_count>` marker. For the
known Warlock case, `follower_count=1` and exactly 116 bytes of payload follow.
D2R rejects count/payload mismatches, but accepts and preserves a valid
Warlock-bound payload.

High-confidence fields inside the 116-byte payload:

| Offset | Field | Confidence |
| --- | --- | --- |
| `+0` | follower-kind tag, invariant `0x0018` | high |
| `+4` | monster `hcIdx` | high |
| `+6` | monster seed | high |
| `+52` | Bind Demon skill level at bind time | high |
| `+80..+84` | MonUMod affix indices | high |
| `+92..+93` | embedded `gf` bytes, payload data | high |

Unknown or only partially understood fields:

| Offset | Current hypothesis |
| --- | --- |
| `+2` | bind generation, follower index, or state counter |
| `+24..+31` | monster-derived runtime stats |
| `+44` / `+48` | likely health/resource percentages or normalized caps |
| `+64..+79` | runtime/affix/status bitfields |
| `+88` | hash, checksum, or runtime token |
| `+95..+115` | RotW-specific tail data after embedded `gf` |

Chargen implication: bound demons are safe to preserve or clone from a known
fixture. They are not yet safe to synthesize from `monster: fallen` style YAML
without a live-generated template payload.

### Iron Golem

The Iron Golem lives in the `kf` section, before the `lf` follower marker:

```text
kf <u8:has_golem> [JM-less encoded item] 01 00 lf <u16:follower_count>
```

Live results show the golem item payload is variable-length item encoding:

| Live capture | Shape |
| --- | --- |
| First golem | `has_golem=1`, `kf_to_lf_gap=58`, 55-byte payload |
| Reloads | same 55-byte payload persisted unchanged |
| Second golem | `has_golem=1`, `kf_to_lf_gap=29`, 26-byte payload |
| Second golem reload | 26-byte payload persisted except byte `+1` canonicalized `0x20 -> 0x00`; next reload was byte-stable |

Chargen implication: Iron Golem support is much closer than demon synthesis.
The likely writer path is to encode one normal item bitstream, omit the `JM`
count prefix, write it after `kf 01`, then append the existing `01 00 lf 00 00`
tail.

## Key Questions

### Can there be more than one Iron Golem?

Status: answered.

Hypothesis: no. The file format has a single `kf` marker followed by one
`has_golem` flag and one item bitstream before the fixed `01 00 lf` bridge.
Necromancer gameplay also replaces the existing Iron Golem when a new one is
made.

Test:

1. Keep a `probenecro.d2s` fixture with an active golem.
2. Make a new Iron Golem from a second item.
3. Confirm D2R rewrites the same single `kf 01 <item>` payload rather than
   appending another payload.

Current result: the second golem replaced the first; only one `kf 01` item
payload remained.

### Can there be more than one bound demon?

Status: answered for live D2R join behavior; unsupported for chargen.

Hypothesis: probably not through normal gameplay. The known Warlock save uses
`follower_count=1` and one fixed 116-byte payload. The format can express
`follower_count=N`, but the live join test below rejected `N>1` for bound
demons.

Test:

1. Forge a Warlock save with `follower_count=2` and two copied 116-byte demon
   payloads.
2. Scanner must recognize exactly 232 trailing payload bytes.
3. Load in D2R and observe whether it appears, joins, spawns one demon, spawns
   two demons, strips the extra payload, or rejects the save.
4. Save/quit and rescan.

Safety: this is a deliberate format-boundary test. Keep it out of normal
chargen until live behavior is known.

2026-05-08 result: D2R rejected both count-2 bound-demon probes at game join:

- `probewltwo`: `follower_count=2` with the same valid 116-byte payload copied
  twice. The scanner reported checksum/size ok and exactly 232 trailing bytes.
- `probewlmix`: `follower_count=2` with two different known 116-byte payloads.
  The scanner again reported checksum/size ok and exactly 232 trailing bytes.

Neither save was rewritten after the failed join attempts. Treat live D2R as
supporting one bound demon at most, even though the trailing `lf` field is a
numeric count.

## Work Plan

### Milestone 1: Read-Side Parsers

Status: answered for the current public evidence set.

Keep these parser contracts:

- Iron Golem decode reports `has_golem`, raw item payload bytes, payload byte
  length, bridge bytes, and best-effort item header metadata.
- Follower parsing reports only high-confidence bound-demon fields and exposes
  uncertain regions as raw slices with offsets.
- Unknown bound-demon slices must not be labeled as stats in code.

Acceptance guard:

- No-golem saves still decode as `has_golem=false`.
- Active golem captures decode as one payload with the observed variable
  lengths.
- Bound demon parsing still returns exactly one 116-byte payload for the known
  Warlock case.

### Milestone 2: Preserve and Round-Trip

Status: answered for the tested active-golem preservation path.

Keep these writer contracts:

- No active golem: `kf 00 01 00 lf <followers>`.
- Active golem: `kf 01 <single item bytes> 01 00 lf <followers>`.
- Do not write more than one golem item. The live recast test replaced the
  previous golem, and the section has only one flag plus one item byte stream.
- Preservation should mirror followers: explicit payload over preserve over
  strip.

Acceptance guard:

- A save with `kf 01` remains `kf 01` after a rebuild that edits normal items.
- Scanner reports the same golem payload hash after no-op rebuild, unless a
  documented D2R canonicalization byte changes during live reload/save.
- Tests cover no-golem, active-golem, explicit payload, and explicit strip.

### Milestone 3: Iron Golem Chargen Writer

Status: implemented for v1 generated normal/magic items, with broader item
families still experimental.

Supported v1 YAML shape:

```yaml
skills:
  IronGolem: 1
iron_golem:
  item:
    magic: true
    base: flc
    properties:
      fire_res: 10
```

Answered evidence:

- The Iron Golem item starts immediately after the `has_golem` byte. There is
  no `JM` prefix and no additional golem header.
- The existing item encoder can produce a JM-less payload suitable for the
  `kf 01 <payload> 01 00 lf <followers>` tail.
- The live storage shape is `storage=0`, `location=1`, and nonzero `bodyloc`
  from the selected slot (`weapon` defaults to `bodyloc=4`).
- Generated normal and magic v1 YAML support has visual positive evidence and
  checksum-clean post-save evidence.
- The broader expansion batch has load/save persistence evidence, but not full
  visual confirmation for every family.

Current promotion policy:

- Keep normal/magic generated Iron Golems in the supported v1 surface.
- Treat empty socketed normal, set, and crafted/ethereal payloads as promising
  but not promoted until visual confirmation is recorded.
- Treat runewords and uniques as canonicalization-aware candidates, not strict
  byte-preservation cases.

Next proof methods:

- Add a visual confirmation matrix for socketed, runeword, unique, set, rare,
  and crafted families before broadening the public YAML contract.
- For runewords and uniques, assert post-save structural validity and documented
  canonicalization rather than unchanged payload bytes.

### Milestone 4: Demon Stats Research

Status: still open; template-derived field overrides have answered pieces, but
full synthesis remains blocked.

Answered evidence:

- `probewldemon` proves one visible Warlock bound demon can persist as
  `follower_count=1` plus exactly 116 payload bytes.
- Count-2 bound-demon probes were scanner-clean but failed game join; treat live
  D2R as supporting one bound demon at most.
- `+89..+91` is volatile runtime data and should not be authored.
- `+80..+84` and `+4..+5` are authorable experimental fields for affixes and
  monster identity in a template-derived payload.
- `+52` persists as Bind Demon level metadata, but visible behavior is unproved.
- The second edited-payload batch proved Cold Enchanted and Stone Skin display
  from single authored affix bytes and persist. Lightning Enchanted byte `03`
  persists but did not display as Lightning Enchanted for this bound demon.
- The embedded `gf` bytes are payload data, not a section marker.
- Sorceress borrowed-follower payloads load structurally but are stripped back
  to `follower_count=0` on save.

Still open:

- `+24..+31`, `+44/+48`, `+64..+79`, `+88`, and `+95..+115` remain unknown.
- The five MonUMod bytes do not account for every visible property; `bindtank`
  retained visible properties outside that decoded list.
- Damage/heal captures are optional, not primary, because bound demons heal
  quickly and are hard to preserve in an injured state.

Next proof methods:

- Diff only the 116-byte payload.
- Track stable identity fields separately from runtime-mutating fields.
- Cross-reference `monster_hcidx` with MonStats and affixes with MonUMod.
- Run natural high-property captures and a small Bind Demon level matrix.

Acceptance guard:

- A field-confidence table exists.
- The scanner reports high-confidence fields and raw unknown slices.
- No writer synthesizes unknown runtime fields.

### Milestone 5: Bound Demon Chargen Policy

Status: v1 template cloning remains supported; experimental template-derived
overrides are implemented for proven fields. Fully synthesized payloads remain
blocked.

Safe v1:

```yaml
bound_demon:
  template: marrowbind_demon_b
```

Experimental v2, only with a live-derived template base:

```yaml
bound_demon:
  template: bindtank_capture
  monster_hcidx: 20
  affixes: [Extra Strong, Extra Fast]
  bind_level: 20
```

Blocked:

- Fully synthesized `monster: fallen` payloads without a live-derived 116-byte
  template remain blocked until unknown runtime/hash fields are decoded or live
  proof shows D2R canonicalizes a minimal synthesized payload safely.

## Recommended Next Action

Use the cleaned evidence split to drive two separate follow-ups: a golem
expansion-family visual matrix before broadening YAML support, and live-test
`demexp` to verify the new YAML override path end to end.
