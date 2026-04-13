import unittest
from d2r_mod.overlay import load_overlay, apply_overlay


SAMPLE_ROWS = [
    {"skill": "Frozen Orb", "EMin": "120", "EMax": "180", "mana": "30"},
    {"skill": "Blizzard", "EMin": "80", "EMax": "100", "mana": "25"},
]


class TestLoadOverlay(unittest.TestCase):
    def test_load_yaml(self):
        yaml_str = """
target: data/global/excel/Skills.txt
changes:
  - row: {skill: "Frozen Orb"}
    set:
      mana: 20
"""
        overlay = load_overlay(yaml_str)
        self.assertEqual(overlay["target"], "data/global/excel/Skills.txt")
        self.assertEqual(len(overlay["changes"]), 1)
        self.assertEqual(overlay["changes"][0]["set"]["mana"], 20)


class TestApplyOverlay(unittest.TestCase):
    def _rows(self):
        import copy
        return copy.deepcopy(SAMPLE_ROWS)

    def test_set_operation(self):
        rows = self._rows()
        overlay = {
            "target": "test.txt",
            "changes": [{"row": {"skill": "Frozen Orb"}, "set": {"mana": 20}}],
        }
        apply_overlay(rows, overlay)
        self.assertEqual(rows[0]["mana"], "20")

    def test_multiply_operation(self):
        rows = self._rows()
        overlay = {
            "target": "test.txt",
            "changes": [{"row": {"skill": "Blizzard"}, "multiply": {"EMin": 1.3}}],
        }
        apply_overlay(rows, overlay)
        self.assertEqual(rows[1]["EMin"], "104")

    def test_add_operation(self):
        rows = self._rows()
        overlay = {
            "target": "test.txt",
            "changes": [{"row": {"skill": "Frozen Orb"}, "add": {"mana": -5}}],
        }
        apply_overlay(rows, overlay)
        self.assertEqual(rows[0]["mana"], "25")

    def test_skip_empty_cells_multiply(self):
        rows = [{"skill": "Test", "EMin": "", "EMax": "100"}]
        overlay = {
            "target": "test.txt",
            "changes": [{"row": {"skill": "Test"}, "multiply": {"EMin": 2.0, "EMax": 2.0}}],
        }
        apply_overlay(rows, overlay)
        self.assertEqual(rows[0]["EMin"], "")
        self.assertEqual(rows[0]["EMax"], "200")

    def test_error_on_zero_matches(self):
        rows = self._rows()
        overlay = {
            "target": "test.txt",
            "changes": [{"row": {"skill": "Fireball"}, "set": {"mana": 10}}],
        }
        with self.assertRaises(ValueError):
            apply_overlay(rows, overlay)

    def test_error_on_multiple_matches(self):
        rows = self._rows() + [{"skill": "Frozen Orb", "EMin": "50", "EMax": "60", "mana": "15"}]
        overlay = {
            "target": "test.txt",
            "changes": [{"row": {"skill": "Frozen Orb"}, "set": {"mana": 10}}],
        }
        with self.assertRaises(ValueError):
            apply_overlay(rows, overlay)

    def test_error_on_non_numeric_multiply(self):
        rows = [{"skill": "Test", "EMin": "abc"}]
        overlay = {
            "target": "test.txt",
            "changes": [{"row": {"skill": "Test"}, "multiply": {"EMin": 2.0}}],
        }
        with self.assertRaises(ValueError):
            apply_overlay(rows, overlay)

    def test_empty_changes(self):
        rows = self._rows()
        import copy
        original = copy.deepcopy(rows)
        overlay = {"target": "test.txt", "changes": []}
        warnings = apply_overlay(rows, overlay)
        self.assertEqual(warnings, [])
        self.assertEqual(rows, original)

    def test_yaml_bool_in_selector(self):
        rows = [{"skill": "Orb", "enabled": "1"}]
        overlay = {
            "target": "test.txt",
            "changes": [{"row": {"enabled": True}, "set": {"skill": "Changed"}}],
        }
        apply_overlay(rows, overlay)
        self.assertEqual(rows[0]["skill"], "Changed")

    def test_set_yaml_bool_writes_1_not_true(self):
        """set with YAML True writes '1', not 'True'."""
        rows = [{"skill": "Orb", "enabled": "0"}]
        overlay = {
            "target": "test.txt",
            "changes": [{"row": {"skill": "Orb"}, "set": {"enabled": True}}],
        }
        apply_overlay(rows, overlay)
        self.assertEqual(rows[0]["enabled"], "1")

    def test_set_yaml_none_writes_empty(self):
        """set with YAML null writes '', not 'None'."""
        rows = [{"skill": "Orb", "mana": "30"}]
        overlay = {
            "target": "test.txt",
            "changes": [{"row": {"skill": "Orb"}, "set": {"mana": None}}],
        }
        apply_overlay(rows, overlay)
        self.assertEqual(rows[0]["mana"], "")


class TestLevelScaledColumns(unittest.TestCase):
    def test_expand_base_name(self):
        rows = [{"skill": "Orb", "EMin1": "10", "EMin2": "20", "EMin3": "30", "EMax": "100"}]
        overlay = {
            "target": "test.txt",
            "changes": [{"row": {"skill": "Orb"}, "multiply": {"EMin": 2.0}}],
        }
        apply_overlay(rows, overlay)
        self.assertEqual(rows[0]["EMin1"], "20")
        self.assertEqual(rows[0]["EMin2"], "40")
        self.assertEqual(rows[0]["EMin3"], "60")
        self.assertEqual(rows[0]["EMax"], "100")

    def test_specific_column(self):
        rows = [{"skill": "Orb", "EMin1": "10", "EMin2": "20"}]
        overlay = {
            "target": "test.txt",
            "changes": [{"row": {"skill": "Orb"}, "set": {"EMin2": 99}}],
        }
        apply_overlay(rows, overlay)
        self.assertEqual(rows[0]["EMin1"], "10")
        self.assertEqual(rows[0]["EMin2"], "99")

    def test_literal_column_exists(self):
        rows = [{"skill": "Orb", "mana": "30", "mana1": "5"}]
        overlay = {
            "target": "test.txt",
            "changes": [{"row": {"skill": "Orb"}, "set": {"mana": 20}}],
        }
        apply_overlay(rows, overlay)
        self.assertEqual(rows[0]["mana"], "20")
        self.assertEqual(rows[0]["mana1"], "5")


if __name__ == "__main__":
    unittest.main()
