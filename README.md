# d2r-tools

D2R modding toolkit for Linux, Steam Deck, and Windows. YAML-driven character builder and data modding pipeline for Diablo II: Resurrected (including Reign of the Warlock expansion).

## Features

- **YAML character builder** - declare characters in YAML, build `.d2s` save files
- **Data mod pipeline** - YAML overlays applied to game tables, built and deployed
- **CASC read/write** - pure Python, no external tools needed
- **Integrated validation** - scanner catches structural problems before loading the game
- **Reign of the Warlock** expansion support (8 classes including Warlock)

## Quickstart

```bash
git clone <repo-url>
cd d2r-tools
pip3 install -e .
d2r-mod extract        # extracts + generates data from your D2R install
d2r-chargen build MyChar
```

(or `pip install -e .` if `pip` points to Python 3 on your system)

Three commands from clone to working. The extract step generates Python data modules from your D2R installation (required for legal reasons - no game data is distributed).

```bash
# If D2R is not auto-detected:
d2r-mod extract --game-dir /path/to/Diablo\ II\ Resurrected
# Or set the environment variable:
export D2R_GAME_DIR="/path/to/Diablo II Resurrected"
```

An example character YAML is included in `chars/ExamplePaladin.yaml`. 
Create your own characters in the `chars/` directory.

D2R install path is auto-detected on Linux/Steam Deck and Windows. Use `--game-dir` to override.

## Character Definition (YAML)

Characters are defined in YAML files placed in a `chars/` directory. Here's a complete example:

```yaml
schema_version: 1
name: MyPaladin
class: paladin
level: 85

stats:
  strength: 156
  dexterity: 100
  vitality: 250
  energy: 15

skills:
  Holy Shield: 20
  Smite: 20
  Fanaticism: 20
  Charge: 1
  Salvation: 1
  Cleansing: 1

equipment:
  # Unique items - resolved automatically from game data
  - slot: helm
    unique: Guillaume's Face

  # Runeword items - specify runeword name and base item code
  - slot: body
    runeword: Fortitude
    base: utp         # Archon Plate

  # Rare/crafted items with explicit properties
  - slot: hands
    rare: true
    base: uvg          # Vampirebone Gloves
    ilvl: 90
    properties:
      fire_res: 30
      cold_res: 30
      light_res: 30
      life: 20

  - slot: weapon
    unique: Grief
    base: 7cr          # Phase Blade

  - slot: shield
    unique: Herald of Zakarum

  - slot: belt
    unique: Verdungo's Hearty Cord

  - slot: feet
    unique: Gore Rider

  - slot: neck
    rare: true
    ilvl: 90
    properties:
      class_skills: [2, paladin]
      fcr: 10
      fire_res: 30
      light_res: 25

  - slot: ring_right
    unique: Bul Katho's Wedding Band

  - slot: ring_left
    unique: Ravenfrost

inventory:
  charms:
    # Unique charms
    - unique: Annihilus
      properties:
        all_skills: 1
        strength: 20
        dexterity: 20
        fire_res: 20
        cold_res: 20
        light_res: 20
        poison_res: 20
        add_exp: 10

    # Repeatable magic charms
    - magic_grand_charm:
        count: 8
        properties:
          skill_tab: [1, 15]   # Combat skills (paladin)
          life: 40

    - magic_small_charm:
        count: 5
        properties:
          life: 20
          light_res: 11

merc:
  equipment:
    - slot: weapon
      unique: The Reaper's Toll
      ethereal: true
```

### Slot Names

`helm`, `body`, `weapon`, `shield`, `hands`, `belt`, `feet`, `neck`, `ring_right`, `ring_left`, `weapon_switch`, `shield_switch`

### Item Types

| Field | Description |
|-------|-------------|
| `unique: "Name"` | Unique item - stats auto-resolved from game data |
| `set_item: "Name"` | Set item |
| `runeword: "Name"` | Runeword - requires `base` code |
| `rare: true` | Rare item - requires `base` and `properties` |
| `magic_grand_charm` | Magic grand charm with `count` and `properties` |
| `magic_small_charm` | Magic small charm with `count` and `properties` |

