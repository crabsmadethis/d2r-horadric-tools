"""Audit build/string_registry.json against vanilla JSON + patches/json_strings/.

Categorizes each entry:
  vanilla_identity  — vanilla JSON has Key=X with enUS matching registry value
  needs_override    — vanilla JSON has Key=X but different enUS
  patch_covered     — vanilla JSON lacks Key=X, but patches/json_strings/ adds it
  orphan            — neither vanilla nor patches serve this key via JSON

Usage:
  python3 -m tools.audit_string_registry               # human report
  python3 -m tools.audit_string_registry --json        # machine output
"""
import argparse
import glob
import json
import os
import sys

import yaml


def _load_vanilla_index(vanilla_strings_dir: str) -> dict[str, tuple[str, str]]:
    """Return {Key: (filename, enUS)} across all vanilla JSON string files."""
    index: dict[str, tuple[str, str]] = {}
    for path in sorted(glob.glob(os.path.join(vanilla_strings_dir, "*.json"))):
        fname = os.path.basename(path)
        with open(path, encoding="utf-8-sig") as f:
            try:
                entries = json.load(f)
            except json.JSONDecodeError:
                continue
        for entry in entries:
            key = entry.get("Key")
            enus = entry.get("enUS")
            if key is None or enus is None:
                continue
            if key not in index:
                index[key] = (fname, enus)
    return index


def _load_patch_keys(patches_dir: str) -> set[str]:
    """Return the set of keys declared in patches/json_strings/*.yaml."""
    keys: set[str] = set()
    if not os.path.isdir(patches_dir):
        return keys
    for path in sorted(glob.glob(os.path.join(patches_dir, "*.yaml"))):
        if os.path.basename(path).startswith("_"):
            continue
        with open(path) as f:
            config = yaml.safe_load(f) or {}
        for entry in config.get("entries", []):
            k = entry.get("key")
            if k:
                keys.add(k)
    return keys


def categorize_entry(
    key: str,
    value: str,
    vanilla_index: dict[str, tuple[str, str]],
    patch_keys: set[str],
) -> dict:
    """Classify a single registry entry."""
    if key in vanilla_index:
        fname, enus = vanilla_index[key]
        if enus == value:
            return {"category": "vanilla_identity", "json_file": fname}
        return {"category": "needs_override", "json_file": fname,
                "vanilla_value": enus, "mod_value": value}
    if key in patch_keys:
        return {"category": "patch_covered"}
    return {"category": "orphan"}


def build_report(
    registry_path: str,
    vanilla_strings_dir: str,
    patches_dir: str,
) -> dict:
    """Return a structured report: {tables: {name: {category: [entries]}}}."""
    with open(registry_path) as f:
        registry = json.load(f)
    vanilla_index = _load_vanilla_index(vanilla_strings_dir)
    patch_keys = _load_patch_keys(patches_dir)

    tables: dict[str, dict[str, list]] = {}
    for table, entries in registry.items():
        tables[table] = {"vanilla_identity": [], "needs_override": [],
                         "patch_covered": [], "orphan": []}
        for key, value in entries.items():
            cat = categorize_entry(key, value, vanilla_index, patch_keys)
            tables[table][cat["category"]].append({"key": key, "value": value,
                                                    **{k: v for k, v in cat.items()
                                                       if k != "category"}})
    return {"tables": tables}


def main() -> int:
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true",
                        help="emit machine-readable JSON instead of summary")
    parser.add_argument("--registry",
                        default=os.path.join(repo, "build", "string_registry.json"))
    parser.add_argument("--vanilla-strings",
                        default=os.path.join(repo, "vanilla", "data", "local",
                                             "lng", "strings"))
    parser.add_argument("--patches",
                        default=os.path.join(repo, "patches", "json_strings"))
    args = parser.parse_args()

    if not os.path.exists(args.registry):
        print(f"ERROR: registry not found at {args.registry}. "
              f"Run `python3 -m d2r_mod build` first.")
        return 2

    report = build_report(args.registry, args.vanilla_strings, args.patches)
    if args.json:
        json.dump(report, sys.stdout, indent=2)
        print()
        return 0

    for table, cats in report["tables"].items():
        total = sum(len(v) for v in cats.values())
        print(f"\n=== {table} ({total} entries) ===")
        for cat, items in cats.items():
            if items:
                print(f"  {cat}: {len(items)}")
                for item in items[:5]:
                    print(f"    - {item['key']!r}")
                if len(items) > 5:
                    print(f"    ... +{len(items) - 5} more")
    return 0


if __name__ == "__main__":
    sys.exit(main())
