"""Stale vanilla data detection via .vanilla_version and .build.info."""

import os
import json
from datetime import datetime, timezone


VERSION_FILE = ".vanilla_version"


def write_vanilla_version(vanilla_dir: str, build_key: str) -> None:
    data = {
        "build_key": build_key,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    path = os.path.join(vanilla_dir, VERSION_FILE)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def read_vanilla_version(vanilla_dir: str) -> dict | None:
    path = os.path.join(vanilla_dir, VERSION_FILE)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _read_build_key(game_dir: str) -> str | None:
    path = os.path.join(game_dir, ".build.info")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        lines = f.read().strip().split("\n")
    if len(lines) < 2:
        return None
    headers = [h.split("!")[0].strip() for h in lines[0].split("|")]
    values = [v.strip() for v in lines[1].split("|")]
    try:
        idx = headers.index("Build Key")
        return values[idx]
    except (ValueError, IndexError):
        return None


def check_stale(vanilla_dir: str, game_dir: str) -> str | None:
    version_info = read_vanilla_version(vanilla_dir)
    if version_info is None:
        return None
    game_key = _read_build_key(game_dir)
    if game_key is None:
        return None
    vanilla_key = version_info["build_key"]
    if vanilla_key == game_key:
        return None
    return (
        f"vanilla/ was extracted from build {vanilla_key} "
        f"but game is now build {game_key} — consider re-extracting"
    )