### Classes

`amazon`, `sorceress`, `necromancer`, `paladin`, `barbarian`, `druid`, `assassin`, `warlock`

## CLI Reference

### d2r-chargen

```bash
d2r-chargen build <name> [--phase N] [--force]   # Build character (phases 1-4)
d2r-chargen validate <name> [--yaml-only]         # Validate YAML definition
d2r-chargen list                                   # List defined characters
d2r-chargen scan <name>                           # Run scanner diagnostics
d2r-chargen import <name> [--force]               # Import .d2s -> YAML
d2r-chargen diff <file1> <file2>                  # Compare .d2s files
```

### d2r-mod

```bash
d2r-mod extract [--game-dir PATH]    # Extract game data + generate Python modules
d2r-mod build [--no-regen]           # Build mod from vanilla + overlays
d2r-mod deploy [--force] [--no-casc] # Deploy mod to game directory
d2r-mod undeploy                     # Remove mod from game
d2r-mod diff [--summary]             # Compare vanilla vs modded tables
d2r-mod inject [--from-dir PATH]     # Inject files into CASC archive
d2r-mod audit [--skills] [--items]   # Audit game data
d2r-mod clean                        # Remove build/ and reset data
d2r-mod update                       # Re-extract after game update
```

## Data Mod Overlays

Overlays modify D2R data tables declaratively using YAML. Place overlay files in an `overlays/` directory and run `d2r-mod build`.

Create an `overlays/` directory in your project root to add custom overlays.
If no overlays directory exists, `d2r-mod build` will proceed with vanilla data only.

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

Each overlay targets a specific game table (TSV file) and specifies row matches and column changes. See `examples/sample_overlay.yaml` for a complete example.

## Architecture

```
d2r_chargen/          YAML character builder
  build_lib.py        Binary item encoder (Huffman, stat encoding, checksums)
  character.py        Build orchestrator (YAML -> items -> .d2s)
  resolve.py          Name-to-ID resolution (uniques, runewords, stats, skills)
  save.py             Save file operations (stats, skills, waypoints, items)
  scanner.py          Diagnostic validator
  data/               Game data (generated via extract, not distributed)

d2r_mod/              Data modding pipeline
  casc.py             Pure Python CASC reader
  casc_write.py       CASC archive builder
  overlay.py          YAML overlay loader and applier
  build.py            Build orchestrator (vanilla + overlays -> build/)
  deploy.py           Deploy/undeploy mod files
  regen.py            Generate chargen data from extracted tables
```

## Platform Support

| Platform | Status |
|----------|--------|
| Linux / Steam Deck (Proton) | Supported, tested |
| Windows | Untested — path detection included, contributions welcome |
| macOS | Unsupported |

## Requirements

- Python 3.9+
- PyYAML
- Diablo II: Resurrected (for data extraction)

## License

MIT

## Claude Code Integration

d2r-tools includes optional [Claude Code](https://claude.ai/code) integration
for natural-language character building, safe save editing, and mod development.

### Setup

```bash
pip install mcp                   # required for data lookup server
d2r-mod claude-setup              # registers MCP server + installs hooks
```

Open a new Claude Code session in the repo directory. Claude automatically
picks up the slash commands and skills.

### Slash Commands

| Command | Description |
|---------|-------------|
| `/d2r-build <name>` | Safe build cycle (backup → build → scan → verify) |
| `/d2r-validate <name>` | Validate character YAML without building |
| `/d2r-scan <name>` | Run diagnostic scanner |
| `/d2r-lookup <query>` | Look up items, stats, skills from game data |
| `/d2r-deploy` | Build and deploy mod to game |
| `/d2r-undeploy` | Remove mod from game |

### Skills (activate automatically)

- **d2r-safe-edit** — enforces backup→edit→scan→verify on every save file change
- **d2r-character-design** — guides new character creation with verified game data
- **d2r-mod-overlay** — guides game balance changes via overlay YAMLs
- **d2r-troubleshoot** — systematic diagnosis for crashes and load errors

### Uninstall

```bash
d2r-mod claude-teardown           # removes hooks + MCP registration
```
