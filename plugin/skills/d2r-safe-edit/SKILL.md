---
name: d2r-safe-edit
description: Use when modifying D2R save files, character definitions, or game data — enforces incremental edit-scan-verify cycle that prevents cascading corruption
---

# D2R Safe Edit

## Overview

Every D2R save file edit follows the same cycle: **backup, edit one thing, scan, verify, repeat.** Skipping steps or batching edits causes cascading corruption that is extremely difficult to debug.

## The Cycle

```
backup → edit ONE thing → scan → verify → next edit
```

Never batch. Never skip scanning. Never deploy with scanner errors.

## Before Any Edit

1. **Backup the .d2s** (Rule 3)
   ```python
   shutil.copy2(path, path + '.pre_DESCRIPTION_bak')
   ```
   Verify the backup exists before proceeding.

2. **Verify preconditions:**
   - UID exists in data file (Rule 1) — use MCP `d2r_lookup_unique` or read `unique_items.py`
   - Item code matches base type in `item_bases.py`
   - Target storage has free space (check grid with scanner)
   - Stats are non-zero (Dex/Energy must never be 0)

## During Edit

3. **Edit ONE thing.** Not two. Not "one more small fix."
   - Stats OR items OR skills — pick one per cycle
   - If using chargen: one `--phase` at a time

4. **Write to temp, verify, then overwrite** (Rule 10)
   - Never write directly to a live .d2s
   - Parse the temp file back with scanner
   - Verify item counts/positions/types match intent
   - Only then copy to real location

## After Edit

5. **Run scanner** (Rule 4)
   ```bash
   d2r-chargen scan CHARNAME
   ```

6. **Evaluate ALL scanner output** (Rule 12)
   - Hard error → STOP. Fix before proceeding. Never dismiss as false positive without bit-level proof (Rule 11).
   - Checksum mismatch → recalculate (Rule 5)
   - LF inconsistent → fix merc state
   - Encoding issues → rebuild item

7. **Only proceed to next edit when scanner is clean.**

## Red Flags — STOP Immediately

- "Let me just do this other edit too" → NO. One edit per cycle.
- "That scanner warning is probably fine" → NO. Investigate every error.
- "I'll scan after all the edits" → NO. Scan after EACH edit.
- "The number makes semantic sense" → NOT proof. Check actual encoding (Rule 11).
- "Let me rebuild the whole file" → NO. Targeted section edits only (Rule 2).

## Merc Rules

- NEVER inject items directly into JM[merc] (Rule 6). Place in stash, equip in-game.
- Only safe merc edit: setting lf_count.
- Verify lf_count >= 1 before any merc-related work.

## After All Edits Complete

- Remind user: **Fully exit and relaunch D2R** (Rule 7).

## Debugging Escalation

If an edit causes FAILED TO JOIN GAME:
1. Compare scanner output between working backup and broken file
2. Startup crash (<60s) = bad data. Runtime crash (>5min) = engine issue.
3. If chargen YAML fails but manual binary works → bug is in resolve.py
