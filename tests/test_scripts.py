import unittest
import tempfile
import os
from d2r_mod.scripts import run_script


class TestRunScript(unittest.TestCase):
    def _write_script(self, tmpdir, name, code):
        path = os.path.join(tmpdir, name)
        with open(path, "w") as f:
            f.write(code)
        return path

    def test_basic_mutation(self):
        tables = {"test.txt": [{"Name": "A", "Value": "10"}]}
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_script(tmpdir, "s.py", """
def apply(tables):
    for row in tables['test.txt']:
        row['Value'] = str(int(row['Value']) * 2)
""")
            run_script(path, tables)
        self.assertEqual(tables["test.txt"][0]["Value"], "20")

    def test_row_count_validation(self):
        tables = {"test.txt": [{"Name": "A"}]}
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_script(tmpdir, "s.py", """
def apply(tables):
    tables['test.txt'].append({"Name": "B"})
""")
            with self.assertRaises(ValueError):
                run_script(path, tables)

    def test_warnings_returned(self):
        tables = {"test.txt": [{"Name": "A"}]}
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_script(tmpdir, "s.py", """
def apply(tables):
    return ["Skipped 1 row"]
""")
            warnings = run_script(path, tables)
        self.assertEqual(warnings, ["Skipped 1 row"])

    def test_no_return_is_ok(self):
        tables = {"test.txt": [{"Name": "A"}]}
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_script(tmpdir, "s.py", """
def apply(tables):
    pass
""")
            warnings = run_script(path, tables)
        self.assertEqual(warnings, [])

    def test_new_table_key_rejected(self):
        tables = {"test.txt": [{"Name": "A"}]}
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_script(tmpdir, "s.py", """
def apply(tables):
    tables['new.txt'] = [{"Name": "B"}]
""")
            with self.assertRaises(ValueError):
                run_script(path, tables)


    def test_allow_add_permits_new_rows(self):
        tables = {"test.txt": [{"Name": "A"}]}
        with tempfile.TemporaryDirectory() as d:
            script = os.path.join(d, "add_row.py")
            with open(script, "w") as f:
                f.write('def apply(tables):\n    tables["test.txt"].append({"Name": "B"})\n')
            from d2r_mod.scripts import run_script
            run_script(script, tables, allow_add=True)
        self.assertEqual(len(tables["test.txt"]), 2)

    def test_allow_add_still_rejects_removal(self):
        tables = {"test.txt": [{"Name": "A"}, {"Name": "B"}]}
        with tempfile.TemporaryDirectory() as d:
            script = os.path.join(d, "remove_row.py")
            with open(script, "w") as f:
                f.write('def apply(tables):\n    tables["test.txt"].pop()\n')
            from d2r_mod.scripts import run_script
            with self.assertRaises(ValueError):
                run_script(script, tables, allow_add=True)

    def test_default_mode_still_rejects_additions(self):
        tables = {"test.txt": [{"Name": "A"}]}
        with tempfile.TemporaryDirectory() as d:
            script = os.path.join(d, "add_row.py")
            with open(script, "w") as f:
                f.write('def apply(tables):\n    tables["test.txt"].append({"Name": "B"})\n')
            from d2r_mod.scripts import run_script
            with self.assertRaises(ValueError):
                run_script(script, tables)


if __name__ == "__main__":
    unittest.main()
