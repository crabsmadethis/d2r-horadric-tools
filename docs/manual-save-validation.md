# Manual Save Validation

Automated checks come first. Use manual D2R validation only when unit tests,
fixture checks, and `d2r-chargen scan` cannot answer whether the game accepts,
renders, preserves, canonicalizes, or rejects a generated save shape.

Manual validation records must stay public-safe. Do not commit personal saves,
unpublished save corpora, local filesystem paths, account identifiers, machine
names, screen captures, or blow-by-blow session logs.

## Standard Loop

1. Fully exit D2R.
2. Back up the target save family outside this repository.
3. Build, forge, or edit into a staging directory.
4. Run the scanner on the staged save.
5. Promote one staged save only after the scanner passes.
6. Relaunch D2R and perform the smallest observation needed.
7. Save and exit.
8. Copy the resulting save back to staging.
9. Run the scanner again.
10. Record the stable technical result, not the local session details.

Scanner hard errors block promotion unless there is bit-level proof that the
scanner is wrong.

## Environment Placeholders

Use placeholders or environment variables in examples. Keep real paths out of
public docs and issue comments.

```bash
export D2R_PUBLIC_REPO="/path/to/d2r-horadric-tools"
export D2R_SAVE_DIR="/path/to/offline-save-directory"
export D2R_STAGE_DIR="/path/to/staging-directory"
export D2R_BACKUP_DIR="/path/to/backup-directory"
```

## Recording A Result

Use this shape when a manual result belongs in a public doc:

```text
Finding: <stable behavior>
Input shape: <public YAML, synthetic fixture, or byte-layout summary>
Pre-promotion validation: scanner passed on the staged save
Manual observation: D2R accepted, rendered, rejected, stripped, rewrote, or preserved <field>
Post-save validation: scanner passed or failed with <specific public-safe reason>
Limitation: <what this result does not prove>
```

Good public examples:

- `monster_hcidx=724` preserved after save/exit for a 116-byte bound-demon
  payload.
- D2R rewrote a volatile follower-payload slice on save/exit.
- A scanner-clean multi-follower shape failed to join game.
- A `template_path` build re-extracted the same 116-byte bound-demon payload
  after scanner-clean generation.

Avoid:

- Disposable character names unless they are part of a synthetic fixture.
- Exact local save paths.
- Game-client or operating-system profile paths.
- Screenshots, unpublished save bytes, or local payload corpora.
- Narrative notes such as who clicked what or when a machine was restarted.

## Promotion Checklist

Before promoting a staged save:

- The target save family has a backup.
- The staged save passes `d2r-chargen scan <name>`.
- Only one risky change is under test.
- The embedded character name and file basename match.
- The character name is simple enough for offline character-select visibility.
- D2R will be fully relaunched after the file change.

After save/exit:

- Scan the returned save.
- Compare only the fields relevant to the test.
- Classify D2R rewrites separately from tool writer bugs.
- Move stable findings into the relevant public reference or fixture note.
