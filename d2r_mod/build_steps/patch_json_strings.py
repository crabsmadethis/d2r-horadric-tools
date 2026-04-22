"""
Build step: patch D2R JSON string files with new entries.

Reads YAML specs from a patches directory, loads vanilla JSON string files,
appends new entries with globally unique IDs, and writes patched files to
the build directory.

YAML spec format (patches/json_strings/*.yaml):

    target: item-names.json
    entries:
      - key: "Manoomin"
        value: "Manoomin"
      - key: "Custom Sword"
        value: "Blade of Thunder"
"""

import glob
import json
import os

import yaml

_STRINGS_SUBDIR = os.path.join("data", "local", "lng", "strings")


def _parse_next_id(vanilla_dir: str) -> int:
    path = os.path.join(vanilla_dir, "data", "local", "lng", "next_string_id.txt")
    if not os.path.exists(path):
        return 28105
    with open(path) as f:
        text = f.read()
    for line in text.splitlines():
        line = line.strip()
        if line.isdigit():
            return int(line)
    return 28105


def run(
    patches_dir: str,
    vanilla_dir: str,
    build_dir: str,
) -> dict[str, int]:
    """Apply JSON string patches from YAML specs.

    Args:
        patches_dir: Directory containing *.yaml patch specs.
        vanilla_dir: Root of extracted vanilla files.
        build_dir:   Root of build output.

    Returns:
        {'added': int, 'skipped': int, 'files': list[str]}
    """
    if not os.path.isdir(patches_dir):
        return {"added": 0, "overridden": 0, "unchanged": 0, "skipped": 0, "files": []}

    yaml_files = sorted(glob.glob(os.path.join(patches_dir, "*.yaml")))
    if not yaml_files:
        return {"added": 0, "overridden": 0, "unchanged": 0, "skipped": 0, "files": []}

    patches_by_target: dict[str, list[dict]] = {}
    for yaml_path in yaml_files:
        if os.path.basename(yaml_path).startswith("_"):
            continue
        with open(yaml_path) as f:
            config = yaml.safe_load(f)
        target = config.get("target", "")
        entries = config.get("entries", [])
        if not target or not entries:
            continue
        patches_by_target.setdefault(target, []).extend(entries)

    if not patches_by_target:
        return {"added": 0, "overridden": 0, "unchanged": 0, "skipped": 0, "files": []}

    next_id = _parse_next_id(vanilla_dir)
    added = 0
    overridden = 0
    unchanged = 0
    files_written = []

    for target_file, patch_entries in sorted(patches_by_target.items()):
        vanilla_path = os.path.join(vanilla_dir, _STRINGS_SUBDIR, target_file)
        if not os.path.exists(vanilla_path):
            continue

        with open(vanilla_path, encoding="utf-8-sig") as f:
            entries = json.load(f)

        entries_by_key = {e["Key"]: e for e in entries}

        for patch in patch_entries:
            key = patch["key"]
            value = patch["value"]
            existing = entries_by_key.get(key)
            if existing is not None:
                if existing.get("enUS") == value:
                    unchanged += 1
                    continue
                existing["enUS"] = value
                overridden += 1
                continue
            new_entry = {
                "id": next_id,
                "Key": key,
                "enUS": value,
            }
            entries.append(new_entry)
            entries_by_key[key] = new_entry
            next_id += 1
            added += 1

        out_dir = os.path.join(build_dir, _STRINGS_SUBDIR)
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, target_file)
        with open(out_path, "w", encoding="utf-8-sig") as f:
            json.dump(entries, f, ensure_ascii=False)
        files_written.append(target_file)

    return {
        "added": added,
        "overridden": overridden,
        "unchanged": unchanged,
        "skipped": unchanged,  # back-compat alias
        "files": files_written,
    }
