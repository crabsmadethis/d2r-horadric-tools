#!/usr/bin/env python3
"""Tests for d2r_chargen.diff — .d2s file comparison."""
import os
import struct
import unittest
import pytest

# diff.py imports scanner.py which imports generated data modules.
pytest.importorskip(
    "d2r_chargen.data.item_stat_cost",
    reason="game data not extracted (run 'd2r-mod extract')",
)


class TestDiffSameFile(unittest.TestCase):
    """Diffing a file against itself should show no changes."""

    def _find_d2s(self):
        saves = os.path.expanduser(
            '~/.local/share/Steam/steamapps/compatdata/2536520/pfx/'
            'drive_c/users/steamuser/Saved Games/Diablo II Resurrected'
        )
        if not os.path.isdir(saves):
            self.skipTest("D2R saves directory not found")
        files = [f for f in os.listdir(saves) if f.endswith('.d2s')]
        if not files:
            self.skipTest("No .d2s files found")
        return os.path.join(saves, files[0])

    def test_no_diff_self(self):
        """Diffing a file against itself produces no changes."""
        from d2r_chargen.diff import diff_saves
        path = self._find_d2s()
        result = diff_saves(path, path)
        self.assertEqual(result['header_changes'], [])
        self.assertEqual(result['stat_changes'], [])
        self.assertEqual(result['items_added'], [])
        self.assertEqual(result['items_removed'], [])


class TestDiffModifiedLevel(unittest.TestCase):
    """Diff detects a level change."""

    def test_level_change_detected(self):
        """Modifying level byte produces a header diff."""
        from d2r_chargen.diff import diff_saves
        import tempfile

        saves = os.path.expanduser(
            '~/.local/share/Steam/steamapps/compatdata/2536520/pfx/'
            'drive_c/users/steamuser/Saved Games/Diablo II Resurrected'
        )
        if not os.path.isdir(saves):
            self.skipTest("D2R saves directory not found")
        files = [f for f in os.listdir(saves) if f.endswith('.d2s')]
        if not files:
            self.skipTest("No .d2s files found")
        original = os.path.join(saves, files[0])

        with tempfile.NamedTemporaryFile(suffix='.d2s', delete=False) as tmp:
            data = bytearray(open(original, 'rb').read())
            # Bump level, but handle lv99 edge case by decrementing instead
            original_level = data[0x1B]
            if original_level < 99:
                data[0x1B] = original_level + 1
            else:
                data[0x1B] = original_level - 1
            tmp.write(data)
            tmp_path = tmp.name

        try:
            result = diff_saves(original, tmp_path)
            level_changes = [c for c in result['header_changes'] if c['field'] == 'level']
            self.assertEqual(len(level_changes), 1)
        finally:
            os.unlink(tmp_path)


if __name__ == '__main__':
    unittest.main()
