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
- Natural binds at hard Bind Demon levels 1, 5, 10, and 20 all saved payload
  `+52` as `7`, while writing the expected threshold affixes into the MonUMod
  bytes. This confirms `+52` is not effective Bind Demon level.
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
- Convert the now-proven natural Bind Demon level thresholds into writer
  semantics that do not depend on payload `+52`.
- Build canonicalization-aware assertions for any field D2R rewrites on
  save/exit.
- Promote experimental YAML fields only after the scanner and docs agree on the
  field confidence.

## Public Validation Standard

Use `docs/manual-save-validation.md` for any local game validation. Public docs
should record the stable behavior and limitation, not disposable character
names, machine details, or session logs.

## Active Manual Probe Focus

Bind Demon table review confirmed that the real skill adds monster affix ids at
specific skill thresholds during the bind action:

| Bind Demon level | Expected skill-granted affixes |
| --- | --- |
| `1..4` | none |
| `5..9` | Extra Strong |
| `10..14` | Extra Strong, Extra Fast |
| `15..19` | Extra Strong, Extra Fast, Spectral Hit |
| `20+` | Extra Strong, Extra Fast, Spectral Hit, Aura Enchanted |

The next decisive manual batch is the natural-bind matrix. These characters
start with no follower and must bind a fresh demon in game so D2R runs the
actual Bind Demon server function:

- `natone`: hard Bind Demon level 1
- `natfive`: hard Bind Demon level 5
- `natten`: hard Bind Demon level 10
- `natteen`: hard Bind Demon level 15
- `nattwen`: hard Bind Demon level 20

The `nat*` builds intentionally avoid Annihilus, Hellfire Torch, skillers,
`all_skills`, and `class_skills`. They instead use rare non-skill gear and
small charms for durability, resists, cast/recovery speed, damage reduction,
open wounds, crushing blow, prevent heal, and slow target. This keeps the hard
Bind Demon thresholds exact while still making the live bind attempt practical.

Record the visible affixes after a successful bind, then save/exit and scan the
resulting follower payload. This proves whether the skill table writes the
expected affix bytes and whether payload `+52` is skill level, bind chance
metadata, or something else.

Current natural-bind results:

| Character | Hard level | Source | Visible result | Payload affixes |
| --- | ---: | --- | --- | --- |
| `natone` | 1 | Hell Fallen | no added properties | none |
| `natfive` | 5 | Hell Fallen | Extra Strong | `5` |
| `natten` | 10 | rare Hell Fallen, started Lightning/Cold/Cursed | retained source affixes, gained Extra Strong and Extra Fast | `7, 17, 18, 5, 6` |
| `natteen` | 15 | Hell Fallen | Extra Strong, Extra Fast, Spectral Hit | `5, 6, 27` |
| `nattwen` | 20 | Hell Fallen | Extra Strong, Extra Fast, Spectral Hit, Aura Enchanted | `5, 6, 27, 30` |

The natural-bind matrix confirms that D2R writes the expected threshold affixes
into the MonUMod bytes during the bind action. Existing source-monster affixes
can carry through ahead of or alongside those threshold affixes, so robust
chargen should model two inputs: source monster affixes and skill-granted
threshold affixes.

The secondary manual batch is the synthetic combo control, already built as
`btone`, `bttwo`, `btthr`, `btfor`, `btfast`, and `btmiss`. Use it only after
the natural-bind matrix if the live affix labels still need byte-combination
isolation.
