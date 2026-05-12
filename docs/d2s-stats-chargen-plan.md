# D2S Follower Feature Status

This page summarizes follower-related chargen support. It is not a manual
validation scratchpad; keep disposable validation details outside the public
repo.

## Bound Demon

Known shape:

```text
lf <u16:follower_count> [116-byte bound-demon payload]
```

Supported public behavior:

- Preserve or strip an existing follower block.
- Clone one known 116-byte template payload.
- Clone one local `.d2s` template payload by fixture name or `template_path`.
- Experimentally override proven template-derived fields:
  - `monster_hcidx`
  - `monster_seed`
  - `bind_level` / `bind_demon_level`
  - raw `affixes` / `raw_affixes` for up to seven MonUMod bytes
  - player-facing `source_affixes` plus `skill_affixes: auto`, where the
    skill-granted affixes derive from effective Bind Demon level and
    source-affix visibility still depends on compatible template context such
    as the observed `bitfields_64_79` slice
  - Fanaticism/Aura Enchanted pairing in the composed affix writer, so the
    live-positive aura flavor path stays adjacent in the seven MonUMod slots

Still blocked:

- Fully synthesized `monster: fallen` style payloads without a template base.
- Multiple bound demons.
- Authoring unknown runtime/hash slices.

Writer policy:

- Write `follower_count=0` when no payload is requested.
- Write `follower_count=1` only with exactly one 116-byte payload.
- Preserve unknown bytes from the template base.
- Treat bytes `+89..+91` as volatile runtime data.
- Treat payload `+52` as persisted bind metadata, not effective skill level.
- Do not combine raw `affixes` with `source_affixes` / `skill_affixes`.

## Iron Golem

Known shape:

```text
kf <u8:has_golem> [JM-less item payload] 01 00 lf <u16:follower_count>
```

Supported public behavior:

- Preserve or strip an existing golem payload.
- Generate v1 normal and magic Iron Golem payloads for Necromancers that have
  `IronGolem` learned.

Still experimental:

- Socketed, runeword, unique, set, rare, crafted, and ethereal item families.
- Assertions that require byte-for-byte preservation after D2R canonicalizes an
  item payload.

Writer policy:

- Do not write more than one golem item.
- Omit the `JM` item-count prefix inside the golem section.
- Keep broader item-family support behind targeted tests until expectations are
  canonicalization-aware.

## Validation Policy

- Unit tests should cover parser and writer invariants first.
- Scanner output must pass before any local manual validation.
- Manual game validation should record only the stable public finding, using
  `docs/manual-save-validation.md` as the result template.
