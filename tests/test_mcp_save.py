"""Tests for d2r_mcp.save tool implementations."""
import os
import shutil
import struct
import pytest

FIXTURE = os.path.join(
    os.path.dirname(__file__), "fixtures", "hexshade_lv98_haseen.d2s"
)


@pytest.fixture
def good_save(tmp_path):
    """Copy the fixture into a tmp path so tests never mutate it."""
    dst = tmp_path / "Hexshade.d2s"
    shutil.copy2(FIXTURE, dst)
    return str(dst)


@pytest.fixture
def broken_save(tmp_path, good_save):
    """Fixture with a corrupted checksum — scanner must report it."""
    dst = tmp_path / "Broken.d2s"
    shutil.copy2(good_save, dst)
    data = bytearray(open(dst, "rb").read())
    struct.pack_into("<I", data, 12, 0xDEADBEEF)  # stomp stored checksum
    with open(dst, "wb") as f:
        f.write(data)
    return str(dst)


class TestScan:
    def test_scan_good_save_returns_ok(self, good_save):
        from d2r_mcp.save import scan
        result = scan(good_save)
        assert result["status"] == "ok"
        assert result["checksum_ok"] is True
        assert result["size_ok"] is True
        assert isinstance(result["item_count"], int) and result["item_count"] > 0
        assert result["errors"] == []

    def test_scan_broken_save_returns_error(self, broken_save):
        from d2r_mcp.save import scan
        result = scan(broken_save)
        assert result["status"] == "error"
        assert result["error"]["type"] == "scanner_failed"
        assert len(result["errors"]) >= 1
        assert any("checksum" in e.lower() for e in result["errors"])

    def test_scan_missing_file_returns_error(self, tmp_path):
        from d2r_mcp.save import scan
        result = scan(str(tmp_path / "nonexistent.d2s"))
        assert result["status"] == "error"
        assert result["error"]["type"] == "not_found"

    def test_scan_status_invariant(self, good_save, broken_save):
        """status=='error' iff errors is non-empty (per spec line 139)."""
        from d2r_mcp.save import scan
        for path in (good_save, broken_save):
            r = scan(path)
            assert (r["status"] == "error") == (len(r["errors"]) > 0)


class TestInspect:
    def test_inspect_returns_character_summary(self, good_save):
        from d2r_mcp.save import inspect
        result = inspect(good_save)
        assert result["status"] == "ok"
        assert result["character"]  # non-empty name
        assert result["class"] in ("Amazon", "Sorceress", "Necromancer",
                                   "Paladin", "Barbarian", "Druid",
                                   "Assassin", "Warlock")
        assert isinstance(result["level"], int) and 1 <= result["level"] <= 99
        assert result["progression"] in ("normal", "nightmare", "hell") or \
               result["progression"].startswith("0x")
        assert "stats" in result
        assert "strength" in result["stats"]
        assert "merc" in result

    def test_inspect_missing_file(self, tmp_path):
        from d2r_mcp.save import inspect
        r = inspect(str(tmp_path / "no.d2s"))
        assert r["status"] == "error"
        assert r["error"]["type"] == "not_found"


class TestListItems:
    def test_list_all_items(self, good_save):
        from d2r_mcp.save import list_items
        result = list_items(good_save)
        assert result["status"] == "ok"
        assert isinstance(result["items"], list)
        assert len(result["items"]) > 0
        first = result["items"][0]
        assert "location" in first
        assert first["location"] in (
            "equipped", "inventory", "cube", "stash", "merc_equipped"
        )
        # Items have a type_code key with the item base code or identifier
        assert "type_code" in first

    def test_list_filter_equipped(self, good_save):
        from d2r_mcp.save import list_items
        result = list_items(good_save, location="equipped")
        assert result["status"] == "ok"
        assert all(i["location"] == "equipped" for i in result["items"])

    def test_list_invalid_location(self, good_save):
        from d2r_mcp.save import list_items
        result = list_items(good_save, location="nonsense")
        assert result["status"] == "error"
        assert result["error"]["type"] == "invalid_argument"

    def test_list_missing_file(self, tmp_path):
        from d2r_mcp.save import list_items
        r = list_items(str(tmp_path / "missing.d2s"))
        assert r["status"] == "error"
        assert r["error"]["type"] == "not_found"


class TestDiff:
    def test_diff_identical_returns_empty(self, good_save):
        from d2r_mcp.save import diff
        result = diff(good_save, good_save)
        assert result["status"] == "ok"
        assert result["header_changes"] == []
        assert result["stat_changes"] == []
        assert result["items_added"] == []
        assert result["items_removed"] == []

    def test_diff_different_saves(self, good_save, broken_save):
        from d2r_mcp.save import diff
        result = diff(good_save, broken_save)
        assert result["status"] == "ok"
        # broken_save only mutated checksum byte — header_changes may or may
        # not surface it depending on what _diff_headers inspects.
        # Just verify the result is structurally correct.
        assert isinstance(result["header_changes"], list)
        assert isinstance(result["stat_changes"], list)
        assert isinstance(result["items_added"], list)
        assert isinstance(result["items_removed"], list)

    def test_diff_missing_file(self, good_save, tmp_path):
        from d2r_mcp.save import diff
        r = diff(good_save, str(tmp_path / "no.d2s"))
        assert r["status"] == "error"
        assert r["error"]["type"] == "not_found"
