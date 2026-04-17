---
description: Look up D2R game data — items, stats, skills, runewords from extracted game files
argument-hint: "Item/stat/skill name or 'search <query>' for cross-type search"
---

# D2R Data Lookup

Look up `$ARGUMENTS` in the D2R game data files.

## How to Look Up

Use the MCP data tools (d2r-data server). These query the extracted game data in `d2r_chargen/data/` — the ONLY authoritative source (Rule 9).

**By type (when you know what you're looking for):**
- `d2r_lookup_unique` — unique items by name/UID
- `d2r_lookup_set_item` — set items by name/ID
- `d2r_lookup_item_base` — base items by 3-char code or name
- `d2r_lookup_runeword` — runewords by name/ID (includes runes, valid bases, stats)
- `d2r_lookup_stat` — stats by ID, canonical name, or alias (includes encoding params)
- `d2r_lookup_skill` — skills by name/ID

**Cross-type search (when you're not sure):**
- `d2r_search` — searches uniques, sets, runewords, and bases

## Rules

- Rule 1: NEVER hallucinate UIDs, item codes, or binary format values. Every value MUST come from the data files.
- Rule 9: NEVER trust web research for D2R game data. If data isn't in these files, it doesn't exist.
- Rule 14: Verify stat aliases against `d2r_chargen/config.py` PROPERTY_ALIASES.

## Data File Locations

All in `/home/deck/d2r-editor/d2r_chargen/data/`:
- `unique_items.py` + `unique_item_stats.py` — unique item definitions and stats
- `set_items.py` — set item definitions
- `item_bases.py` — base item types (dimensions, requirements, sockets)
- `runewords.py` + `runeword_stats.py` — runeword definitions and stats
- `item_stat_cost.py` — stat encoding parameters (save_bits, save_add, etc.)
- `skills.py` — skill definitions
