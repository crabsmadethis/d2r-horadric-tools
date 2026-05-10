# D2S Research Status

This page tracks public `.d2s` save-format findings that are useful for future
tooling work. Keep it concise: answered questions become findings, and remaining
questions must include a proof method.

## Confirmed Findings

| Area | Public finding | Tooling consequence |
| --- | --- | --- |
| Follower payload count | `lf<u16:follower_count>` is followed by exactly `count * 116` payload bytes for known bound-demon saves. | Reject count/payload mismatches in the scanner and writers. |
| Bound demon count | D2R accepts one known Warlock bound-demon payload and rejects tested count-2 bound-demon saves. | Public chargen should support at most one bound demon. |
| Embedded `gf` bytes | `payload[92:94] == b"gf"` inside a bound-demon payload is data, not a section marker. | Do not split the save at that embedded byte pair. |
| Volatile demon bytes | Bound-demon payload bytes `+89..+91` may change on save/exit. | Treat that slice as runtime data; do not author it. |
| Authorable demon fields | Template-derived edits to `monster_hcidx`, bind level, and the five MonUMod bytes can persist. A random monster seed override was stripped back to `follower_count=0` on save/exit. | Keep seed preservation separate from authored seed overrides. |
| Bound-demon visible affixes | Clearing the five MonUMod bytes removes visible properties. Direct Spectral Hit and Aura Enchanted bytes display on at least one original-template model, but not on every tested monster identity. A full five-normal-affix payload can also display Spectral Hit plus Aura Enchanted at runtime. | Treat the five MonUMod bytes, monster identity/model, hard skill level, and payload `+52` as separate persisted inputs; visible labels are not a simple byte-for-byte rendering. |
| Cross-class followers | A structurally valid borrowed follower block can load on a non-Warlock save but is stripped back to `follower_count=0` on save/exit. | Do not expose cross-class follower payloads as normal chargen behavior. |
| Iron Golem block | Iron Golem data lives in `kf` before `lf` as a single variable-length item payload. | Generated golems should use item encoding and must not write multiple golem payloads. |
| `jf` before merc items | The `jf` corpse marker can be present or absent before merc `JM` while the tail remains parseable. | Preserve the existing marker shape unless a targeted edit proves a safe normalization. |

## Open Questions

| Question | Why it matters | Next proof method |
| --- | --- | --- |
| Unknown bound-demon payload slices at `+24..+31`, `+44/+48`, `+64..+79`, `+88`, and `+95..+115` | Full bound-demon synthesis is blocked until these bytes are understood or proven ignorable. | Aggregate local payloads with a decoder that reports stable/volatile slices without printing local paths. |
| Bound-demon model identity | `monster_hcidx` can persist, but some forced monster-identity payloads can look visually wrong even when structurally valid. | Compare original-template payloads against monster-id overrides while holding seed, bind metadata, and affix bytes constant. |
| Bind Demon level behavior | `Skills.txt` grants Extra Strong at level 5, Extra Fast at 10, Spectral Hit at 15, and Aura Enchanted at 20 through Bind Demon calc fields. Payload `+52` persists, but it is not enough to add visible properties to a pre-authored follower. | Use fresh natural binds at hard levels 1, 5, 10, 15, and 20; do not infer skill-tier behavior from pre-authored follower payloads. |
| Spectral/Aura trigger | Five normal authored affixes can display Spectral Hit plus Aura Enchanted even when those bytes are not present. | Test prefix counts and focused combinations of Extra Strong, Fire Enchanted, Cursed, Mana Burn, and Extra Fast. |
| Merc status at `0xA7..0xA8` | The field has more observed values than the writer currently understands. | Group local saves by hireling id, difficulty, merc gear count, and progression. |
| Broader Iron Golem item families | Normal and magic generated golems are supported, but more item families need canonicalization-aware expectations. | Add synthetic fixture tests first; use manual validation only for item families tests cannot prove. |

## Recording Rules

- Put durable byte-layout facts in `docs/d2s_format.md`.
- Put user-facing manual procedures in `docs/manual-save-validation.md`.
- Do not commit raw saves, local paths, or session diaries.
- Do not leave an answered question in this file as "open"; move it to the
  confirmed table with the limitation that still matters.
