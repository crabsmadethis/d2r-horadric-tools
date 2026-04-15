"""Test that missing chargen data files produce a helpful error."""
import importlib
import importlib.util
import sys
import pytest


def test_missing_data_gives_clear_error(monkeypatch):
    """If generated data modules are absent, CLI gives actionable message."""
    _real_find_spec = importlib.util.find_spec

    blocked = {
        'd2r_chargen.data.item_stat_cost',
        'd2r_chargen.data.item_bases',
        'd2r_chargen.data.item_dimensions',
        'd2r_chargen.data.runewords',
        'd2r_chargen.data.runeword_stats',
        'd2r_chargen.data.unique_items',
        'd2r_chargen.data.unique_item_stats',
        'd2r_chargen.data.set_items',
        'd2r_chargen.data.skills',
    }

    def _mock_find_spec(name, *args, **kwargs):
        if name in blocked:
            return None
        return _real_find_spec(name, *args, **kwargs)

    monkeypatch.setattr("importlib.util.find_spec", _mock_find_spec)

    from d2r_chargen.data import check_data_available
    with pytest.raises(SystemExit, match="1"):
        check_data_available()


@pytest.mark.integration
def test_data_available_passes_when_present():
    """Guard passes silently when all data modules exist."""
    from d2r_chargen.data import check_data_available
    # Should not raise — data files exist after extraction
    check_data_available()
