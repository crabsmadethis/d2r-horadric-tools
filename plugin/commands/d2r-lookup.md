---
description: Look up D2R game data — items, stats, skills, runewords from extracted game files
argument-hint: "Item/stat/skill name or 'search <query>' for cross-type search"
---

# D2R Data Lookup

Look up `$ARGUMENTS` in the D2R game data files.

## How to Look Up

Use the MCP data tools (d2r-data server) if available. These query the extracted game data in `d2r_chargen/data/` — the ONLY authoritative source (Rule 9).

**By type (when you know what you're looking for):**
- `d2r_lookup_unique` — unique items by name/UID
- `d2r_lookup_set_item` — set items by name/ID
- `d2r_lookup_item_base` — base items by 3-char code or name
- `d2r_lookup_runeword` — runewords by name/ID (includes runes, valid bases, stats)
- `d2r_lookup_stat` — stats by ID, canonical name, or alias (includes encoding params)
- `d2r_lookup_skill` — skills by name/ID

**Cross-type search (when you're not sure):**
- `d2r_search` — searches uniques, sets, runewords, and bases

**Fallback (if MCP server not available):**
Read the data files directly from `d2r_chargen/data/` using Grep or Read tools.

## Rules

- Rule 1: NEVER hallucinate UIDs, item codes, or binary format values.
- Rule 9: NEVER trust web research for D2R game data. If data isn't in these files, it doesn't exist.
