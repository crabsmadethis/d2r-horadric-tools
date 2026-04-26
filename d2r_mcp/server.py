"""FastMCP server exposing D2R game data lookup tools.

Usage:
    python3 -m d2r_mcp          # stdio transport (for Claude Code)
"""
import sys

from mcp.server.fastmcp import FastMCP

from d2r_mcp.lookups import (
    lookup_unique, lookup_set_item, lookup_item_base,
    lookup_runeword, lookup_stat, lookup_skill, search_all,
)

mcp = FastMCP("d2r-tools")


@mcp.tool()
async def d2r_lookup_unique(query: str) -> str:
    """Look up a D2R unique item by name or numeric UID.

    Searches unique_items.py data. Returns item info + stats.
    Supports substring matching (e.g. "harlequin" finds Harlequin Crest).

    Args:
        query: Item name (or substring) or numeric UID
    """
    return lookup_unique(query)


@mcp.tool()
async def d2r_lookup_set_item(query: str) -> str:
    """Look up a D2R set item by name or numeric ID.

    Searches set_items.py data. Returns item info + set membership.
    Supports substring matching.

    Args:
        query: Item name (or substring) or numeric set item ID
    """
    return lookup_set_item(query)


@mcp.tool()
async def d2r_lookup_item_base(query: str) -> str:
    """Look up a D2R base item by 3-char code or name.

    Searches item_bases.py data. Returns dimensions, requirements, sockets.
    Supports substring matching on names.

    Args:
        query: 3-character item code (e.g. "hax") or item name
    """
    return lookup_item_base(query)


@mcp.tool()
async def d2r_lookup_runeword(query: str) -> str:
    """Look up a D2R runeword by name or numeric ID.

    Searches runewords.py data. Returns runes, valid bases, stats.
    Supports substring matching.

    Args:
        query: Runeword name (or substring) or numeric runeword ID
    """
    return lookup_runeword(query)


@mcp.tool()
async def d2r_lookup_stat(query: str) -> str:
    """Look up a D2R stat by ID, canonical name, or YAML alias.

    Searches item_stat_cost.py data. Returns encoding info (save bits,
    save add, param bits, value shift) needed for binary stat encoding.

    Args:
        query: Stat ID, canonical name (e.g. "fireresist"), or alias (e.g. "fcr")
    """
    return lookup_stat(query)


@mcp.tool()
async def d2r_lookup_skill(query: str) -> str:
    """Look up a D2R skill by name or numeric ID.

    Searches skills.py data. Returns skill ID and class.
    Supports substring matching.

    Args:
        query: Skill name (or substring) or numeric skill ID
    """
    return lookup_skill(query)


@mcp.tool()
async def d2r_search(query: str) -> str:
    """Search across ALL D2R item types: uniques, sets, runewords, bases.

    Use this when you don't know what type of item you're looking for.
    Returns up to 20 results tagged by type.

    Args:
        query: Search term (substring match across all item names)
    """
    return search_all(query)


from d2r_mcp.save import (
    scan as _save_scan,
    inspect as _save_inspect,
    list_items as _save_list_items,
    diff as _save_diff,
)


@mcp.tool()
async def d2r_save_scan(path: str) -> dict:
    """Run d2rdoctor scanner on a .d2s save file.

    Returns a structured result with checksum/size status, item counts,
    and any scanner errors or warnings. status == "error" iff errors is
    non-empty. Deployment-blocker rule: never deploy a save that this tool
    flags as error (see CLAUDE.md Rule #17).

    Args:
        path: Absolute path to .d2s file, or bare character name
              (resolved against Steam saves dir).
    """
    return _save_scan(path)


@mcp.tool()
async def d2r_save_inspect(path: str) -> dict:
    """Summarize a .d2s save: class, level, stats, progression, merc.

    No scanner pass — use d2r_save_scan for validation.

    Args:
        path: Absolute path to .d2s file, or bare character name.
    """
    return _save_inspect(path)


@mcp.tool()
async def d2r_save_list_items(path: str, location: str | None = None) -> dict:
    """List items on disk in a .d2s save, optionally filtered by location.

    Args:
        path: Absolute path to .d2s file, or bare character name.
        location: Filter: equipped, inventory, cube, stash,
                  merc_equipped, or None for all.
    """
    return _save_list_items(path, location=location)


@mcp.tool()
async def d2r_save_diff(path_a: str, path_b: str) -> dict:
    """Compare two .d2s files and return structural differences.

    Args:
        path_a: First save (treated as "before").
        path_b: Second save (treated as "after").
    """
    return _save_diff(path_a, path_b)


