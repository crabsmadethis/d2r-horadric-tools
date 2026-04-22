"""
Build step: auto-register custom unique item display names in a .tbl file.

DR-1 HYPOTHESIS: D2R reads ``expansionstring.tbl`` (not ``patchstring.tbl``)
for unique-item name lookup, matching the pattern used by vanilla expansion
uniques such as Annihilus and Hellfire Torch.  Set DEFAULT_TARGET_TBL to
"string" or "patchstring" here if DR-1 experiment proves otherwise.

Usage (called by build.py):

    from d2r_mod.build_steps.register_custom_uniques import run, load_vanilla_keys

    vanilla_keys = load_vanilla_keys()
    result = run(unique_items_path, target_tbl_path, vanilla_keys)
    # result = {'added': N, 'skipped': M}

Design guarantees:
  - IDEMPOTENT: running twice produces identical output.
  - NON-DESTRUCTIVE: existing keys in target_tbl are preserved unchanged.
  - ZERO-TOUCH: future custom uniques added to new_uniques.py are
    registered automatically with no manual YAML edits required.
"""

import os

# DR-1 HYPOTHESIS: flip to "string" or "patchstring" if experiment disproves this.
DEFAULT_TARGET_TBL = "expansionstring"

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_VANILLA_KEYS_PATH = os.path.join(_THIS_DIR, "vanilla_string_keys.txt")


def load_vanilla_keys(path: str | None = None) -> set[str]:
    """Load the checked-in vanilla key corpus.

    Returns a set of string keys that are already known to vanilla D2R
    (union of string.tbl + expansionstring.tbl + patchstring.tbl).
    Regenerate with: python3 -m d2r_mod.build_steps.build_vanilla_keys
    """
    p = path or _VANILLA_KEYS_PATH
    with open(p, encoding="utf-8") as f:
        return {line.rstrip("\n") for line in f if line.strip()}


def _parse_unique_items(unique_items_path: str) -> list[str]:
    """Parse UniqueItems.txt (TSV) and return the list of index-column values.

    Rows with empty or whitespace-only index values are excluded (D2R
    convention: these are disabled/placeholder rows).  Header row and rows
    starting with special markers ('*', '#') are also excluded.
    """
    names: list[str] = []
    with open(unique_items_path, encoding="latin-1") as f:
        lines = f.read().splitlines()

    if not lines:
        return names

    # First line is the header — skip it
    for line in lines[1:]:
        if not line.strip():
            continue
        index_col = line.split("\t")[0]
        stripped = index_col.strip()
        if not stripped:
            continue  # empty index = disabled row
        if stripped.startswith("*") or stripped.startswith("#"):
            continue  # special marker rows
        names.append(stripped)

    return names


def run(
    unique_items_path: str | os.PathLike,
    target_tbl_path: str | os.PathLike,
    vanilla_keys: set[str],
    json_served_names: set[str] | None = None,
) -> dict[str, int]:
    """Register custom unique display names in the target .tbl file.

    For each row in UniqueItems.txt:
      - Skip rows with empty/blank index column.
      - Skip rows whose index is in ``vanilla_keys`` (already known to game).
      - Skip rows whose index is in ``json_served_names`` (D2R reads names from
        JSON not TBL — feedback_strings_json_vs_tbl.md — so any TBL write for
        a JSON-served key is dead weight).
      - Skip rows whose index is already present in target_tbl (idempotent).
      - Otherwise, add ``name → name`` entry to the target tbl.

    The target_tbl is created from scratch if it does not exist.

    Returns:
        {'added': int, 'skipped': int, 'skipped_json': int}
    """
    from d2r_mod.assets.tbl import parse_tbl, build_tbl

    unique_items_path = str(unique_items_path)
    target_tbl_path = str(target_tbl_path)
    json_served_names = json_served_names or set()

    # Parse existing target tbl (or start empty)
    if os.path.exists(target_tbl_path):
        with open(target_tbl_path, "rb") as f:
            existing_data = f.read()
        entries: dict[str, str] = parse_tbl(existing_data)
    else:
        os.makedirs(os.path.dirname(target_tbl_path), exist_ok=True)
        entries = {}

    # Parse unique item names from TSV
    names = _parse_unique_items(unique_items_path)

    added = 0
    skipped = 0
    skipped_json = 0
    for name in names:
        if name in vanilla_keys:
            skipped += 1
            continue
        if name in json_served_names:
            skipped_json += 1
            continue
        if name in entries:
            # Already registered (idempotent: second run hits this branch)
            skipped += 1
            continue
        entries[name] = name
        added += 1

    # Write updated tbl back
    new_data = build_tbl(entries)
    with open(target_tbl_path, "wb") as f:
        f.write(new_data)

    return {"added": added, "skipped": skipped, "skipped_json": skipped_json}
