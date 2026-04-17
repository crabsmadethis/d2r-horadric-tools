---
description: Run diagnostic scanner on a D2R character save file
argument-hint: "Character name (e.g. MyPaladin) or 'all'"
---

# D2R Scanner

Run the scanner on `$ARGUMENTS`.

```bash
d2r-chargen scan $ARGUMENTS
```

## Interpreting Results

- **Hard error** — Deployment blocker. Fix before loading in D2R.
- **Checksum MISMATCH** — Recalculate with `calc_checksum()` before writing.
- **LF INCONSISTENT** — Merc items present but lf_count=0. Remove merc items or fix count.
- **Encoding issues** — Wrong ext bits. Rebuild with corrected `build_item()`.
- **Grid view** — Each cell shows first char of item type. `.` = free slot.

## Rules

- Rule 4: Always run scanner after every edit
- Rule 11: Scanner hard errors are deployment blockers — never dismiss without bit-level proof
- Rule 12: Investigate every remaining error before closing
