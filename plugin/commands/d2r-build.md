---
description: Build a D2R character safely — backup, build, scan, verify cycle
argument-hint: "Character name (e.g. MyPaladin) and optional --phase N"
---

# D2R Safe Build

Build character `$ARGUMENTS` using the chargen with full safety workflow.

## Mandatory Steps

Execute these in order. Do NOT skip or combine steps.

### 1. Backup existing save

If a .d2s exists for this character, back it up:
```python
import shutil, os
from d2r_chargen.config import SAVES
name = "$ARGUMENTS".split()[0]
d2s = os.path.join(SAVES, f"{name}.d2s")
if os.path.exists(d2s):
    shutil.copy2(d2s, d2s + ".pre_build_bak")
```

### 2. Run chargen build

```bash
d2r-chargen build $ARGUMENTS
```

If the build fails, stop and diagnose. Do NOT proceed to scanning.

### 3. Run scanner

```bash
d2r-chargen scan $ARGUMENTS
```

### 4. Check scanner output

- **Any hard error?** → Do NOT deploy. Fix the issue first.
- **Checksum MISMATCH?** → Recalculate before writing.
- **LF INCONSISTENT?** → Remove merc items or fix lf_count.
- **Encoding issues?** → Rebuild with corrected properties.

Only proceed if scanner reports clean.

### 5. Verify and report

Tell the user:
- Build status (success/fail)
- Scanner results (clean/warnings/errors)
- Remind them: **D2R caches saves at startup. Fully exit and relaunch D2R to see changes.**

## Rules Enforced

- Rule 3: Always backup before writing .d2s
- Rule 4: Always run scanner after every edit
- Rule 5: Always verify checksums
- Rule 10: Write to temp, verify, then overwrite (chargen handles this)
- Rule 11: Scanner hard errors are deployment blockers
- Rule 12: Edit incrementally, test after each change
