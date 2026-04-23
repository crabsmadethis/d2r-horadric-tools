"""Build orchestrator: vanilla + overlays + scripts → build/."""

import importlib.util
import os
import sys
import glob
import shutil

import yaml

from d2r_mod.tsv import read_tsv_file, write_tsv_file
from d2r_mod.overlay import load_overlay_file, apply_overlay
from d2r_mod.scripts import run_script
from d2r_mod.version import check_stale

# tools/ lives at the project root alongside d2r_mod/ but isn't an
# installed package, so `from tools.* import ...` below only resolves
# when cwd is the project root. Put the project root on sys.path so
# build_mod works regardless of caller cwd (CLI run from elsewhere,
# MCP server, etc).
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)



def _detect_game_dir() -> str | None:
    """Auto-detect D2R installation directory. Override with D2R_GAME_DIR env var."""
    if 'D2R_GAME_DIR' in os.environ:
        p = os.environ['D2R_GAME_DIR']
        return p if os.path.isdir(p) else None

    # Common Steam library locations (Linux)
    suffix = "steamapps/common/Diablo II Resurrected"

    # Check direct Steam library
    direct = os.path.join(os.path.expanduser("~/.local/share/Steam"), suffix)
    if os.path.isdir(direct):
        return direct

    # Check mounted media (SD cards, USB drives)
    media = "/run/media"
    if os.path.isdir(media):
        for user in os.listdir(media):
            user_dir = os.path.join(media, user)
            if not os.path.isdir(user_dir):
                continue
            for vol in os.listdir(user_dir):
                candidate = os.path.join(user_dir, vol, suffix)
                if os.path.isdir(candidate):
                    return candidate

    # Windows
    for drive in ["C", "D", "E", "F"]:
        candidate = os.path.join(f"{drive}:", "Program Files (x86)",
                                 "Steam", "steamapps", "common",
                                 "Diablo II Resurrected")
        if os.path.isdir(candidate):
            return candidate

    return None


DEFAULT_GAME_DIR = _detect_game_dir()

def _find_txt_files(vanilla_dir: str) -> dict[str, str]:
    result = {}
    for root, _, files in os.walk(vanilla_dir):
        for f in files:
            if f.endswith(".txt"):
                abs_path = os.path.join(root, f)
                rel_path = os.path.relpath(abs_path, vanilla_dir)
                result[rel_path] = abs_path
    return result


def _find_all_files(vanilla_dir: str) -> dict[str, str]:
    result = {}
    for root, _, files in os.walk(vanilla_dir):
        for f in files:
            if f.startswith("."):
                continue
            abs_path = os.path.join(root, f)
            rel_path = os.path.relpath(abs_path, vanilla_dir)
            result[rel_path] = abs_path
    return result


