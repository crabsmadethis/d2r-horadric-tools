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
async def d2r_lookup_unique(query: str | int) -> str:
    """Look up a D2R unique item by name or numeric UID. Read-only, instant.

    Returns formatted JSON with uid, name, code, qlvl, base_name, stats.
    Substring matching on names (e.g. "harlequin" finds Harlequin Crest).
    Returns "not found" string on miss. Returns "data not extracted" if
    d2r_chargen/data/*.py is empty (run `python3 -m d2r_mod extract` to
    populate, then restart the MCP server). Use this when resolving a
    unique item reference in a YAML build or verifying a UID before encoding.
    """
    return lookup_unique(query)


@mcp.tool()
async def d2r_lookup_set_item(query: str | int) -> str:
    """Look up a D2R set item by name or numeric ID. Read-only, instant.

    Returns formatted JSON with set_id, name, code, set_name, qlvl,
    base_name. Substring matching on names. Returns "not found" string on
    miss. Returns "data not extracted" if game data files are absent.
    Use this when resolving a set item reference in a YAML build or
    confirming set membership before encoding.
    """
    return lookup_set_item(query)


@mcp.tool()
async def d2r_lookup_item_base(query: str) -> str:
    """Look up a D2R item base by 3-char code or name. Read-only, instant.

    Returns formatted JSON with code, name, width, height, item_class,
    max_sockets, req_str, req_dex, durability, tier, categories. Accepts
    exact 3-char code (e.g. "hax") or name substring. Returns "not found"
    string on miss. Returns "data not extracted" if game data files are
    absent. Use this when checking socket capacity, inventory dimensions,
    or stat requirements before placing an item in a YAML build.
    """
    return lookup_item_base(query)


@mcp.tool()
async def d2r_lookup_runeword(query: str | int) -> str:
    """Look up a D2R runeword by name or numeric ID. Read-only, instant.

    Returns formatted JSON with rw_id, name, runes, rune_names, sockets,
    bases, clvl, stats. Substring matching on names. Returns "not found"
    string on miss. Returns "data not extracted" if game data files are
    absent. Use this when planning a socketed item in a YAML build or
    verifying rune order and valid base types before encoding.
    """
    return lookup_runeword(query)


@mcp.tool()
async def d2r_lookup_stat(query: str | int) -> str:
    """Look up a D2R stat by ID, canonical name, or YAML alias. Read-only, instant.

    Returns formatted JSON with stat_id, name, save_bits, save_add,
    save_param_bits, signed, value_shift, csv_bits, aliases. Accepts numeric
    ID, canonical name (e.g. "fireresist"), or YAML alias (e.g. "fcr");
    also does substring match on canonical names. Returns "not found" string
    on miss. Returns "data not extracted" if game data files are absent.
    Use this when verifying stat encoding parameters before writing binary
    item data or when resolving an alias to its canonical stat.
    """
    return lookup_stat(query)


@mcp.tool()
async def d2r_lookup_skill(query: str | int) -> str:
    """Look up a D2R skill by name or numeric ID. Read-only, instant.

    Returns formatted JSON with skill_id, name, and char_class (present only
    for class-specific skills). Substring matching on names. Returns "not
    found" string on miss. Returns "data not extracted" if game data files
    are absent. Use this when resolving a skill reference in a YAML build
    or investigating skill encoding.
    """
    return lookup_skill(query)


