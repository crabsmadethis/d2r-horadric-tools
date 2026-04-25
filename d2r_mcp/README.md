# d2r-tools MCP Server

A [Model Context Protocol](https://modelcontextprotocol.io) server exposing the D2R tooling (game data lookups, save inspection, chargen, mod pipeline) as typed tools to any MCP-compatible agent — Claude Code, Codex, Cursor, etc.

## Launch

```bash
python3 -m d2r_mcp
```

Stdio transport only. Requires the `d2r-chargen` package installed (`pip install -e .` from the project root).

## Tool Categories

Tools are prefixed by category. The server registers 23 tools across 4 categories.

### `d2r_lookup_*` — game data (read-only)

Typed queries against the extracted D2R data files. Use these instead of grepping files or guessing UIDs/codes.

- `d2r_lookup_unique(query)` — unique items by name or UID
- `d2r_lookup_set_item(query)` — set items by name or ID
- `d2r_lookup_item_base(query)` — base items by 3-char code or name
- `d2r_lookup_runeword(query)` — runewords by name or ID
- `d2r_lookup_stat(query)` — stat encoding info by ID, name, or YAML alias
- `d2r_lookup_skill(query)` — skills by name or ID
- `d2r_search(query)` — cross-type search (up to 20 results)

### `d2r_save_*` — save file inspection (read-only)

- `d2r_save_scan(path)` — run d2rdoctor scanner, return structured result (checksum, size, item counts, errors, warnings)
- `d2r_save_inspect(path)` — class, level, stats, progression, merc summary
- `d2r_save_list_items(path, location=None)` — enumerate items with their storage location
- `d2r_save_diff(path_a, path_b)` — structural diff between two saves

All accept absolute paths or bare character names (resolved against the Steam saves directory).

### `d2r_chargen_*` — character build pipeline (mutation)

- `d2r_chargen_list()` — list characters defined in `chars/*.yaml`
- `d2r_chargen_validate(name, yaml_only=False)` — YAML schema validation + optional dry-run binary build + scanner check
- `d2r_chargen_build(name, phase=None, force=False)` — build and deploy. Structurally enforces CLAUDE.md rules #3, #4, #10, #17: back up live save, scan the staging build before promoting, never modify the live save on scanner failure.
- `d2r_chargen_import(name, force=False)` — import a server-synced `.d2s` into `chars/<name>.yaml`

### `d2r_mod_*` — mod data pipeline (mutation)

Wrappers for the `d2r-mod` CLI.

- `d2r_mod_build(...)` — build mod from vanilla + overlays + scripts
- `d2r_mod_deploy(...)` — build + deploy (runs CASC injection by default)
- `d2r_mod_undeploy(keep_mod=False, ...)` — remove mod
- `d2r_mod_diff(file=None, summary=False)` — vanilla vs build table diff
- `d2r_mod_extract(...)` — extract vanilla from CASC archive
- `d2r_mod_clean()` — remove `build/` and reset chargen data
- `d2r_mod_recover(...)` — full recovery pipeline (extract → build → deploy)
- `d2r_mod_audit(skills=False, items=False, all=False, ...)` — generate audit reports

## Return Envelope

Every tool returns a dict:

```json
{
  "status": "ok" | "error",
  "error": {"type": "...", "detail": "..."},   // only on error
  ...tool-specific payload...
}
```

## Registering with MCP Clients

### Claude Code (project-scoped)

This repo has a `.mcp.json` at the project root registering the server under the name `d2r-tools`. Open the project in Claude Code; the workspace trust prompt surfaces the server.

### Claude Code (user-scoped)

```bash
claude mcp add d2r-tools --transport stdio --scope user -- python3 -m d2r_mcp
```

Requires the package on your Python path (`pip install -e .` from the repo root).

### Other clients (Codex, Cursor)

Add to the client's MCP config:

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

## Safety Notes

Mutation tools (`d2r_chargen_build`, `d2r_mod_deploy`) enforce the CLAUDE.md rules structurally. In particular:

- `d2r_chargen_build` writes to a staging file, runs the scanner on the staging, and only promotes to the live save if the scanner passes. The live save's mtime is never modified on scanner failure.
- A single `{live}.pre_chargen_bak` backup is taken before any staging write — restore via `cp {live}.pre_chargen_bak {live}`.

## Development

Test suite lives in `tests/test_mcp_*.py`:

```bash
python3 -m pytest tests/test_mcp_envelope.py tests/test_mcp_lookups.py \
                  tests/test_mcp_save.py tests/test_mcp_chargen.py \
                  tests/test_mcp_mod.py tests/test_mcp_server_integration.py \
                  tests/test_chargen_safety.py -v
```

The integration test (`test_mcp_server_integration.py`) spawns the real server over stdio and verifies tool registration + invocation end-to-end.
