# Bound Demon Chargen Roadmap

This roadmap defines the public chargen path for Reign of the Warlock
bound-demon support. The current supported direction is template-derived
authoring: start from a known 116-byte follower payload, preserve unknown
bytes, and expose only fields that have scanner and Offline validation behind
them.

Template-free synthesis remains blocked. A scanner-clean payload is not enough:
D2R must instantiate the demon, keep `follower_count=1` after save/exit, and
preserve or predictably canonicalize every authored field.

## Current Support

Supported v1 behavior copies a known template payload:

```yaml
bound_demon:
  template: known_template
```

The v1.2 target is still template-derived, but with a player-facing intent
surface:

```yaml
bound_demon:
  template_path: .local-demon-templates/black-lancer-seven-slot.d2s
  monster_hcidx: 724
  source_affixes: [Fanaticism, Aura Enchanted, Cursed, Stone Skin]
  skill_affixes: auto
  effective_bind_level: 20
```

`template_path` points at a local template outside the tracked public repo.
`template` is reserved for a safe fixture that can be shipped publicly.

## Field Confidence

| Offset | Meaning | Writer posture |
| --- | --- | --- |
| `+0..+1` | follower kind tag `0x0018` | Fixed for known bound demons. |
| `+4..+5` | `monster_hcidx` | Authorable in template-derived payloads. Values are zero-based MonStats row indexes, not the MonStats `*hcIdx` column. |
| `+6..+9` | monster seed | Preserve from template. Arbitrary seed override can strip the follower. |
| `+24..+31` | `runtime_stats_24_31` | D2R-rewritten in same-model controls; do not expose as normal YAML. |
| `+44..+51` | `percent_or_caps_44_51` | Can preserve nonzero bytes in same-model controls; keep template-owned. |
| `+52..+55` | persisted bind metadata | Persistent bind metadata, not effective Bind Demon skill level. |
| `+64..+79` | `bitfields_64_79` | Source-context slice. Can be required for visible source-style affixes. |
| `+80..+86` | seven MonUMod affix bytes | Authorable in template-derived payloads; composed from source affixes plus skill-granted affixes. |
| `+88` | `hash_or_runtime_byte_88` | D2R-rewritten in same-model controls; do not author. |
| `+89..+91` | volatile runtime bytes | D2R-rewritten; do not author. |
| `+92..+93` | embedded `gf` payload data | Payload data, not a section marker. |
| `+94` | `post_gf_opcode_94` | Structural for known 116-byte payloads; keep `06`. |
| `+95..+115` | `post_gf_tail_95_115` | Mixed structural/runtime tail. Preserve from template unless a narrow probe proves a target-specific rewrite. |

The seven MonUMod bytes are necessary but not sufficient for every visible
property. Source-style labels can require compatible template context such as
`bitfields_64_79`. Bytes `+85/+86` are affix overflow slots, not model
candidate bytes.

## Affix Model

Public YAML separates the demon's source state from Bind Demon skill output:

- `source_affixes`: affixes the monster already had before binding.
- `skill_affixes: auto`: affixes derived from the effective Bind Demon level.
- `effective_bind_level`: optional override when chargen cannot infer the bind
  state from active equipment and inventory.

Confirmed Bind Demon thresholds:

| Effective Bind Demon level | Skill-granted affixes |
| ---: | --- |
| `1..4` | none |
| `5..9` | Extra Strong |
| `10..14` | Extra Strong, Extra Fast |
| `15..19` | Extra Strong, Extra Fast, Spectral Hit |
| `20+` | Extra Strong, Extra Fast, Spectral Hit, Aura Enchanted |

Payload `+52` is not the effective skill level. Natural binds at multiple hard
skill levels kept the same persisted bind metadata while the MonUMod vector
changed according to the skill table.

The legacy `affixes` / `raw_affixes` field remains a raw seven-slot research
override. Do not combine it with `source_affixes` or `skill_affixes`.

Chargen validation emits a non-fatal warning when
`bound_demon.source_affixes` is non-empty. The warning is intentional: the
seven-slot tuple alone may not carry every source-style label unless the
template has compatible source context.

## Template Inspection First

Template inspection is the first v1.2 step for recipe work and for any model
identity hypothesis:

```bash
python3 tools/d2s_demon_template_inspect.py <template.d2s>
python3 tools/d2s_demon_template_inspect.py <template.d2s> \
  --excel-dir <extracted-excel-dir>
python3 tools/d2s_demon_template_inspect.py <template.d2s> \
  --excel-dir <extracted-excel-dir> \
  --compare-hcidx <target-row-index> [<target-row-index> ...]
```

