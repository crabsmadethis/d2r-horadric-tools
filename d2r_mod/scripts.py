"""Run Python balance scripts against loaded D2R tables."""

import importlib.util


def run_script(path: str, tables: dict[str, list[dict]], allow_add: bool = False) -> list[str]:
    """Load and execute a balance script.

    The script must define apply(tables). Row counts are validated
    before and after execution — scripts must not add/remove rows.
    If allow_add is True, scripts may append rows but still may not
    remove rows from existing tables.
    Returns list of warning strings from the script (or empty list).
    """
    keys_before = set(tables.keys())
    counts_before = {k: len(v) for k, v in tables.items()}

    spec = importlib.util.spec_from_file_location("balance_script", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    if not hasattr(mod, "apply"):
        raise ValueError(f"Script {path} has no apply() function")

    result = mod.apply(tables)

    keys_after = set(tables.keys())
    if keys_after != keys_before:
        added = keys_after - keys_before
        removed = keys_before - keys_after
        raise ValueError(
            f"Script {path} modified table keys: added={added}, removed={removed}"
        )

    for key, before in counts_before.items():
        after = len(tables.get(key, []))
        if after != before:
            if allow_add and after > before:
                continue  # additions permitted
            raise ValueError(
                f"Script {path} changed row count for {key}: {before} → {after}"
            )

    if result is None:
        return []
    return list(result)
