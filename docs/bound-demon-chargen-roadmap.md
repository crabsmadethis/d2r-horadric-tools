# Bound Demon Chargen Roadmap

This roadmap defines the public chargen path for Reign of the Warlock
bound-demon support. The current supported direction is template-derived
authoring: start from a known 116-byte follower payload, preserve unknown
bytes, and expose only fields that have scanner and Offline validation behind
them.

Arbitrary template-free synthesis remains blocked. A scanner-clean payload is
not enough: D2R must instantiate the demon, keep `follower_count=1` after
save/exit, and preserve or predictably canonicalize every authored field. A
narrow seed-backed Black Lancer proof now exists, but it is not yet a public
`monster: NAME` writer contract.

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

An experimental internal initializer now exists for tests and research tooling:
`d2r_chargen.demon_synthesis.build_bound_demon_payload`. It builds a 116-byte
payload only from explicit row, seed, affix, and named context-slice inputs.
This is not a public `monster: NAME` writer and should not be wired to normal
YAML without a validation mode that names the exact support record.

## Field Confidence

| Offset | Meaning | Writer posture |
| --- | --- | --- |
| `+0..+1` | follower kind tag `0x0018` | Fixed for known bound demons. |
| `+4..+5` | `monster_hcidx` | Authorable in template-derived payloads. Values are zero-based MonStats row indexes, not the MonStats `*hcIdx` column. |
| `+6..+9` | monster seed | Preserve from template for v1.2 recipes. For the narrow row-724 Black Lancer true-synthesis proof, a compatible seed was required and seed-only synthesis preserved the seven-affix tuple plus the validated visible generated names. Incompatible/default seeds zeroed the authored MonUMod tuple. A seed-only runtime read did not preserve the earlier context-rich Aura Enchanted flavor for the same seed, so do not expose arbitrary seed/name/aura authoring until the RNG/context semantics are decoded or the user supplies an explicitly validated seed. |
| `+24..+31` | `runtime_stats_24_31` | D2R-rewritten in some controls and not normal player-facing YAML. In the current row-724 Black Lancer true-synthesis proof, this slice was sufficient to restore the context-rich Aura Enchanted branch for a validated seed while bitfields-only and post-`gf`-tail-only controls were not. Cross-seed controls reused the original nonzero slice with seedh and seedi and decoded as seed-specific Might level 11 and Holy Fire level 11; all-zero controls for the same seeds preserved the package but decoded as level-1 Holy Freeze and Might. The compact Aura Enchanted activation pair also depends on this slice: Aura Enchanted with zero slice activates a level-1 seed-selected/default aura branch, while the same tuple plus `02 00 00 00 43 00 00 00` restores the higher branch. Current compact results with the original slice are Fanaticism level 8 for seed `0x0008F2C2`, Holy Shock level 8 for seed `0x0008F2C8`, Might level 11 for seed `0x0008F2C9`, and Holy Fire level 11 for seed `0x0008F2CA`; row-188 and row-572 repeats for seed `0x0008F2C2` kept the zero-slice Might / nonzero-slice Fanaticism pattern. Aura Enchanted-only repeats for seedc2, seedg, seedh, and seedi reproduced the same selected modifier skill/level branches as the matching Fanaticism + Aura Enchanted pairs, so the Fanaticism byte is not required for aura skill/level selection in the current support set. Compact Aura Enchanted plus Stone Skin and compact Aura Enchanted plus Cursed also preserved the seedc2 zero-slice Might / nonzero-slice Fanaticism branch. Four additional genuine source slices now show this is not a binary nonzero gate: `02 00 00 00 55 00 00 00` gives seedc2 Fanaticism level 11, `53 00 00 00 52 00 00 00` gives seedc2 Fanaticism level 10, and the 6b-family slices `6b 00 00 00 55 00 00 00` / `6b 00 00 00 57 00 00 00` both give seedc2 Fanaticism level 11. A separate Cursed-only row-724 mutation loop shows nonzero source slices do not drive the hidden Cursed-only branch; they route normally with no selected modifier branch. Treat this slice as an internal or explicitly validated aura-context input, not a decoded generic field or direct aura id. |
| `+44..+51` | `percent_or_caps_44_51` | Matched row-20 p1/p4/p8 captures produced repeated decimal `0`, `150`, and `350`, matching `50 * (players - 1)`. Controlled one-slice edits preserved authored zero, `350`, and exaggerated `3500` values through load/save. Healthy runtime replays for actual p1/p4/p8 all kept HP/maxHP `32768/32768` in the currently decoded stat branches, and controlled context isolates did not turn `+44/+48` into a standalone visible-strength knob. Treat as a writer-controllable player-count-shaped field for the tested shell, but keep template-owned until the exact HP/damage/AR/defense semantic is proven. |
| `+52..+55` | persisted bind metadata | Persistent bind metadata, not effective Bind Demon skill level. |
| `+64..+79` | `bitfields_64_79` | Source-context slice. Can be required for visible source-style affixes, and p8-derived variants are load/save-stable in row-20 player-count isolates. Bitfields alone, and bitfields combined with the p8-derived post-`gf` tail without volatile bytes, did not reproduce the high runtime modifier branch. Keep template-owned until semantic effect is proven. |
| `+80..+86` | seven MonUMod affix bytes | Authorable in template-derived payloads; composed from source affixes plus skill-granted affixes. Seed-backed matrix evidence shows compact tuples can persist on rows `724` and `188`, but visual/runtime semantics are narrower: Cursed and skill-threshold tuples render, while Fanaticism alone does not create a visible label or selected-bound-demon aura modifier. Aura Enchanted activates an aura branch; the validated runtime context slice then restores seed-selected flavor rather than a universal Fanaticism output. Aura Enchanted-only repeats for seedc2, seedg, seedh, and seedi reproduced the same selected modifier skill/level as Fanaticism plus Aura Enchanted. Compact Aura Enchanted plus Stone Skin and compact Aura Enchanted plus Cursed preserved the selected aura branch, but visible labels for those sibling tuples still need validation. This has been repeated on rows `188` and `572`, but still belongs to a validated support set rather than arbitrary source-affix/aura selection. |
| `+88` | `hash_or_runtime_byte_88` | D2R-rewritten in same-model controls; do not author. |
| `+89..+91` | volatile runtime bytes | D2R-rewritten; copied p8 values are canonicalized on load/save. P8-derived values alone did not reproduce the high runtime modifier branch. Do not author. |
| `+92..+93` | embedded `gf` payload data | Payload data, not a section marker. |
| `+94` | `post_gf_opcode_94` | Structural for known 116-byte payloads; keep `06`. |
| `+95..+97` | health-like runtime-tail candidate | A damaged controlled p8-percent save changed these bytes while preserving row, affixes, and `+44/+48 = 350`. Interpreted as little-endian fixed-point x256, the movement is health-like, but reload validation showed the demon loaded full. P8-derived tail isolates stayed load/save-stable but did not reproduce the high runtime modifier branch. Preserve from template; do not treat it as authoritative visible current HP. |
| `+98..+115` | remaining `post_gf_tail_95_115` | Mixed structural/runtime tail. The p8-derived tail is load/save-stable in a row-20 p1-derived shell, but tail-only and tail-plus-bitfield isolates did not explain actual p8 strength. Preserve from template unless a narrow probe proves a target-specific rewrite. |

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
template has compatible source context. In current true-synthesis evidence,
the Fanaticism byte persists in compact tuples but does not independently
activate the runtime aura modifier. The current minimal tested activation
recipe also requires Aura Enchanted plus the validated `runtime_stats_24_31`
slice; seed still participates in flavor, so keep Fanaticism/Aura Enchanted
recipes tied to validated package context until broader row and seed repeats
exist. User
visual validation confirmed the row-724 nonzero-slice pair: the seed
`0x0008F2C2` case showed Fanaticism and the seed `0x0008F2C8` case showed
Holy Shock. The row-188 and row-572 repeats preserved the same zero-slice
default and nonzero-slice Fanaticism pattern for seed `0x0008F2C2`; the row-724
seed `0x0008F2C9` compact repeat matched the broader seedh aura matrix with
zero-slice Holy Freeze level 1 and nonzero-slice Might level 11. The row-724
seed `0x0008F2CA` compact repeat also matched the broader seedi matrix with
zero-slice Might level 1 and nonzero-slice Holy Fire level 11. Aura
Enchanted-only repeats for seedc2, seedg, seedh, and seedi reproduced the same
selected modifier skill/level branches as the matching Fanaticism plus Aura
Enchanted pairs, showing that the Fanaticism byte is not required for aura
branch selection in the current support set.
Compact Stone Skin and Cursed siblings now preserve the same selected aura
branch for seed `0x0008F2C2`: Aura Enchanted plus Stone Skin and Aura Enchanted
plus Cursed both decode as Might level 1 with zero `runtime_stats_24_31` and
Fanaticism level 8 with the validated nonzero slice. Player-visible Stone Skin
and Cursed label rendering for those compact sibling tuples remains a
validation gate; sanitized runtime summaries classify Stone Skin as raw selected stat `36`
(`damageresist`) increasing from `33` to `83`, while compact Aura+Cursed still
needs a deeper source-effect or UI-label decoder.
Additional genuine source slices now show the runtime slice carries more than
zero/nonzero state. Aura Enchanted-only seedc2 with
`02 00 00 00 55 00 00 00` decodes as Fanaticism level 11, while
`53 00 00 00 52 00 00 00` decodes as Fanaticism level 10. The 6b-family
source slices `6b 00 00 00 55 00 00 00` and
`6b 00 00 00 57 00 00 00` both decode as Fanaticism level 11.
Screenshot-based user review confirmed both row-188 cases look like
Mauler-family demons with an aura; runtime decode remains the source of the
specific Might/Fanaticism distinction.

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
| 4 | `synthesis_validated` package | Build all 116 bytes without copying a template payload, using a package registry with validated seed/context/canonicalization facts. | Initial exact row-724 package enabled; expand only by registry entry |
| 5 | algorithmic `synthesis` / `monster: NAME` | Derive row, generated-name seed, aura context, affix context, pcount/stat policy, and canonicalization from declared intent. | Research-only until the full support matrix exists |

