# D2S Version Roadmap

Status: planning reference for public `.d2s` and mod-tooling releases. Version
labels align with package tags when a milestone is published.

This roadmap turns `docs/d2s-open-questions.md` into release gates. The bias is
to ship useful template-derived tools while keeping template-free synthesis
behind proof.

## Release Principles

- Ship proven authoring surfaces before solving every unknown byte.
- Keep answered research questions out of the open-question table.
- Treat scanner hard errors as release blockers.
- Require parser/scanner coverage for every writer feature.
- Require a backup -> build/edit -> scan -> Offline validation path for
  save-affecting features.
- Keep raw saves, local paths, private evidence, and disposable validation
  details out of the public repo.

## Version Map

| Version | Theme | User-facing result | Proof gate | Held back |
| --- | --- | --- | --- | --- |
| `v1.1.0` | Demon and Iron Golem support | Seven-slot bound-demon affix parsing, `template_path`, `source_affixes`, `skill_affixes: auto`, row-index model authoring for proven targets, normal/magic Iron Golem support, and coherent docs. | Public hygiene, Ruff, CI-style public pytest subset, focused follower tests, and template-path build/scan coverage. | Template-free demon synthesis, arbitrary model swaps, shared stash writers, and complex socket-filler authoring. |
| `v1.2` | Player-facing bound-demon templates | A practical template workflow: inspect a local template, attach optional MonStats row context, compose source plus skill affixes, document reusable packages, and warn when a request depends on template context. `tools/d2s_demon_template_inspect.py` is the first step; `docs/bound-demon-template-recipes.md` is the recipe contract. | Each documented recipe passes `d2r-chargen validate` with the resolved follower payload scanned, then builds, loads in Offline play, saves, and rescans with either preserved bytes or documented canonical rewrites. | `monster: NAME` synthesis with no template, seed overrides, unsupported source contexts, and arbitrary model swaps. |
| `v1.3` | Item-family completion | Better character and follower items: symbolic rare/crafted naming, canonicalization-aware Iron Golem item families including runewords, expansion quest/misc items, and a narrow socketed magic/unique-jewel surface if productized. | Fixture-backed encode/decode tests, scanner assertions for parent/filler counts, and one representative Offline validation per newly supported family. | Shared stash mutation, arbitrary jewel sub-items, and broader socketed jewel families without separate proof. |
| `v1.4` | Stash and profile boundary | Read/inspect support for shared stash plus a separate stash safety ladder. Writer support follows only after backup/restore behavior is repeatable. | Disposable profile decode, public-safe structure notes, restore test, scanner checks, and separate manual validation recipe. | Shared stash writer by default and any operation without a restore path. |
| `v2.0` | Validated bound-demon support-set synthesis | A registry-backed `synthesis_validated` writer that builds exact validated 116-byte packages from public code and public-safe package records, plus first-class template inspection/extraction for users who have an existing demon. | A package registry, actionable diagnostics, extraction workflow, scanner-backed build validation, Offline load/save evidence, canonicalization profiles, and semantic support flags for each package. The first narrow row-724 Black Lancer seed-backed proof is live-positive for persistence and validated names, and a validated `runtime_stats_24_31` slice restores the context-rich aura for one user-visible package; broader rows and generated-name/aura promises require package entries before exposure. | Universal `monster: NAME` synthesis, general claims for every monster row, generated-name authoring without decoded or registered seed semantics, aura-flavor authoring without decoded or registered context proof, pcount/combat-stat knobs, and writer paths where scanner-clean does not match Offline behavior. |

## Open-Question Routing

| Open question | Route |
| --- | --- |
| General template-free bound-demon synthesis | Research-only until the algorithmic matrix exists. Public `v2.0` stops at registry-backed support-set synthesis and template extraction, not universal `monster: NAME` authoring. |
| Bound-demon name/aura generation algorithm | `v1.2` documents seed/context preservation and the confirmed seed/name dependency while keeping aura flavor separate; `v2.0` may accept only package-registered seed/name/aura claims before any generated-name or aura authoring is exposed. |
| Bound-demon player-count stat scaling | `v1.2` recipe guidance if captured templates simply preserve stronger demons; keep public `v2.0` fail-fast for HP/damage/AR/defense knobs unless a package explicitly validates those semantics. |
| Bound-demon semantic inspection | Public-safe evidence recipe prerequisite for scalable name/stat validation; keep public output to sanitized findings. |
| Broader model identity | Constrain through recipes in `v1.2`; promote only selected row/family packages through the `v2.0` registry. |
| Merc status at `0xA7..0xA8` | Backlog unless it blocks item, merc, or stash work; likely grouped with `v1.4` profile evidence. |
| Runeword Iron Golem canonicalization details | `v1.3` polish: parent-plus-filler support now passes scanner and Offline validation for Insight and Strength, but exact parent rewrite fields can be documented more deeply. |
| Unique Iron Golem canonicalization details | `v1.3`, optional polish for byte-level rewrite expectations. |
| Rare item naming | `v1.3`, because it affects normal character authoring before synthesis. |
| Broader socketed jewels through chargen | `v1.3` for the narrow normal-parent magic `jew` and unique `cjw` cases after YAML productization; rare jewels, other unique variants, and other parent qualities stay gated separately. |
| Shared stash support | `v1.4`, with a separate safety ladder. |
| Expansion quest and misc items | `v1.3`, family by family. |

## Next Checkpoint

`v1.1.0` is published. The next public checkpoint is `v1.2`: turn current D2S
findings into a usable single-player demon-template workflow without implying
template-free synthesis.

Immediate `v1.2` gate:

- Inspect candidate templates with `tools/d2s_demon_template_inspect.py`.
- Use `--excel-dir` and `--compare-hcidx` before staging model-identity work.
- Keep `docs/bound-demon-template-recipes.md` split between proven recipes and
  draft row-context templates. Promote draft entries to known-good only after
  scan and Offline validation.
- Treat `/players`-dependent demon strength as template-preserved behavior in
  v1.2. Do not expose HP, damage, AR, defense, or pcount synthesis knobs until
  combat-state runtime evidence supports the exact field semantics.
- Keep seed overrides, generated-name authoring, explicit aura-flavor authoring,
  unsupported source contexts, arbitrary model swaps, and template-free
  `monster: NAME` synthesis out of the v1.2 player-facing surface. Carry the
  narrow seed-backed synthesis proof into v2.0 planning as a package-registry
  contract, not as arbitrary name/aura selection.
- Use `docs/bound-demon-validated-synthesis-plan.md` as the v2.0 chargen plan:
  add a validated-package registry, diagnostics, template inspection/extraction,
  and hard fail-fast behavior. The first exact `synthesis_validated` package is
  enabled; add more only through registry promotion.
