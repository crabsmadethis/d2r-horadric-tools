# D2S Follower Feature Status

This page summarizes follower-related chargen support. It is a public feature
status reference, not a validation scratchpad.

## Bound Demon

Known shape:

```text
lf <u16:follower_count> [116-byte bound-demon payload]
```

Supported public behavior:

- Preserve or strip an existing follower block.
- Clone one known 116-byte template payload.
- Clone one local `.d2s` template payload through `template_path`.
- Inspect a local `.d2s` template or raw 116-byte payload with
  `tools/d2s_demon_template_inspect.py` before YAML recipe work.
- Compose template-derived affixes from `source_affixes` plus
  `skill_affixes: auto`.
- Warn during chargen validation when `bound_demon.source_affixes` is non-empty
  because source-style labels require compatible template source context.
- Author seven MonUMod slots at `+80..+86` in template-derived payloads.
- Document reusable player-facing packages with
  `docs/bound-demon-template-recipes.md`.

Experimental but constrained:

- Template-derived `monster_hcidx` overrides for proven row indexes.
- Raw `affixes` / `raw_affixes` seven-slot overrides for research controls.
- `--compare-hcidx` model-row comparisons using caller-supplied extracted
  MonStats/MonStats2 data.

Blocked:

- Fully synthesized `monster: NAME` payloads without a template base.
- Multiple bound demons.
- Seed overrides as normal YAML.
- Authoring unknown runtime, hash-like, source-context, or post-`gf` tail
  slices without a target-specific proof.

Writer policy:

- Write `follower_count=0` when no payload is requested.
- Write `follower_count=1` only with exactly one 116-byte payload.
- Preserve unknown bytes from the template base.
- Treat payload `monster_hcidx` as a zero-based MonStats row index, not the
  MonStats `*hcIdx` column.
- Treat payload `+52` as persisted bind metadata, not effective Bind Demon
  level.
- Derive `skill_affixes: auto` from effective Bind Demon level.
- Keep source affixes separate from skill-granted affixes.
- Treat bytes `+89..+91` as volatile runtime data.
- Keep `+94 == 06` for known 116-byte payloads.
- Do not combine raw `affixes` with `source_affixes` / `skill_affixes`.

Current recipe posture:

- Template-derived authoring is supported.
- Template inspection is the first v1.2 step.
- The Black Lancer seven-slot package is a recipe for proven compatible
  templates, not evidence for template-free synthesis.
- Source-affix visibility may depend on template context such as
  `bitfields_64_79`.

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

- Unit tests cover parser and writer invariants first.
- Scanner output must pass before local manual validation.
- `d2r-chargen validate <name>` without `--yaml-only` builds a temporary save
  that includes requested bound-demon and Iron Golem payloads before scanning.
- Template-derived recipes need build -> scan -> Offline load -> save/exit ->
  rescan evidence before they are documented as known-good.
- Public docs record stable findings and limitations, not local saves, private
  paths, or one-off session logs.
