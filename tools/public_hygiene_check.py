#!/usr/bin/env python3
"""Fail on internal/private project debris in GitHub-facing files."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CHECK_PATHS = [
    "AGENTS.md",
    "README.md",
    "CONTRIBUTING.md",
    "CLAUDE.md",
    "docs",
    ".github",
    "plugin",
    "tools",
    "d2r_mcp",
    "tests/fixtures",
    "chars",
]

ALLOWED_PUBLIC_CHAR_FILES = {
    "chars/ExamplePaladin.yaml",
}

FORBIDDEN_FILES = {
    "docs/github-cleanup-agent-plan.md": "internal cleanup plan",
    "docs/d2s-live-test-plan.md": "live-test scratchpad",
}

PATTERNS = [
    (r"\bclient[- ]side modding\b", "private project framing"),
    (r"\bhypervisor\b", "private project framing"),
    (r"\bBazzite\b", "machine-specific environment"),
    (r"\brecovered-repos\b", "project-hub path"),
    (r"\bd2r-hyper\b|\bd2r-control\b|\bd2r_play\b", "private repo/module reference"),
    (r"\bprivate harness\b", "private harness reference"),
    (r"\bmemory[- ]observation\b", "private observation wording"),
    (r"\bruntime observation\b", "private observation wording"),
    (
        r"\bprivate (observer|runtime|report|candidate|mutation)\b",
        "private observation wording",
    ),
    (r"\bcontrol harness\b", "private control-harness wording"),
    (r"\breverse[- ]engineering\b", "reverse-engineering wording"),
    (r"Steam userdata|Proton compatdata|steamapps/compatdata", "machine-specific save path"),
    (r"/Users/|/home/[A-Za-z0-9_.-]+", "machine-specific absolute path"),
    (r"\bSK256\b|\.claude/file-history|docs/recovered-memory", "local recovery artifact"),
    (r"github-cleanup-agent-plan|Agent Topology|cleanup agents?", "internal agent plan"),
    (r"\bworker agents?\b|orchestrator owns", "internal agent plan"),
    (
        r"\blive[- ]test\b|\blive D2R\b|\blive probe\b|\blive[- ]validation\b",
        "live-test scratchpad wording",
    ),
    (
        r"\bmxseed[a-z]*\b|\bsynth(?!esis|esize|etic)[a-z]+\b",
        "disposable validation character name",
    ),
    (
        r"\bD2SProbe\b|\bprobewldemon\b|\bprobesorc\b|\bprobenecro\b|"
        r"\bprobewlzero\b|\bprobewlalt\b|\bprobewltwo\b|\bprobewlmix\b|"
        r"\bdemclone\b|\bdemauras\b|\bdemblank\b|\bdemfalln\b|\bdemlvl\b|"
        r"\bdemfallz\b|\bdemlite\b|\bdemcold\b|\bdemstone\b|\bdemmulti\b|"
        r"\bdemexp\b|\bdemynul\b|\bdemycol\b|\bdemysto\b|\bdemyfur\b|"
        r"\bdemyaur\b|\bdemysee\b",
        "disposable validation character name",
    ),
]


def iter_files() -> list[Path]:
    files: list[Path] = []
    for rel in CHECK_PATHS:
        path = ROOT / rel
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(
                p
                for p in path.rglob("*")
                if p.is_file()
                and p.name != "public_hygiene_check.py"
                and p.suffix.lower() in {".md", ".py", ".yml", ".yaml", ".txt"}
                and ".pytest_cache" not in p.parts
            )
    return sorted(set(files))


def main() -> int:
    failures: list[str] = []

    for rel, reason in FORBIDDEN_FILES.items():
        if (ROOT / rel).exists():
            failures.append(f"{rel}: forbidden public file ({reason})")

    for path in (ROOT / "chars").glob("*.yaml"):
        rel = path.relative_to(ROOT).as_posix()
        if rel not in ALLOWED_PUBLIC_CHAR_FILES:
            failures.append(
                f"{rel}: local/disposable character YAML must not live in the public chars folder; "
                "keep it outside the repo with D2R_CHARS or add an explicit public-example allowlist entry"
            )

    compiled = [(re.compile(pattern, re.IGNORECASE), reason) for pattern, reason in PATTERNS]
    for path in iter_files():
        rel = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), 1):
            for pattern, reason in compiled:
                match = pattern.search(line)
                if match:
                    failures.append(f"{rel}:{lineno}: {reason}: {match.group(0)!r}")

    if failures:
        print("Public hygiene check failed:")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print("Public hygiene check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
