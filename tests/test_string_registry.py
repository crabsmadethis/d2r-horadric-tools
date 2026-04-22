"""Tests for d2r_mod.build_steps.build_string_registry."""

import json
import os
import unittest
from pathlib import Path

from d2r_mod.assets.tbl import build_tbl, parse_tbl


class TestBuildStringRegistryUnit(unittest.TestCase):
    """Pure-unit tests — no vanilla data required."""

    def _make_tbl(self, tmp: Path, subdir: str, name: str, entries: dict) -> Path:
        """Write a .tbl file under tmp/subdir/data/local/lng/eng/name.tbl."""
        tbl_dir = tmp / subdir / "data" / "local" / "lng" / "eng"
        tbl_dir.mkdir(parents=True, exist_ok=True)
        path = tbl_dir / f"{name}.tbl"
        path.write_bytes(build_tbl(entries))
        return path

    def test_detects_custom_entries(self):
        """Custom entries in built .tbl but not in vanilla appear in registry."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            self._make_tbl(tmp, "vanilla", "expansionstring",
                           {"Annihilus": "Annihilus"})
            self._make_tbl(tmp, "build", "expansionstring",
                           {"Annihilus": "Annihilus", "Manoomin": "Manoomin"})

            from d2r_mod.build_steps.build_string_registry import run
            registry = run(
                build_dir=str(tmp / "build"),
                vanilla_dir=str(tmp / "vanilla"),
            )

            self.assertIn("expansionstring", registry)
            self.assertEqual(registry["expansionstring"]["Manoomin"], "Manoomin")
            self.assertNotIn("Annihilus", registry["expansionstring"])

    def test_empty_when_no_custom_strings(self):
        """Registry is empty when built .tbl matches vanilla exactly."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            entries = {"Annihilus": "Annihilus", "SomeKey": "SomeValue"}
            self._make_tbl(tmp, "vanilla", "expansionstring", entries)
            self._make_tbl(tmp, "build", "expansionstring", entries)

            from d2r_mod.build_steps.build_string_registry import run
            registry = run(
                build_dir=str(tmp / "build"),
                vanilla_dir=str(tmp / "vanilla"),
            )

            custom = registry.get("expansionstring", {})
            self.assertEqual(len(custom), 0)

    def test_multiple_tables(self):
        """Registry groups custom strings by source table name."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            self._make_tbl(tmp, "vanilla", "expansionstring",
                           {"Annihilus": "Annihilus"})
            self._make_tbl(tmp, "vanilla", "patchstring",
                           {"vps": "Minor Healing Potion"})
            self._make_tbl(tmp, "build", "expansionstring",
                           {"Annihilus": "Annihilus", "Manoomin": "Manoomin"})
            self._make_tbl(tmp, "build", "patchstring",
                           {"vps": "Wild Rice Cake", "yps": "Manoomin Tea"})

            from d2r_mod.build_steps.build_string_registry import run
            registry = run(
                build_dir=str(tmp / "build"),
                vanilla_dir=str(tmp / "vanilla"),
            )

            self.assertEqual(registry["expansionstring"]["Manoomin"], "Manoomin")
            self.assertEqual(registry["patchstring"]["vps"], "Wild Rice Cake")
            self.assertEqual(registry["patchstring"]["yps"], "Manoomin Tea")

    def test_modified_value_counts_as_custom(self):
        """A key that exists in vanilla but with a different value is custom."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            self._make_tbl(tmp, "vanilla", "patchstring",
                           {"vps": "Minor Healing Potion"})
            self._make_tbl(tmp, "build", "patchstring",
                           {"vps": "Wild Rice Cake"})

            from d2r_mod.build_steps.build_string_registry import run
            registry = run(
                build_dir=str(tmp / "build"),
                vanilla_dir=str(tmp / "vanilla"),
            )

            self.assertEqual(registry["patchstring"]["vps"], "Wild Rice Cake")

    def test_json_output(self):
        """run() writes string_registry.json to build_dir when write=True."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            self._make_tbl(tmp, "vanilla", "expansionstring",
                           {"Annihilus": "Annihilus"})
            self._make_tbl(tmp, "build", "expansionstring",
                           {"Annihilus": "Annihilus", "Manoomin": "Manoomin"})

            from d2r_mod.build_steps.build_string_registry import run
            run(
                build_dir=str(tmp / "build"),
                vanilla_dir=str(tmp / "vanilla"),
                write=True,
            )

            json_path = tmp / "build" / "string_registry.json"
            self.assertTrue(json_path.exists())
            with open(json_path) as f:
                data = json.load(f)
            self.assertEqual(data["expansionstring"]["Manoomin"], "Manoomin")

    def test_no_tbl_files_produces_empty_registry(self):
        """If no .tbl files exist in either dir, registry is empty."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "vanilla").mkdir()
            (tmp / "build").mkdir()

            from d2r_mod.build_steps.build_string_registry import run
            registry = run(
                build_dir=str(tmp / "build"),
                vanilla_dir=str(tmp / "vanilla"),
            )

            self.assertEqual(registry, {})


_REPO_ROOT = Path(__file__).parent.parent
HAS_VANILLA = (_REPO_ROOT / "vanilla").is_dir()
BUILD_DIR = _REPO_ROOT / "build"


@unittest.skipUnless(HAS_VANILLA, "vanilla data required")
class TestStringRegistryIntegration(unittest.TestCase):
    """Integration tests — require vanilla data and a completed build."""

    def test_build_produces_registry_json(self):
        """After a full build, build/string_registry.json must exist."""
        registry_path = BUILD_DIR / "string_registry.json"
        if not registry_path.exists():
            self.skipTest("build/ not populated — run d2r-mod build first")

        with open(registry_path) as f:
            registry = json.load(f)

        exp = registry.get("expansionstring", {})
        self.assertIn("Manoomin", exp, "Manoomin should be in registry")

    def test_registry_contains_string_patches(self):
        """String patch entries (wild_rice.yaml) appear in registry."""
        registry_path = BUILD_DIR / "string_registry.json"
        if not registry_path.exists():
            self.skipTest("build/ not populated — run d2r-mod build first")

        with open(registry_path) as f:
            registry = json.load(f)

        patch = registry.get("patchstring", {})
        self.assertEqual(patch.get("vps"), "Wild Rice Cake")
        self.assertEqual(patch.get("yps"), "Manoomin Tea")

    def test_registry_excludes_vanilla_strings(self):
        """Vanilla strings must NOT appear in the registry."""
        registry_path = BUILD_DIR / "string_registry.json"
        if not registry_path.exists():
            self.skipTest("build/ not populated — run d2r-mod build first")

        with open(registry_path) as f:
            registry = json.load(f)

        for table_name, entries in registry.items():
            self.assertNotIn("Annihilus", entries,
                             f"Vanilla string 'Annihilus' found in {table_name}")
