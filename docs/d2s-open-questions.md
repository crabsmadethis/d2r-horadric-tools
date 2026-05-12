# D2S Research Status

This page tracks public `.d2s` findings that still shape tooling decisions.
Answered questions belong in the confirmed table with their current limitation;
open questions must name the next proof method.

For release sequencing, see `docs/d2s-version-roadmap.md`.

## Confirmed Findings

| Area | Public finding | Tooling consequence |
| --- | --- | --- |
| Follower payload shape | Known bound-demon saves use `lf<u16:follower_count>` followed by exactly `count * 116` payload bytes. D2R accepts one known Warlock bound demon and rejects tested count-2 saves. | Writers support at most one bound demon and scanners reject count/payload mismatches. |
| Embedded payload markers | `payload[92:94] == b"gf"` is payload data, not a stats-section marker. | Parsers must not split the save at the embedded byte pair. |
| Template-derived authoring | Template-derived edits can preserve `monster_hcidx`, persisted bind metadata, and seven MonUMod affix bytes. Arbitrary seed override can strip the follower on save/exit. | Keep the supported player surface template-derived; preserve seeds and unknown slices by default. |
| Row-index identity | Payload `monster_hcidx` values are zero-based MonStats row indexes, not the MonStats `*hcIdx` column. Value `723` produced Dark Archer; corrected value `724` produced Black Lancer. | Inspection and model tools must use row indexes and should expose row-context comparisons before validation. |
| Bind Demon thresholds | Effective Bind Demon level grants Extra Strong at 5, Extra Fast at 10, Spectral Hit at 15, and Aura Enchanted at 20. Payload `+52` remained persisted metadata and is not the effective skill level. Source monster affixes can carry through separately. | YAML separates `source_affixes` from `skill_affixes: auto`; skill-granted affixes derive from effective Bind Demon level. |
| Seven-slot affix vector | The persisted MonUMod vector is seven bytes at `+80..+86`; `+85/+86` are overflow affix slots, not model-candidate bytes. | Writers and scanners should handle seven slots and avoid five-slot assumptions. |
| Source-affix context | Some visible source-style labels require compatible context outside the seven MonUMod bytes. Black Lancer source-label work showed `bitfields_64_79` can be sufficient for Cursed and Stone Skin, while copied post-`gf` tail bytes did not change that result. Fanaticism plus Aura Enchanted exposed the visible aura path; Aura Enchanted alone did not in the tested context. | Recipes must record source-context requirements. Fanaticism is source/aura flavor, not a Bind Demon threshold affix. |
| Same-model unknown slices | Same-model Fallen probes classify several slices as D2R-rewritten or structural. `+89..+91`, `+24..+31`, `+88`, `+96/+97`, `+104/+105/+106`, and `+109/+111/+112` can be rewritten; `+94` should remain `06`; `+101/+102` can save as an invalid 106-byte payload; `+114/+115` should be preserved as `f0 1f` for same-model Fallen. | Unknown slices stay template-owned unless a narrow target-specific probe proves otherwise. |
| Model identity | Model behavior is target-dependent. Fallen-family row-index-only swaps are not solved; Council Member `347` and Black Lancer `724` are proven from the current Fallen control. | Template-derived model recipes may be documented for proven targets, but arbitrary `monster: NAME` synthesis stays blocked. |
| Template inspection | `tools/d2s_demon_template_inspect.py` inspects one raw 116-byte payload or `.d2s` template without printing local paths, seed values, or raw unknown-slice bytes by default. It reports row index, bind metadata, labeled affix slots, unknown-slice posture, optional MonStats context, and candidate row comparisons. | Template inspection is the first v1.2 recipe step and the first step before a model-identity hypothesis. |
| Template recipes | `docs/bound-demon-template-recipes.md` defines the public recipe contract for template-derived packages without committing local template saves. Chargen validation warns when `bound_demon.source_affixes` is non-empty because source-style labels depend on compatible template source context, and binary validation scans requested follower/golem payloads in a temporary save. | Document reusable packages as validation-gated recipes, not as probe diaries, and make source-context requirements visible before build. |
| Cross-class followers | A structurally valid borrowed follower block can load on a non-Warlock save but is stripped back to `follower_count=0` on save/exit. | Do not expose cross-class follower payloads as normal chargen behavior. |
| Iron Golem block | Iron Golem data lives in `kf` before `lf` as a single variable-length item payload. | Generated golems use item encoding and must not write multiple golem payloads. |

## Open Questions

| Question | Why it matters | Next proof method |
| --- | --- | --- |
| Template-free bound-demon synthesis | A template-derived payload can be edited, but arbitrary synthesis requires knowing which bytes are fixed, generated, model-derived, volatile, source-context, or rejected. | Follow the synthesis ladder in `docs/bound-demon-chargen-roadmap.md`: inspect templates, classify corpora, run same-model binds, isolate affixes, mutate one slice at a time, then test same-family and cross-family model swaps before a synthetic initializer. |
| Broader model identity | Some targets are row-index-only from the current control, while same-family Fallen swaps are not. | Inspect candidate templates with `tools/d2s_demon_template_inspect.py --excel-dir <extracted-excel-dir> --compare-hcidx <target-row-index>`, compare rows with `tools/d2s_monster_model_compare.py`, then validate one documented row-index or companion-offset hypothesis at a time. |
| Merc status at `0xA7..0xA8` | The field has more observed values than the writer currently understands. | Group local saves by hireling id, difficulty, merc gear count, and progression. |
| Broader Iron Golem item families | Normal and magic generated golems are supported, but more item families need canonicalization-aware expectations. | Add synthetic fixture tests first; use manual validation only for item families tests cannot prove. |
| Rare item naming | Rare and crafted items carry first-name and last-name row ids separate from stat affixes. | Add fixture-backed name-resolution and import tests, then manually validate one deterministic rare per major item class. |
| Socketed jewels through chargen | Simple rune fillers are supported, but magic or rare jewel fillers remain unsafe until parent/filler counts and bit offsets are proven. | Build one staged socketed parent with one jewel filler, scan structure, then validate Offline. Until proven, merge intended jewel stats onto the parent item. |
| Shared stash support | Shared stash files are outside the character `.d2s` and have a larger blast radius. | Decode disposable Offline profile stash files into public-safe structure notes, then create a separate backup/edit/scan/restore ladder before writer support. |
| Expansion quest and misc items | Misc item bases exist, but stack counts, quest flags, usability, placement, and acceptance are not broadly proven. | Expand synthetic fixtures by family, verify quantity/stack behavior, then manually validate one representative per family. |

## Recording Rules

- Put durable byte-layout facts in `docs/d2s_format.md`.
- Put reusable manual procedures in `docs/manual-save-validation.md`.
- Do not commit raw saves, local paths, private evidence, or session diaries.
- Do not leave answered questions in the open table.
