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
| `v1.3` | Item-family completion | Better character and follower items: symbolic rare/crafted naming, broader Iron Golem item families where proven, expansion quest/misc items, and a socketed-jewel decision. | Fixture-backed encode/decode tests, scanner assertions for parent/filler counts, and one representative Offline validation per newly supported family. | Shared stash mutation and arbitrary jewel sub-items if parent/filler proof still fails. |
| `v1.4` | Stash and profile boundary | Read/inspect support for shared stash plus a separate stash safety ladder. Writer support follows only after backup/restore behavior is repeatable. | Disposable profile decode, public-safe structure notes, restore test, scanner checks, and separate manual validation recipe. | Shared stash writer by default and any operation without a restore path. |
| `v2.0` | Template-free bound-demon synthesis | A gated synthesis writer that builds the 116-byte follower payload from stable inputs and documented canonical rewrites. | Template inspection, corpus classification, same-model binds, affix isolation, one-slice mutations, same-family and cross-family model swaps, then a synthetic initializer that scans, loads visibly, saves, and rescans with `follower_count=1`. | General claims for every monster row and writer paths where scanner-clean does not match Offline behavior. |

## Open-Question Routing

| Open question | Route |
| --- | --- |
| Template-free bound-demon synthesis | `v2.0`, after the full synthesis ladder passes. |
| Broader model identity | Constrain through recipes in `v1.2`; solve selected target sets in `v2.0`. |
| Merc status at `0xA7..0xA8` | Backlog unless it blocks item, merc, or stash work; likely grouped with `v1.4` profile evidence. |
| Broader Iron Golem item families | `v1.3`, one family at a time. |
| Rare item naming | `v1.3`, because it affects normal character authoring before synthesis. |
| Socketed jewels through chargen | `v1.3`, only if parent/filler scanner proof is clean. |
| Shared stash support | `v1.4`, with a separate safety ladder. |
| Expansion quest and misc items | `v1.3`, family by family. |

## Next Checkpoint

`v1.1.0` is published. The next public checkpoint is `v1.2`: turn current D2S
findings into a usable single-player demon-template workflow without implying
template-free synthesis.

Immediate `v1.2` gate:

- Inspect candidate templates with `tools/d2s_demon_template_inspect.py`.
- Use `--excel-dir` and `--compare-hcidx` before staging model-identity work.
- Expand `docs/bound-demon-template-recipes.md` from the first Black Lancer
  package into additional known-good recipes only after scan and Offline
  validation.
- Keep seed overrides, unsupported source contexts, arbitrary model swaps, and
  template-free `monster: NAME` synthesis out of the player-facing surface.
