import unittest
import tempfile
import os
from unittest.mock import patch, MagicMock
from d2r_mod.cli import parse_args, cmd_update, cmd_deploy


class TestParseArgs(unittest.TestCase):
    def test_build(self):
        args = parse_args(["build"])
        self.assertEqual(args.command, "build")

    def test_deploy(self):
        args = parse_args(["deploy"])
        self.assertEqual(args.command, "deploy")
        self.assertFalse(args.force)

    def test_deploy_force(self):
        args = parse_args(["deploy", "--force"])
        self.assertEqual(args.command, "deploy")
        self.assertTrue(args.force)

    def test_undeploy(self):
        args = parse_args(["undeploy"])
        self.assertEqual(args.command, "undeploy")

    def test_clean(self):
        args = parse_args(["clean"])
        self.assertEqual(args.command, "clean")

    def test_diff_default(self):
        args = parse_args(["diff"])
        self.assertEqual(args.command, "diff")
        self.assertIsNone(args.file)
        self.assertFalse(args.summary)

    def test_diff_with_file(self):
        args = parse_args(["diff", "Skills.txt"])
        self.assertEqual(args.file, "Skills.txt")

    def test_diff_summary(self):
        args = parse_args(["diff", "--summary"])
        self.assertTrue(args.summary)

    def test_build_warn_conflicts(self):
        args = parse_args(["build", "--warn-conflicts"])
        self.assertTrue(args.warn_conflicts)

    def test_no_command(self):
        with self.assertRaises(SystemExit):
            parse_args([])

    def test_update(self):
        args = parse_args(["update"])
        self.assertEqual(args.command, "update")
        self.assertFalse(args.warn_conflicts)
        self.assertFalse(args.no_regen)

    def test_update_with_flags(self):
        args = parse_args(["update", "--warn-conflicts", "--no-regen"])
        self.assertEqual(args.command, "update")
        self.assertTrue(args.warn_conflicts)
        self.assertTrue(args.no_regen)

    def test_update_custom_game_dir(self):
        args = parse_args(["update", "--game-dir", "/tmp/test"])
        self.assertEqual(args.game_dir, "/tmp/test")


class TestCmdUpdate(unittest.TestCase):
    """Test that cmd_update calls extract, build, and deploy in order."""

    @patch("d2r_mod.cli.build_mod")
    @patch("d2r_mod.cli._project_root")
    def test_cmd_update_runs_pipeline(self, mock_root, mock_build):
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_root.return_value = tmpdir
            os.makedirs(os.path.join(tmpdir, "vanilla"))
            os.makedirs(os.path.join(tmpdir, "overlays"))
            os.makedirs(os.path.join(tmpdir, "scripts"))

            mock_build.return_value = []

            mock_extract = MagicMock(return_value={"f1": "/path/f1"})
            mock_parse_build = MagicMock(return_value="abc123")
            mock_write_version = MagicMock()
            mock_deploy = MagicMock()

            with patch("d2r_mod.cli.extract_vanilla", mock_extract, create=True), \
                 patch("d2r_mod.casc.extract_vanilla", mock_extract), \
                 patch("d2r_mod.casc._parse_build_info", mock_parse_build), \
                 patch("d2r_mod.version.write_vanilla_version", mock_write_version), \
                 patch("d2r_mod.deploy.deploy_mod", mock_deploy):

                args = parse_args(["update", "--game-dir", tmpdir])
                cmd_update(args)

                mock_extract.assert_called_once()
                mock_parse_build.assert_called_once_with(tmpdir)
                mock_write_version.assert_called_once()
                mock_build.assert_called_once()
                mock_deploy.assert_called_once()
                # Deploy should be called with force=True
                _, kwargs = mock_deploy.call_args
                self.assertTrue(kwargs.get("force", False))


