# Horadric Tools for Diablo II: Resurrected

[![Tests](https://github.com/crabsmadethis/d2r-horadric-tools/actions/workflows/test.yml/badge.svg)](https://github.com/crabsmadethis/d2r-horadric-tools/actions/workflows/test.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Platform: Linux](https://img.shields.io/badge/platform-Linux%20%7C%20Steam%20Deck-orange.svg)](#platform-support)

Horadric Tools is a Python toolkit for offline Diablo II: Resurrected save and
data-mod workflows. It builds `.d2s` characters from YAML, scans save files
before they are loaded, builds data mods from declarative patches, and exposes
the same operations through an MCP server.

The repository is Linux / Steam Deck first. Windows path detection exists but
needs more testing. The repo does not ship Blizzard game data, private save
files, memory captures, or Battle.net automation.

## Toolkit Scope

Horadric Tools provides:

- `d2r-chargen`: YAML-to-`.d2s` character generation, import, diff, validation,
  and scanning.
- `d2r-mod`: local data extraction, overlay builds, JSON string patches, CASC
  deploy helpers, diffs, audits, and cleanup commands.
- `d2r_mcp`: 23 MCP tools for lookup, save inspection, character generation,
  and mod-pipeline automation.
- Public diagnostics in `tools/` for corpus scans, follower payload inspection,
  model-row comparison, and repo hygiene checks.

Character generation currently covers equipment, runewords, charms, stats,
skills, mercenary gear, Iron Golems, and experimental template-derived bound
demons. Bound-demon template recipes are documented in
[docs/bound-demon-template-recipes.md](docs/bound-demon-template-recipes.md);
they keep source affixes separate from Bind Demon skill affixes and do not
treat template-derived support as arbitrary algorithmic synthesis. A narrow
registry-backed `synthesis_validated` surface is also available for exact
validated packages; list those ids with `d2r-chargen bound-demon-packages`.

## Non-Goals

- Online play, ladder play, or Battle.net automation.
- Trainers, bots, maphacks, or live memory editors.
- Committed extracted D2R data, raw save corpora, or machine-local fixtures.
- Loading generated saves without first running the scanner.

For `.d2s` work, the expected loop is: write to staging, recompute size and
checksum, scan, then promote only scanner-clean output.

## Quickstart

```bash
git clone https://github.com/crabsmadethis/d2r-horadric-tools.git
cd d2r-horadric-tools
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Generate local lookup data from your D2R install:

```bash
d2r-mod extract
```

If the install is not auto-detected:

```bash
d2r-mod extract --game-dir "/path/to/Diablo II Resurrected"
```

Validate the included example character:

```bash
d2r-chargen validate ExamplePaladin
```

Build it only when your save directory is configured and you are ready to write
the generated save:

```bash
d2r-chargen build ExamplePaladin --force
d2r-chargen scan ExamplePaladin
```

D2R caches saves at startup, so fully exit and relaunch the game after changing
a local save file.

## Character YAML

The tracked `chars/` directory contains curated examples only. Keep disposable
or validation-specific character drafts outside the repo and point the tools at
them with `D2R_CHARS=/path/to/chars`.

```yaml
schema_version: 1
name: ExamplePaladin
class: paladin
level: 85
progression: hell_complete

stats:
  strength: 156
  dexterity: 125
  vitality: 250
  energy: 25

skills:
  Blessed Hammer: 20
  Concentration: 20
  Vigor: 20

equipment:
  - slot: helm
    unique: Harlequin Crest
  - slot: body
    runeword: Enigma
    base: utp
  - slot: weapon
    runeword: Heart of the Oak
    base: fla

inventory:
  charms:
    - magic_grand_charm:
        count: 8
        properties:
          skill_tab: [1, 15]
          life: 40
```

See [chars/ExamplePaladin.yaml](chars/ExamplePaladin.yaml) for a fuller
example.

Iron Golem payloads are authored with an `iron_golem:` block on Necromancers
that have `IronGolem` learned. The supported public surface includes normal,
magic, ethereal, set, rare, crafted, socketed-normal, and runeword payloads.
Runeword golems are written as a JM-less parent followed by generated rune
filler records inside the golem block. Unique payloads require explicit
canonicalization opt-in because D2R rewrites some bytes on save/exit. Manual
socket filler authoring and broad jewel-filler authoring remain gated; current
live proof covers only the narrow character-item shape for a normal parent plus
one magic `jew` or unique `cjw` filler, and that YAML surface is not exposed
yet.

```yaml
class: necromancer
skills:
  IronGolem: 1
iron_golem:
  item:
    runeword: Insight
    base: 7wc
```

Supported class names:

```text
amazon, sorceress, necromancer, paladin, barbarian, druid, assassin, warlock
```

Common equipment slots:

```text
helm, body, weapon, shield, hands, belt, feet, neck, ring_right, ring_left,
weapon_switch, shield_switch
```

## CLI Reference

### `d2r-chargen`

```bash
d2r-chargen list
d2r-chargen validate <name> [--yaml-only]
d2r-chargen build <name> [--phase N] [--force]
d2r-chargen scan <name>
d2r-chargen import <name> [--force]
d2r-chargen diff <file1> <file2>
d2r-chargen bound-demon-packages [--json] [--all]
```

`validate` checks YAML and binary encoding without writing a save, including
bound-demon and Iron Golem payloads when the YAML requests them. `build` writes
through the safety pipeline and should be followed by `scan` before the result
is loaded in game.

For bound demons, normal reusable authoring should use `template_path` or a
listed `synthesis_validated` package id. Raw context slices, generated-name
requests, aura-choice requests, pcount/stat knobs, and algorithmic
`monster: NAME` synthesis fail before any save is written unless a validated
package explicitly owns that behavior.

Bound-demon template workflow:

```bash
python3 tools/d2s_demon_template_inspect.py <template.d2s>
python3 tools/d2s_demon_template_inspect.py <template.d2s> \
  --extract-payload .local-demon-templates/<template>.bin \
  --emit-yaml-snippet
```

The emitted YAML snippet is preserve-only. It names `template_path` and the
payload row index, but does not add source or skill affix edits. Put character
drafts and extracted templates outside the repo:

```bash
export D2R_CHARS=/path/to/local/chars
export D2R_SAVES=/path/to/offline-saves
d2r-chargen validate MyWarlock
d2r-chargen build MyWarlock --force
d2r-chargen scan MyWarlock
```

The public template catalog currently documents Black Lancer, Mauler,
Lister-style/Baal Subject 5, and Hephasto-family entries in
[docs/bound-demon-template-recipes.md](docs/bound-demon-template-recipes.md).

### `d2r-mod`

```bash
d2r-mod extract [--game-dir PATH]
d2r-mod build [--no-regen]
d2r-mod deploy [--force] [--no-casc]
d2r-mod undeploy
d2r-mod diff [--summary]
d2r-mod inject [--from-dir PATH]
d2r-mod audit [--skills] [--items]
d2r-mod clean
d2r-mod update
```

Commands that read or write game data need a detected D2R install or an
explicit `--game-dir` / `D2R_GAME_DIR`.

## Data Mod Overlays

Overlays modify D2R data tables declaratively. Place overlay files in
`overlays/` and run `d2r-mod build`.

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

If no `overlays/` directory exists, the build proceeds with vanilla data only.
See [examples/sample_overlay.yaml](examples/sample_overlay.yaml) for a complete
example.

## JSON String Patches

D2R reads most item, mercenary, and UI strings from JSON files under
`data/local/lng/strings/`. Put YAML specs in `patches/json_strings/` to add or
override strings:

```yaml
description: "Rename a few potions"
target: item-names.json
entries:
  - key: "vps"
    value: "Wild Rice Cake"
  - key: "MyCustomItem"
    value: "Heart of the Mountain"
```

After `d2r-mod build`, patched JSON files are written to
`build/data/local/lng/strings/`. D2R caches strings at startup, so fully exit
and relaunch to see changes.

## MCP Server

Horadric Tools ships an [MCP](https://modelcontextprotocol.io) server with 23
tools across lookup, save inspection, chargen, and mod-pipeline categories.

Install the package and the MCP SDK before launching the server:

```bash
pip install -e .
pip install mcp
```

Launch it with:

```bash
python3 -m d2r_mcp
```

Claude Code:

```bash
claude mcp add d2r-tools --transport stdio --scope user -- python3 -m d2r_mcp
```

Generic MCP config:

```json
{
  "mcpServers": {
    "d2r-tools": {
      "command": "python3",
      "args": ["-m", "d2r_mcp"],
      "env": {}
    }
  }
}
```

See [d2r_mcp/README.md](d2r_mcp/README.md) for the full tool catalog and safety
notes.

## Safety Model

The save-file workflow is intentionally conservative:

1. Back up the target save family before writing.
2. Start from an existing valid `.d2s` template when possible.
3. Write changes to a temp or staging file.
4. Recompute size and checksum.
5. Run `d2r-chargen scan <name>`.
6. Promote only scanner-clean files.

Scanner hard errors are deployment blockers unless there is bit-level evidence
that the scanner is wrong. Detailed save-format notes live in
[docs/d2s_format.md](docs/d2s_format.md).

## Repository Map

```text
d2r_chargen/    Character YAML parser, save writer, scanner, importer, diff
d2r_mod/        Data extraction, overlays, CASC read/write, deploy pipeline
d2r_mcp/        MCP server, tool wrappers, response envelope, MCP docs
chars/          Curated example character YAML
examples/       Public overlay examples
docs/           Save-format notes, validation docs, public research writeups
tools/          Standalone diagnostics, corpus tools, hygiene checks
plugin/         Optional Claude Code plugin commands
tests/          Unit, MCP, scanner, mod-pipeline, and fixture-gated tests
```

Generated data, build output, local evidence, and extracted game files should
stay untracked.

## Platform Support

| Platform | Status |
| --- | --- |
| Linux / Steam Deck (Proton) | Supported, tested |
| Windows | Path detection included, needs more testing |
| macOS | Unsupported for playing D2R; useful for docs and code work only |

## Requirements

- Python 3.11+
- PyYAML, installed by the package
- Diablo II: Resurrected for data extraction and live game use
- MCP SDK for MCP server use (`pip install mcp`)

## Contributing

Start with [CONTRIBUTING.md](CONTRIBUTING.md). Before opening a PR, run:

```bash
python tools/public_hygiene_check.py
ruff check .
pytest tests/ -v --timeout=60 \
  -m "not integration and not slow and not e2e and not smoke" \
  --ignore=tests/fixtures/ \
  --ignore=tests/test_chargen.py \
  --ignore=tests/test_decoder.py \
  --ignore=tests/test_fixtures.py \
  --ignore=tests/test_importer.py
```

## License

MIT
