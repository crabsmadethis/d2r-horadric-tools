"""Tests for d2r-mod claude-setup / claude-teardown."""
import json
import os
import pytest

from d2r_mod.claude_setup import (
    check_dependencies,
    build_mcp_entry,
    build_hook_entries,
    apply_setup,
    apply_teardown,
    check_game_data,
)


@pytest.fixture
def fake_home(tmp_path):
    """Create a fake ~/.claude/ directory."""
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    return tmp_path


@pytest.fixture
def repo_root(tmp_path):
    """Create a fake repo root with all hook scripts."""
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    for name in [
        "d2r_alias_validator.py", "d2r_web_data_guard.sh",
        "d2r_xdotool_guard.sh", "d2s_backup_guard.sh",
        "d2r_verify_guard.sh", "d2r_verify_guard_post.sh",
        "d2r_verify_cleanup.sh",
    ]:
        (hooks_dir / name).write_text("#!/bin/bash\nexit 0\n")
    return tmp_path


def test_build_mcp_entry(repo_root):
    entry = build_mcp_entry(str(repo_root))
    assert entry["command"] == "python3"
    assert entry["args"] == ["-m", "d2r_mcp"]
    assert entry["cwd"] == str(repo_root)


def test_build_hook_entries(repo_root):
    entries = build_hook_entries(str(repo_root))
    # All three event types should be present
    assert "PreToolUse" in entries
    assert "PostToolUse" in entries
    assert "SessionStart" in entries
    # Each entry should have command pointing to repo hooks
    for event_type, hooks in entries.items():
        for hook in hooks:
            assert "command" in hook
            assert str(repo_root) in hook["command"]


def test_apply_setup_creates_settings(fake_home, repo_root):
    settings_path = os.path.join(str(fake_home), ".claude", "settings.json")
    apply_setup(str(repo_root), claude_dir=os.path.join(str(fake_home), ".claude"))
    assert os.path.exists(settings_path)
    with open(settings_path) as f:
        settings = json.load(f)
    assert "d2r-data" in settings.get("mcpServers", {})


def test_apply_setup_preserves_existing(fake_home, repo_root):
    settings_path = os.path.join(str(fake_home), ".claude", "settings.json")
    existing = {"mcpServers": {"other-server": {"command": "node"}}, "hooks": {"PreToolUse": [{"matcher": "Bash", "command": "/usr/bin/my-hook"}]}}
    with open(settings_path, "w") as f:
        json.dump(existing, f)
    apply_setup(str(repo_root), claude_dir=os.path.join(str(fake_home), ".claude"))
    with open(settings_path) as f:
        settings = json.load(f)
    assert "other-server" in settings["mcpServers"]
    assert "d2r-data" in settings["mcpServers"]


def test_apply_teardown_removes_entries(fake_home, repo_root):
    settings_path = os.path.join(str(fake_home), ".claude", "settings.json")
    apply_setup(str(repo_root), claude_dir=os.path.join(str(fake_home), ".claude"))
    apply_teardown(str(repo_root), claude_dir=os.path.join(str(fake_home), ".claude"))
    with open(settings_path) as f:
        settings = json.load(f)
    assert "d2r-data" not in settings.get("mcpServers", {})


def test_apply_teardown_preserves_other_hooks(fake_home, repo_root):
    settings_path = os.path.join(str(fake_home), ".claude", "settings.json")
    apply_setup(str(repo_root), claude_dir=os.path.join(str(fake_home), ".claude"))
    with open(settings_path) as f:
        settings = json.load(f)
    settings.setdefault("hooks", {}).setdefault("PreToolUse", []).append(
        {"matcher": "Bash", "command": "/usr/bin/my-hook"}
    )
    with open(settings_path, "w") as f:
        json.dump(settings, f)
    apply_teardown(str(repo_root), claude_dir=os.path.join(str(fake_home), ".claude"))
    with open(settings_path) as f:
        settings = json.load(f)
    pre_hooks = settings.get("hooks", {}).get("PreToolUse", [])
    assert any(h["command"] == "/usr/bin/my-hook" for h in pre_hooks)


def test_check_game_data_missing(tmp_path):
    result = check_game_data(str(tmp_path))
    assert result["ok"] is False
    assert result["missing"]


def test_check_game_data_present(tmp_path):
    data_dir = tmp_path / "d2r_chargen" / "data"
    data_dir.mkdir(parents=True)
    for mod in ["unique_items", "set_items", "item_bases", "item_dimensions",
                "runewords", "item_stat_cost", "skills"]:
        (data_dir / f"{mod}.py").write_text(f"# {mod}")
    result = check_game_data(str(tmp_path))
    assert result["ok"] is True
