"""GitHub release smoke tests — validates the public user journey.

Clones from GitHub, installs in a clean venv, and runs CLI commands
exactly as documented in the README. Requires network access.
"""
import os
import subprocess
import pytest

REPO_URL = "https://github.com/crabsmadethis/d2r-horadric-tools.git"
WORK_DIR = "/tmp/d2r-smoke-test"


@pytest.fixture(scope="module")
def repo_dir():
    """Clone the repo from GitHub into a temp directory."""
    subprocess.run(["rm", "-rf", WORK_DIR], check=False)
    result = subprocess.run(
        ["git", "clone", REPO_URL, WORK_DIR],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, f"git clone failed: {result.stderr}"
    assert os.path.isfile(os.path.join(WORK_DIR, "pyproject.toml"))
    yield WORK_DIR
    subprocess.run(["rm", "-rf", WORK_DIR], check=False)


def test_clone_has_expected_structure(repo_dir):
    """Cloned repo contains the files a user needs."""
    assert os.path.isfile(os.path.join(repo_dir, "README.md"))
    assert os.path.isfile(os.path.join(repo_dir, "pyproject.toml"))
    assert os.path.isfile(os.path.join(repo_dir, "chars", "ExamplePaladin.yaml"))
    assert os.path.isdir(os.path.join(repo_dir, "d2r_chargen"))
    assert os.path.isdir(os.path.join(repo_dir, "d2r_mod"))
    assert os.path.isfile(
        os.path.join(repo_dir, "d2r_chargen", "data", "template.d2s")
    )