@mcp.tool()
async def d2r_search(query: str) -> str:
    """Search across D2R uniques, sets, runewords, and bases. Read-only, instant.

    Returns formatted JSON with results (list of {type, id, name, ...}),
    count, and query; capped at 20 matches. Returns "data not extracted" if
    game data files are absent. Use this when you know a name fragment but
    not the item type. Do not use when you need full stat detail for a
    specific item — use the type-specific lookup tools instead.
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
    """Validate a .d2s save with d2rdoctor — read-only, seconds.

    Checks checksum integrity, file size, item counts, and encoding
    correctness. Scanner hard errors are deployment blockers — never deploy
    a save this tool flags as error. Use before any chargen build deploy,
    after editing binary save fields, or when diagnosing a character that
    fails to load.

    Returns {status, character, class_id, level, checksum_ok, size_ok,
    item_count, merc_count, errors: [], warnings: []} on success.
    On failure: status=error with code=not_found (file missing),
    scan_exception (scanner raised), or scanner_failed (hard errors found;
    payload fields still present for inspection).

    Args:
        path: Absolute path, ~-prefixed path, or bare character name
              (resolved against the Steam saves directory).
    """
    return _save_scan(path)


@mcp.tool()
async def d2r_save_inspect(path: str) -> dict:
    """Decode a .d2s save into a human-readable summary — read-only, instant.

    Reads class, level, progression, stats, and merc info from the save
    header and stat section. Descriptive only — not validation-grade. Do
    not use as a deployment gate. Use when you need a quick character
    overview without full structural validation.

    Returns {status, character, class, class_id, level, progression,
    stats: {}, merc: {present, type_id?, xp?}}.
    On failure: status=error with code=not_found (file missing).

    Args:
        path: Absolute path, ~-prefixed path, or bare character name
              (resolved against the Steam saves directory).
    """
    return _save_inspect(path)


@mcp.tool()
async def d2r_save_list_items(path: str, location: str | None = None) -> dict:
    """List decoded items in a .d2s save, optionally filtered by location — read-only, instant.

    Decodes all item buckets from the save. Use when auditing what items a
    character carries, verifying a chargen build placed items correctly, or
    investigating item layout before a deploy.

    Returns {status, items: [{location, type_code, ...decoded_fields}],
    total: int}. Decoded fields include slot, unique/set/runeword/base name,
    quality flags, and properties where available.
    Note: belt items are not decoded by the underlying importer and are
    absent from results regardless of the location filter.
    On failure: status=error with code=not_found (file missing) or
    invalid_argument (unrecognised location string).

    Args:
        path: Absolute path, ~-prefixed path, or bare character name
              (resolved against the Steam saves directory).
        location: One of equipped, inventory, cube, stash, merc_equipped,
                  or None for all. Any other value returns invalid_argument.
    """
    return _save_list_items(path, location=location)


@mcp.tool()
async def d2r_save_diff(path_a: str, path_b: str) -> dict:
    """Structurally diff two .d2s saves and return changes — read-only, instant.

    Compares header fields, stat section, and item lists between two saves.
    Use when verifying what a chargen build changed relative to a backup,
    or auditing before/after a manual binary edit.

    Returns {status, header_changes: [], stat_changes: [], items_added: [],
    items_removed: [], items_moved: []}. Empty lists mean no changes in
    that category.
    On failure: status=error with code=not_found for whichever file is
    missing (path_a or path_b checked independently).

    Args:
        path_a: First save — absolute path, ~-prefixed, or bare character name.
        path_b: Second save — same resolution rules as path_a.
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
    """List character names defined in chars/*.yaml — read-only, instant.

    Returns {characters: [names], chars_dir}. merc_templates.yaml is excluded.
    Use when you need to know which characters exist before validating,
    building, or inspecting one by name.
    """
    return _chargen_list()


@mcp.tool()
async def d2r_chargen_validate(name: str, yaml_only: bool = False) -> dict:
    """Validate a character YAML and optionally dry-run a full binary build — read-only, seconds.

    yaml_only=True: validates YAML schema only (instant). yaml_only=False
    (default): also builds to a temp .d2s and runs the scanner — same
    pipeline as `python3 -m d2r_chargen validate`. No live files are written
    in either mode.

    Returns {character, yaml_valid, binary_valid (bool or None when
    yaml_only=True), item_count, warnings}. On failure: status=error with
    code=not_found (no YAML at chars/<name>.yaml), yaml_validation_failed,
    scanner_failed (includes scanner_errors list), or build_exception.

    Use before deploying to catch schema and encoding errors without touching
    the live save. Do not use as a deployment substitute — scanner hard errors
    from the dry-run must block the actual build too.

    Args:
        yaml_only: True = schema check only (instant). False = schema +
                   binary build + scanner pass (~seconds). Interaction:
                   yaml_only=True makes binary_valid always None.
    """
    return _chargen_validate(name, yaml_only=yaml_only)


@mcp.tool()
async def d2r_chargen_build(
    name: str, phase: int | None = None, force: bool = False
) -> dict:
    """Build and deploy a character to the live saves directory (~seconds, overwrites live save).

    Enforces backup → temp-build → scanner → promote pipeline: backs up the
    live save, builds to a temp .d2s, runs the scanner on the temp, and only
    promotes if the scanner passes. Live save is untouched on any scanner
    failure.

    Returns {character, phase_completed, backup_path, scanner_result,
    rolled_back: False} on success. On failure: status=error with
    code=not_found (no YAML, rolled_back=True), build_exception (exception
    during build, rolled_back=True), or build_failed (deploy_character
    returned False, includes phase_failed and scanner_result).

    Use when chars/<name>.yaml is ready to push to the game. Do not use if
    D2R is running — exit fully first (D2R caches saves at session startup
    and will overwrite the deployed file on exit).

    Args:
        phase: Deploy through phase 1-4. Default (None) = full deploy (all
               4 phases). Use phase=1 for items-only; lower phases are
               build checkpoints.
        force: Skip the freshness gate (discards server-synced progress).
               Use only when intentionally abandoning server state.
    """
    return _chargen_build(name, phase=phase, force=force)


