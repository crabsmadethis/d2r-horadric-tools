"""Tests for d2r_mcp.mod tool implementations."""
import os
import pytest


class TestDiff:
    def test_diff_requires_build(self, tmp_path, monkeypatch):
        # Run from a dir that has no vanilla/ or build/ — should return
        # a clean error envelope, not crash.
        monkeypatch.chdir(tmp_path)
        # Patch _project_root so the wrapper looks for build/ and vanilla/
        # in a non-existent location (the tmp dir we just chdir'd to).
        monkeypatch.setattr("d2r_mcp.mod._project_root", lambda: str(tmp_path))
        from d2r_mcp.mod import diff
        r = diff()
        assert r["status"] == "error"
        assert r["error"]["type"] in ("missing_dir", "build_required")

    @pytest.mark.integration
    def test_diff_summary_returns_list(self):
        from d2r_mcp.mod import diff
        # Relies on autouse build_mod_once conftest fixture which runs a
        # real build into ../build relative to the project root.
        r = diff(summary=True)
        assert r["status"] == "ok"
        assert isinstance(r["changed_files"], list)