from d2r_mcp.chargen import (
    list_chars as _chargen_list,
    validate as _chargen_validate,
    build as _chargen_build,
    import_save as _chargen_import,
)


@mcp.tool()
async def d2r_chargen_list() -> dict:
    """List character names defined in chars/*.yaml."""
    return _chargen_list()


@mcp.tool()
async def d2r_chargen_validate(name: str, yaml_only: bool = False) -> dict:
    """Validate a character YAML and optionally run a dry-run binary build.

    Args:
        name: Character name (resolves to chars/<name>.yaml).
        yaml_only: Skip the dry-run binary build + scanner pass.
    """
    return _chargen_validate(name, yaml_only=yaml_only)


@mcp.tool()
async def d2r_chargen_build(
    name: str, phase: int | None = None, force: bool = False
) -> dict:
    """Build and deploy a character to the live saves directory.

    Structurally enforces CLAUDE.md rules #3, #4, #10, #17: backs up the
    live save, builds to a temp file, runs the scanner on the temp, and
    only promotes the temp to the live save if the scanner passes. Live
    save is untouched on scanner failure.

    Args:
        name: Character name (chars/<name>.yaml must exist).
        phase: Deploy through phase (1-4). Default: full deploy (4).
        force: Skip the freshness gate (discards server progress). Avoid
               unless intentional.
    """
    return _chargen_build(name, phase=phase, force=force)


@mcp.tool()
async def d2r_chargen_import(name: str, force: bool = False) -> dict:
    """Import a server-synced .d2s save into chars/<name>.yaml.

    Args:
        name: Character name (reads live save at <SAVES>/<name>.d2s).
        force: Overwrite an existing chars/<name>.yaml.
    """
    return _chargen_import(name, force=force)


from d2r_mcp.mod import (
    build as _mod_build, deploy as _mod_deploy, undeploy as _mod_undeploy,
    diff as _mod_diff, extract as _mod_extract, clean as _mod_clean,
    update as _mod_update, audit as _mod_audit,
)


@mcp.tool()
async def d2r_mod_build(warn_conflicts: bool = False, no_regen: bool = False,
                        game_dir: str | None = None) -> dict:
    """Build mod from vanilla + overlays + scripts into build/."""
    return _mod_build(warn_conflicts=warn_conflicts, no_regen=no_regen,
                      game_dir=game_dir)


@mcp.tool()
async def d2r_mod_deploy(force: bool = False, no_casc: bool = False,
                         no_build: bool = False, warn_conflicts: bool = False,
                         no_regen: bool = False,
                         game_dir: str | None = None) -> dict:
    """Build + deploy mod to the game mod folder (runs CASC injection by default)."""
    return _mod_deploy(force=force, no_casc=no_casc, no_build=no_build,
                       warn_conflicts=warn_conflicts, no_regen=no_regen,
                       game_dir=game_dir)


@mcp.tool()
async def d2r_mod_undeploy(keep_mod: bool = False,
                           game_dir: str | None = None) -> dict:
    """Remove mod from the game."""
    return _mod_undeploy(keep_mod=keep_mod, game_dir=game_dir)


@mcp.tool()
async def d2r_mod_diff(file: str | None = None, summary: bool = False) -> dict:
    """Compare vanilla/ vs build/ tables. Returns list of changed files."""
    return _mod_diff(file=file, summary=summary)


@mcp.tool()
async def d2r_mod_extract(game_dir: str | None = None) -> dict:
    """Extract vanilla data from CASC archive into vanilla/."""
    return _mod_extract(game_dir=game_dir)


@mcp.tool()
async def d2r_mod_clean() -> dict:
    """Remove build/ and reset chargen data."""
    return _mod_clean()


@mcp.tool()
async def d2r_mod_update(warn_conflicts: bool = False, no_regen: bool = False,
                         game_dir: str | None = None) -> dict:
    """Full recovery pipeline: extract → build → deploy."""
    return _mod_update(warn_conflicts=warn_conflicts, no_regen=no_regen,
                       game_dir=game_dir)


@mcp.tool()
async def d2r_mod_audit(skills: bool = False, items: bool = False,
                        audit_all: bool = False,
                        output_dir: str | None = None) -> dict:
    """Audit vanilla skills and items; write markdown reports.

    Args:
        skills: Run skills audit.
        items: Run items audit.
        audit_all: Run both audits (overrides skills/items).
        output_dir: Directory to write reports into. Default: docs/audit.
    """
    return _mod_audit(skills=skills, items=items, audit_all=audit_all,
                      output_dir=output_dir)


def main():
    sys.stderr.write("D2R tools MCP server starting...\n")
    mcp.run(transport="stdio")
