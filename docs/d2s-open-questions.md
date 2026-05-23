# D2S Research Status

This page tracks public `.d2s` findings that still shape tooling decisions.
Confirmed findings belong below with their current limitation. Open questions
must name the next proof method.

For release sequencing, see `docs/d2s-version-roadmap.md`.

## Confirmed Findings

### Bound demon payload shape

- Finding: known bound-demon saves use `lf<u16:follower_count>` followed by exactly
  `count * 116` payload bytes.
- Consequence: writers support at most one bound demon; scanners reject
  follower_count/payload mismatches; corpus tooling should report aggregate counters.

### Embedded payload markers

- Finding: `payload[92:94] == b"gf"` is payload data, not a stats-section marker.
- Consequence: parsers must not split at the embedded byte pair.

### Template-derived authoring (current public surface)

- Finding: template-derived edits can preserve `monster_hcidx`, bind metadata, and the
  seven-slot MonUMod vector; incompatible/default seeds can zero authored source-affix
  bytes or strip the follower on save/exit.
- Consequence: keep the player surface template-derived by default; treat explicit seed
  and context-slice authoring as validation-gated future work.

### Row identity

- Finding: payload `monster_hcidx` values are zero-based MonStats row indexes (not `*hcIdx`).
- Consequence: inspection/model tools should treat them as row indexes and expose row
  context comparisons before validation.

### Bind Demon thresholds

- Finding: effective Bind Demon level grants Extra Strong at 5, Extra Fast at 10, Spectral
  Hit at 15, and Aura Enchanted at 20; payload `+52` is persisted metadata, not the
  effective skill level.
- Consequence: YAML keeps `source_affixes` separate from `skill_affixes: auto`.

### Seven-slot affix vector

- Finding: the persisted MonUMod vector is seven bytes at `+80..+86` (`+85/+86` are
  overflow slots, not model-candidate bytes).
- Consequence: writers/scanners must support seven slots (not five).

### Source-affix context

- Finding: visible source-style labels can require compatible context outside the seven
  MonUMod bytes; treat Fanaticism as source/aura flavor, not a Bind Demon threshold affix.
- Consequence: recipes must record source-context requirements; do not expose arbitrary
  public authoring that depends on unvalidated context slices.

### Same-model unknown slices (Fallen controls)

- Finding: several slices are D2R-rewritten or structural for same-model Fallen probes,
  including `+89..+91`, `+24..+31`, `+88`, `+96/+97`, `+104/+105/+106`, and `+109/+111/+112`.
  `+94` should remain `06`, and `+114/+115` should preserve `f0 1f` for same-model Fallen.
- Consequence: unknown slices remain template-owned/preserve-first unless a proof says
  otherwise.

### Expansion quest and misc items (single-item stash persistence matrix)

- Finding: some quest/reward bases persist as a single stash item through Offline load/save,
  while others are removed on save/exit even when the save loads and scans clean.
- Status: closed enough for `v1.3` as a mixed preservation/removal limitation; only run
  another single-item ladder if it would change what the public writer can promise.
- Current single-item matrix (scanner-clean staging, post-save stash inspection):
  - Preserved: `leg`, `tr1`, `tr2`, `qf1`, `qf2`, `j34`
  - Removed: `hdm`, `msf`, `hst`, `qhr`, `bbb`
- Consequence: keep this family-by-family. Do not infer quest usability, turn-in behavior,
  or general persistence from a single base code. Run another single-item ladder only if it
  would change what the public writer can promise.

## Open Questions

### Merc status at `0xA7..0xA8`

- Current state: the field has more observed values than the writer understands; the
  committed fixture corpus currently observes only `0` and `1` (1 committed `.d2s` under
  `tests/fixtures/`).
- Next proof (public-safe): run an external-corpus aggregate grouping pass and share only
  aggregate-only JSON output:
  - `python3 tools/d2s_corpus_scan.py <roots...> --report merc-status-context --json > merc-status-report.json`
- Boundary: this does not decode semantics; it only groups observed values against other
  parsed fields.
- Tooling rule: preserve the field by default and treat it as a raw `u16` status field; only
  change it with fixture-backed writer intent or live proof for a specific hireling state.

### Shared stash support

- Current state: shared stash files are outside the character `.d2s` and have a larger blast
  radius than per-character writes.
- Next proof: `v1.4` safety ladder (disposable profile decode + backup/edit/scan/restore) with
  public-safe structure notes before any writer support.

## Recording Rules

- Put durable byte-layout facts in `docs/d2s_format.md`.
- Put reusable manual procedures in `docs/manual-save-validation.md`.
- Do not commit raw saves, local paths, unpublished evidence, or session diaries.
- Do not leave answered questions in the open table.
