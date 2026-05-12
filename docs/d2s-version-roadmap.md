# D2S Version Roadmap

Status: planning reference for public `.d2s` and mod-tooling releases. Version
labels align with package tags when a milestone is published.

This roadmap translates `docs/d2s-open-questions.md` into the next few release
gates. The bias is to ship useful template-derived tools while keeping
template-free synthesis behind proof, not optimism.

## Guiding Split

- Ship proven authoring surfaces before solving every unknown byte.
- Keep answered questions out of the open-question table.
- Treat scanner hard errors as release blockers.
- Require every new writer feature to have parser/scanner coverage plus a
  backup -> build/edit -> scan -> Offline validation path.
- Keep raw saves, local paths, and disposable validation details out of the
  public repo.

## Version Map

| Version | Theme | User-facing result | D2S questions handled | Proof gate | Held back |
| --- | --- | --- | --- | --- | --- |
| `v1.1.0` | Demon and Iron Golem support | Seven-slot bound-demon affix parsing, `template_path`, `source_affixes`, `skill_affixes: auto`, row-index model authoring, normal/magic Iron Golem support, and coherent docs. | Bind Demon threshold behavior is closed; five-slot demon-affix assumptions are removed; current template-derived Black Lancer support is documented as supported-with-template. | Public hygiene, Ruff, CI-style public pytest subset, focused follower tests, and one ignored template-path build/scan sample. | Template-free demon synthesis, arbitrary model swaps, shared stash writers, and complex socket filler authoring. |
| `v1.2` | Player-facing bound-demon templates | A practical demon-template workflow: inspect a local template, compose source plus skill affixes, reuse proven packages, and get scanner warnings when a request depends on template context. | Bound-demon model identity stays constrained to known-good targets; source-affix context is documented as a template requirement instead of hidden magic. | Each documented template recipe builds, scans, loads in Offline play, saves, and scans again with either preserved bytes or documented canonical rewrites. | `monster: NAME` synthesis with no template; unsupported source-affix contexts; seed overrides. |
| `v1.3` | Item-family completion | Better character and follower items: symbolic rare/crafted naming, broader Iron Golem item families where proven, expansion quest/misc items, and a narrow socketed-jewel decision. | Rare item naming, expansion/misc item behavior, socketed jewel safety, and broader Iron Golem item-family questions move from open questions into supported cases or explicit rejections. | Fixture-backed encode/decode tests, scanner assertions for parent/filler counts, and one representative Offline validation per newly supported family. | Shared stash mutation; arbitrary jewel sub-items if the parent/filler proof still fails. |
| `v1.4` | Stash and profile boundary | Read/inspect support for shared stash and a separate safety ladder for stash work. Writer support only follows after backup/restore behavior is boring and repeatable. | Shared stash support gets its own file-format notes and blast-radius rules instead of being treated like a character `.d2s` extension. Merc status can be grouped here if stash/profile fixtures expose useful patterns. | Disposable profile decode, public-safe structure notes, restore test, scanner checks, and a separate manual validation recipe. | Shared stash writer by default; any operation without a restore path. |
| `v2.0` | Template-free bound-demon synthesis | A gated `synthesize: true` style demon writer that builds the 116-byte follower payload from stable inputs and documented canonical rewrites. | Template-free synthesis and model identity are no longer open for the supported target set. Unknown slices are either decoded, fixed, D2R-rewritten, target-specific, or rejected. | Corpus classification, same-model binds, one-slice mutation results, same-family and cross-family model swaps, then a synthetic initializer that scans, loads visibly, saves, and rescans with `follower_count=1`. | General claims for every monster row; any writer path where scanner-clean does not match Offline behavior. |

## Open-Question Routing

| Open question | Version route |
| --- | --- |
| Bound-demon model identity | Constrain in `v1.2`; solve for selected targets in `v2.0`. |
| Template-free bound-demon synthesis | `v2.0`, after the full synthesis proof ladder passes. |
| Merc status at `0xA7..0xA8` | Backlog unless it blocks item, merc, or stash work; likely grouped with `v1.4` profile evidence. |
| Broader Iron Golem item families | `v1.3`, one item family at a time. |
| Rare item naming | `v1.3`, because it affects normal character authoring before synthesis. |
| Socketed jewels through chargen | `v1.3`, but only if parent/filler scanner proof is clean. |
| Shared stash support | `v1.4`, with a separate safety ladder. |
| Expansion quest and misc items | `v1.3`, family by family. |

## Next Checkpoint

Finish and publish `v1.1.0` first: docs coherence, public hygiene, Ruff,
focused follower tests, CI-style public tests, and a clean diff check. After
that, choose between:

- `v1.2` if the goal is better single-player demon authoring soon.
- `v1.3` if the goal is broader character/item generation before more demon
  synthesis research.

The recommended path is `v1.2` next. It turns the current D2S findings into a
usable mod-player workflow while keeping the harder synthesis questions safely
gated.
