import unittest
from d2r_mod.diff import diff_tables, format_diff, summarize_diff


class TestDiffTables(unittest.TestCase):
    def test_changed_cell(self):
        vanilla = [{"skill": "Orb", "mana": "30"}]
        build = [{"skill": "Orb", "mana": "20"}]
        changes = diff_tables(vanilla, build, key_cols=["skill"])
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["row_key"], {"skill": "Orb"})
        self.assertEqual(changes[0]["column"], "mana")
        self.assertEqual(changes[0]["old"], "30")
        self.assertEqual(changes[0]["new"], "20")

    def test_no_changes(self):
        rows = [{"skill": "Orb", "mana": "30"}]
        changes = diff_tables(rows, rows, key_cols=["skill"])
        self.assertEqual(changes, [])

    def test_multiple_changes(self):
        vanilla = [{"skill": "Orb", "EMin": "100", "EMax": "200"}]
        build = [{"skill": "Orb", "EMin": "120", "EMax": "250"}]
        changes = diff_tables(vanilla, build, key_cols=["skill"])
        self.assertEqual(len(changes), 2)


    def test_added_rows(self):
        vanilla = [{"skill": "Orb", "mana": "30"}]
        build = [
            {"skill": "Orb", "mana": "30"},
            {"skill": "NewSpell", "mana": "50"},
        ]
        changes = diff_tables(vanilla, build, key_cols=["skill"])
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["row_key"], {"skill": "NewSpell"})
        self.assertEqual(changes[0]["column"], "mana")
        self.assertEqual(changes[0]["old"], "")
        self.assertEqual(changes[0]["new"], "50")
        self.assertTrue(changes[0]["added"])

    def test_added_rows_multiple_columns(self):
        vanilla = [{"skill": "Orb", "mana": "30", "EMin": "100"}]
        build = [
            {"skill": "Orb", "mana": "30", "EMin": "100"},
            {"skill": "NewSpell", "mana": "50", "EMin": "200"},
        ]
        changes = diff_tables(vanilla, build, key_cols=["skill"])
        self.assertEqual(len(changes), 2)
        self.assertTrue(all(c["added"] for c in changes))

    def test_added_rows_empty_cells_skipped(self):
        vanilla = [{"skill": "Orb", "mana": "30", "EMin": "100"}]
        build = [
            {"skill": "Orb", "mana": "30", "EMin": "100"},
            {"skill": "NewSpell", "mana": "50", "EMin": ""},
        ]
        changes = diff_tables(vanilla, build, key_cols=["skill"])
        # Empty EMin should not generate a change entry
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["column"], "mana")

    def test_existing_rows_not_marked_added(self):
        vanilla = [{"skill": "Orb", "mana": "30"}]
        build = [{"skill": "Orb", "mana": "20"}]
        changes = diff_tables(vanilla, build, key_cols=["skill"])
        self.assertFalse(changes[0]["added"])

    def test_build_fewer_rows_raises(self):
        vanilla = [{"skill": "Orb", "mana": "30"}, {"skill": "Nova", "mana": "25"}]
        build = [{"skill": "Orb", "mana": "30"}]
        with self.assertRaises(ValueError):
            diff_tables(vanilla, build, key_cols=["skill"])


class TestFormatDiff(unittest.TestCase):
    def test_format(self):
        changes = [{"row_key": {"skill": "Orb"}, "column": "mana", "old": "30", "new": "20"}]
        output = format_diff("Skills.txt", changes)
        self.assertIn("Orb", output)
        self.assertIn("30", output)
        self.assertIn("20", output)

    def test_format_diff_added(self):
        changes = [
            {"row_key": {"skill": "NewSpell"}, "column": "mana", "old": "", "new": "50", "added": True},
        ]
        output = format_diff("Skills.txt", changes)
        self.assertIn("[+]", output)
        self.assertIn("NewSpell", output)
        self.assertIn("50", output)

    def test_format_diff_non_added_no_plus_prefix(self):
        changes = [
            {"row_key": {"skill": "Orb"}, "column": "mana", "old": "30", "new": "20", "added": False},
        ]
        output = format_diff("Skills.txt", changes)
        self.assertNotIn("[+]", output)


class TestSummarizeDiff(unittest.TestCase):
    def test_summary(self):
        changes = [
            {"row_key": {"skill": "Orb"}, "column": "mana", "old": "30", "new": "20"},
            {"row_key": {"skill": "Orb"}, "column": "EMin", "old": "100", "new": "120"},
        ]
        output = summarize_diff("Skills.txt", changes)
        self.assertIn("Skills.txt", output)


class TestCmdDiffSummaryFooter(unittest.TestCase):
    """cmd_diff --summary must print a footer with the changed file count."""

    def _make_tsv(self, path, rows):
        import csv
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter="\t")
            writer.writeheader()
            writer.writerows(rows)

    def test_summary_footer_printed(self):
        """--summary mode must print '<N> file(s) with changes' after the per-file summaries."""
        import tempfile, os, argparse
        from unittest.mock import patch
        from d2r_mod import cli

        with tempfile.TemporaryDirectory() as root:
            vanilla_dir = os.path.join(root, "vanilla", "data", "global", "excel")
            build_dir = os.path.join(root, "build", "data", "global", "excel")
            os.makedirs(vanilla_dir)
            os.makedirs(build_dir)

            vanilla_rows = [{"skill": "Orb", "mana": "30"}]
            build_rows = [{"skill": "Orb", "mana": "20"}]
            self._make_tsv(os.path.join(vanilla_dir, "Skills.txt"), vanilla_rows)
            self._make_tsv(os.path.join(build_dir, "Skills.txt"), build_rows)

            args = argparse.Namespace(file=None, summary=True)
            printed = []
            with patch.object(cli, "_project_root", return_value=root):
                with patch("builtins.print", side_effect=lambda *a, **kw: printed.append(" ".join(str(x) for x in a))):
                    cli.cmd_diff(args)

        footer = printed[-1]
        self.assertIn("1 file(s) with changes", footer, f"Footer not found in output: {printed}")

    def test_summary_footer_zero_when_no_changes(self):
        """--summary must print '0 file(s) with changes' when nothing changed."""
        import tempfile, os, argparse
        from unittest.mock import patch
        from d2r_mod import cli

        with tempfile.TemporaryDirectory() as root:
            vanilla_dir = os.path.join(root, "vanilla", "data", "global", "excel")
            build_dir = os.path.join(root, "build", "data", "global", "excel")
            os.makedirs(vanilla_dir)
            os.makedirs(build_dir)

            rows = [{"skill": "Orb", "mana": "30"}]
            self._make_tsv(os.path.join(vanilla_dir, "Skills.txt"), rows)
            self._make_tsv(os.path.join(build_dir, "Skills.txt"), rows)

            args = argparse.Namespace(file=None, summary=True)
            printed = []
            with patch.object(cli, "_project_root", return_value=root):
                with patch("builtins.print", side_effect=lambda *a, **kw: printed.append(" ".join(str(x) for x in a))):
                    cli.cmd_diff(args)

        footer = printed[-1]
        self.assertIn("0 file(s) with changes", footer, f"Footer not found in output: {printed}")


if __name__ == "__main__":
    unittest.main()
