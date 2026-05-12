# Bound Demon Template Recipes

Bound-demon support is template-derived. A recipe is the public-safe contract
for turning one local captured template into repeatable YAML intent without
committing the template save.

Use this page for v1.2 player-facing demon packages. Template-free
`monster: NAME` synthesis remains blocked until the full payload synthesis
ladder in `docs/bound-demon-chargen-roadmap.md` passes.

## Workflow

1. Inspect the local template:

   ```bash
   python3 tools/d2s_demon_template_inspect.py <template.d2s>
   ```

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
   require compatible template source context. Non-`--yaml-only` validation
   also injects the resolved bound-demon payload into a temporary save and runs
   the scanner.

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
| Unsupported edits | Seed overrides, unsupported source contexts, unrelated rows, or synthesis. |
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
  source_affixes: [<source property>, ...]
  skill_affixes: auto
  effective_bind_level: <optional explicit level>
```

Use `template` only for a tracked fixture that is safe to ship publicly. The
legacy `affixes` / `raw_affixes` field is for research controls, not normal
recipes.

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
- Fanaticism is source/aura flavor, not a Bind Demon threshold affix.
- Aura Enchanted stays in the source list for this package so the aura flavor
  remains adjacent to Fanaticism in the composed seven-slot tuple.
- Extra Strong, Extra Fast, Spectral Hit, and Aura Enchanted are the
  skill-threshold affixes at effective Bind Demon level 20; the composer
  removes duplicates when source and skill lists overlap.
- Compatible source context is required. The seven MonUMod bytes are necessary
  but not sufficient for every visible source property.

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
- Scanner validation precedes Offline acceptance claims.
- The result is summarized as stable behavior, not a session log.
