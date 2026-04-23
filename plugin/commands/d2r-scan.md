---
description: Run d2rdoctor scanner on a character or all characters
argument-hint: "Character name (e.g. Tempest) or 'all'"
---

# D2R Scanner

Run the d2rdoctor scanner on `$ARGUMENTS`.

```bash
TARGET="${ARGUMENTS:-all}"
python3 -m d2r_chargen scan "$TARGET"
```

## Interpreting Results

- **Hard error (returns False):** Deployment blocker. Fix before loading in D2R.
- **Checksum MISMATCH:** Recalculate with `calc_checksum()` before writing.
- **LF INCONSISTENT:** Merc items present but lf_count=0. Remove merc items or fix count.
- **Ghost character:** `.ctl` exists but `.d2s` missing. Restore from backup or delete support files.
- **Encoding issues:** Wrong ext bits. Rebuild with corrected `build_item()`.
- **Grid view:** Each cell shows first char of item type. `.` = free slot.

## Rules

- Rule 4: Always run scanner after every edit
- Rule 17: Scanner hard errors are deployment blockers — never dismiss without bit-level proof
- Rule 19: Investigate every remaining error before closing
