"""
Build step: produce string_registry.json listing all custom (non-vanilla) strings.

Compares built .tbl files against vanilla .tbl files and emits a JSON registry
of custom key-value pairs grouped by table name.  The runtime string injector
reads this registry to know which strings to inject into D2R's memory.

Usage (called by build.py Step 5e):

    from d2r_mod.build_steps.build_string_registry import run
    registry = run(build_dir, vanilla_dir, write=True)
"""

import json
import os

from d2r_mod.assets.tbl import parse_tbl

_TBL_SUBDIR = os.path.join("data", "local", "lng", "eng")


def run(
    build_dir: str,
    vanilla_dir: str,
    write: bool = False,
) -> dict[str, dict[str, str]]:
    """Diff built .tbl files against vanilla and return custom strings.

    Returns:
        {table_name: {key: value, ...}, ...}
        Only tables with at least one custom entry are included.
    """
    build_tbl_dir = os.path.join(build_dir, _TBL_SUBDIR)
    vanilla_tbl_dir = os.path.join(vanilla_dir, _TBL_SUBDIR)

    registry: dict[str, dict[str, str]] = {}

    if not os.path.isdir(build_tbl_dir):
        return registry

    for filename in sorted(os.listdir(build_tbl_dir)):
        if not filename.endswith(".tbl"):
            continue

        table_name = filename[:-4]  # strip .tbl

        build_path = os.path.join(build_tbl_dir, filename)
        vanilla_path = os.path.join(vanilla_tbl_dir, filename)

        with open(build_path, "rb") as f:
            built_entries = parse_tbl(f.read())

        if os.path.exists(vanilla_path):
            with open(vanilla_path, "rb") as f:
                vanilla_entries = parse_tbl(f.read())
        else:
            vanilla_entries = {}

        custom: dict[str, str] = {}
        for key, value in built_entries.items():
            if key not in vanilla_entries or vanilla_entries[key] != value:
                custom[key] = value

        if custom:
            registry[table_name] = custom

    if write:
        out_path = os.path.join(build_dir, "string_registry.json")
        with open(out_path, "w") as f:
            json.dump(registry, f, indent=2, ensure_ascii=False)
            f.write("\n")

    return registry