@mcp.tool()
async def d2r_chargen_import(name: str, force: bool = False) -> dict:
    """Import a server-synced .d2s save and write chars/<name>.yaml (~seconds, writes one file).

    Reads <SAVES>/<name>.d2s and generates a YAML character definition at
    chars/<name>.yaml. force=True overwrites an existing YAML without backup
    (destructive — the existing YAML is permanently lost). force=False
    (default) returns would_overwrite if the file already exists.

    Returns {character, yaml_path, items_count} on success. On failure:
    status=error with code=not_found (no live .d2s at <SAVES>/<name>.d2s),
    would_overwrite (YAML exists and force=False), or import_exception.

    Use when creating a new YAML definition from an existing live character
    for the first time. Do not pass force=True if the existing YAML contains
    manual edits you want to preserve — there is no recovery path.

    Args:
        force: Overwrite chars/<name>.yaml without backup if it already
               exists. Destructive — existing YAML content is lost.
    """
    return _chargen_import(name, force=force)


from d2r_mcp.mod import (
    build as _mod_build, deploy as _mod_deploy, undeploy as _mod_undeploy,
    diff as _mod_diff, extract as _mod_extract, clean as _mod_clean,
    recover as _mod_recover, audit as _mod_audit,
)


@mcp.tool()
async def d2r_mod_build(warn_conflicts: bool = False, no_regen: bool = False,
                        game_dir: str | None = None) -> dict:
    """Build mod from vanilla/ + overlays/ + scripts/ into build/ (~20s, idempotent, overwrites prior build).

    Returns {status, warnings, build_dir} on success. Fails with
    code=missing_dir when vanilla/ or overlays/ are absent (run
    d2r_mod_extract first); code=build_exception for any other build error.

    Use when you want to rebuild without deploying — e.g., to inspect build/
    output before committing to a deploy.

    Args:
        warn_conflicts: emit warnings when an overlay file shadows a vanilla
                        file (useful for auditing overlay scope).
        no_regen: skip the chargen-data regen step (faster when scripts/
                  haven't changed since the last regen).
        game_dir: override D2R install path (default: DEFAULT_GAME_DIR).
    """
    return _mod_build(warn_conflicts=warn_conflicts, no_regen=no_regen,
                      game_dir=game_dir)


@mcp.tool()
async def d2r_mod_deploy(force: bool = False, no_casc: bool = False,
                         no_build: bool = False, warn_conflicts: bool = False,
                         no_regen: bool = False,
                         game_dir: str | None = None) -> dict:
    """Deploy mod to D2R's mod folder + CASC overlay (~25s, idempotent, overwrites prior deploy).

    Returns {status, warnings, build_dir, game_dir} on success; {status:
    error, code, message, warnings} on failure. Failure modes:
    code=missing_dir when vanilla/, overlays/, or game_dir is absent;
    code=deploy_exception for any error during deploy_mod / deploy_casc /
    verify_deploy.

    Args:
        force: pass force=True to deploy_mod (bypasses its safety checks).
        no_casc: skip the deploy_casc step — mod folder still updates,
                 CASC overlay does not. Use when you only need txt/tbl data.
        no_build: skip the build step; deploy whatever is currently in
                  build/. Note: makes warn_conflicts and no_regen no-ops
                  since those only feed the build branch. force and no_casc
                  still apply.
        warn_conflicts: emit warnings when an overlay shadows vanilla data
                        (build-only — no-op when no_build=True).
        no_regen: skip the chargen-data regen step inside build (build-only
                  — no-op when no_build=True).
        game_dir: override D2R install path (default: DEFAULT_GAME_DIR).
    """
    return _mod_deploy(force=force, no_casc=no_casc, no_build=no_build,
                       warn_conflicts=warn_conflicts, no_regen=no_regen,
                       game_dir=game_dir)


@mcp.tool()
async def d2r_mod_undeploy(keep_mod: bool = False,
                           game_dir: str | None = None) -> dict:
    """Remove the deployed mod from the D2R game directory (instant, irreversible without re-deploy).

    Removes the symlinked or copied mod folder from game_dir. No backup is
    made by this tool — ensure build/ is intact before running if you need
    to re-deploy later. keep_mod=False (default) removes both the CASC
    overlay and the mod folder; keep_mod=True removes only the CASC overlay
    and leaves the mod folder in place.

    Returns {status, game_dir, keep_mod} on success. Fails with
    code=undeploy_exception on any error during removal.

    Use when uninstalling the mod or resetting to vanilla before a clean
    re-extract + re-deploy.
    """
    return _mod_undeploy(keep_mod=keep_mod, game_dir=game_dir)


