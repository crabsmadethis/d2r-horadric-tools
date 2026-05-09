# GitHub Cleanup Agent Plan

Status: executed on branch `codex/github-cleanup`.
Lane: public tooling (`d2r-horadric-tools-current/`).

## Execution Result

The cleanup was executed with one orchestrator plus bounded workers. The final
branch keeps the repo public-safe, makes `docs/d2s_format.md` the canonical
save-format reference, moves completed live probes out of active future-test
framing, aligns Python/CI metadata, and removes stale broken historical
references from public docs and comments.

## Goal

Bring the public GitHub repo back to a clean, internally consistent state:

- no open questions that already have public-safe answers
- active test plans contain only tests that still need action
- docs, tools, CI metadata, and agent instructions do not contradict each other
- private evidence remains outside the public repo, with only sanitized findings
  committed

## Non-Goals

- Do not run new live D2R tests unless the cleanup uncovers a question that
  cannot be answered from existing public-safe evidence.
- Do not move private saves, raw corpora, Steam userdata paths, Proton
  compatdata paths, recovered private source, or machine-local calibration into
  the public repo.
- Do not use this cleanup to implement new `.d2s` features. Code changes should
  be limited to guards, tests, or metadata needed to make the repo coherent.
- Do not treat local-only commits or Bazzite state as GitHub state without
  verifying the remote branch.

## Current Drift Snapshot

These are the first confirmed cleanup targets from the 2026-05-09 repo review.
The cleanup agents should validate the details before editing, but should not
reopen questions that the 2026-05-08 live probes already answered.

| Area | Drift / risk | Desired end state |
| --- | --- | --- |
| `docs/d2s-open-questions.md` | Mixes active questions with long answered result logs. | Split answered findings from still-open questions; every remaining question has a next proof method. |
| `docs/d2s-live-test-plan.md` | Active plan includes completed probe ladders and Bazzite-specific staging notes. | Keep repeatable recipes and safety rules; move completed results to an evidence/results section or another doc. |
| `docs/d2s_format.md` | "Open questions" are stale as of 2026-04-25; cross-class follower and embedded `gf` questions now have answers; merc status values are outdated. | Canonical format reference reflects current known answers and clearly marks only real unknowns. |
| `docs/save-format.md` | Overlaps with `docs/d2s_format.md`, has `last_verified_commit: TBD-AT-MERGE`, and describes version `99`/`105` in a confusing way. | Either retire it in favor of `docs/d2s_format.md` or make it a short compatibility stub pointing at the canonical doc. |
| Python/test metadata | README says Python 3.10+, CONTRIBUTING says 3.11+, `pyproject.toml` says `>=3.9`, CI runs 3.11/3.12. Docs mention a `smoke` marker that is not declared. CI ignores missing legacy test files. | One supported Python story, one Tier 1 test command, declared markers match docs and workflows, no stale ignores. |
| Public/private boundary | Some examples mention local paths such as Proton compatdata or recovered-repo locations. Some are okay as runtime discovery examples, but committed fixtures and instructions should not depend on machine-local paths. | Public docs use environment variables, synthetic paths, or explicitly public-safe aggregate descriptions. |
| Missing/stale references | Docs and comments reference `docs/superpowers/...`, `rca_master_plan.md`, and fixture files that may not exist in this repo snapshot. | Every reference either resolves in the public repo or is rewritten as historical context without a broken path. |
| Agent/plugin docs | Plugin commands and agent docs should reflect the same backup -> stage -> scan -> promote safety flow and current repo boundaries. | Agent-facing docs tell the same story as CLI/MCP docs and validation ladder. |

## Agent Topology

Use one orchestrator and bounded worker agents. Workers should own disjoint file
sets and return changed paths, validation run, and residual risk. The
orchestrator owns final integration, conflict resolution, and PR state.

