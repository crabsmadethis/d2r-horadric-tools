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

### Iron Golem Item Encoding Plan

Use the existing item encoder. `build_item(...)` already returns a raw item
bitstream without a `JM<count>` section wrapper; `rebuild_items(...)` adds `JM`
only around character, corpse, and merc item sections. The Iron Golem writer
should therefore pass one generated item byte string directly into the `kf`
tail.

Tail shape:

```text
kf <u8:has_golem> [golem_item_bytes] 01 00 lf <u16:follower_count> [followers]
```

Use precise length names in code:

- `kf_to_lf_gap = lf - kf`
- `golem_item_bytes = data[kf + 3 : lf - 2]`
- `bridge = data[lf - 2 : lf]`, expected `01 00`

The current live `probenecro` second-golem save has `kf_to_lf_gap=29`,
`has_golem=1`, `bridge=01 00`, and a 24-byte `golem_item_bytes` payload. That
payload decodes as a normal item header at byte 0:

```text
type=flc ilvl=35 quality=4 storage=0 col=4 row=0 bodyloc=4 location=1 ext=101
```

This confirms the item starts immediately after the `has_golem` byte; there is
no `JM` prefix and no additional golem header.

Implementation order:

1. Add a read-only `d2r_chargen/iron_golem.py` helper with:
   - `decode_iron_golem_block(data) -> has_golem, item_payload, bridge`
   - strict marker checks: `kf` before trailing `lf`, bridge must be `01 00`
   - `decode_item_header(item_payload, 0)` best-effort metadata when present
2. Update `tools/d2s_corpus_scan.py` to report:
   - `has_golem_byte`
   - `golem_item_payload_bytes`
   - `golem_bridge_ok`
   - optional item header buckets: type, quality, storage, location, bodyloc
3. Update `rebuild_items(...)` to preserve the existing golem block by default:
   - current behavior always writes `kf 00`, which strips an active Iron Golem
   - add `preserve_golem=True` and optional `iron_golem_payload=None`
   - precedence should mirror followers: explicit payload > preserve > strip
4. Add YAML support after preservation tests pass:

```yaml
iron_golem:
  item:
    normal: true
    base: cap
    ilvl: 35
    quality: 2
```

The resolver should reuse the existing item-definition path, but force the
storage/location fields into the same equipped-looking shape D2R wrote for the
live golem (`storage=0`, `location=1`, nonzero `bodyloc`). Start with simple
normal or magic items. Defer runewords, socket fillers, and inventory-position
semantics until a plain item survives live testing.

Writer output rules:

- No active golem:
  `kf 00 01 00 lf <followers>`
- Active golem:
  `kf 01 <single item bytes> 01 00 lf <followers>`
- Do not write more than one golem item. The live recast test replaced the
  previous golem, and the section has only one flag plus one item byte stream.

Tests before live promotion:

- No-golem fixture round-trips to `kf 00 01 00 lf`.
- Active-golem fixture round-trips with the same `golem_item_bytes` hash.
- Explicit `iron_golem_payload` writes `kf 01` and keeps followers unchanged.
- Explicit strip writes `kf 00` and keeps followers unchanged.
- Scanner can decode the current live `probenecro` payload header from byte 0.

Live test ladder:

1. Preserve-only rebuild of `probenecro`; confirm the existing golem still
   appears and payload hash is unchanged or only known runtime bytes change.
2. Generate a disposable Necromancer with a plain normal item golem.
3. Reload/save once; expect D2R may canonicalize byte `+1`, based on the
   second-golem capture.
4. Only after a normal item survives, try magic properties. Keep the generated
   item conservative: no sockets, no runeword, no fillers.

### Milestone 4: Demon Stats Research

Gather enough fixtures to separate item/monster identity from runtime state.

Tests:

- Reload/save `probewldemon` without combat.
- Treat damage/heal as optional instead of primary: bound demons are hard to
  keep injured and heal quickly, so this only helps if a durable injured save
  can be captured without a lot of manual wrestling.
- Waypoint and fight one small pack, save/quit.
- Rebind to two known monsters, save/quit each.
- If safe, vary Bind Demon skill level and compare `+52` and derived fields.
- Positive template-variant probe: `probewlalt` joined and spawned a demon with
  the alternate known 116-byte payload. On save-and-quit, D2R preserved
  `follower_count=1` and the 116-byte payload shape but canonicalized payload
  offsets `+89..+91` and `+95..+97`. On a second reload/save, `+95..+97`
  stayed stable but `+89..+91` changed again. On a third reload/save,
  `+95..+97` stayed stable again and `+89..+91` became `00 00 00`.

Analysis:

- Diff only the 116-byte payload.
- Track stable identity fields separately from runtime-mutating fields.
- Cross-reference `monster_hcidx` with MonStats and affixes with MonUMod.
- Treat `+24..+31`, `+44/+48`, `+64..+79`, `+88`, and `+95..+115` as unknown
  until multiple controlled fixtures agree.
- Treat `+89..+91` as actively volatile based on the repeated `probewlalt`
  reload/save result.

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
