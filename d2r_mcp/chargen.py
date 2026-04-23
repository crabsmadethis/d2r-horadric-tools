"""Chargen tool implementations for d2r_mcp.

Mutation tools take a character NAME (not inline YAML, not a .d2s path).
The name resolves to chars/<name>.yaml, which must exist as a diff-able
git-trackable artifact before any build. This forces agents to modify
YAML via the Edit tool rather than smuggling content through tool args.
"""
import os

from d2r_mcp.envelope import ok, error


def _chars_dir() -> str:
    """Resolve CHARS_DIR at call time (respects monkeypatched env)."""
    from d2r_chargen.config import CHARS_DIR
    return CHARS_DIR


def list_chars() -> dict:
    """List character names defined in chars/*.yaml (excludes merc_templates)."""
    cdir = _chars_dir()
    if not os.path.isdir(cdir):
        return ok(characters=[], chars_dir=cdir)
    names = []
    for f in sorted(os.listdir(cdir)):
        if f.endswith(".yaml") and f != "merc_templates.yaml":
            names.append(f[:-5])
    return ok(characters=names, chars_dir=cdir)


def validate(name: str, yaml_only: bool = False) -> dict:
    """Validate a character YAML, optionally running a dry-run binary build.

    Args:
        name: Character name (resolves to chars/<name>.yaml).
        yaml_only: If True, only validate YAML schema. If False (default),
                   also build to a temp .d2s and run the scanner — same
                   discipline as `python3 -m d2r_chargen validate <name>`.

    Returns:
        On ok: {character, yaml_valid, binary_valid (bool or None if
        yaml_only), item_count, warnings}.
        On error: error.type in {not_found, yaml_validation_failed,
                                 scanner_failed, build_exception}.
    """
    from d2r_chargen.character import load_character_yaml, validate_char_def
    yaml_path = os.path.join(_chars_dir(), f"{name}.yaml")
    if not os.path.exists(yaml_path):
        return error("not_found", f"no character YAML at {yaml_path}")

    try:
        char_def = load_character_yaml(yaml_path)
        validate_char_def(char_def)
    except Exception as ex:
        return error(
            "yaml_validation_failed",
            f"{type(ex).__name__}: {ex}",
            character=name,
        )

    if yaml_only:
        return ok(character=name, yaml_valid=True, binary_valid=None)

    # Binary validation: mirror cmd_validate in d2r_chargen/cli.py
    import shutil, struct, tempfile
    from d2r_chargen.character import build_all_items
    from d2r_chargen.save import (
        set_character_stats, set_skills, rebuild_items, calc_checksum,
    )
    from d2r_chargen.resolve import resolve_skills
    from d2r_chargen.scanner import scan_character_data
    from d2r_chargen.config import SAVES

    try:
        all_items = build_all_items(char_def)
    except Exception as ex:
        return error("build_exception", f"{type(ex).__name__}: {ex}",
                     character=name)

    template_path = os.path.join(
        os.path.dirname(__file__), "..", "d2r_chargen", "data", "template.d2s"
    )
    existing = os.path.join(SAVES, f"{char_def['name']}.d2s")
    if os.path.exists(existing):
        template_path = existing

    with tempfile.NamedTemporaryFile(suffix=".d2s", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        shutil.copy2(template_path, tmp_path)
        data = bytearray(open(tmp_path, "rb").read())
        skill_array = resolve_skills(char_def["class"], char_def.get("skills", {}))
        stats = char_def["stats"]
        data = set_character_stats(
            data, stats["strength"], stats["dexterity"],
            stats["vitality"], stats["energy"],
            level=char_def.get("level", 99),
            char_class=char_def["class"],
            skill_points_spent=sum(skill_array),
        )
        data = set_skills(data, skill_array)
        struct.pack_into("<I", data, 8, len(data))
        data[12:16] = b"\x00\x00\x00\x00"
        struct.pack_into("<I", data, 12, calc_checksum(data))
        with open(tmp_path, "wb") as f:
            f.write(data)
        item_bytes_list = [b for _, b in all_items]
        result_data = rebuild_items(tmp_path, item_bytes_list, [])
        with open(tmp_path, "wb") as f:
            f.write(result_data)
        scan = scan_character_data(tmp_path)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    if scan["errors"]:
        return error(
            "scanner_failed",
            f"{len(scan['errors'])} hard error(s) in dry-run build",
            character=name,
            yaml_valid=True,
            binary_valid=False,
            scanner_errors=scan["errors"],
            scanner_warnings=scan["warnings"],
        )
    return ok(
        character=name,
        yaml_valid=True,
        binary_valid=True,
        item_count=scan["item_count"],
        warnings=scan["warnings"],
    )


def build(name: str, phase: int | None = None, force: bool = False) -> dict:
    """Build and deploy a character from chars/<name>.yaml.

    Wraps d2r_chargen.character.deploy_character. Rule enforcement lives
    in the wrapped function — see tests/test_chargen_safety.py for the
    invariant (live save untouched on scanner failure).

    Args:
        name: Character name (chars/<name>.yaml must exist).
        phase: Deploy up to this phase (1-4). None = full deploy (phase=4).
        force: Skip the freshness gate. Use only when intentionally
               discarding server-synced progress.

    Returns:
        On ok: {character, phase_completed, backup_path, scanner_result,
                rolled_back: False}.
        On error: {character, phase_failed, scanner_result, rolled_back,
                   error: {type, detail}}.
    """
    yaml_path = os.path.join(_chars_dir(), f"{name}.yaml")
    if not os.path.exists(yaml_path):
        return error("not_found", f"no character YAML at {yaml_path}",
                     character=name, rolled_back=True)

    from d2r_chargen.character import deploy_character
    from d2r_chargen.config import SAVES
    phase_arg = 4 if phase is None else phase

    # Snapshot live save BEFORE the call so we can detect whether the
    # promote step ever touched it. Use a content hash, not just mtime —
    # mtime has 1-second granularity on some ext4 configs, which would
    # false-positive on fast successful builds.
    import hashlib
    live_path = os.path.join(SAVES, f"{name}.d2s")

    def _hash_or_none(p):
        if not os.path.exists(p):
            return None
        with open(p, "rb") as _f:
            return hashlib.sha256(_f.read()).hexdigest()

    pre_hash = _hash_or_none(live_path)

    try:
        result = deploy_character(name, phase=phase_arg, force=force)
    except Exception as ex:
        return error(
            "build_exception", f"{type(ex).__name__}: {ex}",
            character=name, rolled_back=True,
        )

    post_hash = _hash_or_none(live_path)
    # rolled_back means the live file is byte-identical to its pre-call
    # state. Success + unchanged file is impossible (promote writes new
    # bytes), so this is a reliable proxy for "live save was never
    # touched." If the file didn't exist before and doesn't after, treat
    # deploy_character's own return value as authoritative.
    if pre_hash is None and post_hash is None:
        rolled_back = (result is False)
    else:
        rolled_back = (pre_hash == post_hash)

    scanner_result = None
    if os.path.exists(live_path):
        from d2r_mcp.save import scan as _scan
        scanner_result = _scan(live_path)

    # The refactored deploy_character now uses a single pre_chargen_bak
    # (not per-phase) — look for that first, fall back to the plan's
    # legacy naming only if it exists.
    backup_path = f"{live_path}.pre_chargen_bak"
    if not os.path.exists(backup_path):
        legacy = f"{live_path}.pre_phase{phase_arg}_bak"
        backup_path = legacy if os.path.exists(legacy) else None

    if result is False:
        return error(
            "build_failed",
            f"deploy_character returned False for {name} (phase {phase_arg})",
            character=name,
            phase_failed=phase_arg,
            backup_path=backup_path,
            scanner_result=scanner_result,
            rolled_back=rolled_back,
        )

    return ok(
        character=name,
        phase_completed=phase_arg,
        backup_path=backup_path,
        scanner_result=scanner_result,
        rolled_back=False,
    )


def import_save(name: str, force: bool = False) -> dict:
    """Import a server-synced .d2s into the chars/<name>.yaml workflow.

    Args:
        name: Character name (reads <SAVES>/<name>.d2s).
        force: Overwrite an existing chars/<name>.yaml.

    Returns:
        On ok: {character, yaml_path, items_count}.
        On error: error.type in {not_found, would_overwrite, import_exception}.
    """
    from d2r_chargen.config import SAVES
    d2s_path = os.path.join(SAVES, f"{name}.d2s")
    if not os.path.exists(d2s_path):
        return error("not_found", f"{d2s_path} not found", character=name)

    out_path = os.path.join(_chars_dir(), f"{name}.yaml")
    if os.path.exists(out_path) and not force:
        return error(
            "would_overwrite",
            f"{out_path} already exists; pass force=True to overwrite",
            character=name, yaml_path=out_path,
        )

    from d2r_chargen.importer import import_character, dict_to_yaml
    try:
        result = import_character(d2s_path)
        yaml_str = dict_to_yaml(result)
    except Exception as ex:
        return error("import_exception", f"{type(ex).__name__}: {ex}",
                     character=name)

    with open(out_path, "w") as f:
        f.write(yaml_str)

    item_count = (
        len(result.get("equipment", []))
        + len(result.get("inventory", []))
        + len(result.get("stash", []))
        + len(result.get("cube", []))
    )
    return ok(character=name, yaml_path=out_path, items_count=item_count)
