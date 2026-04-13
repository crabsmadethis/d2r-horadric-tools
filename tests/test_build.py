import unittest
import tempfile
import os
import shutil
from d2r_mod.build import build_mod
from d2r_mod.tsv import read_tsv_file, write_tsv_file


class TestBuildMod(unittest.TestCase):
    def _setup_vanilla(self, tmpdir):
        vanilla = os.path.join(tmpdir, "vanilla", "data", "global", "excel")
        os.makedirs(vanilla)
        write_tsv_file(
            os.path.join(vanilla, "Skills.txt"),
            [
                {"skill": "Frozen Orb", "EMin": "100", "mana": "30"},
                {"skill": "Blizzard", "EMin": "80", "mana": "25"},
            ],
        )
        return os.path.join(tmpdir, "vanilla")

    def _setup_overlay(self, tmpdir):
        overlays = os.path.join(tmpdir, "overlays")
        os.makedirs(overlays)
        with open(os.path.join(overlays, "01_skills.yaml"), "w") as f:
            f.write("""target: data/global/excel/Skills.txt
changes:
  - row: {skill: "Frozen Orb"}
    set:
      mana: 20
""")
        return overlays

    def test_basic_build(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            vanilla = self._setup_vanilla(tmpdir)
            overlays = self._setup_overlay(tmpdir)
            build_dir = os.path.join(tmpdir, "build")
            scripts_dir = os.path.join(tmpdir, "scripts")
            os.makedirs(scripts_dir)

            build_mod(
                vanilla_dir=vanilla,
                overlays_dir=overlays,
                scripts_dir=scripts_dir,
                build_dir=build_dir,
                regen=False,
            )

            out_path = os.path.join(build_dir, "data", "global", "excel", "Skills.txt")
            self.assertTrue(os.path.exists(out_path))
            rows = read_tsv_file(out_path)
            self.assertEqual(rows[0]["mana"], "20")
            self.assertEqual(rows[1]["mana"], "25")

    def test_missing_vanilla_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(FileNotFoundError):
                build_mod(
                    vanilla_dir=os.path.join(tmpdir, "nope"),
                    overlays_dir=os.path.join(tmpdir, "overlays"),
                    scripts_dir=os.path.join(tmpdir, "scripts"),
                    build_dir=os.path.join(tmpdir, "build"),
                    regen=False,
                )

    def test_idempotent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            vanilla = self._setup_vanilla(tmpdir)
            overlays = self._setup_overlay(tmpdir)
            build_dir = os.path.join(tmpdir, "build")
            scripts_dir = os.path.join(tmpdir, "scripts")
            os.makedirs(scripts_dir)

            build_mod(vanilla_dir=vanilla, overlays_dir=overlays,
                      scripts_dir=scripts_dir, build_dir=build_dir, regen=False)
            out1 = os.path.join(build_dir, "data", "global", "excel", "Skills.txt")
            content1 = open(out1).read()

            build_mod(vanilla_dir=vanilla, overlays_dir=overlays,
                      scripts_dir=scripts_dir, build_dir=build_dir, regen=False)
            content2 = open(out1).read()
            self.assertEqual(content1, content2)

    def test_overlay_targets_nonexistent_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            vanilla = self._setup_vanilla(tmpdir)
            overlays = os.path.join(tmpdir, "overlays")
            os.makedirs(overlays)
            with open(os.path.join(overlays, "bad.yaml"), "w") as f:
                f.write("target: data/global/excel/Nope.txt\nchanges: []\n")
            scripts_dir = os.path.join(tmpdir, "scripts")
            os.makedirs(scripts_dir)
            build_dir = os.path.join(tmpdir, "build")

            with self.assertRaises(FileNotFoundError):
                build_mod(vanilla_dir=vanilla, overlays_dir=overlays,
                          scripts_dir=scripts_dir, build_dir=build_dir, regen=False)


if __name__ == "__main__":
    unittest.main()
