import unittest
import tempfile
import os
from d2r_mod.version import write_vanilla_version, read_vanilla_version, check_stale


class TestVanillaVersion(unittest.TestCase):
    def test_write_and_read(self):
        with tempfile.TemporaryDirectory() as d:
            write_vanilla_version(d, "abc123")
            info = read_vanilla_version(d)
            self.assertEqual(info["build_key"], "abc123")
            self.assertIn("timestamp", info)

    def test_read_missing(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(read_vanilla_version(d))

    def test_stale_detection(self):
        with tempfile.TemporaryDirectory() as vanilla_dir:
            write_vanilla_version(vanilla_dir, "old_key")
            with tempfile.TemporaryDirectory() as game_dir:
                build_info = "Branch!STRING:0|Active!DEC:1|Build Key!HEX:16\n|1|new_key\n"
                with open(os.path.join(game_dir, ".build.info"), "w") as f:
                    f.write(build_info)
                warning = check_stale(vanilla_dir, game_dir)
                self.assertIn("old_key", warning)
                self.assertIn("new_key", warning)

    def test_not_stale(self):
        with tempfile.TemporaryDirectory() as vanilla_dir:
            write_vanilla_version(vanilla_dir, "same_key")
            with tempfile.TemporaryDirectory() as game_dir:
                build_info = "Branch!STRING:0|Active!DEC:1|Build Key!HEX:16\n|1|same_key\n"
                with open(os.path.join(game_dir, ".build.info"), "w") as f:
                    f.write(build_info)
                self.assertIsNone(check_stale(vanilla_dir, game_dir))

    def test_missing_build_info_skips(self):
        with tempfile.TemporaryDirectory() as vanilla_dir:
            write_vanilla_version(vanilla_dir, "key")
            self.assertIsNone(check_stale(vanilla_dir, "/nonexistent"))

    def test_read_build_key_parses_pipe_delimited(self):
        """_read_build_key must parse pipe-delimited .build.info correctly."""
        from d2r_mod.version import _read_build_key
        with tempfile.TemporaryDirectory() as tmpdir:
            build_info = os.path.join(tmpdir, ".build.info")
            with open(build_info, "w") as f:
                f.write("Branch!STRING:0|Active!DEC:1|Build Key!HEX:16\n")
                f.write("|1|1e0838cffde2b9cb56f212d243eee4ec\n")
            result = _read_build_key(tmpdir)
            self.assertEqual(result, "1e0838cffde2b9cb56f212d243eee4ec")


if __name__ == "__main__":
    unittest.main()
