"""Minimal test configuration for d2r-tools public repo."""
import os
import pytest


def _has_game_data():
    """Check if generated data modules are available."""
    data_dir = os.path.join(
        os.path.dirname(__file__), "..", "d2r_chargen", "data"
    )
    return os.path.exists(os.path.join(data_dir, "unique_items.py"))

HAS_DATA = _has_game_data()


def pytest_collection_modifyitems(config, items):
    """Auto-skip integration tests if game data is not available."""
    if not HAS_DATA:
        skip = pytest.mark.skip(reason="game data not extracted (run 'd2r-mod extract')")
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip)
