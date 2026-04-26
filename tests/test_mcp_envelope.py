"""Tests for d2r_mcp.envelope helpers."""
# Skip entire file if game data not extracted
import pytest
pytest.importorskip("d2r_chargen.data.item_stat_cost",
                     reason="game data not extracted (run 'd2r-mod extract')")

from d2r_mcp.envelope import ok, error


def test_ok_minimal():
    assert ok() == {"status": "ok"}


def test_ok_with_payload():
    result = ok(character="Tempest", level=14)
    assert result == {"status": "ok", "character": "Tempest", "level": 14}


def test_ok_with_warnings():
    result = ok(warnings=["w1", "w2"])
    assert result == {"status": "ok", "warnings": ["w1", "w2"]}


def test_error_minimal():
    result = error("not_found", "no such character: Ghost")
    assert result == {
        "status": "error",
        "error": {"type": "not_found", "detail": "no such character: Ghost"},
    }


def test_error_with_extra_fields():
    result = error("scanner_failed", "5 hard errors", character="X", rolled_back=True)
    assert result["status"] == "error"
    assert result["error"] == {"type": "scanner_failed", "detail": "5 hard errors"}
    assert result["character"] == "X"
    assert result["rolled_back"] is True
