---
name: d2r-parallel-agents
description: Use when working on multiple D2R characters, data lookups, or validations simultaneously — patterns for dispatching parallel agents on a 16GB Steam Deck
---

# D2R Parallel Agent Dispatch

## Overview

Claude Code's Agent tool can parallelize D2R work across characters or tasks. On a 16GB Steam Deck, dispatch at most 2 agents simultaneously to avoid OOM.

## When to Parallelize

**Good candidates (independent, read-only or isolated writes):**
- Validating multiple character YAMLs simultaneously
- Looking up game data for several items at once
- Scanning multiple characters after a batch change
- Reviewing multiple char definitions for issues

**Do NOT parallelize:**
- Building characters that share stash (collision risk)
- Edits to the same .d2s file
- Anything that writes to shared state

## Dispatch Patterns

### Pattern 1: Parallel Validation

Validate all characters at once. Each agent validates one character.

```
Agent({
  description: "Validate Tempest YAML",
  prompt: "Run `python3 -m d2r_chargen validate Tempest` and report results. Only report — do not fix anything."
})
Agent({
  description: "Validate Obsidian YAML",
  prompt: "Run `python3 -m d2r_chargen validate Obsidian` and report results. Only report — do not fix anything."
})
```

### Pattern 2: Parallel Data Lookup

Look up multiple items simultaneously for character planning.

```
Agent({
  description: "Look up Enigma runeword",
  prompt: "Use the d2r_lookup_runeword MCP tool to look up 'Enigma'. Return the full result including runes, valid bases, and stats."
})
Agent({
  description: "Look up Harlequin Crest",
  prompt: "Use the d2r_lookup_unique MCP tool to look up 'Harlequin Crest'. Return UID, base, and all stats."
})
```

### Pattern 3: Parallel Scan

Scan multiple characters after a mod data change.

```
Agent({
  description: "Scan Tempest",
  prompt: "Run the d2rdoctor scanner on Tempest. Report: clean, warnings, or hard errors. Full output."
})
Agent({
  description: "Scan Malachar",
  prompt: "Run the d2rdoctor scanner on Malachar. Report: clean, warnings, or hard errors. Full output."
})
```

### Pattern 4: Sequential Build with Parallel Validation

Build characters one at a time (they may share stash), then validate in parallel.

```
# Step 1: Build sequentially (shared state)
python3 -m d2r_chargen build Tempest
python3 -m d2r_chargen build Obsidian

# Step 2: Scan in parallel (read-only)
Agent({ description: "Scan Tempest", ... })
Agent({ description: "Scan Obsidian", ... })
```

## Constraints

- **Max 2 concurrent agents** on this Steam Deck (16GB RAM)
- **Never run D2R + agents** — D2R takes 4-6GB under Proton
- **Agents can't share context** — each starts fresh, brief them fully
- **Read-only agents are always safe** — lookups, validation, scanning
- **Write agents need coordination** — never two agents writing the same file

## Agent Prompt Template

When dispatching D2R agents, include:
1. The exact command to run
2. What to report (success/fail, specific fields, full output)
3. Whether to fix issues or just report
4. Relevant rules if the agent will be writing files

Example:
```
"Run `python3 -m d2r_chargen validate Tempest` from the repo root.
Report: pass/fail and any validation errors.
Do NOT attempt to fix anything — report only.
If validation passes, also run the d2rdoctor scanner and include its output."
```
