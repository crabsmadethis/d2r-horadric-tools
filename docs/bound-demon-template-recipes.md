# Bound Demon Template Recipes

Bound-demon support is template-derived. A recipe is the public-safe contract
for turning one local captured template into repeatable YAML intent without
committing the template save.

Use this page for player-facing demon templates. Template-free
`monster: NAME` synthesis remains blocked; public authoring is either
preserve-first `template_path` or a named `synthesis_validated` package from
the registry.

## Workflow

1. Inspect the local template:

   ```bash
   python3 tools/d2s_demon_template_inspect.py <template.d2s>
   ```

   To extract a reusable local raw-payload template and YAML snippet:

   ```bash
   python3 tools/d2s_demon_template_inspect.py <template.d2s> \
     --extract-payload .local-demon-templates/<template>.bin \
     --emit-yaml-snippet
   ```

   The emitted snippet is preserve-only: it names `template_path` and
   `monster_hcidx` but does not add `source_affixes` or `skill_affixes`.
   Keep extracted templates outside the public repo unless they are
   intentionally safe to publish.

2. Attach row context when extracted table data is available:

   ```bash
   python3 tools/d2s_demon_template_inspect.py <template.d2s> \
     --excel-dir <extracted-excel-dir>
   ```

3. Compare candidate payload row indexes before model overrides:

   ```bash
   python3 tools/d2s_demon_template_inspect.py <template.d2s> \
     --excel-dir <extracted-excel-dir> \
     --compare-hcidx <target-row-index>
   ```

4. Split the inspected affix tuple into public YAML intent:

   - `source_affixes`: properties the source monster already carried.
   - `skill_affixes`: Bind Demon threshold properties, normally `auto`.
   - `effective_bind_level`: explicit only when chargen cannot infer the bind
     state.

5. Run chargen validation before build. YAML with non-empty
   `bound_demon.source_affixes` emits a warning because source-style labels
   require template-derived or validated package context, and public chargen
   does not synthesize arbitrary source effects, aura flavor, generated names,
   or hidden support branches. Non-`--yaml-only` validation also injects the
   resolved bound-demon payload into a temporary save and runs the scanner.

6. Build and scan in staging. Promote one save at a time only after the scanner
   passes.

7. Record the result as accepted, preserved, canonicalized, rejected, or still
   unproven. Do not record local paths, raw saves, or session logs.

## Recipe Contract

Every public recipe should include:

| Field | Meaning |
| --- | --- |
| Recipe name | Human-facing package label. |
| Template source | `template_path` placeholder or safe tracked fixture name. |
| Payload row index | `monster_hcidx`, the zero-based MonStats row index. |
| Source context requirement | Required, optional, or unknown source-affix context. |
| Source affixes | YAML `source_affixes` list. |
| Skill affixes | Usually `skill_affixes: auto`. |
| Effective Bind Demon level | Required only when overriding inferred level. |
| Known-good model scope | Model row(s) and template family proven for this recipe. |
| Canonicalization expectation | Authored fields that should be preserved or may be rewritten. |
| Unsupported edits | Seed overrides, unsupported source contexts, raw context-slice fields, unrelated rows, or synthesis. |
| Validation state | Current recipe state from the table below. |

## Recipe States

| State | Meaning |
| --- | --- |
| Draft | YAML intent exists, but build/scan has not proven the save shape. |
| Scanner-clean | The generated save scans without hard errors. |
| Offline accepted | D2R accepts the save and instantiates the follower. |
| Preserved | Save/exit keeps `follower_count=1`, the intended row index, and expected affix bytes. |
| Canonicalized | Save/exit rewrites known volatile/runtime bytes without changing the player-facing result. |
| Rejected | D2R strips the follower, fails to instantiate it, or writes a scanner-invalid shape. |

Do not call a recipe known-good until it reaches `Preserved` or an explicitly
documented `Canonicalized` state.

## Public YAML Shape

