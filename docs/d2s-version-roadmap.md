# D2S Version Roadmap

Status: planning reference for public `.d2s` and mod-tooling releases. Version
labels align with package tags when a milestone is published. `v1.2.0` is
published on GitHub `main`; the active public checkpoint is `v1.3`.

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
| `v1.2.0` | Player-facing bound-demon templates | Published template workflow: inspect or extract a local template, use preserve-first `template_path`, list exact `synthesis_validated` packages, document reusable package/catalog entries, and warn or fail when a request depends on unvalidated template/source context. `tools/d2s_demon_template_inspect.py` is the entry point; `docs/bound-demon-template-recipes.md` is the recipe contract. | Public hygiene, Ruff, GitHub Actions on Python 3.11 and 3.12, template extraction tests, package-listing tests, scanner-backed build validation, and merged PR #14 at `7271b27`. | `monster: NAME` synthesis with no template, generated-name authoring, aura-flavor authoring outside package claims, unsupported source contexts, and arbitrary model swaps. |
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
| Runeword Iron Golem canonicalization details | `v1.3` polish: parent-plus-filler support now passes scanner and Offline validation for Insight and Strength, and regression coverage now checks parent-only and socket-filler-only diff grouping. Further work is live-evidence documentation, not a new writer surface. |
| Unique Iron Golem canonicalization details | `v1.3`, optional polish for byte-level rewrite expectations. The Gnasher axe-family and Tarnhelm helm-family proofs now both preserve the single-parent shape while rewriting different parent offsets. |
| Rare item naming | `v1.3`, because it affects normal character authoring before synthesis. |
| Broader socketed jewels through chargen | `v1.3` now exposes the narrow normal-parent `stash_items` surface for one magic `jew` filler or the validated `Guardian's Thunder` unique `cjw` filler. Rare jewels, other unique variants, other parent qualities, and Iron Golem jewel fillers stay gated separately. |
| Shared stash support | `v1.4`, with a separate safety ladder. |
| Expansion quest and misc items | `v1.3`, family by family. |

## Next Checkpoint

`v1.2.0` is published. The next public checkpoint is `v1.3`: item-family
completion for ordinary character and follower authoring. This is the track
that should catch player-facing build quality issues such as anonymous rare
names, incomplete rare/crafted naming, and under-productized socket-filler
surfaces before they reach curated examples or travel characters.

Immediate `v1.3` gates:

- Keep rare and crafted item naming under regression: numeric and symbolic
  first/last name fields now have fixture-backed encode/import coverage,
  preserve through Offline load/save, and resolve visible names through
  `RareSuffix.txt` for both displayed words. Any future naming expansion needs
  the same fixture plus Offline tooltip proof before changing the authoring
  contract.
- Keep Iron Golem canonicalization detail current: parent-versus-filler diff
  grouping is covered for runewords, and the unique-family map now includes
  both The Gnasher and Tarnhelm with focused regression coverage for each
  documented rewrite shape. The next useful polish is another representative
  unique family only if it would change the public opt-in warning or writer
  behavior.
- Keep the newly exposed narrow socketed-normal parent surface under
  regression: `stash_items` may build one normal socketed parent with exactly
  one magic `jew` or validated `Guardian's Thunder` `cjw` filler. Rare jewels,
  broader unique variants, socketed magic/rare parents, and Iron Golem jewel
  fillers stay gated separately. Regression coverage now also proves sibling
  `cjw` uniques such as `Guardian's Light` remain rejected until separately
  validated, and socket fillers are rejected on magic, rare, and unique stash
  parents.
- Expand quest and misc item support family by family with synthetic fixtures
  and one representative Offline validation per family. The first local fixture
  pass covers explicit quantities for tokens, essences, keys, Worldstone shards,
  and tomes (including tome book-field alignment), and the representative
  full-save scanner path is covered. Representative Offline runs accepted
  token/key/tome and essence/Worldstone shard items and scanned clean after
  save/exit, but only tome quantity preserved; token, key, essence, and shard
  quantities canonicalized away. A representative organ placement run accepted
  Mephisto's Brain, Baal's Eye, and Diablo's Horn, preserved item codes and
  stash placement, and scanned clean after save/exit. Public importer coverage
  round-trips that organ trio back to bases `mbr`, `bey`, and `dhn`, and
  synthetic scanner/import coverage includes quest weapon/reward bases Horadric
  Malus (`hdm`), Staff of Kings (`msf`), Horadric Staff (`hst`), Khalim's Flail
  (`qf1`), Khalim's Will (`qf2`), Khalim's Heart (`qhr`), Lam Esen's Tome
  (`bbb`), A Jade Figurine (`j34`), Wirt's Leg (`leg`), Scroll of Resistance
  (`tr2`), and Horadric Scroll (`tr1`).
  A representative multi-item quest weapon/reward batch loaded and saved cleanly
  but D2R removed all tested stash items on save/exit. Follow-up single-item
  Offline ladders show a mixed stash-persistence matrix: preserved `leg`, `tr1`,
  `tr2`, `qf1`, `qf2`, and `j34`; removed `hdm`, `msf`, `hst`, `qhr`, and `bbb`.
  Treat this as closed enough for `v1.3` as a mixed preservation/removal
  limitation: only run another single-item ladder if it would change what the
  public writer can promise. Quest usability and turn-in behavior stay gated
  separately.
- Keep shared stash mutation out of `v1.3`; `v1.4` owns the separate stash
  backup/restore safety ladder.

Parallel `v2.0` registry track:

- Use `docs/bound-demon-validated-synthesis-plan.md` as the chargen plan for
  validated package synthesis.
- Add packages only through registry promotion, with scanner output, Offline
  load/save evidence, canonicalization profile, and explicit semantic support
  flags.
- Keep seed overrides, generated-name authoring, explicit aura-flavor
  authoring, unsupported source contexts, arbitrary model swaps, pcount/combat
  stat knobs, and template-free `monster: NAME` synthesis out of normal YAML
  unless a package explicitly owns that behavior.
