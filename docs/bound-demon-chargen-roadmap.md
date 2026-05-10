# Bound Demon Chargen Roadmap

This roadmap describes the public chargen path from template cloning toward
more robust Reign of the Warlock bound-demon generation.

## Goal

Safe v1 support copies a known template payload:

```yaml
bound_demon:
  template: known_template
```

The robust target is a YAML surface that can author a demon from stable fields:

```yaml
bound_demon:
  template: known_template
  monster_hcidx: 20
  affixes: [Extra Strong, Extra Fast]
  bind_level: 20
```

Full synthesis without a template remains blocked until the remaining runtime
and hash-like bytes are decoded or proven ignorable.

## Field Confidence

| Offset | Meaning | Writer confidence |
| --- | --- | --- |
| `+0..+1` | follower kind tag `0x0018` | fixed |
| `+4..+5` | `monster_hcidx` | authorable in template-derived payloads |
| `+6..+9` | monster seed | preserve template value; arbitrary override is unsafe |
| `+52..+55` | persisted bind metadata | persistent; not proven to be current Bind Demon skill level |
| `+80..+84` | five MonUMod affix bytes | authorable in template-derived payloads |
| `+89..+91` | volatile runtime bytes | do not author |
| `+92..+93` | embedded `gf` payload data | data, not a section marker |

The five MonUMod bytes do not explain every visible property. Some properties
can be monster-specific or stored in other still-unknown payload regions.

Recent live validation tightened two important limits:

- A direct Spectral Hit plus Aura Enchanted affix-byte override persisted in
  the save, but did not visibly display those properties.
- A non-template monster seed caused D2R to save the character back with
  `follower_count=0`, so seed override must stay blocked until seed semantics
  are decoded.
- A natural bind with the Warlock skill block showing Bind Demon level 20 still
  saved payload `+52` as `7`; do not treat this field as the current skill
  level until a natural bind-level matrix explains it.
- A pre-authored empty-affix follower matrix at hard Bind Demon levels 1, 5,
  10, 15, and 20 displayed no added properties and saved back with unchanged
  empty affix bytes. Skill level and payload `+52` are therefore not sufficient
  to make tooltip-granted properties appear on an authored follower.
- Original-template and forced-monster payloads both displayed the five authored
  normal affixes. Spectral Hit plus Aura Enchanted displayed when authored
  directly on the original template model, and also appeared at runtime when
  the five normal affix bytes were authored together. Clearing those five bytes
  removed all visible properties.

## Support Tiers

| Tier | YAML | Meaning | Status |
| --- | --- | --- | --- |
| 1 | `template: NAME` | Copy a known 116-byte payload | Supported |
| 2 | template plus safe field overrides | Edit proven fields while preserving the rest | Experimental |
| 3 | template plus monster identity changes | Change model while borrowing compatible runtime fields | Experimental |
| 4 | fully synthesized payload | Build all 116 bytes without a template | Blocked |

## Remaining Work

- Decode or classify unknown slices at `+24..+31`, `+44/+48`, `+64..+79`,
  `+88`, and `+95..+115`.
- Prove which template/model fields control visible demon shape.
- Prove whether Bind Demon level affects freshly bound demons, as distinct from
  pre-authored follower payloads.
- Build canonicalization-aware assertions for any field D2R rewrites on
  save/exit.
- Promote experimental YAML fields only after the scanner and docs agree on the
  field confidence.

## Public Validation Standard

Use `docs/manual-save-validation.md` for any local game validation. Public docs
should record the stable behavior and limitation, not disposable character
names, machine details, or session logs.

## Active Manual Probe Focus

The affix-isolation batch ruled out single Extra Strong, Fire Enchanted,
Cursed, Mana Burn, Extra Fast, and Fire/Cursed/Mana as the source of the
unexpected Spectral Hit plus Aura Enchanted display.

The next manual batch should isolate whether the Spectral Hit plus Aura
Enchanted runtime display is triggered by affix count, a specific affix
combination, or the presence of Extra Fast with the earlier affixes.
