#!/usr/bin/env python3
"""Compare Codex's matrix report against the matrix expectations.

Inputs:
  matrix.yaml         — defines rows + expectations
  codex_report.out    — raw `codex exec` stdout; contains a fenced JSON block
                        with the per-row results Codex produced.

Output: prints a per-row PASS/FAIL table + overall summary. Exit 0 if all
pass, 1 otherwise.
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML not installed; `pip install pyyaml` or `pip install --user pyyaml`")

HERE = Path(__file__).parent
MATRIX = HERE / "matrix.yaml"
REPORT = HERE / "codex_report.out"


def load_matrix() -> list[dict]:
    with MATRIX.open() as f:
        return yaml.safe_load(f)["rows"]


def extract_codex_json(report_text: str) -> dict:
    """Pull the final fenced ```json block from codex exec output."""
    # Matches ```json\n{...}\n```
    blocks = re.findall(r"```json\s*\n(.*?)\n```", report_text, re.DOTALL)
    if not blocks:
        raise ValueError("No ```json fenced block in codex report")
    # Last block is Codex's final answer (earlier blocks may be prompt echoes)
    return json.loads(blocks[-1])


def _unwrap_raw(raw: str) -> str:
    """Normalize Codex's raw-response envelope shapes for substring matching.

    Codex captures MCP tool responses in inconsistent shapes:
      A) {"result": "<inner>"}                      — escaped-json string
      B) [{"type":"text","text":"<inner>"}]          — MCP content array
      C) <inner> bare
    and sometimes emits them as malformed JSON-like text with literal newlines
    inside strings (so json.loads fails). Strategy: do a best-effort structural
    unwrap when json.loads succeeds, then unconditionally collapse any
    remaining backslash-escaped quotes so the matrix expectations (which use
    real quotes) can match.
    """
    import json as _json
    s = raw
    for _ in range(3):
        try:
            obj = _json.loads(s)
        except (ValueError, TypeError):
            break
        if isinstance(obj, dict) and "result" in obj and isinstance(obj["result"], str):
            s = obj["result"]
        elif (isinstance(obj, list) and obj and isinstance(obj[0], dict)
              and obj[0].get("type") == "text" and "text" in obj[0]):
            s = obj[0]["text"]
        else:
            break
    # Collapse any backslash-escaped quotes left over from pseudo-JSON strings
    # whose json.loads failed. Safe because matrix expectations use real quotes.
    if '\\"' in s:
        s = s.replace('\\"', '"')
    return s


def evaluate_row(row: dict, observed: dict) -> tuple[bool, str]:
    """Return (pass, reason)."""
    expect = row.get("expect", {})
    raw = observed.get("raw_response")
    err = observed.get("error")
    if raw is not None:
        raw = _unwrap_raw(raw)

    if "error_regex" in expect:
        pattern = expect["error_regex"]
        # Codex is inconsistent: sometimes tool-level errors surface as `error`,
        # sometimes as a text-content response (MCP isError=true). Accept both.
        candidates = [c for c in (err, raw) if c]
        if not candidates:
            return False, f"expected error matching /{pattern}/ but no output captured"
        matched = any(re.search(pattern, c) for c in candidates)
        if not matched:
            return False, f"none of error/response matched /{pattern}/: {candidates!r}"
        return True, "error matched"

    if "must_contain" in expect:
        if err is not None:
            return False, f"call errored: {err!r}"
        if raw is None:
            return False, "no raw_response captured"
        missing = [s for s in expect["must_contain"] if s not in raw]
        if missing:
            return False, f"missing substrings: {missing}"
        return True, f"all {len(expect['must_contain'])} substrings present"

    return False, "no recognized expectation in matrix row"


def main() -> int:
    rows = load_matrix()
    report_text = REPORT.read_text()
    try:
        codex_report = extract_codex_json(report_text)
    except (ValueError, json.JSONDecodeError) as e:
        print(f"FATAL: cannot parse codex report JSON: {e}", file=sys.stderr)
        print("--- tail of report ---", file=sys.stderr)
        print(report_text[-1500:], file=sys.stderr)
        return 2

    codex_by_id = {r["id"]: r for r in codex_report.get("results", [])}

    passed = 0
    failed_rows: list[tuple[int, str, str]] = []

    print(f"{'id':>3}  {'tool':<24}  {'status':<6}  reason")
    print("-" * 80)
    for row in rows:
        rid = row["id"]
        tool = row["tool"]
        observed = codex_by_id.get(rid)
        if observed is None:
            print(f"{rid:>3}  {tool:<24}  FAIL    no codex result for this id")
            failed_rows.append((rid, tool, "missing from codex report"))
            continue
        ok, reason = evaluate_row(row, observed)
        status = "PASS" if ok else "FAIL"
        print(f"{rid:>3}  {tool:<24}  {status:<6}  {reason}")
        if ok:
            passed += 1
        else:
            failed_rows.append((rid, tool, reason))

    print("-" * 80)
    total = len(rows)
    print(f"Summary: {passed}/{total} passed, {total - passed} failed")
    if failed_rows:
        print("\nDetail on failures:")
        for rid, tool, reason in failed_rows:
            obs = codex_by_id.get(rid, {})
            raw = obs.get("raw_response")
            err = obs.get("error")
            print(f"\nrow {rid} ({tool})")
            print(f"  reason: {reason}")
            if err:
                print(f"  error:  {err}")
            if raw:
                print(f"  raw:    {raw[:400]}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
