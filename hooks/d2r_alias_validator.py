#!/usr/bin/env python3
"""PostToolUse: Validate PROPERTY_ALIASES after config.py edits (Rule 14).

Checks:
1. All aliases resolve to valid STAT_BY_NAME entries
2. Critical aliases map to correct stat IDs (prevents ed->stat17 class bugs)
"""
import json
import sys

input_data = json.load(sys.stdin)

if input_data.get("tool_name") != "Edit":
    sys.exit(0)

file_path = input_data.get("tool_input", {}).get("file_path", "")
if "config.py" not in file_path or "d2r_chargen" not in file_path:
    sys.exit(0)

# Critical alias->stat_id mappings that must not drift.
# Each was the root cause of a crash at least once.
CRITICAL_ALIASES = {
    "ed": ("item_armor_percent", 16),       # Enhanced Defense, NOT stat 17
    "strength": ("strength", 0),
    "dexterity": ("dexterity", 2),
    "vitality": ("vitality", 3),
    "energy": ("energy", 1),
}

try:
    from d2r_chargen.config import PROPERTY_ALIASES
    from d2r_chargen.data.item_stat_cost import STAT_BY_NAME

    errors = []

    # Check 1: all aliases resolve
    for alias, canonical in PROPERTY_ALIASES.items():
        if canonical not in STAT_BY_NAME:
            errors.append(f"  '{alias}' -> '{canonical}' not in STAT_BY_NAME")

    # Check 2: critical aliases map to correct stat IDs
    for alias, (expected_canonical, expected_id) in CRITICAL_ALIASES.items():
        if alias in PROPERTY_ALIASES:
            actual_canonical = PROPERTY_ALIASES[alias]
            actual_id = STAT_BY_NAME.get(actual_canonical)
            if actual_canonical != expected_canonical:
                errors.append(
                    f"  CRITICAL: '{alias}' -> '{actual_canonical}' "
                    f"(expected '{expected_canonical}')"
                )
            elif actual_id != expected_id:
                errors.append(
                    f"  CRITICAL: '{alias}' -> stat {actual_id} "
                    f"(expected stat {expected_id})"
                )

    if errors:
        print("ALIAS VALIDATOR (Rule 14) — errors found:")
        for e in errors:
            print(e)
        print("  Cross-check against build_lib.py constants (lines 840-870)")
        # Exit 0 because the edit already happened — this is advisory.
        # The warning text gets injected as context for Claude.
        sys.exit(0)

    count = len(PROPERTY_ALIASES)
    print(f"Alias validator: all {count} aliases validated OK")

except Exception as e:
    # Don't block on validator errors (import failures, etc.)
    sys.stderr.write(f"Alias validator error: {e}\n")

sys.exit(0)
