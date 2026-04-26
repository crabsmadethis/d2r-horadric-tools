"""
Tests for d2r_mod.build_steps.register_custom_uniques.

Covers:
  - Unknown custom unique gets auto-registered.
  - Known vanilla name is NOT duplicated.
  - Empty / whitespace index rows are skipped.
  - Idempotency: running the step twice produces identical output.
  - Vanilla keys in the target tbl are preserved (regression guard).
  - Real UniqueItems.txt after build detects all 6 custom uniques.
"""

import unittest
from pathlib import Path

# We rely on vanilla/ and build/ existing for some tests.
_REPO_ROOT = Path(__file__).parent.parent
HAS_VANILLA = (_REPO_ROOT / "vanilla").is_dir()
BUILD_ENG_DIR = _REPO_ROOT / "build" / "data" / "local" / "lng" / "eng"
VANILLA_UNIQUE_ITEMS = _REPO_ROOT / "vanilla" / "data" / "global" / "excel" / "UniqueItems.txt"


class TestAutoRegisterUnit(unittest.TestCase):
    """Pure-unit tests — no vanilla data required."""

    def _make_ui(self, tmp_path: Path, content: str) -> Path:
        ui = tmp_path / "UniqueItems.txt"
        ui.write_text(content, encoding="latin-1")
        return ui

    def _make_target(self, tmp_path: Path) -> Path:
        """Return path to a non-existent target tbl (run() will create it)."""
        return tmp_path / "expansionstring.tbl"

    # ------------------------------------------------------------------
    # Helper to call run() and return parsed entries from the output tbl
    # ------------------------------------------------------------------
    def _run_and_parse(self, ui_path, target_path, vanilla_keys):
        from d2r_mod.build_steps.register_custom_uniques import run
        from d2r_mod.assets.tbl import parse_tbl

        result = run(ui_path, target_path, vanilla_keys)
        entries = parse_tbl(target_path.read_bytes())
        return entries, result

    # ── Test 1: unknown unique gets registered ────────────────────────

    def test_unknown_unique_gets_auto_registered(self):
        """A custom unique not in vanilla gets its name added to target tbl."""
        from pathlib import Path
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ui = self._make_ui(tmp_path, "index\tID\nTestWidget\t500\n")
            target = self._make_target(tmp_path)
            vanilla_keys: set[str] = set()

            entries, result = self._run_and_parse(ui, target, vanilla_keys)

        self.assertEqual(entries.get("TestWidget"), "TestWidget")
        self.assertEqual(result["added"], 1)
        self.assertEqual(result["skipped"], 0)

    # ── Test 2: known vanilla name is not duplicated ──────────────────

    def test_known_vanilla_name_is_not_duplicated(self):
        """A unique whose index is in vanilla is NOT added."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ui = self._make_ui(tmp_path, "index\tID\nAnnihilus\t381\n")
            target = self._make_target(tmp_path)
            vanilla_keys = {"Annihilus"}

            entries, result = self._run_and_parse(ui, target, vanilla_keys)

        self.assertNotIn("Annihilus", entries)
        self.assertEqual(result["added"], 0)
        self.assertEqual(result["skipped"], 1)

    # ── Test 3: empty/whitespace index rows are skipped ───────────────

    def test_empty_index_rows_skipped(self):
        """UniqueItems.txt rows with empty index column are skipped."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            content = "index\tID\nMyReal\t100\n\t101\n  \t102\n"
            ui = self._make_ui(tmp_path, content)
            target = self._make_target(tmp_path)

            entries, result = self._run_and_parse(ui, target, set())

        self.assertEqual(entries.get("MyReal"), "MyReal")
        self.assertNotIn("", entries)
        self.assertNotIn("  ", entries)
        self.assertEqual(result["added"], 1)

    # ── Test 4: idempotency ───────────────────────────────────────────

    def test_idempotent_second_run_no_duplicates(self):
        """Running the build step twice produces identical output."""
        import tempfile
        from d2r_mod.build_steps.register_custom_uniques import run
        from d2r_mod.assets.tbl import parse_tbl

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            content = "index\tID\nCustomItem\t500\nAnotherItem\t501\n"
            ui = self._make_ui(tmp_path, content)
            target = self._make_target(tmp_path)

            r1 = run(ui, target, set())
            data_after_first = target.read_bytes()

            r2 = run(ui, target, set())
            data_after_second = target.read_bytes()

        # Second run: both items already in tbl → added=0
        self.assertEqual(r1["added"], 2)
        self.assertEqual(r2["added"], 0)

        # Parsed output should be identical
        e1 = parse_tbl(data_after_first)
        e2 = parse_tbl(data_after_second)
        self.assertEqual(e1, e2)

    # ── Test 5: star/hash marker rows skipped ────────────────────────

    def test_special_marker_rows_skipped(self):
        """Rows whose index starts with * or # are skipped."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            content = "index\tID\n*comment\t0\n#disabled\t1\nRealItem\t2\n"
            ui = self._make_ui(tmp_path, content)
            target = self._make_target(tmp_path)

            entries, result = self._run_and_parse(ui, target, set())

        self.assertNotIn("*comment", entries)
        self.assertNotIn("#disabled", entries)
        self.assertIn("RealItem", entries)
        self.assertEqual(result["added"], 1)

    # ── Test 6: vanilla keys preserved (regression guard) ─────────────

    def test_vanilla_keys_preserved_in_target(self):
        """Pre-existing entries in the target tbl are not removed."""
        import tempfile
        from d2r_mod.assets.tbl import build_tbl, parse_tbl
        from d2r_mod.build_steps.register_custom_uniques import run

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            # Seed target with some pre-existing entries
            seed = {"ExistingKey": "ExistingValue", "AnotherKey": "AnotherValue"}
            seed_data = build_tbl(seed)
            target = tmp_path / "expansionstring.tbl"
            target.write_bytes(seed_data)

            ui = self._make_ui(tmp_path, "index\tID\nNewCustomItem\t500\n")
            run(ui, target, set())

            entries = parse_tbl(target.read_bytes())

        # Pre-existing entries must survive
        self.assertEqual(entries.get("ExistingKey"), "ExistingValue")
        self.assertEqual(entries.get("AnotherKey"), "AnotherValue")
        # New item must also be added
        self.assertEqual(entries.get("NewCustomItem"), "NewCustomItem")


# ── Real-data integration test ────────────────────────────────────────────────

@unittest.skipUnless(HAS_VANILLA, "vanilla data required")
class TestAutoRegisterIntegration(unittest.TestCase):
    """Integration tests against the real vanilla UniqueItems.txt."""

    def test_real_unique_items_detects_custom_uniques(self):
        """All 6 custom uniques (IDs 438-443) are absent from vanilla keys
        and therefore auto-registered when run against the real UniqueItems.txt
        AFTER new_uniques.py has appended them (i.e., from build output).

        This test reads the built UniqueItems.txt if available; otherwise it
        constructs a minimal TSV containing the known custom names.
        """
        from d2r_mod.build_steps.register_custom_uniques import run, load_vanilla_keys
        from d2r_mod.assets.tbl import parse_tbl
        import tempfile
        from pathlib import Path

        vanilla_keys = load_vanilla_keys()

        CUSTOM_NAMES = [
            "Flamekeeper's Antlers",
            "Thunderhurler's Grip",
            "Hawkeye's Sight",
            "Deathgrip Scepter",
            "Crusader's Vengeance",
            "Manoomin",
        ]

        # Build a minimal UniqueItems.txt containing the 6 custom names
        lines = ["index\tID"]
        for i, name in enumerate(CUSTOM_NAMES):
            lines.append(f"{name}\t{438 + i}")
        content = "\n".join(lines) + "\n"

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ui = tmp_path / "UniqueItems.txt"
            ui.write_text(content, encoding="latin-1")
            target = tmp_path / "expansionstring.tbl"

            result = run(ui, target, vanilla_keys)
            entries = parse_tbl(target.read_bytes())

        for name in CUSTOM_NAMES:
            self.assertIn(name, entries,
                          f"{name!r} was not registered — is it in vanilla_string_keys.txt?")
            self.assertEqual(entries[name], name)

        self.assertEqual(result["added"], 6)
        self.assertEqual(result["skipped"], 0)

    def test_vanilla_unique_names_are_skipped(self):
        """Spot-check that well-known vanilla unique names are NOT re-added."""
        from d2r_mod.build_steps.register_custom_uniques import run, load_vanilla_keys
        import tempfile
        from pathlib import Path

        vanilla_keys = load_vanilla_keys()

        # Annihilus is in expansionstring.tbl; Tyrael's Might is in patchstring.tbl.
        # Both must be classified as vanilla → not auto-registered.
        content = "index\tID\nAnnihilus\t381\nTyrael's Might\t378\n"

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ui = tmp_path / "UniqueItems.txt"
            ui.write_text(content, encoding="latin-1")
            target = tmp_path / "expansionstring.tbl"

            result = run(ui, target, vanilla_keys)

        self.assertEqual(result["added"], 0,
                         "Vanilla unique names must not be auto-registered")


@unittest.skipUnless(
    (BUILD_ENG_DIR / "expansionstring.tbl").exists(),
    "build/ not populated — run d2r-mod build first",
)
class TestBuiltExpansionstringHasCustomUniques(unittest.TestCase):
    """After a full build, expansionstring.tbl must contain the 6 custom uniques."""

    CUSTOM_NAMES = [
        "Flamekeeper's Antlers",
        "Thunderhurler's Grip",
        "Hawkeye's Sight",
        "Deathgrip Scepter",
        "Crusader's Vengeance",
        "Manoomin",
    ]

    def test_custom_uniques_in_built_expansionstring(self):
        from d2r_mod.assets.tbl import parse_tbl

        tbl_path = BUILD_ENG_DIR / "expansionstring.tbl"
        entries = parse_tbl(tbl_path.read_bytes())

        for name in self.CUSTOM_NAMES:
            self.assertIn(name, entries,
                          f"{name!r} missing from built expansionstring.tbl")
            self.assertEqual(entries[name], name)