Use `template_path` for local templates outside the public repo:

```yaml
bound_demon:
  template_path: .local-demon-templates/<template>.d2s
  monster_hcidx: <payload-row-index>
```

That preserve-only form copies the extracted 116-byte payload into the generated
save. Add affix composition only when you intentionally want to rewrite the
seven MonUMod bytes:

```yaml
bound_demon:
  template_path: .local-demon-templates/<template>.bin
  monster_hcidx: <payload-row-index>
  source_affixes: [<source property>, ...]
  skill_affixes: auto
  effective_bind_level: <optional explicit level>
```

Use `template` only for a tracked fixture that is safe to ship publicly. The
legacy `affixes` / `raw_affixes` field is for low-level controls, not normal
recipes.

Use `mode: synthesis_validated` only for package ids listed by:

```bash
d2r-chargen bound-demon-packages
d2r-chargen bound-demon-packages --json
```

Normal package YAML should name the package, not raw seed/context bytes:

```yaml
bound_demon:
  mode: synthesis_validated
  package_id: row724-black-lancer-seedg-holy-shock-v1
```

## Requested Template Index

These entries are recipe templates, not committed `.d2s` template saves.
`template_path` values are placeholders for local captured templates.

| Recipe | Status | Payload row index | Local row id | Notes |
| --- | --- | ---: | --- | --- |
| Black Lancer seven-slot | Preserved | `724` | `cr_lancer9` | Proven compatible template family; one exact registry package is also enabled. |
| Mauler seven-slot | Preserved | `188` | `blunderbore3` | Primary Mauler-family target; the seven-affix tuple preserved and user validation matched expectations. |
| Alternate Mauler seven-slot | Preserved | `620` | `blunderbore6` | Separate Mauler-family row with the same preservation result; keep distinct from row `188`. |
| Hephasto / Hephaesto | Draft, compatible template required | `409` | `hephasto` | Current row swaps from an unrelated shell saved back with no follower; use only with a captured compatible template. |
| Lister-style Baal Subject 5 seven-slot | Preserved | `572` | `baalminion1` | Lister-style target from extracted tables; the seven-affix tuple preserved and user validation matched expectations. |

## Known Package: Black Lancer Seven-Slot

Status: `Preserved` for the proven compatible template family.

Purpose: author a high-tier Black Lancer-style bound demon with Fanaticism aura
flavor, Aura Enchanted, source-style labels, and full Bind Demon threshold
properties.

| Field | Value |
| --- | --- |
| Template source | Local proven Black Lancer-compatible template outside the public repo |
| Payload row index | `724` |
| Source context requirement | Required; use a template proven with compatible source-affix context |
| Source affixes | `Fanaticism`, `Aura Enchanted`, `Cursed`, `Stone Skin` |
| Skill affixes | `auto` |
| Effective Bind Demon level | `20` for the full seven-slot package |
| Expected affix tuple | Fanaticism, Aura Enchanted, Cursed, Stone Skin, Extra Strong, Extra Fast, Spectral Hit |
| Known-good model scope | Black Lancer row `724` with compatible template-derived source context |
| Canonicalization expectation | Follower payload remains valid; known volatile/runtime bytes may be rewritten |
| Unsupported edits | Seed overrides, template-free synthesis, unrelated model rows, unsupported source contexts |

YAML:

```yaml
bound_demon:
  template_path: .local-demon-templates/black-lancer-seven-slot.d2s
  monster_hcidx: 724
  source_affixes:
    - Fanaticism
    - Aura Enchanted
    - Cursed
    - Stone Skin
  skill_affixes: auto
  effective_bind_level: 20
```

Notes:

- Payload row `724` is the zero-based MonStats row index for the proven Black
  Lancer target.
- The exact package `row724-black-lancer-seedg-holy-shock-v1` is available
  through `mode: synthesis_validated` for users who want the registry-backed
  package instead of a local template.
