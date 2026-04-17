---
name: d2r-character-design
description: Use when creating, planning, or designing a new D2R character — guides class selection, gear lookup, stat allocation, and YAML creation with verified game data
---

# D2R Character Design

## Overview

Guide the user through designing a new D2R character. Every item, runeword, and base referenced MUST be verified via MCP lookup or data file read before going into the YAML. No guessing.

## Process

### 1. Discuss Build

Ask the user about:
- Class (amazon, sorceress, necromancer, paladin, barbarian, druid, assassin, warlock)
- Build archetype (e.g., hammerdin, blizzard sorc, summoner necro)
- Level target (usually 99)
- Playstyle priorities (MF, PvP, speed, tank)

### 2. Look Up Gear

For EVERY item:
- **Unique items:** Use `d2r_lookup_unique` to verify name, UID, base code, and stats
- **Runewords:** Use `d2r_lookup_runeword` to verify name, rune recipe, valid base types, and stats
- **Base items:** Use `d2r_lookup_item_base` to verify 3-char code, dimensions, socket count, requirements
- **Set items:** Use `d2r_lookup_set_item` to verify name, ID, and set bonuses

**NEVER reference an item without looking it up first.** This is the single most important rule.

### 3. Allocate Stats

Based on gear requirements:
- Strength: enough to equip highest-requirement item
- Dexterity: enough for block chance or weapon requirements
- Vitality: remainder
- Energy: class base minimum (NEVER 0)

### 4. Allocate Skills

Based on build archetype. Look up skill names via `d2r_lookup_skill` if unsure of exact names.

### 5. Check Grid Fit

- Stash: 10 cols × 8 rows
- Inventory: 10 cols × 4 rows (minus charm space)
- Use `d2r_lookup_item_base` to get dimensions for each item
- Verify items don't collide in stash grid

### 6. Check Socket Counts

For runeword items, verify the base has enough sockets:
- Look up runeword to get required rune count
- Look up base item to get max socket count
- Ensure max_sockets >= rune_count

### 7. Write YAML

Write the character definition to `chars/<name>.yaml` following the schema in README.md.

### 8. Hand Off to Build

Suggest `/d2r-build <name>` for the actual build cycle.

## Key Rules

- Rule 1: Every UID, code, and stat MUST come from data files
- Rule 9: Never trust web research for game data
- Rule 8: Items must include stat properties
- Rule 13: Grouped stats (np>0) encode multiple values under one stat ID; missing this causes FAILED TO JOIN GAME