Future YAML must keep these modes separate:

- `template_path`: template-derived only; preserve local payload context and
  author proven high-confidence fields.
- `synthesis_validated`: validated package synthesis; require a package id and
  explicit seed/context slices, and claim generated name or aura only when the
  public-safe registry/support record has runtime proof for that exact package.
- `synthesis`: algorithmic synthesis for declared rows/features only after the
  full support matrix is complete. This is not the current public chargen
  target.

Current public chargen accepts `mode: synthesis_validated` only when the request
names an enabled registry `package_id` and stays inside that package's exact row
and seed. It rejects `mode: synthesis`, `synthesize: true`, unknown
`package_id` values, and raw context-slice fields such as
`runtime_stats_24_31`. That fail-fast behavior is intentional: unsupported
fields are not hidden template-derived overrides.

The current public synthesis target is described in
`docs/bound-demon-validated-synthesis-plan.md`: expand the validated-package
registry, diagnostics, template extraction, and hard fail-fast behavior before
adding more `synthesis_validated` packages.

## v1.2 Release Gate

v1.2 should ship only when the template workflow is useful without implying
template-free synthesis:

- `tools/d2s_demon_template_inspect.py` is the first recipe step.
- Recipe docs identify template source policy, row index, source context,
  source affixes, skill-affix mode, unsupported edits, and validation state.