- Fanaticism is source/aura flavor, not a Bind Demon threshold affix.
- Aura Enchanted stays in the source list for this package so the aura flavor
  remains adjacent to Fanaticism in the composed seven-slot tuple.
- Extra Strong, Extra Fast, Spectral Hit, and Aura Enchanted are the
  skill-threshold affixes at effective Bind Demon level 20; the composer
  removes duplicates when source and skill lists overlap.
- Compatible source context is required. The seven MonUMod bytes are necessary
  but not sufficient for every visible source property.

## Known Package: Mauler Seven-Slot

Status: `Preserved` for the exact row `188` source-context package.

Purpose: author a Mauler-style bound demon with the same seven-affix package
validated for Black Lancer.

| Field | Value |
| --- | --- |
| Template source | Local captured Mauler-compatible template outside the public repo |
| Payload row index | `188` |
| Local row id | `blunderbore3` |
| Source context requirement | Required; use the compatible source-context template from the validation path |
| Source affixes | `Fanaticism`, `Aura Enchanted`, `Cursed`, `Stone Skin` |
| Skill affixes | `auto` |
| Effective Bind Demon level | `20` for the full skill-threshold package |
| Expected affix tuple | Fanaticism, Aura Enchanted, Cursed, Stone Skin, Extra Strong, Extra Fast, Spectral Hit |
| Known-good model scope | Row `188` with the compatible source-context shell |
| Canonicalization expectation | Known volatile/runtime bytes may be rewritten; seven-affix tuple persisted |
| Unsupported edits | Treat row `620` / `blunderbore6` as a separate alternate target |

YAML:

```yaml
bound_demon:
  template_path: .local-demon-templates/mauler.d2s
  monster_hcidx: 188
  source_affixes:
    - Fanaticism
    - Aura Enchanted
    - Cursed
    - Stone Skin
  skill_affixes: auto
  effective_bind_level: 20
```

Notes:

- The local extracted MonStats table has two `Mauler` rows. This template uses
  row `188` / `blunderbore3` as the primary target.
- Row `620` / `blunderbore6` also has `NameStr=Mauler`; the follow-up
  run preserved the same seven-affix tuple for this alternate row, and user
  validation confirmed it looked as expected.
- The first Offline pass preserved the row `188` follower after save/exit with
  the Bind Demon level-20 skill tuple `05 06 1b 1e 00 00 00` because that demo
  was staged with only skill-threshold affixes.
- The source-context follow-up staged row `188` with
  `25 1e 07 1c 05 06 1b`; D2R saved it back with the tuple preserved and only
  known volatile bytes changed. User validation confirmed the result looked as
  expected in game.

## Draft Template: Hephasto / Hephaesto

Status: `Draft`; a compatible captured template is required.

Purpose: reserve a public YAML shape for the Hephasto-style smith demon target.

| Field | Value |
| --- | --- |
| Template source | Local captured Hephasto-compatible template outside the public repo |
| Payload row index | `409` |
| Local row id | `hephasto` |
| Source context requirement | Required; current non-Hephasto shell is not sufficient |
| Source affixes | none by default; table-derived superunique candidates are Spectral Hit and Aura Enchanted |
| Skill affixes | `auto` |
| Effective Bind Demon level | `20` for the full skill-threshold package |
| Known-good model scope | None yet |
| Canonicalization expectation | Unrelated-shell row swaps stripped the follower; a compatible template has not been validated here |
| Unsupported edits | Do not treat the SuperUniques `hcIdx` value as the payload row index |

YAML:

```yaml
bound_demon:
  template_path: .local-demon-templates/hephasto.d2s
  monster_hcidx: 409
  skill_affixes: auto
  effective_bind_level: 20
```

Notes:

- `hephasto` is the row spelling in the extracted MonStats table. The
  user-facing spelling `Hephaesto` is kept here as an alias for searchability.
- In the current local SuperUniques table, this target is named
  `The Feature Creep` and points at class `hephasto`.