def build_mod(
    vanilla_dir: str,
    overlays_dir: str,
    scripts_dir: str,
    build_dir: str,
    regen: bool = True,
    game_dir: str = DEFAULT_GAME_DIR,
    warn_conflicts: bool = False,
) -> list[str]:
    """Run the full build pipeline. Returns list of warning strings."""
    warnings = []

    if not os.path.isdir(vanilla_dir):
        raise FileNotFoundError(f"vanilla/ not found at {vanilla_dir}")
    txt_files = _find_txt_files(vanilla_dir)
    if not txt_files:
        raise FileNotFoundError(f"No .txt files in {vanilla_dir}")

    if not os.path.isdir(overlays_dir):
        warnings.append(f"Overlays directory not found: {overlays_dir}")
    if not os.path.isdir(scripts_dir):
        warnings.append(f"Scripts directory not found: {scripts_dir}")

    stale_warning = check_stale(vanilla_dir, game_dir)
    if stale_warning:
        warnings.append(stale_warning)
        print(f"WARNING: {stale_warning}")

    # Step 1: Load all .txt files
    tables: dict[str, list[dict]] = {}
    headers: dict[str, list[str]] = {}
    for rel_path, abs_path in txt_files.items():
        rows = read_tsv_file(abs_path)
        tables[rel_path] = rows
        if rows:
            headers[rel_path] = list(rows[0].keys())

    # Step 2: Apply overlays
    overlay_paths = sorted(glob.glob(os.path.join(overlays_dir, "*.yaml")))
    touched_cells: dict[tuple, str] = {}

    for ov_path in overlay_paths:
        overlay = load_overlay_file(ov_path)
        target = overlay["target"]
        if target not in tables:
            raise FileNotFoundError(
                f"Overlay {os.path.basename(ov_path)} targets {target} "
                f"which does not exist in vanilla/"
            )

        if warn_conflicts:
            for change in overlay.get("changes", []):
                selector_key = tuple(sorted(change["row"].items()))
                for op in ("set", "multiply", "add"):
                    if op in change:
                        for col in change[op]:
                            cell_key = (target, selector_key, col)
                            if cell_key in touched_cells:
                                prev = touched_cells[cell_key]
                                warnings.append(
                                    f"Conflict: {target} [{dict(selector_key)}] "
                                    f"column '{col}' touched by both "
                                    f"{prev} and {os.path.basename(ov_path)}"
                                )
                            touched_cells[cell_key] = os.path.basename(ov_path)

        ov_warnings = apply_overlay(tables[target], overlay)
        warnings.extend(ov_warnings)

    # Step 3: Run scripts
    # Scripts named new_*.py are allowed to append rows (allow_add=True).
    # Scripts matching *-ui-json.py are JSON patch scripts (run in Step 5b).
    script_paths = sorted(glob.glob(os.path.join(scripts_dir, "*.py")))
    for script_path in script_paths:
        basename = os.path.basename(script_path)
        if basename.endswith("-ui-json.py"):
            continue  # handled in Step 5b
        allow_add = basename.startswith("new_")
        script_warnings = run_script(script_path, tables, allow_add=allow_add)
        warnings.extend(script_warnings)

    # Step 4: Write modified .txt to build/
    if os.path.exists(build_dir):
        shutil.rmtree(build_dir)

    for rel_path, rows in tables.items():
        out_path = os.path.join(build_dir, rel_path)
        write_tsv_file(out_path, rows, headers.get(rel_path))

    # Step 5: Copy non-.txt files through
    all_files = _find_all_files(vanilla_dir)
    for rel_path, abs_path in all_files.items():
        if rel_path in tables:
            continue
        out_path = os.path.join(build_dir, rel_path)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        shutil.copy2(abs_path, out_path)

    # Step 5b: Run JSON patch scripts against build/
    json_scripts = sorted(glob.glob(os.path.join(scripts_dir, "*-ui-json.py")))
    for script_path in json_scripts:
        spec = importlib.util.spec_from_file_location("json_patch", script_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if hasattr(mod, "apply"):
            result = mod.apply(build_dir)
            if result:
                warnings.extend(result)

    # Step 5c: Patch .tbl string tables
    from d2r_mod.assets.tbl import patch_tbl
    patches_strings_dir = os.path.join(
        os.path.dirname(overlays_dir), "patches", "strings"
    )
    if os.path.isdir(patches_strings_dir):
        string_yamls = sorted(glob.glob(
            os.path.join(patches_strings_dir, "*.yaml")
        ))
        for yaml_path in string_yamls:
            basename = os.path.basename(yaml_path)
            if basename.startswith("_"):
                continue  # skip smoke tests / templates
            with open(yaml_path) as f:
                config = yaml.safe_load(f)
            target = config.get("target", "")
            entries_list = config.get("entries", [])
            if not target or not entries_list:
                continue
            overrides = {e["key"]: e["value"] for e in entries_list}
            # Find all matching .tbl files in build output (one per language)
            tbl_paths = []
            for root, _, files in os.walk(build_dir):
                for fn in files:
                    if fn == target:
                        tbl_paths.append(os.path.join(root, fn))
            if not tbl_paths:
                warnings.append(f"StringPatch: target not found: {target}")
                continue
            for tbl_path in tbl_paths:
                patch_tbl(tbl_path, overrides, tbl_path)
            warnings.append(
                f"StringPatch: patched {len(overrides)} strings in {target} "
                f"({len(tbl_paths)} files) ({basename})"
            )

    # Step 5d: Auto-register custom unique display names in expansionstring.tbl
    # Any UniqueItems.txt index that is absent from the vanilla key corpus is
    # added as a name→name entry so D2R can resolve the display string.
    # Names already served by JSON (vanilla item-names.json or any
    # patches/json_strings/ patch) are skipped — D2R reads item names from JSON
    # not TBL, so a TBL write for a JSON-served key is dead weight
    # (feedback_strings_json_vs_tbl.md).
    from d2r_mod.build_steps.register_custom_uniques import (
        run as _register_custom_uniques,
        load_vanilla_keys as _load_vanilla_keys,
        DEFAULT_TARGET_TBL as _CUSTOM_UNIQUES_TBL,
    )
    _unique_items_build_path = os.path.join(
        build_dir, "data", "global", "excel", "UniqueItems.txt"
    )
    if os.path.exists(_unique_items_build_path):
        _vanilla_keys = _load_vanilla_keys()
        from tools.audit_string_registry import (
            _load_vanilla_index as _load_json_vanilla_index,
            _load_patch_keys as _load_json_patch_keys,
        )
        _json_vanilla_keys = set(
            _load_json_vanilla_index(
                os.path.join(vanilla_dir, "data", "local", "lng", "strings")
            )
        )
        _json_patch_keys = _load_json_patch_keys(
            os.path.join(os.path.dirname(overlays_dir), "patches", "json_strings")
        )
        _json_served = _json_vanilla_keys | _json_patch_keys
        # Register into eng only (English); multi-lang extension is a future concern.
        _target_tbl_path = os.path.join(
            build_dir, "data", "local", "lng", "eng",
            f"{_CUSTOM_UNIQUES_TBL}.tbl"
        )
        _reg_result = _register_custom_uniques(
            _unique_items_build_path, _target_tbl_path, _vanilla_keys,
            json_served_names=_json_served,
        )
        _msg = (
            f"CustomUniques: registered {_reg_result['added']} new name(s) in "
            f"eng/{_CUSTOM_UNIQUES_TBL}.tbl "
            f"(skipped {_reg_result['skipped']} vanilla/existing"
        )
        if _reg_result.get("skipped_json"):
            _msg += f", skipped {_reg_result['skipped_json']} json-served"
        _msg += ")"
        warnings.append(_msg)
    else:
        warnings.append("CustomUniques: UniqueItems.txt not found in build — skipping")

    # Step 5e: Build string registry (custom strings for runtime injection)
    # Diffs built .tbl files against vanilla to produce a flat key→value
    # registry consumed by the runtime string injector.
    from d2r_mod.build_steps.build_string_registry import run as _build_string_registry
    _str_registry = _build_string_registry(
        build_dir=build_dir,
        vanilla_dir=vanilla_dir,
        write=True,
    )
    _total_custom = sum(len(v) for v in _str_registry.values())
    if _total_custom:
        warnings.append(
            f"StringRegistry: {_total_custom} custom string(s) across "
            f"{len(_str_registry)} table(s) → string_registry.json"
        )
    else:
        warnings.append("StringRegistry: no custom strings detected")

    # Step 5f: Patch JSON string files (new keys for D2R's JSON string system)
    _json_patches_dir = os.path.join(
        os.path.dirname(overlays_dir), "patches", "json_strings"
    )
    if os.path.isdir(_json_patches_dir):
        from d2r_mod.build_steps.patch_json_strings import run as _patch_json_strings
        _json_result = _patch_json_strings(
            patches_dir=_json_patches_dir,
            vanilla_dir=vanilla_dir,
            build_dir=build_dir,
        )
        if _json_result["added"]:
            warnings.append(
                f"JsonStrings: added {_json_result['added']} new key(s) to "
                f"{', '.join(_json_result['files'])}"
            )
        if _json_result.get("overridden"):
            warnings.append(
                f"JsonStrings: overrode {_json_result['overridden']} existing key(s)"
            )
    else:
        warnings.append("JsonStrings: no patches/json_strings/ directory — skipping")

    # Step 6: Write modinfo.json (required for D2R to load mod .txt files)
    import json
    modinfo_path = os.path.join(build_dir, "modinfo.json")
    with open(modinfo_path, "w") as f:
        json.dump({"name": "rebalance", "savepath": "../"}, f, indent=2)
        f.write("\n")

    # Step 6b: Write dataversionbuild.txt (prevents "Data version mismatch" warning)
    # Read build number from .build.info, or copy from vanilla/ if already extracted
    dvb_vanilla = os.path.join(vanilla_dir, "data", "global", "dataversionbuild.txt")
    dvb_out = os.path.join(build_dir, "data", "global", "dataversionbuild.txt")
    if os.path.exists(dvb_vanilla):
        os.makedirs(os.path.dirname(dvb_out), exist_ok=True)
        shutil.copy2(dvb_vanilla, dvb_out)
    else:
        # Generate from .build.info
        from d2r_mod.casc import _parse_build_info
        build_info_path = os.path.join(game_dir, ".build.info")
        if os.path.exists(build_info_path):
            with open(build_info_path, "r") as f:
                lines = f.read().strip().split("\n")
            headers = [h.split("!")[0] for h in lines[0].split("|")]
            values = lines[1].split("|")
            for h, v in zip(headers, values):
                if h == "Version":
                    # Version is like "3.1.92198" — take the last component
                    build_num = v.strip().rsplit(".", 1)[-1]
                    os.makedirs(os.path.dirname(dvb_out), exist_ok=True)
                    with open(dvb_out, "w") as f:
                        f.write(build_num)
                    break

    # Step 7: Regen chargen data
    if regen:
        from d2r_mod.regen import regen_all
        regen_all(build_dir)

    return warnings
