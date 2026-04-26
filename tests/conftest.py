"""Minimal test configuration for d2r-tools public repo."""
import os
import pytest


def pytest_collection_modifyitems(config, items):
    """Auto-skip integration tests if game data is not available."""
    data_dir = os.path.join(
        os.path.dirname(__file__), "..", "d2r_chargen", "data"
    )
    has_data = os.path.exists(os.path.join(data_dir, "unique_items.py"))
    if not has_data:
        skip = pytest.mark.skip(reason="game data not extracted (run 'd2r-mod extract')")
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip)
