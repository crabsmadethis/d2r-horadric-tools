"""Tests for config module directory detection."""
import os
from unittest.mock import patch


def test_detect_chars_dir_uses_package_relative_path():
    """CHARS_DIR defaults to chars/ relative to the package location."""
    from d2r_chargen import config

    with patch.dict(os.environ, {}, clear=False):
        env = os.environ.copy()
        env.pop('D2R_CHARS', None)
        with patch.dict(os.environ, env, clear=True):
            result = config._detect_chars_dir()
            # Should be relative to the package's parent directory
            pkg_parent = os.path.dirname(os.path.dirname(os.path.abspath(config.__file__)))
            assert result == os.path.join(pkg_parent, 'chars')


def test_detect_chars_dir_respects_env_var(tmp_path):
    """CHARS_DIR should use D2R_CHARS env var when set."""
    from d2r_chargen.config import _detect_chars_dir

    custom_dir = str(tmp_path / 'my_chars')
    with patch.dict(os.environ, {'D2R_CHARS': custom_dir}):
        result = _detect_chars_dir()
        assert result == custom_dir


def test_project_root_uses_cwd_not_file_location():
    """_project_root must not depend on __file__ location."""
    from d2r_mod import cli

    with patch.object(cli, '__file__', '/fake/site-packages/d2r_mod/cli.py'):
        result = cli._project_root()
        assert result == os.getcwd()
        assert 'site-packages' not in result
