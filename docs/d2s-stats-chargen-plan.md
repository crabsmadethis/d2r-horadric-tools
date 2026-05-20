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
- Clone one extracted raw 116-byte local template payload through
  `template_path`.
- Inspect a local `.d2s` template or raw 116-byte payload with
  `tools/d2s_demon_template_inspect.py` before YAML recipe work.
- Extract a local demon template payload with
  `tools/d2s_demon_template_inspect.py --extract-payload`.
- Compose template-derived affixes from `source_affixes` plus
  `skill_affixes: auto`.
- Build exact registry-backed `synthesis_validated` packages. The current
  enabled package id is `row724-black-lancer-seedg-holy-shock-v1`; list package
  ids with `d2r-chargen bound-demon-packages`.
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

- Universal `monster: NAME` payloads without a template base. Public
  `synthesis_validated` support is planned separately as registry-backed
  package synthesis, not arbitrary algorithmic synthesis.
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
- Template extraction can produce raw 116-byte payload templates for
  `template_path` without committing local saves.
- The Black Lancer seven-slot package is a recipe for proven compatible
  templates, not evidence for template-free synthesis.
- `synthesis_validated` is limited to named registry packages; user YAML cannot
  provide raw context slices or request arbitrary generated names, aura flavor,
  source-affix semantics, pcount/combat stats, or unsupported rows.
- Mauler row `188`, alternate Mauler row `620`, and Baal Subject 5 row `572`
  have byte-level seven-affix persistence proof plus user-confirmed visible
  validation for the exact source-context package; Hephasto/Hephaesto remains a
  rejected-current-shell placeholder.
- Bound-demon display names and Aura Enchanted flavor remain preserve-only for
  the template workflow. Same-row seed evidence supports seed participation,
  but not enough decoded semantics for player-facing seed/name/aura authoring.
  `/players`-dependent stat scaling is also preserve-only: matched captures and
  runtime replays show pcount-shaped bytes, but not enough decoded semantics
  for a player-facing HP/damage/AR/defense knob.
- Source-affix visibility may depend on template context such as
  `bitfields_64_79`.

## Iron Golem

Known shape:

```text
kf <u8:has_golem> [JM-less item payload] 01 00 lf <u16:follower_count>
```

Supported public behavior:

- Preserve or strip an existing golem payload.
- Generate normal, magic, ethereal, set, rare, crafted, and socketed-normal
  Iron Golem payloads for Necromancers that have `IronGolem` learned.
- Generate runeword Iron Golem payloads as a parent record followed by
  generated rune filler records inside the JM-less `kf 01` block. Insight and
  Strength have passed Offline validation with parent-only canonicalization;
  the public-writer Insight path has user-confirmed expected aura behavior.
  Scanner output and the hub loop now group these payloads as parent plus
  `socket_filler_N` records, so post-save canonicalization can be reported by
  record rather than as an undifferentiated byte diff.
- Generate aura-bearing magic parent payloads through normal item property
  encoding; the Meditation/Insight-aura control validated the aura stat on a
  magic single-parent golem as well as the runeword path.
- Generate unique Iron Golem payloads only when the YAML explicitly opts into
  D2R's observed save/exit canonicalization.

Still experimental:

- Manual socket filler and jewel records.
- Assertions that require byte-for-byte preservation after D2R canonicalizes a
  unique or runeword parent payload.
- Cross-class `kf 01` golem authoring.

Writer policy:

- Do not write more than one golem item.
- Omit the `JM` item-count prefix inside the golem section.
- For runewords, write the parent plus the runeword-derived rune fillers
  directly inside `kf 01` before the `01 00 lf` bridge.
- Keep manual rune fillers and jewel fillers blocked until a targeted
  filler-proof passes scanner and Offline validation.

## Validation Policy

- Unit tests cover parser and writer invariants first.
- Scanner output must pass before local manual validation.
- `d2r-chargen validate <name>` without `--yaml-only` builds a temporary save
  that includes requested bound-demon and Iron Golem payloads before scanning.
- Template-derived recipes need build -> scan -> Offline load -> save/exit ->
  rescan evidence before they are documented as known-good.
- Public docs record stable findings and limitations, not local saves, private
  paths, or one-off session logs.
