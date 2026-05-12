# Claude Instructions

Follow these rules when working in this repository. They apply to Claude Code
slash commands, MCP tool use, and direct file edits.

## Data Sources

- Do not invent item IDs, UIDs, stat encodings, runeword IDs, skill IDs, or
  binary format values.
- Read the generated data modules in `d2r_chargen/data/` before using D2R
  constants:
  - `unique_items.py`
  - `set_items.py`
  - `item_bases.py`
  - `item_dimensions.py`
  - `runewords.py`
  - `item_stat_cost.py`
  - `skills.py`
- Use MCP lookups such as `d2r_lookup_unique`, `d2r_lookup_runeword`, and
  `d2r_search` when available.
- Do not trust web research for D2R game data. If the value is not in local
  extracted data or a verified source file, treat it as unknown.

## Save-File Invariants

- Do not rebuild a `.d2s` from scratch when a targeted edit can preserve the
  existing file structure. Header fields around `0x14-0x7F` are interdependent.
- Back up before writing any `.d2s`:

```python
shutil.copy2(path, path + ".pre_DESCRIPTION_bak")
```

- Verify the backup exists before editing.
- Write to a temp or staging path first. Do not write directly to the live
  save path.
- Run the scanner after every edit phase:

```bash
d2r-chargen scan <name>
```

- Verify checksums after writing:

```python
stored == calc_checksum(result)
```

- Verify file-size fields when the write changes file length.
- Promote the temp file to the live path only after scanner validation passes.
- Do not stack multiple risky edits before scanning.
- Treat scanner hard errors as deployment blockers unless bit-level evidence
  proves the scanner is wrong.
- D2R caches saves at session startup. Fully exit and relaunch D2R after file
  changes; staying on character select is not enough.

## Item and Stat Encoding

- Items must include stat properties. `build_item()` with only `unique_id` and
  no `magic_attributes` can display the correct name with zero stats.
- Encode item properties from `item_stat_cost.py`.
- Grouped stats with `num_params > 0` must encode all parameter and value pairs
  under the same stat ID. Splitting or omitting grouped values can make a save
  fail to join.
- Merc gear direct injection requires canonical JM[merc] encoding:
  - `col=bodyloc`, not `0`
  - runeword low 12 bits are `id + 27`
  - runeword high 4 bits are `5`
  - `lf_count=0`
- Use `equipment_mode: direct` for mercenary YAML. The stash-and-equip
  workaround is not required for direct mode.

## Public Repository Rules

- Keep committed files public-safe.
- Do not commit personal saves, extracted game data, raw save corpora, raw
  memory captures, machine-local paths, account identifiers, private notes, or
  live validation logs.
- Document stable behavior, public commands, sanitized format findings, and
  repeatable validation procedures.

## MCP Changes

When changing MCP tools in `d2r_mcp/`, update the coupled public surfaces in
the same change:

- `d2r_mcp/README.md` with the current tool count and behavior.
- Root `README.md` if its MCP tool count is stale.
- Tests in `tests/test_mcp_*.py`.

MCP mutation tools must preserve the same backup, scan, and promote pipeline as
`d2r_chargen_build`.

## Commands

```bash
d2r-chargen list
d2r-chargen validate <name>
d2r-chargen build <name> --force
d2r-chargen scan <name>
d2r-chargen import <name> --force
d2r-chargen diff <file1> <file2>
d2r-mod build
d2r-mod deploy
d2r-mod undeploy
python tools/public_hygiene_check.py
ruff check .
python -m pytest
```

MCP equivalents may be available for lookup, validation, build, scan, and mod
pipeline workflows. Keep CLI and MCP behavior aligned when changing shared
logic.

## Quick Reference

```text
Classes: 0=Amazon 1=Sorceress 2=Necromancer 3=Paladin 4=Barbarian 5=Druid 6=Assassin 7=Warlock
Storage: 0=equipped 1=inventory 2=belt 4=cube 5=personal_stash
Stash: 10 cols x 8 rows
Inventory: 10 cols x 4 rows
Cube: 3 cols x 4 rows
Stats stored x256: HP, Mana, Stamina
Data modules: d2r_chargen/data/
```
