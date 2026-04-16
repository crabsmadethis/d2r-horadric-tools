"""GitHub release smoke tests — validates the public user journey.

Clones from GitHub, installs in a clean venv, and runs CLI commands
exactly as documented in the README. Requires network access.
"""
import os
import subprocess
import pytest

pytestmark = pytest.mark.smoke

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


def test_chargen_help(venv_dir):
    """d2r-chargen --help shows usage and exits 0."""
    r = _run_in_venv(venv_dir, ["d2r-chargen", "--help"])
    assert r.returncode == 0
    assert "build" in r.stdout.lower()


def test_chargen_list(venv_dir, repo_dir):
    """d2r-chargen list finds ExamplePaladin from chars/ in cwd."""
    r = _run_in_venv(venv_dir, ["d2r-chargen", "list"], cwd=repo_dir)
    assert r.returncode == 0
    assert "ExamplePaladin" in r.stdout


def test_mod_help(venv_dir):
    """d2r-mod --help shows usage and exits 0."""
    r = _run_in_venv(venv_dir, ["d2r-mod", "--help"])
    assert r.returncode == 0
    assert "extract" in r.stdout.lower()


def test_mod_build_without_vanilla(venv_dir, repo_dir):
    """d2r-mod build fails gracefully when vanilla/ is missing."""
    # Set D2R_GAME_DIR to a dummy path so the game-dir check passes
    # and we reliably hit the "vanilla/ not found" error.
    fake_game_dir = "/tmp/fake-d2r-game-dir"
    os.makedirs(fake_game_dir, exist_ok=True)
    env_patch = {"D2R_GAME_DIR": fake_game_dir}
    env = os.environ.copy()
    env.update(env_patch)
    env["PATH"] = os.path.join(venv_dir, "bin") + ":" + env.get("PATH", "")
    env["VIRTUAL_ENV"] = venv_dir
    r = subprocess.run(
        ["d2r-mod", "build"], capture_output=True, text=True,
        timeout=30, cwd=repo_dir, env=env,
    )
    assert r.returncode != 0
    assert "vanilla" in (r.stdout + r.stderr).lower()


def test_import_bitwriter(venv_dir):
    """Core build_lib.BitWriter is importable from clean install."""
    python = os.path.join(venv_dir, "bin", "python3")
    r = subprocess.run(
        [python, "-c", "from d2r_chargen.build_lib import BitWriter; print('ok')"],
        capture_output=True, text=True,
    )
    assert r.returncode == 0
    assert "ok" in r.stdout


def test_import_casc(venv_dir):
    """d2r_mod.casc is importable from clean install."""
    python = os.path.join(venv_dir, "bin", "python3")
    r = subprocess.run(
        [python, "-c", "from d2r_mod.casc import extract_vanilla; print('ok')"],
        capture_output=True, text=True,
    )
    assert r.returncode == 0
    assert "ok" in r.stdout


def test_template_bundled(venv_dir):
    """template.d2s is included in the installed package."""
    python = os.path.join(venv_dir, "bin", "python3")
    r = subprocess.run(
        [python, "-c",
         "import d2r_chargen, os; "
         "print(os.path.exists(os.path.join("
         "os.path.dirname(d2r_chargen.__file__), 'data', 'template.d2s')))"],
        capture_output=True, text=True,
    )
    assert r.returncode == 0
    assert "True" in r.stdout


@pytest.fixture(scope="module")
def editable_venv_dir(repo_dir):
    """Create a second venv with editable install (as README suggests)."""
    venv = os.path.join(WORK_DIR, ".smoke-venv-editable")
    subprocess.run(["python3", "-m", "venv", venv], check=True, timeout=30)
    pip = os.path.join(venv, "bin", "pip")
    result = subprocess.run(
        [pip, "install", "-e", repo_dir],
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, f"editable install failed: {result.stderr}"
    yield venv


def test_editable_chargen_list(editable_venv_dir, repo_dir):
    """Editable install: d2r-chargen list works from repo dir."""
    r = _run_in_venv(editable_venv_dir, ["d2r-chargen", "list"], cwd=repo_dir)
    assert r.returncode == 0
    assert "ExamplePaladin" in r.stdout


def test_editable_mod_help(editable_venv_dir):
    """Editable install: d2r-mod --help works."""
    r = _run_in_venv(editable_venv_dir, ["d2r-mod", "--help"])
    assert r.returncode == 0
    assert "extract" in r.stdout.lower()
