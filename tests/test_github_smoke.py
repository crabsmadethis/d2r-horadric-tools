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


@pytest.fixture(scope="module")
def venv_dir(repo_dir):
    """Create a clean venv and install the package (non-editable)."""
    venv = os.path.join(WORK_DIR, ".smoke-venv")
    subprocess.run(["python3", "-m", "venv", venv], check=True, timeout=30)
    pip = os.path.join(venv, "bin", "pip")
    result = subprocess.run(
        [pip, "install", repo_dir],
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, f"pip install failed: {result.stderr}"
    yield venv


def _run_in_venv(venv_dir, cmd, cwd=None, timeout=30):
    """Run a command using the venv's Python/bin."""
    env = os.environ.copy()
    env["PATH"] = os.path.join(venv_dir, "bin") + ":" + env.get("PATH", "")
    env["VIRTUAL_ENV"] = venv_dir
    return subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout,
        cwd=cwd, env=env,
    )


def test_pip_install_succeeds(venv_dir):
    """Non-editable pip install completes without error."""
    pip = os.path.join(venv_dir, "bin", "pip")
    result = subprocess.run(
        [pip, "show", "d2r-tools"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "d2r-tools" in result.stdout
