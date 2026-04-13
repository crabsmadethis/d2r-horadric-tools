import unittest
from d2r_mod.tsv import read_tsv, write_tsv


class TestReadTsv(unittest.TestCase):
    def test_basic_parse(self):
        content = "Name\tLevel\tDamage\nFrozen Orb\t30\t120\nBlizzard\t24\t80\n"
        rows = read_tsv(content)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0], {"Name": "Frozen Orb", "Level": "30", "Damage": "120"})
        self.assertEqual(rows[1], {"Name": "Blizzard", "Level": "24", "Damage": "80"})

    def test_bom_stripped(self):
        content = "\ufeffName\tLevel\nTest\t1\n"
        rows = read_tsv(content)
        self.assertEqual(list(rows[0].keys())[0], "Name")

    def test_crlf_normalized(self):
        content = "Name\tLevel\r\nTest\t1\r\n"
        rows = read_tsv(content)
        self.assertEqual(rows[0], {"Name": "Test", "Level": "1"})

    def test_empty_cells(self):
        content = "A\tB\tC\nfoo\t\tbar\n"
        rows = read_tsv(content)
        self.assertEqual(rows[0], {"A": "foo", "B": "", "C": "bar"})

    def test_trailing_empty_columns(self):
        content = "A\tB\tC\nfoo\t\t\n"
        rows = read_tsv(content)
        self.assertEqual(rows[0], {"A": "foo", "B": "", "C": ""})

    def test_empty_file(self):
        content = "Name\tLevel\n"
        rows = read_tsv(content)
        self.assertEqual(rows, [])

    def test_bom_only_file(self):
        content = "\ufeff\n"
        rows = read_tsv(content)
        self.assertEqual(rows, [])

    def test_extra_columns_preserved(self):
        content = "A\tB\nfoo\tbar\textra\n"
        rows = read_tsv(content)
        self.assertEqual(rows[0]["A"], "foo")
        self.assertEqual(rows[0]["B"], "bar")
        self.assertEqual(rows[0]["_extra_2"], "extra")


class TestWriteTsv(unittest.TestCase):
    def test_roundtrip(self):
        original = "Name\tLevel\tDamage\nFrozen Orb\t30\t120\nBlizzard\t24\t80\n"
        rows = read_tsv(original)
        output = write_tsv(rows)
        reparsed = read_tsv(output)
        self.assertEqual(rows, reparsed)

    def test_explicit_headers(self):
        rows = [{"B": "2", "A": "1"}]
        output = write_tsv(rows, headers=["A", "B"])
        self.assertTrue(output.startswith("A\tB\r\n"))

    def test_crlf_output(self):
        rows = [{"A": "1"}]
        output = write_tsv(rows)
        self.assertIn("\r\n", output)
        self.assertNotIn("\n\n", output.replace("\r\n", "\n"))

    def test_missing_key_becomes_empty(self):
        rows = [{"A": "1"}]
        output = write_tsv(rows, headers=["A", "B"])
        self.assertIn("1\t\r\n", output)


if __name__ == "__main__":
    unittest.main()
