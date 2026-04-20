"""Tests for Step 5c string table patching in the build pipeline."""

import os
import unittest

HAS_VANILLA = os.path.isdir(
    os.path.join(os.path.dirname(__file__), "..", "vanilla")
)
BUILD_DIR = os.path.join(os.path.dirname(__file__), "..", "build")


@unittest.skipUnless(HAS_VANILLA, "vanilla data required")
class TestStringPatches(unittest.TestCase):
    def test_build_output_has_patched_strings(self):
        """After a full build, patchstring.tbl must contain overrides."""
        from d2r_mod.assets.tbl import parse_tbl

        tbl_path = os.path.join(
            BUILD_DIR, "data", "local", "lng", "eng", "patchstring.tbl"
        )
        if not os.path.exists(tbl_path):
            self.skipTest("build/ not populated — run d2r-mod build first")

        with open(tbl_path, "rb") as f:
            entries = parse_tbl(f.read())

        self.assertEqual(entries.get("vps"), "Wild Rice Cake")
        self.assertEqual(entries.get("yps"), "Manoomin Tea")
        self.assertEqual(entries.get("wms"), "Wild Rice Soup")
        # "Manoomin" unique-name entry was removed from wild_rice.yaml;
        # it is now auto-registered in expansionstring.tbl by Step 5d.
        self.assertNotIn("Manoomin", entries,
                         "Manoomin unique-name should NOT be in patchstring.tbl "
                         "(it is auto-registered in expansionstring.tbl now)")

    def test_unmodified_strings_preserved(self):
        from d2r_mod.assets.tbl import parse_tbl

        tbl_path = os.path.join(
            BUILD_DIR, "data", "local", "lng", "eng", "patchstring.tbl"
        )
        if not os.path.exists(tbl_path):
            self.skipTest("build/ not populated — run d2r-mod build first")

        with open(tbl_path, "rb") as f:
            entries = parse_tbl(f.read())
        self.assertGreater(len(entries), 100)

    def test_string_config_format(self):
        """Verify all string patch YAMLs have required fields."""
        import yaml, glob

        patches_dir = os.path.join(os.path.dirname(__file__), "..",
                                   "patches", "strings")
        for path in glob.glob(os.path.join(patches_dir, "*.yaml")):
            if os.path.basename(path).startswith("_"):
                continue
            with open(path) as f:
                config = yaml.safe_load(f)
            self.assertIn("target", config, f"{path}: missing 'target'")
            self.assertIn("entries", config, f"{path}: missing 'entries'")
            for entry in config["entries"]:
                self.assertIn("key", entry, f"{path}: entry missing 'key'")
                self.assertIn("value", entry, f"{path}: entry missing 'value'")
