import importlib.util
import json
import unittest
import tempfile
import os
from d2r_mod.deploy import (
    deploy_mod, undeploy_mod, StaleVanillaError, MOD_NAME,
    _build_launch_options, _LIBPATCH_SO,
)
from d2r_mod.version import write_vanilla_version

HAS_HOST = importlib.util.find_spec("d2r_mod.host") is not None


class TestDeploy(unittest.TestCase):
    def test_deploy_creates_mod_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            build_dir = os.path.join(tmpdir, "build")
            os.makedirs(os.path.join(build_dir, "data", "global", "excel"))
            with open(os.path.join(build_dir, "data", "global", "excel", "Skills.txt"), "w") as f:
                f.write("test")

            game_dir = os.path.join(tmpdir, "game")
            os.makedirs(game_dir)

            deploy_mod(build_dir, game_dir)

            expected = os.path.join(
                game_dir, "mods", MOD_NAME, f"{MOD_NAME}.mpq",
                "data", "global", "excel", "Skills.txt"
            )
            self.assertTrue(os.path.exists(expected))

    def test_undeploy_removes_mod_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            game_dir = os.path.join(tmpdir, "game")
            mod_dir = os.path.join(game_dir, "mods", MOD_NAME)
            os.makedirs(mod_dir)
            with open(os.path.join(mod_dir, "test"), "w") as f:
                f.write("x")

            undeploy_mod(game_dir)
            self.assertFalse(os.path.exists(mod_dir))

    def test_deploy_missing_build_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(FileNotFoundError):
                deploy_mod(os.path.join(tmpdir, "nope"), tmpdir)

    def _make_stale_env(self, tmpdir):
        """Create a build_dir, game_dir with mismatched version, and vanilla_dir."""
        build_dir = os.path.join(tmpdir, "build")
        os.makedirs(os.path.join(build_dir, "data"))
        with open(os.path.join(build_dir, "data", "test.txt"), "w") as f:
            f.write("test")

        game_dir = os.path.join(tmpdir, "game")
        os.makedirs(game_dir)
        with open(os.path.join(game_dir, ".build.info"), "w") as f:
            f.write("Branch!STRING:0|Active!DEC:1|Build Key!HEX:16\n")
            f.write("|1|new_key\n")

        vanilla_dir = os.path.join(tmpdir, "vanilla")
        os.makedirs(vanilla_dir)
        write_vanilla_version(vanilla_dir, "old_key")

        return build_dir, game_dir, vanilla_dir

    def test_deploy_stale_vanilla_raises(self):
        """deploy_mod raises StaleVanillaError when vanilla data is stale."""
        with tempfile.TemporaryDirectory() as tmpdir:
            build_dir, game_dir, vanilla_dir = self._make_stale_env(tmpdir)
            with self.assertRaises(StaleVanillaError) as ctx:
                deploy_mod(build_dir, game_dir, vanilla_dir=vanilla_dir)
            self.assertIn("old_key", str(ctx.exception))
            self.assertIn("new_key", str(ctx.exception))
            self.assertIn("--force", str(ctx.exception))

    def test_deploy_stale_vanilla_force_succeeds(self):
        """deploy_mod with force=True proceeds despite stale vanilla data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            build_dir, game_dir, vanilla_dir = self._make_stale_env(tmpdir)
            deploy_mod(build_dir, game_dir, force=True, vanilla_dir=vanilla_dir)
            # Verify files were deployed
            mod_root = os.path.join(
                game_dir, "mods", MOD_NAME, f"{MOD_NAME}.mpq",
                "data", "test.txt"
            )
            self.assertTrue(os.path.exists(mod_root))

    def test_deploy_no_vanilla_dir_skips_stale_check(self):
        """deploy_mod without vanilla_dir never raises StaleVanillaError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            build_dir = os.path.join(tmpdir, "build")
            os.makedirs(build_dir)
            with open(os.path.join(build_dir, "f.txt"), "w") as f:
                f.write("x")
            game_dir = os.path.join(tmpdir, "game")
            os.makedirs(game_dir)
            # No vanilla_dir passed — should not raise
            deploy_mod(build_dir, game_dir, vanilla_dir=None)

    def test_deploy_matching_version_succeeds(self):
        """deploy_mod succeeds when vanilla version matches game version."""
        with tempfile.TemporaryDirectory() as tmpdir:
            build_dir = os.path.join(tmpdir, "build")
            os.makedirs(build_dir)
            with open(os.path.join(build_dir, "f.txt"), "w") as f:
                f.write("x")
            game_dir = os.path.join(tmpdir, "game")
            os.makedirs(game_dir)
            with open(os.path.join(game_dir, ".build.info"), "w") as f:
                f.write("Branch!STRING:0|Active!DEC:1|Build Key!HEX:16\n")
                f.write("|1|same_key\n")
            vanilla_dir = os.path.join(tmpdir, "vanilla")
            os.makedirs(vanilla_dir)
            write_vanilla_version(vanilla_dir, "same_key")
            # Should not raise
            deploy_mod(build_dir, game_dir, vanilla_dir=vanilla_dir)


    def _make_game_with_patch_config(self, tmpdir, patch_file_exists=False):
        """Create a game dir with a CASC build config referencing a patch-config."""
        build_key = "53d723307439a5c934957add0e81532f"
        patch_key = "847b3ca727f8e9940c537c39f59917b3"

        game_dir = os.path.join(tmpdir, "game")
        os.makedirs(game_dir)
        with open(os.path.join(game_dir, ".build.info"), "w") as f:
            f.write("Branch!STRING:0|Active!DEC:1|Build Key!HEX:16\n")
            f.write(f"|1|{build_key}\n")

        config_dir = os.path.join(
            game_dir, "data", "config",
            build_key[:2], build_key[2:4],
        )
        os.makedirs(config_dir)
        config_path = os.path.join(config_dir, build_key)
        with open(config_path, "w") as f:
            f.write("# Build Configuration\n\n")
            f.write("root = abc123\n")
            f.write("encoding = def456\n")
            f.write("patch-index = aaa bbb\n")
            f.write("patch-index-size = 100 200\n")
            f.write("patch = ccc\n")
            f.write("patch-size = 300\n")
            f.write(f"patch-config = {patch_key}\n")
            f.write("build-name = 92198\n")

        if patch_file_exists:
            pk_dir = os.path.join(
                game_dir, "data", "config",
                patch_key[:2], patch_key[2:4],
            )
            os.makedirs(pk_dir, exist_ok=True)
            with open(os.path.join(pk_dir, patch_key), "w") as f:
                f.write("# Patch config\n")

        return game_dir, config_path

    def test_strip_patch_config_removes_lines(self):
        """_strip_patch_config removes patch-* lines when file is missing."""
        from d2r_mod.deploy import _strip_patch_config
        with tempfile.TemporaryDirectory() as tmpdir:
            game_dir, config_path = self._make_game_with_patch_config(tmpdir)
            _strip_patch_config(game_dir)
            with open(config_path) as f:
                content = f.read()
            self.assertNotIn("patch-config", content)
            self.assertNotIn("patch-index", content)
            self.assertIn("root = abc123", content)
            self.assertIn("build-name = 92198", content)
            # Original backup should exist
            self.assertTrue(os.path.isfile(config_path + ".original"))

    def test_strip_patch_config_skips_when_file_exists(self):
        """_strip_patch_config does nothing when patch-config file exists locally."""
        from d2r_mod.deploy import _strip_patch_config
        with tempfile.TemporaryDirectory() as tmpdir:
            game_dir, config_path = self._make_game_with_patch_config(
                tmpdir, patch_file_exists=True
            )
            _strip_patch_config(game_dir)
            with open(config_path) as f:
                content = f.read()
            self.assertIn("patch-config", content)  # not stripped