- Player-facing YAML keeps `source_affixes` separate from
  `skill_affixes: auto`.
- Chargen validation warns when a recipe requests non-empty
  `source_affixes`, so the template-derived or validated-package context
  dependency is visible before build. The warning also states that public
  chargen does not synthesize arbitrary source effects, aura flavor, generated
  names, or hidden support branches.
- Non-`--yaml-only` chargen validation injects requested bound-demon and
  Iron Golem payloads into a temporary save, so scanner output catches malformed
  follower/golem blocks before promotion.
- Each published recipe has build -> scan -> Offline load -> save/exit ->
  rescan evidence, summarized as public-safe behavior.
- Seed overrides, arbitrary source-context edits, arbitrary model swaps, and
  template-free `monster: NAME` synthesis stay out of the v1.2 supported
  surface. A later synthesis surface may accept explicit validated
  `monster_seed` values, but should not imply generated-name or aura selection
  until the seed tables/RNG/context behavior is decoded.

Use `docs/bound-demon-template-recipes.md` for the recipe contract. The first
known package is the Black Lancer seven-slot recipe: template-derived,
context-required, row index `724`, and not portable template-free synthesis.
Draft row-context templates can reserve future recipe targets, but they must
stay clearly marked until build, scan, Offline load, save/exit, and rescan
evidence exists.

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

