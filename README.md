# Horadric Tools for Diablo II: Resurrected

[![Tests](https://github.com/crabsmadethis/d2r-horadric-tools/actions/workflows/test.yml/badge.svg)](https://github.com/crabsmadethis/d2r-horadric-tools/actions/workflows/test.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Platform: Linux](https://img.shields.io/badge/platform-Linux%20%7C%20Steam%20Deck-orange.svg)](#platform-support)

Horadric Tools is a Python toolkit for offline Diablo II: Resurrected modding
and save-file workflows. It turns YAML into `.d2s` characters, builds data mods
from declarative patches, inspects save files before you load them, and exposes
the same tools through an MCP server for Claude Code, Codex, Cursor, and other
agent clients.

The project is Linux / Steam Deck first, with Windows path detection included
but not heavily tested. It does not ship Blizzard game data, private save files,
or Battle.net automation.

## What It Does

- Build offline `.d2s` characters from YAML.
- Encode equipment, runewords, charms, stats, skills, merc gear, Iron Golems,
  and experimental template-derived bound demons.
- Scan saves for structural problems before you try them in game.
- Extract local D2R data into generated Python lookup tables.
- Build and deploy data mods from YAML overlays and JSON string patches.
- Provide 23 MCP tools for game-data lookup, save inspection, chargen, and mod
  pipeline automation.

## What It Is Not

- Not an online-play tool.
- Not a trainer, bot, maphack, or memory editor.
- Not a bundle of extracted D2R data.
- Not a promise that every generated save is safe to load without scanning.

For save-file work, the core rule is simple: build or edit in staging, scan the
result, then promote it only if validation passes.

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

## Character YAML

The public repo ships only curated example characters in `chars/`. Keep local,
disposable, or validation-specific character drafts outside the tracked repo
and point the tools at them with `D2R_CHARS=/path/to/chars`. A small character
definition looks like:

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

See [chars/ExamplePaladin.yaml](chars/ExamplePaladin.yaml) for a fuller example.

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
```

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

After `d2r-mod build`, patched JSONs land in
`build/data/local/lng/strings/`. D2R caches strings at startup, so fully exit
and relaunch to see changes.

## MCP Server

Horadric Tools ships an [MCP](https://modelcontextprotocol.io) server for agent
clients. It exposes game-data lookups, save inspection, character generation,
and mod pipeline commands as typed tools.

Install the MCP SDK before launching the server:

```bash
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

See [d2r_mcp/README.md](d2r_mcp/README.md) for the full tool catalog.

## Safety Model

The save-file workflow is intentionally conservative:

1. Start from an existing valid `.d2s` template where possible.
2. Write changes to a temp or staging file.
3. Recompute size and checksum.
4. Run `d2r-chargen scan <name>`.
5. Promote only scanner-clean files.

Scanner hard errors are treated as deployment blockers unless there is
bit-level evidence that the scanner is wrong. The detailed save-format notes
live in [docs/d2s_format.md](docs/d2s_format.md).

## Repository Map

```text
d2r_chargen/    YAML character builder, save writer, scanner, import/diff tools
d2r_mod/        Data extraction, overlays, CASC read/write, deploy pipeline
d2r_mcp/        MCP server and tool definitions
chars/          Example character YAML files
examples/       Overlay examples
docs/           Save-format notes and manual validation guidance
tools/          Standalone diagnostics and hygiene checks
plugin/         Optional Claude Code plugin commands and skills
```

## Platform Support

| Platform | Status |
| --- | --- |
| Linux / Steam Deck (Proton) | Supported, tested |
| Windows | Path detection included, needs more testing |
| macOS | Unsupported for playing D2R; useful for docs and code work only |

## Requirements

- Python 3.11+
- PyYAML
- Diablo II: Resurrected for data extraction
- MCP SDK for agent integration (`pip install mcp`)

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
