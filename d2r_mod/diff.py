"""Compare vanilla and build D2R tables at the cell level."""


def diff_tables(
    vanilla: list[dict], build: list[dict], key_cols: list[str] | None = None
) -> list[dict]:
    """Find all cell-level changes between vanilla and build rows.

    If build has more rows than vanilla, the extra rows are reported as
    additions (each non-empty cell is reported with old="" and new=<value>).
    Build may not have *fewer* rows than vanilla.
    """
    if not vanilla:
        return []
    if len(build) < len(vanilla):
        raise ValueError(
            f"Row count mismatch: vanilla has {len(vanilla)}, build has {len(build)} "
            f"(build must not remove rows)"
        )
    if key_cols is None:
        key_cols = [list(vanilla[0].keys())[0]]

    changes = []

    # Compare rows that exist in both vanilla and build
    for v_row, b_row in zip(vanilla, build):
        row_key = {k: v_row.get(k, "") for k in key_cols}
        b_key = {k: b_row.get(k, "") for k in key_cols}
        if row_key != b_key:
            raise ValueError(f"Row key mismatch: vanilla={row_key} vs build={b_key}")
        for col in v_row:
            if col in key_cols:
                continue
            old_val = v_row.get(col, "")
            new_val = b_row.get(col, "")
            if old_val != new_val:
                changes.append({
                    "row_key": row_key,
                    "column": col,
                    "old": old_val,
                    "new": new_val,
                    "added": False,
                })

    # Report rows added by scripts (exist in build but not vanilla)
    for b_row in build[len(vanilla):]:
        row_key = {k: b_row.get(k, "") for k in key_cols}
        for col, new_val in b_row.items():
            if col in key_cols:
                continue
            if new_val:
                changes.append({
                    "row_key": row_key,
                    "column": col,
                    "old": "",
                    "new": new_val,
                    "added": True,
                })

    return changes


def format_diff(filename: str, changes: list[dict]) -> str:
    if not changes:
        return f"{filename}: no changes"
    lines = [f"--- {filename} ---"]
    for c in changes:
        key_str = ", ".join(f"{k}={v}" for k, v in c["row_key"].items())
        prefix = "  [+]" if c.get("added") else "     "
        lines.append(f"{prefix} [{key_str}] {c['column']}: {c['old']} → {c['new']}")
    return "\n".join(lines)


def summarize_diff(filename: str, changes: list[dict]) -> str:
    if not changes:
        return f"{filename}: no changes"
    modified_keys = set()
    added_keys = set()
    for c in changes:
        key = tuple(sorted(c["row_key"].items()))
        if c.get("added"):
            added_keys.add(key)
        else:
            modified_keys.add(key)
    parts = []
    if modified_keys:
        parts.append(f"{len(modified_keys)} row(s) changed")
    if added_keys:
        parts.append(f"{len(added_keys)} row(s) added")
    cell_count = len(changes)
    return f"{filename}: {', '.join(parts)}, {cell_count} cell(s)"