@mcp.tool()
async def d2r_mod_diff(file: str | None = None, summary: bool = False) -> dict:
    """Compare vanilla/ vs build/ .txt tables and report row-level changes (read-only, ~1s).

    Returns {status, changed_files: [{file, change_count, summary | detail}],
    total_changed}. Each entry has either summary (one-line per file) or
    detail (full row diff) depending on the summary flag. Fails with
    code=build_required if vanilla/ or build/ do not exist.

    Use when reviewing what the mod changes before deploying, or when
    auditing overlay scope.
    """
    return _mod_diff(file=file, summary=summary)


@mcp.tool()
async def d2r_mod_extract(game_dir: str | None = None) -> dict:
    """Extract vanilla game data from D2R's CASC archive into vanilla/ (seconds-to-minutes, overwrites vanilla/).

    First-time extraction pulls from the CASC archive and is highly variable
    (depends on archive size and I/O speed). Subsequent runs are faster if
    the index is warm. Overwrites all files in vanilla/ and then runs
    regen_all to regenerate chargen data from the fresh vanilla baseline.

    Returns {status, extracted: <file count>, output_dir} on success. Fails
    with code=missing_dir if the D2R game directory is absent;
    code=extract_exception for CASC read errors.

    Use when vanilla/ is empty, stale after a game patch, or corrupted.
    """
    return _mod_extract(game_dir=game_dir)


@mcp.tool()
async def d2r_mod_clean() -> dict:
    """Remove build/ and regenerate chargen data from vanilla/ (instant, destructive to build/).

    Deletes build/ entirely and runs regen_all against vanilla/ — overwriting
    any manually edited generated chargen data. vanilla/ itself is not
    removed. This cannot be undone without a re-deploy.

    Returns {status, actions: [list of actions taken]} — actions describes
    what was removed and what was regenerated. Fails silently if build/ does
    not exist (no action taken).

    Use when you want to force a clean rebuild from vanilla on next
    d2r_mod_build, or to reset generated chargen data to the vanilla baseline.
    Do not use if you have unsaved manual edits in build/ you intend to keep.
    """
    return _mod_clean()


@mcp.tool()
async def d2r_mod_recover(warn_conflicts: bool = False, no_regen: bool = False,
                          game_dir: str | None = None) -> dict:
    """Run extract → build → deploy as one recovery pipeline (~30s warm; longer first-run).

    Idempotent: overwrites vanilla/, build/, and re-deploys to the live game
    mod folder. Use after a corrupted build, a vanilla data refresh, or when
    the live mod is out of sync with sources.

    Returns the deploy step's envelope: {status, warnings, build_dir,
    game_dir}. Fails with code=missing_dir if vanilla/ sources or the game
    directory is absent; code=extract_exception, build_exception, or
    deploy_exception on phase-specific errors.

    Args:
        warn_conflicts: emit warnings when an overlay shadows vanilla data.
        no_regen: skip the data-regen step inside build (faster, but stale
                  if scripts/ changed since last regen).
        game_dir: override D2R install path (default: detected from
                  DEFAULT_GAME_DIR).
    """
    return _mod_recover(warn_conflicts=warn_conflicts, no_regen=no_regen,
                        game_dir=game_dir)


@mcp.tool()
async def d2r_mod_audit(skills: bool = False, items: bool = False,
                        audit_all: bool = False,
                        output_dir: str | None = None) -> dict:
    """Audit vanilla skill and item data for inconsistencies; write markdown reports (~5s).

    Reads from vanilla/data/global/excel/. Writes one markdown report per
    audit type to output_dir (default: docs/audit/). Returns {status,
    reports: {skills?: {report_path, total, flagged}, items?: {...}}}. Fails
    with code=missing_dir if vanilla/ has not been extracted yet.

    Use when investigating unexpected mod build behavior or verifying that
    vanilla data is internally consistent after an extract. Do not run during
    an in-progress build — the extract phase clobbers vanilla/ and a
    concurrent audit will read a partially written state.

    Args:
        skills: run the skills audit.
        items: run the items audit.
        audit_all: run both audits (overrides skills and items individually).
        output_dir: directory for report files (default: docs/audit/).
    """
    return _mod_audit(skills=skills, items=items, audit_all=audit_all,
                      output_dir=output_dir)


def main():
    sys.stderr.write("D2R tools MCP server starting...\n")
    mcp.run(transport="stdio")
