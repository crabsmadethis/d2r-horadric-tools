"""YAML overlay loading and application for D2R .txt files."""

import yaml


def load_overlay(content: str) -> dict:
    """Parse YAML overlay content into an overlay dict."""
    return yaml.safe_load(content)


def load_overlay_file(path: str) -> dict:
    """Load a YAML overlay from a file."""
    with open(path, "r", encoding="utf-8") as f:
        return load_overlay(f.read())


def _normalize_selector_value(v) -> str:
    """Normalize YAML-parsed selector values to match TSV string cells."""
    if isinstance(v, bool):
        return str(int(v))
    if v is None:
        return ""
    return str(v)


def _find_row(rows: list[dict], selector: dict, overlay_context: str = "") -> dict:
    """Find exactly one row matching all selector key=value pairs."""
    matches = [
        r for r in rows
        if all(r.get(k) == _normalize_selector_value(v) for k, v in selector.items())
    ]
    ctx = f" ({overlay_context})" if overlay_context else ""
    if len(matches) == 0:
        raise ValueError(f"Row selector {selector} matched 0 rows{ctx}")
    if len(matches) > 1:
        raise ValueError(f"Row selector {selector} matched {len(matches)} rows{ctx}")
    return matches[0]


def _apply_set(row: dict, values: dict) -> None:
    for col, val in values.items():
        if isinstance(val, bool):
            row[col] = str(int(val))
        elif val is None:
            row[col] = ""
        else:
            row[col] = str(val)


def _apply_numeric(row: dict, values: dict, op: str) -> None:
    for col, val in values.items():
        cell = row.get(col, "")
        if cell == "":
            continue
        try:
            num = float(cell)
        except ValueError:
            raise ValueError(
                f"Cannot apply {op} to non-numeric cell: column={col}, value={cell!r}"
            )
        if op == "multiply":
            result = round(num * val)
        elif op == "add":
            result = round(num + val)
        else:
            raise ValueError(f"Unknown numeric op: {op}")
        row[col] = str(result)


def _expand_level_scaled(headers: list[str], col: str) -> list[str]:
    """Expand a base column name to all level-scaled variants.
    If col is 'EMin', returns ['EMin1', 'EMin2', ...] for all matching headers.
    If col already has a digit suffix or exists literally, returns [col].
    """
    import re
    if col in headers:
        return [col]
    if re.search(r'\d+$', col):
        return [col]
    pattern = re.compile(f'^{re.escape(col)}(\\d+)$')
    expanded = [h for h in headers if pattern.match(h)]
    if not expanded:
        return [col]
    return expanded


def apply_overlay(rows: list[dict], overlay: dict) -> list[str]:
    """Apply an overlay's changes to rows. Returns list of warnings."""
    warnings = []
    headers = list(rows[0].keys()) if rows else []

    for change in overlay.get("changes", []):
        selector = change["row"]
        comment = change.get("comment", "")
        row = _find_row(rows, selector, comment)

        if "set" in change:
            _apply_set(row, change["set"])

        for op in ("multiply", "add"):
            if op in change:
                expanded_vals = {}
                for col, val in change[op].items():
                    for ecol in _expand_level_scaled(headers, col):
                        expanded_vals[ecol] = val
                _apply_numeric(row, expanded_vals, op)

    return warnings