- Superunique mods `27` and `30` map to Spectral Hit and Aura Enchanted. They
  are not included as default `source_affixes` until a compatible template
  proves the intended source context.
- Row-swap attempts from an unrelated source shell saved back with no follower
  payload. Do not treat row `409` as supported unless the user supplies a
  captured compatible Hephasto template and it passes validation.

## Known Package: Lister-Style Baal Subject 5 Seven-Slot

Status: `Preserved` for the exact row `572` source-context package.

Purpose: reserve a public YAML shape for the Lister-style Baal-wave demon
target while preserving the actual row names found in extracted tables and the
validated source-context package.

| Field | Value |
| --- | --- |
| Template source | Local captured Baal Subject 5-compatible template outside the public repo |
| Payload row index | `572` |
| Local row id | `baalminion1` |
| Source context requirement | Required; use the compatible source-context template from the validation path |
| Source affixes | `Fanaticism`, `Aura Enchanted`, `Cursed`, `Stone Skin`; table-derived superunique candidate is Spectral Hit |
| Skill affixes | `auto` |
| Effective Bind Demon level | `20` for the full skill-threshold package |
| Expected affix tuple | Fanaticism, Aura Enchanted, Cursed, Stone Skin, Extra Strong, Extra Fast, Spectral Hit |
| Known-good model scope | Row `572` with the compatible source-context shell |
| Canonicalization expectation | Known volatile/runtime bytes may be rewritten; seven-affix tuple persisted |
| Unsupported edits | Do not claim literal Lister display identity unless the user's extracted tables and validation confirm it |

YAML:

```yaml
bound_demon:
  template_path: .local-demon-templates/baal-subject-five.d2s
  monster_hcidx: 572
  source_affixes:
    - Fanaticism
    - Aura Enchanted
    - Cursed
    - Stone Skin
  skill_affixes: auto
  effective_bind_level: 20
```

Notes:

- The current extracted tables did not contain a literal `Lester` or `Lister`
  row.
- The likely Lister-style target is SuperUniques `Baal Subject 5`, class
  `baalminion1`, whose MonStats row index is `572`.
- If a different data set restores the classic display name, rerun template
  inspection and update this entry with that row context before validation.
- The first Offline pass preserved the row `572` follower after save/exit with
  the Bind Demon level-20 skill tuple `05 06 1b 1e 00 00 00` because that demo
  was staged with only skill-threshold affixes.
- The source-context follow-up staged row `572` with
  `25 1e 07 1c 05 06 1b`; D2R saved it back with the tuple preserved and only
  known volatile bytes changed. User validation confirmed the result looked as
  expected in game.

## Mod Integration Notes

Payload `monster_hcidx` values are zero-based MonStats row indexes. They are
not the MonStats `*hcIdx` column. If a data mod changes MonStats row order,
MonStatsEx links, MonStats2 assumptions, Skills thresholds, or MonUMod labels,
rerun template inspection against the extracted table set used for the build.

Changing the Bind Demon skill table changes what `skill_affixes: auto` means.
Update the threshold resolver and tests before documenting a recipe that
depends on changed thresholds.

Do not publish a recipe as portable across mods unless the relevant MonStats,
MonStats2, Skills, and MonUMod assumptions are named and checked.

## Review Checklist

- The recipe uses `template_path` or a safe tracked fixture.
- The row index came from template inspection, not the `*hcIdx` column.
- Source affixes and skill affixes are separate.
- Chargen validation warned for any non-empty `source_affixes` list, and the
  warning was reviewed before build.
- Source-context requirements are explicit.
- Seed overrides are absent.
- If using `mode: synthesis_validated`, the YAML names an enabled package id
  and does not include raw context-slice fields.
- If using `template_path`, `mode: synthesis`, `synthesize: true`,
  `package_id`, and raw context-slice fields are absent.
- Scanner validation precedes Offline acceptance claims.
- The result is summarized as stable behavior, not a session log.
