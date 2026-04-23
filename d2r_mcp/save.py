"""Save-file inspection tools for d2r_mcp.

Each function returns a structured envelope dict. Paths can be absolute,
~-expanded, or bare character names (resolved against d2r_chargen.config.SAVES).
"""
import os

from d2r_chargen.config import SAVES
from d2r_mcp.envelope import ok, error


def _resolve_save_path(path: str) -> str:
    """Resolve a user-supplied path to an absolute .d2s path.

    Accepts absolute paths, ~-prefixed paths, or bare character names
    (resolved against the Steam saves directory).
    """
    expanded = os.path.expanduser(path)
    if os.path.isabs(expanded) and os.path.exists(expanded):
        return expanded
    if not expanded.endswith(".d2s"):
        candidate = os.path.join(SAVES, f"{expanded}.d2s")
        if os.path.exists(candidate):
            return candidate
    candidate = os.path.join(SAVES, expanded)
    if os.path.exists(candidate):
        return candidate
    return expanded  # caller handles non-existence


def scan(path: str) -> dict:
    """Run d2rdoctor scanner on a .d2s file, return structured envelope.

    Args:
        path: Absolute path, ~-prefixed path, or bare character name.

    Returns:
        Envelope dict. On ok, payload includes character/class_id/level/
        checksum_ok/size_ok/item_count/merc_count/errors/warnings. On error,
        either error.type == "not_found" (missing file) or "scanner_failed"
        (errors non-empty), with the raw scanner fields still included.
    """
    resolved = _resolve_save_path(path)
    if not os.path.exists(resolved):
        return error("not_found", f"save file not found: {path}")

    from d2r_chargen.scanner import scan_character_data
    try:
        raw = scan_character_data(resolved)
    except Exception as ex:
        return error("scan_exception", f"{type(ex).__name__}: {ex}")

    payload = {
        "character": raw["name"],
        "class_id": raw["class_id"],
        "level": raw["level"],
        "checksum_ok": raw["checksum_ok"],
        "size_ok": raw["size_ok"],
        "item_count": raw["item_count"],
        "merc_count": raw["merc_count"],
        "errors": raw["errors"],
        "warnings": raw["warnings"],
    }
    if raw["errors"]:
        return error(
            "scanner_failed",
            f"{len(raw['errors'])} hard error(s) in {os.path.basename(resolved)}",
            **payload,
        )
    return ok(**payload)


_CLASS_NAMES = ["Amazon", "Sorceress", "Necromancer", "Paladin",
                "Barbarian", "Druid", "Assassin", "Warlock"]


def inspect(path: str) -> dict:
    """Return a human-readable character summary.

    Decodes class, level, progression, stats, waypoints, and merc info from
    the .d2s header and stats section. Does not run the full scanner; use
    scan() for validation.
    """
    resolved = _resolve_save_path(path)
    if not os.path.exists(resolved):
        return error("not_found", f"save file not found: {path}")

    from d2r_chargen.importer import _read_name, _decode_character_stats
    with open(resolved, "rb") as f:
        data = bytearray(f.read())

    cls_id = data[0x18]
    class_name = _CLASS_NAMES[cls_id] if 0 <= cls_id < len(_CLASS_NAMES) \
        else f"class_{cls_id}"
    level = data[0x1B]
    prog = data[0x15]
    progression = {0x00: "normal", 0x05: "nightmare", 0x0F: "hell"}.get(
        prog, f"0x{prog:02X}"
    )
    stats = _decode_character_stats(data)

    # Merc summary (kept minimal — full merc decode is the scanner's job)
    merc = {"present": False}
    merc_type = int.from_bytes(data[0xA8:0xAA], "little")
    if merc_type not in (0, 0xFFFF):
        merc["present"] = True
        merc["type_id"] = merc_type
        merc["xp"] = int.from_bytes(data[0xAA:0xAE], "little")

    return ok(
        character=_read_name(data),
        **{"class": class_name},
        class_id=cls_id,
        level=level,
        progression=progression,
        stats=stats,
        merc=merc,
    )