class TestCmdDeploy(unittest.TestCase):
    """Test that cmd_deploy passes force and vanilla_dir correctly."""

    @patch("d2r_mod.cli._project_root")
    def test_cmd_deploy_passes_force_and_vanilla_dir(self, mock_root):
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_root.return_value = tmpdir
            build_dir = os.path.join(tmpdir, "build")
            os.makedirs(build_dir)
            with open(os.path.join(build_dir, "f.txt"), "w") as f:
                f.write("x")
            game_dir = os.path.join(tmpdir, "game")
            os.makedirs(game_dir)

            mock_deploy = MagicMock()
            mock_verify = MagicMock(return_value=True)
            with patch("d2r_mod.deploy.deploy_mod", mock_deploy), \
                 patch("d2r_mod.deploy.verify_deploy", mock_verify):
                args = parse_args(["deploy", "--force", "--no-build",
                                   "--game-dir", game_dir])
                cmd_deploy(args)

                mock_deploy.assert_called_once()
                call_args = mock_deploy.call_args
                self.assertTrue(call_args.kwargs.get("force") or call_args[1].get("force"))
                vanilla_dir = call_args.kwargs.get("vanilla_dir") or call_args[1].get("vanilla_dir")
                self.assertEqual(vanilla_dir, os.path.join(tmpdir, "vanilla"))

    @patch("d2r_mod.cli._project_root")
    def test_cmd_deploy_builds_by_default(self, mock_root):
        """deploy runs build first unless --no-build."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_root.return_value = tmpdir
            build_dir = os.path.join(tmpdir, "build")
            os.makedirs(build_dir)
            game_dir = os.path.join(tmpdir, "game")
            os.makedirs(game_dir)

            mock_build = MagicMock(return_value=[])
            mock_deploy = MagicMock()
            mock_verify = MagicMock(return_value=True)
            with patch("d2r_mod.cli.build_mod", mock_build), \
                 patch("d2r_mod.deploy.deploy_mod", mock_deploy), \
                 patch("d2r_mod.deploy.verify_deploy", mock_verify):
                args = parse_args(["deploy", "--force", "--game-dir", game_dir])
                cmd_deploy(args)
                mock_build.assert_called_once()

    @patch("d2r_mod.cli._project_root")
    def test_cmd_deploy_skips_build_with_flag(self, mock_root):
        """--no-build skips the build step."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_root.return_value = tmpdir
            build_dir = os.path.join(tmpdir, "build")
            os.makedirs(build_dir)
            game_dir = os.path.join(tmpdir, "game")
            os.makedirs(game_dir)

            mock_build = MagicMock(return_value=[])
            mock_deploy = MagicMock()
            mock_verify = MagicMock(return_value=True)
            with patch("d2r_mod.cli.build_mod", mock_build), \
                 patch("d2r_mod.deploy.deploy_mod", mock_deploy), \
                 patch("d2r_mod.deploy.verify_deploy", mock_verify):
                args = parse_args(["deploy", "--force", "--no-build",
                                   "--game-dir", game_dir])
                cmd_deploy(args)
                mock_build.assert_not_called()


def test_cli_optional_modules(monkeypatch):
    """CLI parse_args works when engine/host/verify are absent."""
    import importlib
    import d2r_mod.cli as cli_mod

    _real_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__
    blocked = {'d2r_mod.engine', 'd2r_mod.engine.cli', 'd2r_mod.host', 'd2r_mod.host.cli', 'd2r_mod.verify'}

    def _mock_import(name, *args, **kwargs):
        if name in blocked:
            raise ImportError(f"mocked: {name}")
        return _real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", _mock_import)
    importlib.reload(cli_mod)

    args = cli_mod.parse_args(["extract"])
    assert args.command == "extract"

    import io
    buf = io.StringIO()
    try:
        cli_mod.parse_args(["--help"])
    except SystemExit:
        pass


def test_extract_calls_regen(monkeypatch, tmp_path):
    """cmd_extract chains CASC extraction with data regeneration."""
    import d2r_mod.cli as cli_mod

    extracted = {}
    regen_called = {}

    def mock_extract(game_dir, output_dir, **kw):
        extracted["game_dir"] = game_dir
        extracted["output_dir"] = output_dir
        return {"file1.txt": str(tmp_path / "file1.txt")}

    def mock_parse_build_info(game_dir):
        return "fakebuildkey"

    def mock_write_version(output_dir, build_key):
        pass

    def mock_regen_all(build_dir, chargen_data_dir=None):
        regen_called["build_dir"] = build_dir

    monkeypatch.setattr("d2r_mod.cli._project_root", lambda: str(tmp_path))
    monkeypatch.setattr("d2r_mod.casc.extract_vanilla", mock_extract)
    monkeypatch.setattr("d2r_mod.casc._parse_build_info", mock_parse_build_info)
    monkeypatch.setattr("d2r_mod.version.write_vanilla_version", mock_write_version)
    monkeypatch.setattr("d2r_mod.regen.regen_all", mock_regen_all)

    import argparse
    args = argparse.Namespace(game_dir="/fake/game", command="extract")
    cli_mod.cmd_extract(args)

    assert "build_dir" in regen_called
    assert regen_called["build_dir"] == str(tmp_path / "vanilla")


if __name__ == "__main__":
    unittest.main()
