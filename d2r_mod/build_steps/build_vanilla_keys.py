"""
Tool for generating (or regenerating) vanilla_string_keys.txt.

Usage:
    python3 -m d2r_mod.build_steps.build_vanilla_keys [vanilla_tbl_dir] [output_path]

Defaults:
    vanilla_tbl_dir = <repo_root>/vanilla/data/local/lng/eng/
    output_path     = <this_directory>/vanilla_string_keys.txt

DESIGN CHOICE: We parse the three vanilla .tbl files (string.tbl,
expansionstring.tbl, patchstring.tbl) from the checked-in vanilla/
directory.  These files are extracted from the unmodded game and
committed to the repo as the ground truth for "what D2R already knows."

The resulting key set is used by register_custom_uniques.py to decide
which UniqueItems.txt index values are "already handled by the game"
(vanilla or any patched-in string) vs. "genuinely new and need
auto-registration."

Re-run this script after a D2R patch by re-extracting the vanilla .tbl
files into vanilla/data/local/lng/eng/ and running:

    python3 -m d2r_mod.build_steps.build_vanilla_keys

The output is checked in alongside the script so normal builds don't
need the vanilla files present.
"""

import os
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(_THIS_DIR))


def build_keys(vanilla_tbl_dir: str) -> set[str]:
    """Parse all three vanilla .tbl files and return the union of their keys."""
    from d2r_mod.assets.tbl import parse_tbl

    all_keys: set[str] = set()
    for tbl_name in ("string.tbl", "expansionstring.tbl", "patchstring.tbl"):
        path = os.path.join(vanilla_tbl_dir, tbl_name)
        if not os.path.exists(path):
            print(f"WARNING: {tbl_name} not found at {path} — skipping", file=sys.stderr)
            continue
        with open(path, "rb") as f:
            data = f.read()
        entries = parse_tbl(data)
        all_keys.update(entries.keys())
        print(f"  {tbl_name}: {len(entries)} keys", file=sys.stderr)

    return all_keys


def main() -> None:
    vanilla_tbl_dir = (
        sys.argv[1]
        if len(sys.argv) > 1
        else os.path.join(_REPO_ROOT, "vanilla", "data", "local", "lng", "eng")
    )
    output_path = (
        sys.argv[2]
        if len(sys.argv) > 2
        else os.path.join(_THIS_DIR, "vanilla_string_keys.txt")
    )

    print(f"Reading vanilla .tbl files from: {vanilla_tbl_dir}", file=sys.stderr)
    all_keys = build_keys(vanilla_tbl_dir)
    print(f"Total unique vanilla keys: {len(all_keys)}", file=sys.stderr)

    sorted_keys = sorted(all_keys)
    with open(output_path, "w", encoding="utf-8") as f:
        for key in sorted_keys:
            f.write(key + "\n")

    print(f"Written {len(sorted_keys)} keys to: {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
