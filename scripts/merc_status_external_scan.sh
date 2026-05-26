#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

usage() {
  cat <<'EOF'
Usage:
  scripts/merc_status_external_scan.sh [--out <path>] <root> [<root>...]
  scripts/merc_status_external_scan.sh [--out <path>] --stdin-roots
  scripts/merc_status_external_scan.sh [--out <path>] --roots-file <path>
  scripts/merc_status_external_scan.sh [--top <n>] ...

Writes a shareable, aggregate-only merc-status report:
  - Uses --report merc-status-context --json
  - Verifies the JSON does not contain absolute input paths
  - Verifies the JSON omits filename examples (shareable by default)

Notes:
  - Pass corpus roots as directories or individual .d2s files.
  - --stdin-roots reads newline-separated roots from stdin (helps avoid shell history).
  - --roots-file reads newline-separated roots from a file.
  - Do not paste raw corpus paths into public issues; share only the JSON output.
EOF
}

out_path="merc-status-report.json"
roots=()
stdin_roots=0
roots_file=""
top_n=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --out)
      shift
      if [ "$#" -eq 0 ]; then
        printf 'error: --out requires a path\n' >&2
        exit 2
      fi
      out_path="$1"
      ;;
    --top)
      shift
      if [ "$#" -eq 0 ]; then
        printf 'error: --top requires a number\n' >&2
        exit 2
      fi
      top_n="$1"
      ;;
    --stdin-roots)
      stdin_roots=1
      ;;
    --roots-file)
      shift
      if [ "$#" -eq 0 ]; then
        printf 'error: --roots-file requires a path\n' >&2
        exit 2
      fi
      roots_file="$1"
      ;;
    --)
      shift
      roots+=("$@")
      break
      ;;
    -*)
      printf 'error: unknown flag: %s\n' "$1" >&2
      exit 2
      ;;
    *)
      roots+=("$1")
      ;;
  esac
  shift
done

if [ "$stdin_roots" -eq 1 ]; then
  if [ "${#roots[@]}" -ne 0 ]; then
    printf 'error: --stdin-roots cannot be combined with positional roots\n' >&2
    exit 2
  fi
  if [ -n "$roots_file" ]; then
    printf 'error: --stdin-roots cannot be combined with --roots-file\n' >&2
    exit 2
  fi
  while IFS= read -r line; do
    line="${line%$'\r'}"
    if [ -n "$line" ]; then
      roots+=("$line")
    fi
  done
fi

if [ -n "$roots_file" ]; then
  if [ "${#roots[@]}" -ne 0 ]; then
    printf 'error: --roots-file cannot be combined with positional roots\n' >&2
    exit 2
  fi
  if [ "$stdin_roots" -eq 1 ]; then
    printf 'error: --roots-file cannot be combined with --stdin-roots\n' >&2
    exit 2
  fi
  if [ ! -f "$roots_file" ]; then
    printf 'error: roots file not found: %s\n' "$roots_file" >&2
    exit 2
  fi
  while IFS= read -r line; do
    line="${line%$'\r'}"
    if [ -n "$line" ]; then
      roots+=("$line")
    fi
  done <"$roots_file"
fi

if [ "${#roots[@]}" -eq 0 ]; then
  usage >&2
  exit 2
fi

if [ -n "$top_n" ]; then
  python3 "$ROOT/tools/d2s_corpus_scan.py" "${roots[@]}" \
    --report merc-status-context \
    --json --top "$top_n" >"$out_path"
else
  python3 "$ROOT/tools/d2s_corpus_scan.py" "${roots[@]}" \
    --report merc-status-context \
    --json >"$out_path"
fi

python3 - "$out_path" "${roots[@]}" <<'PY'
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

out_path = Path(sys.argv[1])
roots = sys.argv[2:]

data = json.loads(out_path.read_text(encoding="utf-8"))

errors: list[str] = []
if data.get("report") != "merc-status-context":
    errors.append(f"unexpected report: {data.get('report')!r}")

dump = json.dumps(data, sort_keys=True)

for root in roots:
    try:
        resolved = str(Path(root).expanduser().resolve())
    except OSError:
        resolved = os.path.abspath(os.path.expanduser(root))
    if resolved and resolved in dump:
        errors.append(f"output contains input root path: {resolved}")

for needle in ("/Users/", "\\\\Users\\\\", "C:\\\\Users\\\\"):
    if needle in dump:
        errors.append(f"output contains path-like marker: {needle!r}")

for needle in ("/home/", "/Volumes/", "/private/", "/tmp/", "AppData\\\\", ":\\\\"):
    if needle in dump:
        errors.append(f"output contains path-like marker: {needle!r}")

if "examples" in data:
    errors.append("output contains 'examples' field; expected report payload only")

if errors:
    sys.stderr.write("error: merc-status report failed shareability checks:\n")
    for err in errors:
        sys.stderr.write(f"- {err}\n")
    sys.exit(3)

valid = data.get("valid_d2s")
sys.stdout.write(f"ok: wrote {out_path} (valid_d2s={valid})\n")
PY
