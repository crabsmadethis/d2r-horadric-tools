---
name: d2r-safe-edit
description: Use when modifying D2R save files, character definitions, or game data — enforces incremental edit-scan-verify cycle that prevents cascading corruption
---

# D2R Safe Edit

## Overview

Every D2R save file edit follows the same cycle: **backup, edit one thing, scan, verify, repeat.** Skipping steps or batching edits has caused 15+ hours of debugging across multiple sessions. This skill is non-negotiable.

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
   - UID exists in data file (Rule 1) — `d2r_lookup_unique` or read `unique_items.py`
   - Item code matches base type in `item_bases.py`
   - Target storage has free space (check grid with scanner)
   - Stats are non-zero (Rule: Dex/Energy must never be 0)

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

5. **Run d2rdoctor scanner** (Rule 4)
   ```bash
   python3 -m d2r_chargen scan CHARNAME
   ```

6. **Evaluate ALL scanner output** (Rule 19)
   - Hard error → STOP. Fix before proceeding. Never dismiss as false positive without bit-level proof (Rule 17).
   - Checksum mismatch → recalculate (Rule 5)
   - LF inconsistent → fix merc state
   - Encoding issues → rebuild item

7. **Only proceed to next edit when scanner is clean.**

## Red Flags — STOP Immediately

- "Let me just do this other edit too" → NO. One edit per cycle.
- "That scanner warning is probably fine" → NO. Investigate every error (Rule 19).
- "I'll scan after all the edits" → NO. Scan after EACH edit (Rule 12).
- "The number makes semantic sense" → NOT proof. Check actual encoding (Rule 17).
- "Let me rebuild the whole file" → NO. Targeted section edits only (Rule 2).

## Merc Rules

- NEVER inject items directly into JM[merc] (Rule 6). Place in stash, equip in-game.
- Only safe merc edit: setting lf_count.
- Verify lf_count >= 1 before any merc-related work.

## After All Edits Complete

- Remind user: **Fully exit and relaunch D2R** — staying on character select does NOT reload (Rule 7).
- If YAML build fails but hand-patched binary works → bug is in resolve.py (Rule 18).

## Debugging Escalation

If an edit causes FAILED TO JOIN GAME:
1. Check blz-log.txt FIRST
2. Compare scanner output between working backup and broken file
3. Startup crash (<60s) = bad data. Runtime crash (>5min) = Wine/Proton issue.
4. If chargen YAML fails but manual binary works → resolve.py bug (Rule 18)
