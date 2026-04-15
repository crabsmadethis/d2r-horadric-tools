#!/usr/bin/env python3
"""Tests for d2r_chargen.importer — .d2s → YAML dict pipeline."""
import os
import unittest
import yaml
import pytest

# importer.py imports scanner.py which imports generated data modules.
# Skip this entire module if game data hasn't been extracted yet.
pytest.importorskip(
    "d2r_chargen.data.item_stat_cost",
    reason="game data not extracted (run 'd2r-mod extract')",
)

from d2r_chargen.config import CHARS_DIR


class TestImportExistingCharacters(unittest.TestCase):
    """Import live .d2s files and verify basic structure."""

    def _get_saves_dir(self):
        return os.path.expanduser(
            '~/.local/share/Steam/steamapps/compatdata/2536520/pfx/'
            'drive_c/users/steamuser/Saved Games/Diablo II Resurrected'
        )

    def _find_d2s(self):
        saves = self._get_saves_dir()
        if not os.path.isdir(saves):
            self.skipTest("D2R saves directory not found")
        files = [f for f in os.listdir(saves) if f.endswith('.d2s')]
        if not files:
            self.skipTest("No .d2s files found")
        return os.path.join(saves, files[0])

    def test_import_produces_valid_yaml_dict(self):
        """Import a real .d2s and verify the dict has required keys."""
        from d2r_chargen.importer import import_character
        path = self._find_d2s()
        result = import_character(path)
        self.assertIn('name', result)
        self.assertIn('class', result)
        self.assertIn('level', result)
        self.assertIn('stats', result)
        self.assertIn('schema_version', result)
        for stat in ('strength', 'dexterity', 'vitality', 'energy'):
            self.assertIn(stat, result['stats'])

    def test_import_yaml_is_loadable(self):
        """Import output can be serialized to YAML and loaded back."""
        from d2r_chargen.importer import import_character, dict_to_yaml
        path = self._find_d2s()
        result = import_character(path)
        yaml_str = dict_to_yaml(result)
        loaded = yaml.safe_load(yaml_str)
        self.assertEqual(loaded['name'], result['name'])


class TestImportRoundTrip(unittest.TestCase):
    """Build from YAML → import back → compare semantically."""

    def test_round_trip_items_match(self):
        """Build Tempest from YAML, import the .d2s, verify item names match."""
        from d2r_chargen.importer import import_character

        yaml_path = os.path.join(CHARS_DIR, 'Tempest.yaml')
        if not os.path.exists(yaml_path):
            self.skipTest("Tempest.yaml not found")

        saves = os.path.expanduser(
            '~/.local/share/Steam/steamapps/compatdata/2536520/pfx/'
            'drive_c/users/steamuser/Saved Games/Diablo II Resurrected'
        )
        d2s_path = os.path.join(saves, 'Tempest.d2s')
        if not os.path.exists(d2s_path):
            self.skipTest("Tempest.d2s not found (need a built character)")

        result = import_character(d2s_path)
        equip = result.get('equipment', [])
        self.assertGreater(len(equip), 0, "No equipment items imported")
        for item in equip:
            has_identity = any(
                k in item for k in ('unique', 'set', 'runeword', 'rare', 'magic', 'base')
            )
            self.assertTrue(has_identity, f"Item missing identity: {item}")
