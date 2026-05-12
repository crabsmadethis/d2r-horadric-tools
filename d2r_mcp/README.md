# Horadric Tools MCP Server

`d2r_mcp` exposes the public Horadric Tools surface to MCP clients over stdio:
game-data lookup, save-file inspection, character YAML workflows, and the data
mod pipeline.

The server is intentionally local. It reads generated D2R data modules from this
checkout, resolves saves through the same config as `d2r-chargen`, and delegates
mutating work to the existing CLI/library paths instead of implementing a
separate write path.

## Launch

Install Horadric Tools from the repository root:

```bash
pip install -e .
```

Install the MCP Python SDK before starting the server:

```bash
pip install mcp
```

Run the stdio server:

```bash
python3 -m d2r_mcp
```

`d2r_mcp.server.main()` currently calls `mcp.run(transport="stdio")`; no other
transport is configured in this package.

## Client Config

For a user-scoped Claude Code install:

```bash
claude mcp add d2r-tools --transport stdio --scope user -- python3 -m d2r_mcp
```

For clients that accept JSON MCP server definitions:

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

If you keep MCP configuration in a project-scoped file, use the same command,
arguments, and environment shape shown above. This repository does not require
a committed project-local MCP config file.

## Tool Catalog

`d2r_mcp/server.py` registers 23 tools in 4 categories.

### `d2r_lookup_*` - Game Data, Read-Only

Lookup tools query generated data modules under `d2r_chargen/data/`. Use them
instead of guessing item UIDs, runeword IDs, item codes, stat encodings, or skill
IDs.

- `d2r_lookup_unique(query)` - unique items by name substring or numeric UID
- `d2r_lookup_set_item(query)` - set items by name substring or numeric ID
- `d2r_lookup_item_base(query)` - base items by 3-character code or name
- `d2r_lookup_runeword(query)` - runewords by name substring or numeric ID
- `d2r_lookup_stat(query)` - stat encoding by ID, canonical name, or YAML alias
- `d2r_lookup_skill(query)` - skills by name substring or numeric ID
- `d2r_search(query)` - cross-type search across uniques, sets, runewords, and bases

These tools are read-only. They return formatted lookup text from
`d2r_mcp/lookups.py`.

### `d2r_save_*` - Save Inspection, Read-Only

Save tools accept an absolute path, a `~`-expanded path, or a bare character name
resolved against `d2r_chargen.config.SAVES`.

- `d2r_save_scan(path)` - run the scanner and return checksum, file-size,
  item-count, merc-count, error, and warning fields
- `d2r_save_inspect(path)` - summarize class, level, progression, stats, and
  minimal merc presence without running the scanner
- `d2r_save_list_items(path, location=None)` - list decoded items, optionally
  filtered to `equipped`, `inventory`, `cube`, `stash`, or `merc_equipped`
- `d2r_save_diff(path_a, path_b)` - compare two saves and return structural
  header, stat, item-added, item-removed, and item-moved changes

These tools are read-only. `d2r_save_scan` is the validation gate for `.d2s`
work; scanner hard errors are deployment blockers unless disproven with
bit-level evidence.

### `d2r_chargen_*` - Character YAML Workflow

Chargen tools work from named YAML files in `chars/`. They do not accept inline
YAML payloads.

- `d2r_chargen_list()` - list character YAMLs, excluding `merc_templates.yaml`
- `d2r_chargen_validate(name, yaml_only=False)` - validate YAML and, unless
  `yaml_only` is true, run a dry-run binary build plus scanner pass
- `d2r_chargen_build(name, phase=None, force=False)` - build from
  `chars/<name>.yaml` and deploy through the requested phase
- `d2r_chargen_import(name, force=False)` - import the configured live
  `<name>.d2s` save into `chars/<name>.yaml`

`d2r_chargen_list`, `d2r_chargen_validate`, and `d2r_chargen_import` mutate only
the repository workflow files they explicitly report. `d2r_chargen_build` is the
live-save mutation tool: it delegates to `deploy_character`, backs up the live
save, builds through staging, scans before promotion, and reports rollback state
through the response envelope.

### `d2r_mod_*` - Data Mod Pipeline

Mod tools wrap the `d2r-mod` pipeline.

- `d2r_mod_build(warn_conflicts=False, no_regen=False, game_dir=None)` - build
  `build/` from vanilla data, overlays, scripts, and generated tables
- `d2r_mod_deploy(force=False, no_casc=False, no_build=False,
  warn_conflicts=False, no_regen=False, game_dir=None)` - build and deploy the
  mod, running CASC injection unless disabled
- `d2r_mod_undeploy(keep_mod=False, game_dir=None)` - remove the deployed mod
- `d2r_mod_diff(file=None, summary=False)` - compare `vanilla/` and `build/`
  tables
- `d2r_mod_extract(game_dir=None)` - extract vanilla data from the CASC archive
  into `vanilla/`
- `d2r_mod_clean()` - remove `build/` and reset generated chargen data
- `d2r_mod_update(warn_conflicts=False, no_regen=False, game_dir=None)` - run
  the extract, build, and deploy recovery pipeline
- `d2r_mod_audit(skills=False, items=False, audit_all=False, output_dir=None)` -
  generate skills and/or items audit reports

These tools can write local build output, extracted/generated data, deployed mod
files, or audit reports depending on the command. Treat `d2r_mod_deploy` and
`d2r_mod_update` as game-install mutations.

## Return Shapes

Lookup tools return formatted text. Save, chargen, and mod tools return a
structured envelope dict:

```json
{
  "status": "ok",
  "...": "tool-specific payload"
}
```

On failure, the same structured tools return:

```json
{
  "status": "error",
  "error": {
    "type": "machine_readable_error_type",
    "detail": "human-readable detail"
  },
  "...": "optional context"
}
```

`d2r_mcp/envelope.py` defines the shared `ok()` and `error()` helpers, and
`tests/test_mcp_envelope.py` covers the envelope shape. The stdio integration
test parses dict returns from MCP content before asserting on `status`.

## Safety Boundaries

- Lookup and save-inspection tools are read-only.
- `d2r_save_inspect`, `d2r_save_list_items`, and `d2r_save_diff` are inspection
  tools, not deployment approval. Use `d2r_save_scan` for validation.
- `d2r_chargen_build` must leave the live save untouched when backup or scanner
  validation fails. Tests in `tests/test_chargen_safety.py` cover the live-save
  invariant.
- `d2r_chargen_build` uses a single `{live}.pre_chargen_bak` backup path when
  the underlying deploy path creates it.
- Mod pipeline tools may modify local build directories, generated data,
  deployed mod files, and audit output. Keep extracted game data and local
  machine paths out of public commits.
- Do not use MCP tools to bypass the normal save workflow: backup, stage, scan,
  then promote only after validation passes.

## Development Checks

Focused MCP tests:

```bash
python3 -m pytest tests/test_mcp_envelope.py tests/test_mcp_lookups.py \
  tests/test_mcp_save.py tests/test_mcp_chargen.py tests/test_mcp_mod.py \
  tests/test_mcp_server_integration.py tests/test_chargen_safety.py -v
```

`tests/test_mcp_server_integration.py` starts the real stdio server, lists
registered tools, and calls `d2r_save_scan` through an MCP client session.

When adding or changing an MCP tool:

- update this README's count, category, signature, and safety notes
- update the root README if its MCP count or setup text becomes stale
- add or update `tests/test_mcp_*.py`
- keep mutation tools on the same backup, scan, and promote path as the CLI
