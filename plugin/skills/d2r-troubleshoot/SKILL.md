---
name: d2r-troubleshoot
description: Use when encountering D2R errors — FAILED TO JOIN GAME, Error:7, Error:8, crashes, save corruption — provides systematic diagnosis before attempting fixes
---

# D2R Troubleshoot

## Overview

Systematic diagnosis for D2R errors. Do NOT guess at fixes — follow this diagnostic sequence to identify the root cause first.

## Step 1: Classify the Error

| Symptom | Category | Likely Cause |
|---------|----------|-------------|
| FAILED TO JOIN GAME | Save data | Bad item encoding, missing stats, bad socket fillers |
| Error:7 | Save structure | Zero stats, corrupt header, bad section offsets |
| Error:8 | Merc data | Items injected into JM[merc], lf_count mismatch |
| Crash at startup (<60s) | Save data | Corrupt .d2s, ghost character (.ctl without .d2s) |
| Crash during play (>5min) | Engine | Wine/Proton issue, not save-related |
| Character missing | File system | .d2s deleted or renamed, ghost .ctl files |

## Step 2: Check Logs

Look for blz-log.txt in the D2R save directory or game directory. It contains crash details.

## Step 3: Run Scanner

```bash
d2r-chargen scan <character_name>
```

Look for:
- **Hard errors** → the primary suspect
- **Checksum mismatches** → file was modified without recalculating
- **LF inconsistency** → merc items present but lf_count=0
- **Ghost characters** → .ctl without .d2s

## Step 4: Compare With Backup

If a backup exists (`.pre_*_bak` files):
```bash
d2r-chargen scan <character_name>  # scan current
# Compare with backup — look for what changed
```

The diverging line between backup scan and current scan is usually the bug.

## Step 5: Check Common Causes

### FAILED TO JOIN GAME
1. **Zero stats** — Dex and Energy must never be 0. Check character stats.
2. **Missing magic_attributes** — Items with only `unique_id` and no properties have zero stats in-game.
3. **Non-simple socket fillers** — Magic jewels (quality=4) in socketed items cause this. Only use runes (simple fillers).
4. **Grouped stats** — Stats with `num_params > 0` must encode all param+value pairs together.
5. **Bad stat encoding** — Verify stat aliases match `item_stat_cost.py` definitions.

### Error:7
1. **Zero Dex/Energy** — Class base minimum required, never 0.
2. **Corrupt header** — Was the file rebuilt from scratch? (Rule 2 violation)

### Error:8
1. **Merc items in JM[merc]** — Items must go in stash, equip in-game (Rule 6).
2. **lf_count mismatch** — lf_count must be >= 1 if merc exists.

### Ghost Character Crash
1. Look for `.ctl` files without matching `.d2s`
2. Either restore `.d2s` from backup, or delete `.ctl`, `.key`, `.ma*`, `.map` files

## Step 6: Fix and Verify

After identifying the cause:
1. Fix the specific issue (use `/d2r-build` if it's a chargen problem)
2. Run scanner to verify the fix
3. Check ALL scanner output — don't just verify the one fix (Rule 12)
4. Remind user to fully relaunch D2R (Rule 7)
