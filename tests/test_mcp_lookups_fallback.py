"""MCP lookups graceful-degradation tests.

Public-repo fresh clones don't have game data extracted yet. d2r_mcp.lookups
must still import and let the server start; each lookup function returns a
typed "data not extracted" message instead of raising.
"""
import unittest
from unittest.mock import patch

from d2r_mcp import lookups


class TestNoDataFallback(unittest.TestCase):
    """With _HAS_DATA=False, every lookup returns the no-data message."""

    def _each_lookup(self):
        return [
            ("lookup_unique", ("soj",)),
            ("lookup_set_item", ("tal rasha",)),
            ("lookup_item_base", ("hax",)),
            ("lookup_runeword", ("enigma",)),
            ("lookup_stat", ("ed",)),
            ("lookup_skill", ("meteor",)),
            ("search_all", ("sword",)),
        ]

    def test_each_lookup_returns_no_data_message(self):
        with patch.object(lookups, "_HAS_DATA", False):
            for fn_name, args in self._each_lookup():
                fn = getattr(lookups, fn_name)
                result = fn(*args)
                self.assertIn(
                    "Game data not extracted",
                    result,
                    f"{fn_name} should return the no-data message when _HAS_DATA=False",
                )

    def test_module_imports_without_data(self):
        """Smoke test: module attributes exist and have sane fallback types."""
        self.assertIn(lookups._HAS_DATA, (True, False))
        self.assertIsInstance(lookups.UNIQUE_ITEMS, dict)
        self.assertIsInstance(lookups.SKILLS, dict)


if __name__ == "__main__":
    unittest.main()