| Agent | Role | Owns | Output |
| --- | --- | --- | --- |
| Orchestrator | Plan, branch, merge queue, final decision log. | This plan, task board, final PR body. | Cleanup matrix, integrated branch, final validation summary. |
| A: Evidence Resolver | Classify every `.d2s` open question as answered, still open, or blocked. | `docs/d2s-open-questions.md`, `docs/bound-demon-chargen-roadmap.md`, `docs/d2s-stats-chargen-plan.md`. | Resolved-question table plus remaining proof ladder. |
| B: Format Canonicalizer | Make one save-format reference authoritative. | `docs/d2s_format.md`, `docs/save-format.md`, code comments that cite format docs. | Canonical format doc with no stale answered questions. |
| C: Test Plan Curator | Convert completed live-test ladders into reusable recipes/results. | `docs/d2s-live-test-plan.md`, root validation docs if public-safe changes are needed. | Active test plan containing only runnable future tests. |
| D: Repo Metadata Cleaner | Align GitHub, CI, README, packaging, and contribution docs. | `README.md`, `CONTRIBUTING.md`, `pyproject.toml`, `.github/*`, `d2r_mcp/README.md` if tool counts changed. | One supported Python/test matrix and clean PR/testing instructions. |
| E: Boundary Auditor | Audit for private leakage and missing-reference risks. | Read-only pass first; edit docs/guards only if orchestrator assigns. | Boundary report and suggested guards. |
| F: Verifier | Run final checks after all worker changes land. | No overlapping edits unless fixing validation docs. | Validation transcript, failure list, merge/no-merge recommendation. |

## Execution Plan

### Phase 0: Snapshot and Task Board

Orchestrator:

1. Confirm lane: public tooling.
2. Create a cleanup branch.
3. Record `git status --short --branch`, current remote, and whether local
   commits are already pushed.
4. Build a cleanup matrix with columns:
   `topic`, `current source`, `current claim`, `current evidence`,
   `answered/still open/conflict`, `edit owner`, `validation`.
5. Give each worker a file ownership set. No worker edits outside its set
   without asking the orchestrator.

Suggested discovery commands:

```bash
rg -n "Open questions|unresolved|TBD|TODO|FIXME|needs|Need|unknown|if/when needed|Semantics TBD" README.md docs d2r_chargen d2r_mod d2r_mcp tools plugin tests
rg -n "docs/superpowers|rca_master_plan|tests/fixtures/.*\\.d2s|compatdata|SK256|/home/|recovered-repos|D2SProbe" README.md docs d2r_chargen d2r_mod d2r_mcp tools plugin tests
rg -n "Python 3\\.(9|10|11)|smoke|test_d2s_diff|test_property_roundtrip" README.md CONTRIBUTING.md pyproject.toml .github
```

### Phase 1: Answered-Question Cleanup

Agent A:

1. For each question in `docs/d2s-open-questions.md`, assign:
   `answered`, `still open`, or `blocked`.
2. Promote answered findings to a concise "Answered Findings" section.
3. Keep real unknowns, but make the next proof method concrete.
4. Do not delete useful live results; compress them into public-safe summaries
   when they are no longer an active test ladder.

Minimum known answer set to preserve:

- Letter-only probe names were visible; digit-bearing probe names were not.
- `probewldemon` preserved one 116-byte bound-demon follower payload.
- D2R rejected `follower_count=2` bound-demon variants at join.
- Borrowed Warlock follower payload on Sorceress loaded but was stripped on
  save-and-quit.
- Embedded `gf` inside the 116-byte demon payload is payload data, not a section
  marker.
- Iron Golem payload length is item-encoding-dependent, not fixed.
- Simple generated normal/magic Iron Golem YAML support has live positive
  evidence.
- Broader golem item families have load/save evidence, but not all have visual
  confirmation.

### Phase 2: Test Plan Normalization

Agent C:

1. Turn `docs/d2s-live-test-plan.md` into three explicit areas:
   `Prerequisites`, `Repeatable Recipes`, and `Completed Public-Safe Results`.
2. Remove completed probes from the active "next test" flow unless they are
   regression recipes.
3. Replace machine-local paths in examples with environment-variable forms
   where possible.
4. Ensure every live test recipe has:
   backup step, staging step, scanner step, live observation fields, and
   post-run scan.