Default output omits local paths, monster seed values, and raw unknown-slice
bytes. The report identifies the payload row index, persisted bind metadata,
seven labeled MonUMod slots, unknown-slice authoring posture, optional MonStats
row context, and candidate row comparisons. Treat inspected raw affixes as an
input to recipe authoring; split them into `source_affixes` and
`skill_affixes` once source context and effective Bind Demon level are known.

## Support Tiers

| Tier | YAML surface | Meaning | Status |
| --- | --- | --- | --- |
| 1 | `template: NAME` | Copy one safe 116-byte payload. | Supported |
| 2 | `template_path` plus safe overrides | Preserve template bytes while authoring proven fields. | v1.2 target |
| 3 | template-derived model changes | Change selected row indexes with template inspection and Offline validation. | Experimental |
| 4 | `monster: NAME` / template-free synthesis | Build all 116 bytes without a template. | Blocked |

## v1.2 Release Gate

v1.2 should ship only when the template workflow is useful without implying
template-free synthesis:

- `tools/d2s_demon_template_inspect.py` is the first recipe step.
- Recipe docs identify template source policy, row index, source context,
  source affixes, skill-affix mode, unsupported edits, and validation state.
- Player-facing YAML keeps `source_affixes` separate from
  `skill_affixes: auto`.
- Chargen validation warns when a recipe requests non-empty
  `source_affixes`, so the template-context dependency is visible before
  build.
- Non-`--yaml-only` chargen validation injects requested bound-demon and
  Iron Golem payloads into a temporary save, so scanner output catches malformed
  follower/golem blocks before promotion.
- Each published recipe has build -> scan -> Offline load -> save/exit ->
  rescan evidence, summarized as public-safe behavior.
- Seed overrides, arbitrary source-context edits, arbitrary model swaps, and
  template-free `monster: NAME` synthesis stay out of the supported surface.

Use `docs/bound-demon-template-recipes.md` for the recipe contract. The first
known package is the Black Lancer seven-slot recipe: template-derived,
context-required, row index `724`, and not portable template-free synthesis.

## Full Synthesis Proof Ladder

Template-free support requires generic byte rules, not a larger template
library. Work through this ladder before promoting a `synthesize: true` or
`monster: NAME` writer:

1. **Template inspection.** Inspect every candidate template and compare row
   indexes before writing YAML or staging a model probe.
2. **Corpus classification.** Decode available public-safe payload evidence
   into fixed, volatile, seed-correlated, monster-correlated,
   affix-correlated, and unknown slices. Output aggregate findings only.
3. **Same-model natural binds.** Bind the same easy monster repeatedly with
   controlled skill level and no source affixes to isolate seed/runtime
   variation.
4. **Affix-only controls.** Hold model identity constant while varying source
   affixes and effective Bind Demon level.
5. **One-slice mutation controls.** Mutate one unknown slice at a time with
   `tools/d2s_forge_demon_payload.py`; classify outcomes as
   accepted-preserved, accepted-rewritten, accepted-hidden, stripped, or
   scanner-invalid.
6. **Same-family model swaps.** Compare candidate rows with
   `tools/d2s_monster_model_compare.py`, then test one row-index or
   documented companion-offset hypothesis at a time.
7. **Cross-family model swaps.** Repeat across unrelated model families to
   identify fields that are family-specific, model-specific, or generated by
   D2R.
8. **Synthetic initializer.** Build a payload from constants plus generated
   fields, with no template payload bytes.
9. **High-tier validation.** Validate the generic writer on expensive targets
   only after cheaper controls pass.

Current same-model Fallen tail evidence is restrictive: keep `+94 == 06`,
preserve the final `+114/+115` terminator as `f0 1f` for that target family,
and do not author `+101/+102` because it can save back as an invalid 106-byte
payload.

## Stable Model Findings

Model identity is target-dependent.

- Fallen-family row-index-only swaps are not solved. One same-family target
  was visible but stripped on save; another preserved a hidden payload without
  a visible demon.
- Council Member row `347` is proven row-index-only from the current Fallen
  control.
- Black Lancer uses payload row index `724`; an earlier value `723` produced a
  Dark Archer because payload `monster_hcidx` is a zero-based MonStats row
  index, not the `*hcIdx` column.
- Black Lancer affix visibility needs source context for source-style labels.
  Fanaticism is a source/aura-flavor input, and the visible aura path requires
  Aura Enchanted adjacent in the composed affix tuple.
- A generated seven-slot Black Lancer package displayed Fanaticism/Aura
  Enchanted, Cursed, Stone Skin, Extra Strong, Extra Fast, and Spectral Hit,
  then saved back with the follower payload unchanged.

These findings support template-derived recipes. They do not prove arbitrary
template-free synthesis.

## Public Validation Standard

Public docs should record stable behavior, limitations, and proof gates. Do not
commit raw saves, local paths, machine details, disposable character names, or
session diaries. Use `docs/manual-save-validation.md` for reusable public-safe
manual procedures.
