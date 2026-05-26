from __future__ import annotations

import json
import subprocess
from pathlib import Path


def _run_script(tmp_path: Path, *, stdin_roots: bool, roots_file: bool = False, crlf: bool = False) -> dict:
    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "scripts" / "merc_status_external_scan.sh"
    fixture = repo_root / "d2r_chargen" / "data" / "template.d2s"
    out_path = tmp_path / "merc-status-report.json"

    args = [str(script), "--out", str(out_path), "--top", "50"]
    if roots_file:
        roots_path = tmp_path / "roots.txt"
        suffix = "\r\n" if crlf else "\n"
        roots_path.write_text(str(fixture) + suffix, encoding="utf-8")
        proc = subprocess.run(
            [*args, "--roots-file", str(roots_path)],
            text=True,
            capture_output=True,
            check=False,
        )
    elif stdin_roots:
        proc = subprocess.run(
            [*args, "--stdin-roots"],
            input=str(fixture) + ("\r\n" if crlf else "\n"),
            text=True,
            capture_output=True,
            check=False,
        )
    else:
        proc = subprocess.run(
            [*args, str(fixture)],
            text=True,
            capture_output=True,
            check=False,
        )

    assert proc.returncode == 0, proc.stderr
    assert out_path.exists()
    return json.loads(out_path.read_text(encoding="utf-8"))


def test_merc_status_external_scan_script_shareable_json(tmp_path: Path) -> None:
    data = _run_script(tmp_path, stdin_roots=False)
    assert data["report"] == "merc-status-context"
    assert "examples" not in data
    assert data["sections"]["merc_status"] == [{"count": 1, "value": "1"}]


def test_merc_status_external_scan_script_stdin_roots(tmp_path: Path) -> None:
    data = _run_script(tmp_path, stdin_roots=True)
    assert data["report"] == "merc-status-context"
    assert "examples" not in data


def test_merc_status_external_scan_script_roots_file(tmp_path: Path) -> None:
    data = _run_script(tmp_path, stdin_roots=False, roots_file=True)
    assert data["report"] == "merc-status-context"
    assert "examples" not in data


def test_merc_status_external_scan_script_accepts_crlf_roots(tmp_path: Path) -> None:
    data = _run_script(tmp_path, stdin_roots=True, crlf=True)
    assert data["report"] == "merc-status-context"


def test_merc_status_external_scan_script_rejects_stdin_roots_with_positional_roots(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "scripts" / "merc_status_external_scan.sh"
    fixture = repo_root / "d2r_chargen" / "data" / "template.d2s"
    out_path = tmp_path / "merc-status-report.json"

    proc = subprocess.run(
        [
            str(script),
            "--out",
            str(out_path),
            "--stdin-roots",
            str(fixture),
        ],
        input=str(fixture) + "\n",
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 2
    assert "cannot be combined" in proc.stderr.lower()