Current narrow true-synthesis result: no-affix field-built payloads can survive
for row `20` and row `724`. For the proven row-724 Black Lancer seven-affix
package, the compatible `monster_seed` is the persistence gate. The tested
row-724 runtime stats, bitfields, and post-`gf` tail are not required for row,
affix, and generated-name persistence once a compatible seed is authored. They
are not solved generally, though: a direct seed-only aura read did not match
the earlier context-rich aura result for the same seed. A single-slice
follow-up restored that aura only when the validated `runtime_stats_24_31`
context slice was included. This is now user-visually validated for the first
aura-preserving package: the generated name stayed on the expected same-seed
name and the aura appeared as a lightning aura. This is enough to plan explicit
validated-package synthesis with aura-context inputs; it is not enough to
promise arbitrary generated names, arbitrary aura flavors, or every monster
row. A row-724 and row-188 source-affix matrix now also proves byte-level
persistence for Fanaticism-only, Cursed-only, Fanaticism+Cursed, and the
skill-threshold-only tuple with seed `0x0008F2C2`. User visual validation shows
Cursed-only and skill-threshold-only render as expected, while Fanaticism-only
does not visibly render and Fanaticism+Cursed renders only Cursed. Do not expose
Fanaticism/source-aura partial tuple authoring as semantically supported until
the missing context rule is decoded. Sanitized runtime summaries show one
additional support-set wrinkle for row-724 Cursed-only controls: a zero
source-slice case can follow a hidden Fanaticism-shaped selected branch, while a
corrected row-188 repeat observed the expected Mauler runtime unit and was
negative for that hidden branch. The row-724 hidden branch matches known Aura
Enchanted-only Fanaticism level-11 source-slice references, so this is a
row-724 source-context effect-family collision, not public generic Cursed
support. User visual validation confirmed the row-724 Cursed-only case is
Cursed with no aura; the Fanaticism presentation belongs to the Aura Enchanted
references. Nonzero Cursed-only source-slice controls route normally with no
selected modifier branch, so the hidden route is a zero-source-slice row-724
support-set behavior, not arbitrary Cursed authoring.
The first cross-seed controls now show why: seedh and seedi with the same
runtime-stat slice kept seed-specific aura outcomes, Might level 11 and
Holy Fire level 11, instead of becoming Holy Shock.

The first row/family matrix has also moved past local staging. Using the same
explicit-field initializer and the same seven-affix package, live Offline
load/save evidence preserves rows `188`, `347`, `572`, and `620`; a second-seed
repeat with seed `0x0008F2C8` now preserves the same package on all four rows
and observes runtime rows `187`, `346`, `571`, and `619`. Row `409` saves back
without a follower across both tested seeds and remains unsupported in the
current shell. These are row/seed persistence support records, not a public
arbitrary monster contract. Generated-name behavior, Aura Enchanted flavor, and
source-affix context still need support-set entries before a public synthesis
mode can promise those semantics; current canonicalization profiles only
describe the tested packages.

## Stable Model Findings

Model identity is target-dependent.

- Fallen-family row-index-only swaps are not solved. One same-family target
  was visible but stripped on save; another preserved a hidden payload without
  a visible demon.
