# Manual Save Validation

Most changes should be proven with unit tests, scanner output, and deterministic
fixture checks. Use manual game validation only when those checks cannot answer
whether D2R accepts and preserves a generated save.

## Safety Loop

1. Fully exit D2R.
2. Back up the target save family outside this repository.
3. Build or forge into a staging directory.
4. Run `d2r-chargen scan <name>` on the staged save.
5. Promote one staged save at a time.
6. Relaunch D2R, perform the smallest needed observation, then save and exit.
7. Copy the resulting save back to a staging area and scan it again.
8. Record only the stable technical finding in public docs.

## Environment

Use placeholders or environment variables in notes and examples. Do not commit
real local paths.

```bash
export D2R_PUBLIC_REPO="/path/to/d2r-horadric-tools"
export D2R_SAVE_DIR="/path/to/local/offline-save-directory"
export D2R_STAGE_DIR="/path/to/staging-directory"
export D2R_BACKUP_DIR="/path/to/backup-directory"
```

## Public Result Template

When a manual result belongs in this repo, write it like this:

```text
Finding: <stable behavior>
Input shape: <public YAML, synthetic fixture, or byte-layout summary>
Validation: scanner passed before promotion; scanner passed after save/exit
Result: D2R accepted/preserved/canonicalized/rejected <specific field>
Limitation: <what this does not prove>
```

Avoid disposable character names, machine names, exact save-directory paths,
and blow-by-blow session logs. The public repo needs the reproducible result,
not the whole scratchpad.
