---
description: Validate a D2R character YAML definition without building or deploying
argument-hint: "Character name (e.g. Tempest)"
---

# D2R Validate

Validate the YAML definition for `$ARGUMENTS` without building or deploying.

```bash
python3 -m d2r_chargen validate $ARGUMENTS
```

This checks:
- YAML syntax and schema
- Item UIDs exist in data files (Rule 1)
- Item codes match base types in item_bases.py
- Stat aliases resolve via PROPERTY_ALIASES (Rule 14)
- Runeword indices exist in runewords.py
- Socket filler validity

No .d2s files are written or modified. Safe to run at any time.

## Follow-up

If validation passes and you want to build:
- Use `/d2r-build $ARGUMENTS` for the full safe build cycle

If validation fails:
- Fix the YAML in `chars/$ARGUMENTS.yaml`
- Re-run validation before attempting a build