### Phase 3: Canonical Format Reference

Agent B:

1. Decide whether `docs/d2s_format.md` or `docs/save-format.md` is canonical.
   Preferred direction: keep `docs/d2s_format.md` as canonical and turn
   `docs/save-format.md` into a short compatibility/stability note unless it
   contains unique current material.
2. Update stale open questions in the canonical doc using existing 2026-05-08
   public-safe results.
3. Update outdated merc-status values to match the corpus findings, while
   keeping semantics unknown.
4. Remove or rewrite broken references to missing docs.
5. Keep unknown fields explicit as raw offsets, not invented meanings.

### Phase 4: Repo and CI Consistency

Agent D:

1. Pick and apply one supported Python policy. Since CI runs 3.11 and 3.12 and
   CONTRIBUTING already says 3.11+, prefer updating README and pyproject to
   `>=3.11` unless there is a tested reason to keep older support.
2. Declare or remove the `smoke` marker consistently.
3. Remove stale `--ignore` entries for missing tests or add comments explaining
   why they remain.
4. Verify README, CONTRIBUTING, PR template, and workflow use the same Tier 1
   command.
5. Check root README and `d2r_mcp/README.md` tool counts if MCP files changed.

### Phase 5: Boundary and Reference Audit

Agent E:

1. Run a public-boundary grep for private-only material.
2. Classify each hit:
   public-safe runtime example, needs env var rewrite, needs removal, or false
   positive.
3. Confirm no raw `.d2s` saves, memory dumps, Steam userdata fixtures, or
   recovered private source are introduced.
4. Recommend a lightweight guard if the same leakage pattern is likely to recur.

Boundary grep:

```bash
rg -n "Steam/userdata|compatdata|Saved Games|\\.d2s$|\\.dmp|/home/|\\.claude/file-history|recovered-repos|SK256|chains\\.json|UnitHashTable" README.md docs d2r_chargen d2r_mod d2r_mcp tools plugin tests .github
```

### Phase 6: Final Verification

Agent F:

Run the lowest sufficient validation first:

```bash
python3 -m pytest tests/ -v --timeout=60 -m "not integration and not slow and not e2e"
ruff check .
python3 -m pytest tests/test_demon_payload_diff.py tests/test_d2s_forge_demon_payload.py tests/test_iron_golem_block.py -q
```

If generated data or optional fixtures are missing, report that as a validation
gap instead of fabricating success. For doc-only cleanup, a full test failure
caused by pre-existing missing generated game data can be documented, but
syntax/lint failures from changed files must be fixed.

Final stale-content checks:

```bash
rg -n "unresolved as of 2026-04-25|TBD-AT-MERGE|Semantics TBD|D2SProbe|test_property_roundtrip|test_d2s_diff" README.md docs CONTRIBUTING.md pyproject.toml .github --glob '!docs/github-cleanup-agent-plan.md'
rg -n "docs/superpowers|rca_master_plan" README.md docs d2r_chargen d2r_mod d2r_mcp tools plugin tests --glob '!docs/github-cleanup-agent-plan.md'
```

## Definition of Done

- Every public `.d2s` question is either answered, still open with a concrete
  proof method, or deliberately out of scope.
- Completed live-test ladders are not presented as future work.
- There is one canonical save-format reference, or the duplicate doc clearly
  redirects to it.
- Python support, CI, CONTRIBUTING, README, markers, and PR template agree.
- Public/private boundary audit has no unclassified high-risk hits.
- Validation results are recorded in the PR or handoff.
- `docs/status.md`, `docs/worklog.md`, or `docs/agent-current-task.md` are
  updated if project state or next work changed.

## Suggested First Worker Dispatch

Dispatch in this order:

1. Agent A and Agent D can run immediately in parallel.
2. Agent B starts after Agent A produces the answered/still-open matrix.
3. Agent C starts after Agent A identifies which live probes are completed.
4. Agent E runs after the first doc edits are integrated.
5. Agent F runs only after all edits land.

This avoids stacked orchestrators while still letting docs, metadata, boundary
audit, and verification move quickly.
