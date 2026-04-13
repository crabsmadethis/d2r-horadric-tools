"""Build orchestrator: vanilla + overlays + scripts → build/."""

import importlib.util
import os
import glob
import shutil

from d2r_mod.tsv import read_tsv_file, write_tsv_file
from d2r_mod.overlay import load_overlay_file, apply_overlay
from d2r_mod.scripts import run_script
from d2r_mod.version import check_stale


DEFAULT_GAME_DIR = (
    "/run/media/deck/SK256/steamapps/common/Diablo II Resurrected"
)


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

    # Step 6: Write modinfo.json (required for D2R to load mod .txt files)
    import json
    modinfo_path = os.path.join(build_dir, "modinfo.json")
    with open(modinfo_path, "w") as f:
        json.dump({"name": "rebalance", "savepath": "../"}, f, indent=2)
        f.write("\n")

    # Step 7: Regen chargen data
    if regen:
        from d2r_mod.regen import regen_all
        regen_all(build_dir)

    return warnings
