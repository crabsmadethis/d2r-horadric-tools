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

Hypothesis: probably not through normal gameplay. The known Warlock save uses
`follower_count=1` and one fixed 116-byte payload. The format can express
`follower_count=N` by the acceptance rule, but we have not proved D2R accepts
`N>1` for bound demons.

Test:

1. Forge a Warlock save with `follower_count=2` and two copied 116-byte demon
   payloads.
2. Scanner must recognize exactly 232 trailing payload bytes.
3. Load in D2R and observe whether it appears, joins, spawns one demon, spawns
   two demons, strips the extra payload, or rejects the save.
4. Save/quit and rescan.

Safety: this is a deliberate format-boundary test. Keep it out of normal
chargen until live behavior is known.

## Work Plan

### Milestone 1: Read-Side Parsers

Add read-only parsers before adding writers.

Tasks:

- Add an `iron_golem` decoder that returns:
  - `has_golem`
  - raw item payload bytes
  - payload byte length
  - parsed item header if existing item decoder can consume the bitstream
- Extend follower parsing reports for bound demon:
  - keep high-confidence fields
  - expose unknown fields as raw slices with offsets
  - never label uncertain fields as stats in code
- Add tests using synthetic byte fixtures or gitignored private fixtures when
  available.

Acceptance:

- Existing no-golem saves still round-trip as `has_golem=false`.
- Live `probenecro` captures decode as one golem payload with lengths 55 and 26.
- Bound demon parser still returns exactly the known high-confidence fields.

### Milestone 2: Preserve and Round-Trip

Make preservation explicit and tested.

Tasks:

- Update item rebuild logic to preserve an existing `kf 01 <item>` golem block
  by default, just as follower payloads are preserved by default.
- Add an explicit strip option for golem blocks for tests and deliberate edits.
- Ensure rebuilding character inventory does not silently delete an Iron Golem.

Acceptance:

- A save with `kf 01` remains `kf 01` after a rebuild that edits normal items.
- Scanner reports the same golem payload hash after no-op rebuild.
- Tests cover both no-golem and active-golem tails.

### Milestone 3: Iron Golem Chargen Writer

Add first-class YAML support once read-side preservation is solid.

Possible YAML:

```yaml
iron_golem:
  item:
    base: cap
    properties:
      fire_res: 10
```

Tasks:

- Reuse existing item builders to produce a single item payload.
- Strip any leading `JM<count>` wrapper if the builder path produces one.
- Write `kf 01 <payload> 01 00 lf 00 00`.
- Validate the item payload with the scanner before touching live saves.

Acceptance:

- Generated Necromancer appears in character select.
- Golem appears in game.
- Save/quit keeps `has_golem=1`.
- Repeated reload preserves or canonicalizes only known runtime bytes.

### Milestone 4: Demon Stats Research

Gather enough fixtures to separate item/monster identity from runtime state.

Tests:

- Reload/save `probewldemon` without combat.
- Damage/heal the demon, save/quit.
- Waypoint and fight one small pack, save/quit.
- Rebind to two known monsters, save/quit each.
- If safe, vary Bind Demon skill level and compare `+52` and derived fields.

Analysis:

- Diff only the 116-byte payload.
- Track stable identity fields separately from runtime-mutating fields.
- Cross-reference `monster_hcidx` with MonStats and affixes with MonUMod.
- Treat `+24..+31`, `+44/+48`, `+64..+79`, `+88`, and `+95..+115` as unknown
  until multiple controlled fixtures agree.

Acceptance:

- A table of field confidence levels exists.
- The scanner reports high-confidence fields and raw unknown slices.
- No writer tries to synthesize unknown runtime fields.

### Milestone 5: Bound Demon Chargen Policy

Decide what chargen should support.

Safe v1:

```yaml
bound_demon:
  template: marrowbind_demon_b
```

Possible v2:

```yaml
bound_demon:
  monster: fallen
  affixes: [Strong, Fast]
  bind_level: 7
```

Do not implement v2 until the unknown runtime/hash fields are understood or
until we can prove D2R canonicalizes a minimally synthesized payload safely.

Acceptance:

- v1 template cloning remains supported and documented.
- v2 remains blocked behind explicit fixture evidence.

## Recommended Next Action

Implement Milestone 1 for Iron Golem read-side parsing first. It gives immediate
chargen safety value and uses evidence we already captured. Demon stat synthesis
should remain research-only until more controlled payload diffs exist.
