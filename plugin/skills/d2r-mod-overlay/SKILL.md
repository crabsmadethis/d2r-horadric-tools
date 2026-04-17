---
name: d2r-mod-overlay
description: Use when the user wants to change game balance, buff/nerf items, modify skills, or adjust drop rates — guides overlay YAML creation and mod deployment
---

# D2R Mod Overlay

## Overview

Guide the user through creating game data modifications using the overlay system. Overlays are YAML files that declaratively change D2R data tables without editing vanilla files directly.

## Process

### 1. Identify the Change

Understand what the user wants to modify:
- Item stats (UniqueItems.txt, SetItems.txt)
- Skill damage/behavior (Skills.txt, Missiles.txt)
- Drop rates (TreasureClassEx.txt)
- Monster stats (MonStats.txt, MonLvl.txt)
- Runeword properties (Runes.txt)

### 2. Look Up Current Values

Use the data files or MCP tools to find current values:
```bash
d2r-mod diff  # if a build already exists, shows current changes
```

Or read vanilla data directly from `vanilla/data/global/excel/` after extraction.

### 3. Write the Overlay

Create a YAML file in `overlays/`:

```yaml
target: data/global/excel/UniqueItems.txt
changes:
  - row: {index: "The Gnasher"}
    set:
      prop4: "dmg%"
      min4: "50"
      max4: "50"
    comment: "Buff The Gnasher with +50% Enhanced Damage"
```

Key overlay fields:
- `target`: path to the game table (relative to data root)
- `row`: match criteria (`index` matches the row key/name column)
- `set`: column values to change
- `comment`: explain the change (for diffing later)

### 4. Build

```bash
d2r-mod build
```

Check for warnings about conflicting overlays.

### 5. Review Changes

```bash
d2r-mod diff --summary   # one-line per changed file
d2r-mod diff              # full diff
```

Show the user exactly what changed.

### 6. Deploy

Confirm with the user, then:
```bash
d2r-mod deploy
```

### 7. Remind User

**D2R caches data at startup. Fully exit and relaunch D2R to see mod changes.**

## Overlay Tips

- One overlay per logical change (don't bundle unrelated changes)
- Use descriptive filenames: `buff-gnasher.yaml`, `fix-sorc-skills.yaml`
- The `comment` field is optional but helps when reviewing diffs later
- Multiple overlays can target the same table — they're applied in filename order
