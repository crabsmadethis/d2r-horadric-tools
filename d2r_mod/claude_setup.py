"""Claude Code setup and teardown for d2r-tools.

Registers/unregisters MCP server and hooks in ~/.claude/settings.json.
"""
import json
import os
from pathlib import Path


# Hook definitions: (script_filename, event_type, matcher)
HOOK_DEFS = [
    ("d2r_alias_validator.py", "PostToolUse", "Edit"),
    ("d2r_web_data_guard.sh", "PreToolUse", "WebSearch|WebFetch"),
    ("d2r_xdotool_guard.sh", "PreToolUse", "Bash"),
    ("d2s_backup_guard.sh", "PreToolUse", "Bash|Write|Edit"),
    ("d2r_verify_guard.sh", "PreToolUse", "Bash"),
    ("d2r_verify_guard_post.sh", "PostToolUse", "Bash"),
    ("d2r_verify_cleanup.sh", "SessionStart", ""),
]

GAME_DATA_MODULES = [
    "unique_items", "set_items", "item_bases", "item_dimensions",
    "runewords", "item_stat_cost", "skills",
]


def check_dependencies() -> dict:
    """Check if required packages are installed."""
    missing = []
    try:
        import mcp  # noqa: F401
    except ImportError:
        missing.append("mcp")
    return {"ok": not missing, "missing": missing}


def build_mcp_entry(repo_root: str) -> dict:
    """Build the MCP server entry for settings.json."""
    return {
        "command": "python3",
        "args": ["-m", "d2r_mcp"],
        "cwd": repo_root,
    }


def build_hook_entries(repo_root: str) -> dict[str, list[dict]]:
    """Build hook entries grouped by event type."""
    hooks_dir = os.path.join(repo_root, "hooks")
    entries: dict[str, list[dict]] = {}
    for filename, event_type, matcher in HOOK_DEFS:
        script_path = os.path.join(hooks_dir, filename)
        if not os.path.exists(script_path):
            continue
        entry = {"command": script_path}
        if matcher:
            entry["matcher"] = matcher
        entries.setdefault(event_type, []).append(entry)
    return entries


def check_game_data(repo_root: str) -> dict:
    """Check if extracted game data modules exist."""
    data_dir = os.path.join(repo_root, "d2r_chargen", "data")
    missing = []
    for mod in GAME_DATA_MODULES:
        if not os.path.exists(os.path.join(data_dir, f"{mod}.py")):
            missing.append(mod)
    return {"ok": not missing, "missing": missing}


def _load_settings(settings_path: str) -> dict:
    """Load settings.json, creating it if needed."""
    if os.path.exists(settings_path):
        with open(settings_path) as f:
            return json.load(f)
    return {}


def _save_settings(settings_path: str, settings: dict) -> None:
    """Write settings.json with pretty formatting."""
    os.makedirs(os.path.dirname(settings_path), exist_ok=True)
    with open(settings_path, "w") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")


def _is_d2r_hook(hook: dict, repo_root: str) -> bool:
    """Check if a hook entry belongs to this d2r-tools install."""
    cmd = hook.get("command", "")
    hooks_dir = os.path.join(repo_root, "hooks")
    return cmd.startswith(hooks_dir)


def apply_setup(repo_root: str, claude_dir: str | None = None) -> dict:
    """Register MCP server and hooks in settings.json."""
    if claude_dir is None:
        claude_dir = os.path.join(Path.home(), ".claude")
    settings_path = os.path.join(claude_dir, "settings.json")
    settings = _load_settings(settings_path)
    result = {}

    # MCP server
    settings.setdefault("mcpServers", {})
    settings["mcpServers"]["d2r-data"] = build_mcp_entry(repo_root)
    result["mcp"] = "registered"

    # Hooks
    hook_entries = build_hook_entries(repo_root)
    settings.setdefault("hooks", {})
    hooks_added = 0
    for event_type, new_hooks in hook_entries.items():
        existing = settings["hooks"].setdefault(event_type, [])
        for hook in new_hooks:
            if any(h.get("command") == hook["command"] for h in existing):
                continue
            existing.append(hook)
            hooks_added += 1
    result["hooks"] = hooks_added

    _save_settings(settings_path, settings)
    return result


def apply_teardown(repo_root: str, claude_dir: str | None = None) -> dict:
    """Remove MCP server and hooks from settings.json."""
    if claude_dir is None:
        claude_dir = os.path.join(Path.home(), ".claude")
    settings_path = os.path.join(claude_dir, "settings.json")
    if not os.path.exists(settings_path):
        return {"mcp": "not_found", "hooks": 0}

    settings = _load_settings(settings_path)
    result = {}

    # Remove MCP server
    mcp_servers = settings.get("mcpServers", {})
    if "d2r-data" in mcp_servers:
        del mcp_servers["d2r-data"]
        result["mcp"] = "removed"
    else:
        result["mcp"] = "not_found"

    # Remove hooks belonging to this repo
    hooks_removed = 0
    hooks = settings.get("hooks", {})
    for event_type in list(hooks.keys()):
        original_count = len(hooks[event_type])
        hooks[event_type] = [
            h for h in hooks[event_type]
            if not _is_d2r_hook(h, repo_root)
        ]
        hooks_removed += original_count - len(hooks[event_type])
        if not hooks[event_type]:
            del hooks[event_type]
    result["hooks"] = hooks_removed

    if not settings.get("hooks"):
        settings.pop("hooks", None)
    if not settings.get("mcpServers"):
        settings.pop("mcpServers", None)

    _save_settings(settings_path, settings)
    return result