# Belt items are not decoded by _decode_items — they are stored differently in
# the binary format and not surfaced by the importer. Valid locations are the
# five buckets returned by _decode_items.
_VALID_LOCATIONS = {"equipped", "inventory", "cube", "stash", "merc_equipped"}


def _item_type_code(item_dict: dict) -> str:
    """Extract a canonical type identifier from a raw importer item dict.

    Priority: base (raw type code) > unique name > set name > runeword name.
    Falls back to "unknown" if none are present.
    """
    if "base" in item_dict:
        return item_dict["base"]
    if "unique" in item_dict:
        return item_dict["unique"]
    if "set" in item_dict:
        return item_dict["set"]
    if "runeword" in item_dict:
        return item_dict["runeword"]
    return "unknown"


def list_items(path: str, location: str | None = None) -> dict:
    """List items on disk, optionally filtered by storage location.

    Args:
        path: Save file path or character name.
        location: One of equipped/inventory/cube/stash/merc_equipped,
                  or None for all.
                  Note: belt items are not decoded by the underlying importer
                  and are therefore not available as a separate location.

    Returns:
        Envelope with "items": list[dict] and "total": int.
        Each item dict has: location, type_code, and any decoded fields
        (slot, unique/set/runeword/base name, quality flags, properties, etc.).
    """
    if location is not None and location not in _VALID_LOCATIONS:
        return error(
            "invalid_argument",
            f"location must be one of {sorted(_VALID_LOCATIONS)} or None, "
            f"got {location!r}",
        )

    resolved = _resolve_save_path(path)
    if not os.path.exists(resolved):
        return error("not_found", f"save file not found: {path}")

    from d2r_chargen.importer import _decode_items
    with open(resolved, "rb") as f:
        data = bytearray(f.read())
    equipment, inventory, stash, cube, merc_equipment = _decode_items(data)

    buckets = {
        "equipped": equipment or [],
        "inventory": inventory or [],
        "cube": cube or [],
        "stash": stash or [],
        "merc_equipped": merc_equipment or [],
    }

    items = []
    for loc, bucket in buckets.items():
        if location is not None and loc != location:
            continue
        for raw in bucket:
            # Skip pure rune fillers (only have a 'rune' key) — these are
            # socketed items that leaked into merc_equipment in the importer.
            if set(raw.keys()) == {"rune"}:
                continue
            item = {"location": loc, "type_code": _item_type_code(raw)}
            item.update(raw)
            items.append(item)

    return ok(items=items, total=len(items))


def diff(path_a: str, path_b: str) -> dict:
    """Structural diff between two .d2s files.

    Wraps d2r_chargen.diff.diff_saves. Returns the same keys
    (header_changes, stat_changes, items_added, items_removed, items_moved)
    wrapped in an envelope.

    Args:
        path_a: First .d2s file (absolute path, ~-prefixed, or character name).
        path_b: Second .d2s file (absolute path, ~-prefixed, or character name).

    Returns:
        Envelope dict with "header_changes", "stat_changes", "items_added",
        "items_removed", "items_moved" keys on ok, or error details on failure.
    """
    resolved_a = _resolve_save_path(path_a)
    resolved_b = _resolve_save_path(path_b)
    if not os.path.exists(resolved_a):
        return error("not_found", f"save file not found: {path_a}")
    if not os.path.exists(resolved_b):
        return error("not_found", f"save file not found: {path_b}")

    from d2r_chargen.diff import diff_saves
    raw = diff_saves(resolved_a, resolved_b)
    return ok(
        header_changes=raw.get("header_changes", []),
        stat_changes=raw.get("stat_changes", []),
        items_added=raw.get("items_added", []),
        items_removed=raw.get("items_removed", []),
        items_moved=raw.get("items_moved", []),
    )