- Council Member row `347` is proven row-index-only from the current Fallen
  control and now also preserves the field-built seven-affix package in the
  row/family matrix across two tested seeds.
- Rows `188`, `572`, and `620` preserve the same field-built seven-affix
  package through Offline load/save across two tested seeds in the current
  support matrix. Treat them as validated row/seed persistence targets only
  until generated-name, aura, and source-affix context gates are filled in.
- Row `409` strips the field-built package in the current shell across both
  tested seeds and should stay behind template or unsupported diagnostics.
- Black Lancer uses payload row index `724`; an earlier value `723` produced a
  Dark Archer because payload `monster_hcidx` is a zero-based MonStats row
  index, not the `*hcIdx` column.
- Black Lancer affix visibility needs source context for source-style labels.
  Fanaticism is a source/aura-flavor input, and the visible aura path requires
  Aura Enchanted adjacent in the composed affix tuple.
- A generated seven-slot Black Lancer package displayed Fanaticism/Aura
  Enchanted, Cursed, Stone Skin, Extra Strong, Extra Fast, and Spectral Hit,
  then saved back with the follower payload unchanged.
- Mauler row `188`, alternate Mauler row `620`, and Baal Subject 5 row `572`
  can preserve valid followers with the seven-affix tuple
  `25 1e 07 1c 05 06 1b` from the current compatible shell. This answers
  byte-level persistence, and user validation confirmed the exact tested
  source-context packages looked as expected in game.
- Hephasto row `409` did not survive the current shell: row-swap tests saved
  back with no follower payload across both tested seeds.

## Active Demon Questions

These are the next demon-specific questions after the current seven-slot recipe
validation:

| Question | Why it matters | Next proof method |
| --- | --- | --- |
| Bound-demon name and aura seed behavior | Player-facing recipes need to preserve generated names and Aura Enchanted flavor predictably. Same-row/same-affix seed probes confirm that changing only `monster_seed` can change the visible generated name, while tested names were not stored as plain ASCII. Seed-only synthesis also preserved the expected visible names for two validated seeds. A seed-only aura read did not match the earlier context-rich aura result for the same seed, so aura flavor is a separate seed/context gate. | Preserve template seeds by default. For synthesis, accept only explicitly validated seed inputs until the prefix/suffix/appellation and Aura Enchanted flavor derivation is decoded. |
| Player-count stat scaling | A demon bound on `/players 8` appears stronger than one bound on `/players 1`; templates need to know whether HP/damage/AR/defense are stored in the follower payload or recalculated from game state. Matched row-20 p1/p4/p8 captures point at repeated decimal `0`, `150`, and `350` in payload `+44/+48`, matching `50 * (players - 1)`, but healthy replays for actual p1/p4/p8 kept the normal decoded stat profile. Controlled edits and context isolates show the known pcount/context bytes are not enough to expose a safe player-facing stat knob. | For v1.2, preserve template bytes and document that pcount strength is preserve-only. For v2.0 synthesis, collect combat-state evidence from actual p1/p8 demons, or add a repeatable evidence recipe for combat HP/damage/AR/defense outside the currently decoded healthy stat branches. |
| Semantic inspection snapshot | User validation worked for current labels, but it does not scale to name/stat research. | Add a repeatable public-safe evidence recipe so validated evidence can report row id, display name, labels, aura state, current/max HP, and location without relying on repeated manual screenshots. |
| Hephasto-compatible source context | Row `409` strips from the current shell, but that does not prove Hephasto can never be a recipe. | Inspect or capture a Hephasto-compatible bound template, compare row/model context, then stage one scanner-clean package before manual validation. |

These questions are still compatible with the template-derived approach. They
should not expose template-free synthesis until the full synthesis ladder has
generic byte rules.

These findings support template-derived recipes. They do not prove arbitrary
template-free synthesis.

## Public Validation Standard

Public docs should record stable behavior, limitations, and proof gates. Do not
commit raw saves, local paths, machine details, disposable character names, or
session diaries. Use `docs/manual-save-validation.md` for reusable public-safe
manual procedures.
