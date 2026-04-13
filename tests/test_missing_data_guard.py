"""Test that missing chargen data files produce a helpful error."""
import importlib
import importlib.util
import sys
import pytest


def test_missing_data_gives_clear_error(monkeypatch):
    """If generated data modules are absent, importing d2r_chargen gives actionable message."""
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

    # Clear cached modules so the guard re-runs
    for mod in list(sys.modules):
        if mod.startswith("d2r_chargen"):
            del sys.modules[mod]

    with pytest.raises(SystemExit, match="1"):
        importlib.import_module("d2r_chargen")
