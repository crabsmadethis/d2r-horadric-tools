# D2R Modding — Claude Rules

## Rules

### 1. NEVER hallucinate UIDs, item codes, or binary format values
Every unique item UID MUST come from `d2r_chargen/data/unique_items.py`. Every set item ID from `set_items.py`. Every item code from `item_bases.py`. Read the file. Search it. Quote the result. Use the MCP tools (`d2r_lookup_unique`, `d2r_lookup_runeword`, etc.) when available.

### 2. NEVER rebuild a .d2s from scratch
The header (0x14-0x7F) has interdependent fields that cannot be reliably reproduced. Always start from an existing .d2s and make targeted section edits.

### 3. ALWAYS backup before writing any .d2s
```python
shutil.copy2(path, path + '.pre_DESCRIPTION_bak')
```
Verify the backup was created before proceeding.

### 4. ALWAYS run scanner after every edit phase
```bash
d2r-chargen scan <name>
```
Do not stack multiple edits and test at the end. Edit one thing → scan → verify → next edit.

### 5. ALWAYS verify checksums after writing
```python
stored == calc_checksum(result)
```

### 6. Merc gear requires canonical encoding in JM[merc]
Direct merc injection works when items use D2R's canonical form: col=bodyloc (not 0), runeword ID biased (low12 = id+27, high4 = 5), and lf_count=0. Use `equipment_mode: direct` in YAML. The stash-and-equip workaround is no longer needed.

### 7. D2R caches saves at session startup
The user MUST fully exit and relaunch D2R after file changes. Staying on character select does NOT reload files.

### 8. Items MUST include stat properties
`build_item()` with only `unique_id` and no magic_attributes produces items that display correct names but have ZERO stats. Always encode properties using `item_stat_cost.py` data.

### 9. NEVER trust web research for D2R game data
ALL item UIDs, stat encoding params, runeword indices, and item base properties MUST come from `d2r_chargen/data/`. If data isn't in those files, it doesn't exist.

### 10. Write to temp, verify, then overwrite
Never write directly to a live .d2s. Write to a temp file, verify with the scanner, THEN copy to the real location.

### 11. Scanner hard errors are deployment blockers
Never deploy a file that fails scanner validation. Never classify a scanner hard error as a "false positive" without bit-level proof.

### 12. Edit incrementally, test after each change
Modify one thing → test → next thing. When a multi-phase edit fails, you can't isolate which phase caused it.

### 13. Grouped stats encode multiple values under one stat ID
When a stat has `num_params > 0` (np>0 in item_stat_cost.py), all param+value pairs must be encoded together. Missing this causes FAILED TO JOIN GAME.

## Workflows

- **Build a character:** `d2r-chargen build <name>` or `/d2r-build <name>`
- **Look up game data:** MCP tools (`d2r_lookup_unique`, `d2r_search`, etc.) or `/d2r-lookup <query>`
- **Validate YAML:** `d2r-chargen validate <name>` or `/d2r-validate <name>`
- **Scan for issues:** `d2r-chargen scan <name>` or `/d2r-scan <name>`
- **Deploy mod:** `d2r-mod build && d2r-mod deploy` or `/d2r-deploy`
- **Revert mod:** `d2r-mod undeploy` or `/d2r-undeploy`

## Quick Reference

```
Classes: 0=Amazon 1=Sorceress 2=Necromancer 3=Paladin 4=Barbarian 5=Druid 6=Assassin 7=Warlock
Storage: 0=equipped 1=inventory 2=belt 4=cube 5=personal_stash
Stash: 10 cols × 8 rows
Inventory: 10 cols × 4 rows
Cube: 3 cols × 4 rows
Stats stored ×256: HP, Mana, Stamina
Data files: d2r_chargen/data/ (unique_items.py, set_items.py, item_bases.py, item_dimensions.py, runewords.py, item_stat_cost.py, skills.py)
```
