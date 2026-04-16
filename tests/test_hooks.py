"""Tests for Claude Code hook scripts.

Tests pipe JSON to hook scripts and verify exit codes + output.
"""
import json
import os
import subprocess
import pytest

HOOKS_DIR = os.path.join(os.path.dirname(__file__), "..", "hooks")


def run_hook(script, tool_name, tool_input):
    """Run a hook script with the given tool call JSON on stdin."""
    payload = json.dumps({"tool_name": tool_name, "tool_input": tool_input})
    result = subprocess.run(
        [script], input=payload, capture_output=True, text=True, timeout=5,
    )
    return result


class TestXdotoolGuard:
    HOOK = f"{HOOKS_DIR}/d2r_xdotool_guard.sh"

    def test_blocks_xdotool_click(self):
        r = run_hook(self.HOOK, "Bash", {"command": "xdotool click 1"})
        assert r.returncode == 2
        assert "evdev" in r.stdout.lower() or "UInput" in r.stdout

    def test_blocks_xdotool_key(self):
        r = run_hook(self.HOOK, "Bash", {"command": "xdotool key Escape"})
        assert r.returncode == 2

    def test_blocks_xdotool_keydown(self):
        r = run_hook(self.HOOK, "Bash", {"command": "xdotool keydown shift"})
        assert r.returncode == 2

    def test_blocks_xdotool_type(self):
        r = run_hook(self.HOOK, "Bash", {"command": "xdotool type hello"})
        assert r.returncode == 2

    def test_blocks_xdotool_mousedown(self):
        r = run_hook(self.HOOK, "Bash", {"command": "xdotool mousedown 1"})
        assert r.returncode == 2

    def test_allows_xdotool_mousemove(self):
        r = run_hook(self.HOOK, "Bash", {"command": "xdotool mousemove 100 200"})
        assert r.returncode == 0

    def test_allows_xdotool_windowactivate(self):
        r = run_hook(self.HOOK, "Bash",
                     {"command": "xdotool windowactivate --sync 12345"})
        assert r.returncode == 0

    def test_allows_non_xdotool_commands(self):
        r = run_hook(self.HOOK, "Bash", {"command": "ls -la"})
        assert r.returncode == 0

    def test_ignores_non_bash_tools(self):
        r = run_hook(self.HOOK, "Read", {"file_path": "/tmp/test"})
        assert r.returncode == 0


class TestWebDataGuard:
    HOOK = f"{HOOKS_DIR}/d2r_web_data_guard.sh"

    def test_warns_on_d2r_unique_search(self):
        r = run_hook(self.HOOK, "WebSearch",
                     {"query": "d2r unique item harlequin crest stats"})
        assert r.returncode == 0  # warn, not block
        assert "MCP" in r.stdout or "data tool" in r.stdout.lower()

    def test_warns_on_d2r_runeword_search(self):
        r = run_hook(self.HOOK, "WebSearch",
                     {"query": "diablo 2 resurrected enigma runeword stats"})
        assert r.returncode == 0
        assert len(r.stdout) > 0  # should have warning text

    def test_warns_on_d2r_stat_search(self):
        r = run_hook(self.HOOK, "WebSearch",
                     {"query": "d2r item stat cost enhanced defense encoding"})
        assert r.returncode == 0
        assert len(r.stdout) > 0

    def test_allows_non_data_d2r_search(self):
        r = run_hook(self.HOOK, "WebSearch",
                     {"query": "d2r proton compatibility steam deck"})
        assert r.returncode == 0
        assert r.stdout == ""  # no warning

    def test_allows_unrelated_search(self):
        r = run_hook(self.HOOK, "WebSearch",
                     {"query": "python asyncio tutorial"})
        assert r.returncode == 0
        assert r.stdout == ""

    def test_ignores_non_web_tools(self):
        r = run_hook(self.HOOK, "Bash", {"command": "echo hello"})
        assert r.returncode == 0
        assert r.stdout == ""

    def test_warns_on_webfetch_d2r_wiki(self):
        r = run_hook(self.HOOK, "WebFetch",
                     {"url": "https://d2.maxroll.gg/items/unique"})
        assert r.returncode == 0
        assert len(r.stdout) > 0


class TestAliasValidator:
    HOOK = f"{HOOKS_DIR}/d2r_alias_validator.py"

    def test_passes_on_valid_config(self):
        """Current config.py should validate cleanly."""
        r = run_hook(self.HOOK, "Edit",
                     {"file_path": "d2r_chargen/config.py",
                      "old_string": "x", "new_string": "x"})
        assert r.returncode == 0
        assert "validated" in r.stdout.lower() or r.stdout == ""

    def test_ignores_non_config_files(self):
        r = run_hook(self.HOOK, "Edit",
                     {"file_path": "d2r_chargen/items.py",
                      "old_string": "x", "new_string": "x"})
        assert r.returncode == 0

    def test_ignores_non_edit_tools(self):
        r = run_hook(self.HOOK, "Read",
                     {"file_path": "d2r_chargen/config.py"})
        assert r.returncode == 0
