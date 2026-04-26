---
description: Build a D2R character safely — backup, build, scan, verify cycle
argument-hint: "Character name (e.g. Tempest) and optional --phase N"
---

# D2R Safe Build

Build character `$ARGUMENTS` using the chargen with full safety workflow.

## Mandatory Steps

Execute these in order. Do NOT skip or combine steps.

### 1. Backup existing save

```bash
CHAR_NAME="$ARGUMENTS"
# Strip --phase flag if present for backup
CHAR_NAME=$(echo "$CHAR_NAME" | sed 's/ *--phase [0-9]*//')
SAVE_DIR="$HOME/.local/share/Steam/steamapps/compatdata/2536520/pfx/drive_c/users/steamuser/Saved Games/Diablo II Resurrected"
D2S="$SAVE_DIR/${CHAR_NAME}.d2s"
if [ -f "$D2S" ]; then
    cp "$D2S" "${D2S}.pre_build_bak"
    echo "Backed up to ${D2S}.pre_build_bak"
else
    echo "No existing save for ${CHAR_NAME} — fresh build"
fi
```

### 2. Run chargen build

```bash
python3 -m d2r_chargen build $ARGUMENTS
```

If the build fails, stop and diagnose. Do NOT proceed to scanning.

### 3. Run d2rdoctor scanner

```bash
python3 << 'PYEOF'
import sys
sys.path.insert(0, '<parent-of-d2r-tools>')
from d2r_scanner import run_scanner
run_scanner('$ARGUMENTS'.split()[0].lower())
PYEOF
```

### 4. Check scanner output

- **Any hard error (returns False)?** → Do NOT deploy. Fix the issue first.
- **Checksum MISMATCH?** → Recalculate before writing.
- **LF INCONSISTENT?** → Remove merc items or fix lf_count.
- **Encoding issues?** → Rebuild with corrected build_item().

Only proceed if scanner reports clean.

### 5. Verify and report

Tell the user:
- Build status (success/fail)
- Scanner results (clean/warnings/errors)
- Remind them: **D2R caches saves at startup. Fully exit and relaunch D2R to see changes** (Rule 7).

## Rules Enforced

- Rule 3: Always backup before writing .d2s
- Rule 4: Always run d2rdoctor after every edit
- Rule 5: Always verify checksums
- Rule 10: Write to temp, verify, then overwrite (chargen handles this)
- Rule 12: Edit incrementally, test after each change
- Rule 17: Scanner hard errors are deployment blockers
- Rule 19: Investigate every remaining scanner error before closing
