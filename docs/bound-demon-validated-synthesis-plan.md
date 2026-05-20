# Bound Demon Validated Synthesis Plan

Status: public roadmap and implementation plan. Public chargen now has the
first registry-backed `synthesis_validated` package and local raw-payload
template extraction support. The remaining work is to expand diagnostics,
registry coverage, and scanner-backed promotion without treating this as
arbitrary `monster: NAME` synthesis.

## Product Boundary

Public chargen should support two durable bound-demon authoring paths:

- `template_path`: the user supplies or extracts a local demon template, and
  chargen preserves the template payload while applying proven high-confidence
  edits.
- `synthesis_validated`: the user selects a named package from a public-safe
  registry, and chargen builds the 116-byte follower payload from public code
  and registry data without copying a donor payload.

The broader `synthesis` / `monster: NAME` mode remains research-only until row
identity, generated-name seed policy, aura-context policy, source-affix context,
combat-stat policy, and canonicalization are decoded for a declared algorithmic
support set.

Current enabled package:

```text
row724-black-lancer-seedg-holy-shock-v1
```

List package ids and support summaries with:

```bash
d2r-chargen bound-demon-packages
d2r-chargen bound-demon-packages --json
```

## Registry

The versioned validated-package registry lives in public code at
`d2r_chargen.bound_demon_registry`. It should contain only sanitized support
records, never raw saves, private paths, memory dumps, or local calibration
  artifacts.

Each package entry should include:

| Field | Purpose |
| --- | --- |
| `package_id` | Stable user-facing id, versioned when semantics change. |
| `summary` | Short human-readable package description. |
| `supported_rows` | Exact payload row indexes and optional family labels. |
| `builder_version` | Payload-builder schema expected by the package. |
| `inputs` | Required monster row, seed policy, affix tuple, bind metadata, and any validated context package id. |
| `canonicalization_profile` | Expected save/exit rewrites and volatile bytes. |
| `semantic_claims` | Which claims are supported: row, generated name, visible labels, aura skill/level, combat stats. |
| `evidence_level` | Public-safe validation level: scanner-clean, Offline accepted, preserved/canonicalized, runtime observed, user-visible observed. |
| `unsupported_dimensions` | Explicit blockers such as generated-name authoring, aura choice, pcount stats, or source-affix variants. |

The registry should prefer small, exact packages over broad claims. A row or
affix tuple is unsupported unless a registry entry says otherwise.

## Diagnostics

`d2r-chargen validate` resolves every bound-demon request into one of three
outcomes:

- accepted `template_path` request
- accepted `synthesis_validated` package id
- hard failure with a named unsupported dimension

Diagnostic messages should be actionable. They should say which field crossed
the validated set and suggest the nearest supported path:

- use `template_path` when the user has a demon template
- choose a listed `package_id` when a validated package exists
- remove unsupported generated-name, aura, pcount, raw context-slice, row, or
  source-affix requests when no package covers them
- inspect/extract a new template when the desired demon exists locally but is
  not yet in the registry

Example failure classes:

| Request shape | Fail-fast reason |
| --- | --- |
| unsupported `monster_hcidx` | Row/family is not in the selected package. |
| arbitrary `source_affixes` | Source-effect and visible-label semantics are not validated for that package. |
| requested generated name | Seed/name derivation is not decoded or registered. |
| requested aura flavor | Aura context is not decoded or registered for that seed/package. |
| pcount or combat stat knobs | HP/damage/AR/defense synthesis is not validated. |
| raw `runtime_stats_24_31` | Raw context slices are internal registry data, not normal YAML. |
| `mode: synthesis` | Algorithmic synthesis is research-only. |

Warnings are acceptable for preserve-only template behavior. Unsupported
synthesis fields should be errors before any save is written.

## Template Inspection And Extraction

Template workflows should become first-class instead of feeling like a private
workaround.

Keep `tools/d2s_demon_template_inspect.py` as the public-safe inspection and
extraction entry point:

```bash
python3 tools/d2s_demon_template_inspect.py <template.d2s> \
  --extract-payload .local-demon-templates/<template>.bin
```

The extraction mode can:

- read a `.d2s` with exactly one bound-demon follower
- write the 116-byte local template payload to a caller-chosen untracked path
- emit a YAML snippet using `template_path`
- optionally include local-only seed and unknown-slice values when the caller
  explicitly asks for them
- validate payload length and high-confidence fields during extraction; use
  `d2r-chargen validate` on the YAML recipe for full scanner validation before
  loading a generated save

Default inspection output omits local paths, raw seeds, raw unknown slices, and
raw save data. Extraction output necessarily names the caller-chosen local
output path and marks it as local-only. `template_path` accepts either a
`.d2s` with one follower payload or one extracted 116-byte raw payload.

## Hard Fail-Fast Behavior

The writer must fail before mutation when a request leaves the validated set.
No fallback should silently downgrade unsupported synthesis into a best-effort
template, seed guess, or partial source-affix edit.

Fail-fast rules:

- `mode: synthesis_validated` requires a registry `package_id`.
- The package id controls the allowed rows, affixes, seed policy, context
  package, and semantic claims.
- User YAML cannot pass raw context slices unless a local debug command is
  deliberately enabled outside normal chargen.
- A package cannot claim generated names, aura flavor, visible source labels,
  or combat stats unless the registry entry includes that support.
- `mode: synthesis` remains rejected in public chargen until algorithmic support
  is explicitly promoted.
- Any scanner hard error blocks deployment.

## Implementation Milestones

1. Done: registry schema plus first enabled package record.
2. Done: validation accepts only exact package requests and rejects unsupported
   row, seed, raw context-slice, name, aura, pcount, or arbitrary synthesis
   fields before writing.
3. Done: local raw-payload extraction workflow, YAML snippet output, and
   privacy warnings.
4. Done: builder integration connects the first registry package to the
   explicit-field payload builder.
5. Done: focused tests cover registry shape, text and JSON package listing,
   resolver package acceptance/rejection, full CLI validation, scanner
   hard-error blocking, template extraction, and raw-payload `template_path`.
6. Done for the first package: public docs list the support surface and keep
   algorithmic synthesis research-only. Keep docs aligned as packages are
   added.

## Promotion Gate

A package can become public only when its registry entry, tests, scanner output,
Offline load/save result, canonicalization profile, and semantic claims all
agree. Missing dimensions must stay listed as unsupported rather than inferred
from a nearby proof.