class TestLaunchOptions(unittest.TestCase):

    def test_base_options_without_libpatch(self):
        """Without libpatch.so, returns base launch options."""
        if os.path.isfile(_LIBPATCH_SO):
            self.skipTest("libpatch.so exists — test only valid before compilation")
        opts = _build_launch_options("/some/game/dir")
        self.assertEqual(opts, "%command% -mod rebalance -txt")
        self.assertNotIn("LD_PRELOAD", opts)

    def test_options_contain_command(self):
        """Launch options always contain %command% and -mod."""
        opts = _build_launch_options("/some/game/dir")
        self.assertIn("%command%", opts)
        self.assertIn("-mod rebalance", opts)


@unittest.skipUnless(HAS_HOST, "d2r_mod.host not available (private-repo only)")
class TestDeployPatchesJson(unittest.TestCase):

    def test_deploy_creates_patches_json(self):
        """deploy_mod creates patches.json in game_dir."""
        with tempfile.TemporaryDirectory() as tmpdir:
            build_dir = os.path.join(tmpdir, "build")
            os.makedirs(build_dir)
            with open(os.path.join(build_dir, "test.txt"), "w") as f:
                f.write("x")

            game_dir = os.path.join(tmpdir, "game")
            os.makedirs(game_dir)

            deploy_mod(build_dir, game_dir)

            patches_json = os.path.join(game_dir, "patches.json")
            self.assertTrue(os.path.isfile(patches_json))

            with open(patches_json) as f:
                data = json.load(f)
            self.assertIn("version", data)
            self.assertNotIn("guard_patterns", data)
            self.assertIn("patches", data)

    def test_deploy_creates_manifest(self):
        """deploy_mod creates deploy_manifest.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            build_dir = os.path.join(tmpdir, "build")
            os.makedirs(build_dir)
            with open(os.path.join(build_dir, "test.txt"), "w") as f:
                f.write("x")

            game_dir = os.path.join(tmpdir, "game")
            os.makedirs(game_dir)

            deploy_mod(build_dir, game_dir)

            manifest = os.path.join(game_dir, "deploy_manifest.json")
            self.assertTrue(os.path.isfile(manifest))
            with open(manifest) as f:
                data = json.load(f)
            self.assertIn("deployed_at", data)
            self.assertIn("patches_json_sha256", data)

    def test_deploy_creates_disable_script(self):
        """deploy_mod creates disable_patches.sh."""
        with tempfile.TemporaryDirectory() as tmpdir:
            build_dir = os.path.join(tmpdir, "build")
            os.makedirs(build_dir)
            with open(os.path.join(build_dir, "test.txt"), "w") as f:
                f.write("x")

            game_dir = os.path.join(tmpdir, "game")
            os.makedirs(game_dir)

            deploy_mod(build_dir, game_dir)

            disable = os.path.join(game_dir, "disable_patches.sh")
            self.assertTrue(os.path.isfile(disable))
            self.assertTrue(os.access(disable, os.X_OK))


class TestUndeployCleanup(unittest.TestCase):

    def test_undeploy_removes_patcher_artifacts(self):
        """undeploy_mod removes patches.json and related files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            game_dir = os.path.join(tmpdir, "game")
            mod_dir = os.path.join(game_dir, "mods", MOD_NAME)
            os.makedirs(mod_dir)

            for name in ("patches.json", "deploy_manifest.json",
                         "disable_patches.sh", "d2r_patch.log"):
                with open(os.path.join(game_dir, name), "w") as f:
                    f.write("x")

            undeploy_mod(game_dir)

            for name in ("patches.json", "deploy_manifest.json",
                         "disable_patches.sh", "d2r_patch.log"):
                self.assertFalse(
                    os.path.exists(os.path.join(game_dir, name)),
                    f"{name} should have been removed",
                )
            self.assertFalse(os.path.exists(mod_dir))

    def test_undeploy_keep_mod(self):
        """undeploy_mod with keep_mod=True preserves mod files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            game_dir = os.path.join(tmpdir, "game")
            mod_dir = os.path.join(game_dir, "mods", MOD_NAME)
            os.makedirs(mod_dir)
            with open(os.path.join(mod_dir, "test"), "w") as f:
                f.write("x")

            with open(os.path.join(game_dir, "patches.json"), "w") as f:
                f.write("{}")

            undeploy_mod(game_dir, keep_mod=True)

            self.assertTrue(os.path.exists(mod_dir), "mod dir should be kept")
            self.assertFalse(
                os.path.exists(os.path.join(game_dir, "patches.json")),
                "patches.json should be removed",
            )


if __name__ == "__main__":
    unittest.main()
