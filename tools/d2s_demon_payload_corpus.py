#!/usr/bin/env python3
"""Summarize Bind Demon follower payloads across raw payloads and saves.

The default report is intentionally aggregate-only: it does not print local
paths or raw payload byte values. Use --include-paths/--include-values for
local-only investigation output.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from d2r_chargen.follower_block import (  # noqa: E402
    DEMON_PAYLOAD_LEN,
    DEMON_UNKNOWN_SLICE_RANGES,
    decode_follower_block,
    parse_demon_payload,
)


CANDIDATE_SUFFIXES = {".bin", ".d2s", ".payload"}


@dataclass(frozen=True)
class PayloadRecord:
    payload: bytes
    source_kind: str
    source_label: str | None = None


@dataclass(frozen=True)
class LoadFailure:
    reason: str
    source_label: str | None = None


FIELD_BYTE_LABELS: dict[int, str] = {
    0: "follower_kind",
    1: "follower_kind",
    4: "monster_hcidx",
    5: "monster_hcidx",
    6: "monster_seed",
    7: "monster_seed",
    8: "monster_seed",
    9: "monster_seed",
    52: "bind_metadata",
    53: "bind_metadata",
    54: "bind_metadata",
    55: "bind_metadata",
    80: "affix_indices",
    81: "affix_indices",
    82: "affix_indices",
    83: "affix_indices",
    84: "affix_indices",
    85: "affix_indices",
    86: "affix_indices",
    89: "volatile_runtime",
    90: "volatile_runtime",
    91: "volatile_runtime",
    92: "embedded_gf_marker",
    93: "embedded_gf_marker",
}

for _label, _start, _end in DEMON_UNKNOWN_SLICE_RANGES:
    for _offset in range(_start, _end):
        FIELD_BYTE_LABELS.setdefault(_offset, f"unknown:{_label}")


def iter_input_files(inputs: Iterable[Path]) -> list[Path]:
    """Expand files and candidate files inside directories in stable order."""

    files: list[Path] = []
    for input_path in inputs:
        if input_path.is_dir():
            files.extend(
                sorted(
                    path
                    for path in input_path.rglob("*")
                    if path.is_file() and path.suffix.lower() in CANDIDATE_SUFFIXES
                )
            )
        else:
            files.append(input_path)
    return files


def load_payload(path: Path, *, include_paths: bool = False) -> PayloadRecord | LoadFailure:
    """Load a raw 116-byte demon payload or the single demon payload in a save."""

    source_label = str(path) if include_paths else path.name
    try:
        data = path.read_bytes()
    except OSError as exc:
        return LoadFailure(f"read error: {exc.__class__.__name__}", source_label)

    if len(data) == DEMON_PAYLOAD_LEN:
        return PayloadRecord(data, "raw", source_label)

    block = decode_follower_block(data)
    if block.follower_count == 0:
        return LoadFailure("no follower payload", source_label)
    if block.follower_count != 1:
        return LoadFailure("expected exactly one follower payload", source_label)
    if not block.payload:
        return LoadFailure("missing follower payload bytes", source_label)
    if len(block.payload) != DEMON_PAYLOAD_LEN:
        return LoadFailure(
            f"expected {DEMON_PAYLOAD_LEN}-byte demon payload", source_label
        )
    return PayloadRecord(block.payload, "d2s", source_label)


def _counter_rows(counter: Counter[Any]) -> list[dict[str, Any]]:
    return [
        {"value": value, "count": count}
        for value, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    ]


def _hex_bytes(data: bytes) -> str:
    return " ".join(f"{value:02x}" for value in data)


def _classify_bytes(
    payloads: list[bytes], *, include_values: bool = False
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    rows: list[dict[str, Any]] = []
    counts = {"fixed": 0, "varies": 0}
    for offset in range(DEMON_PAYLOAD_LEN):
        values = sorted({payload[offset] for payload in payloads})
        classification = "fixed" if len(values) == 1 else "varies"
        counts[classification] += 1
        row: dict[str, Any] = {
            "offset": offset,
            "offset_label": f"+{offset:03d}",
            "field": FIELD_BYTE_LABELS.get(offset),
            "classification": classification,
            "unique_count": len(values),
        }
        if include_values:
            row["values"] = [f"{value:02x}" for value in values]
        rows.append(row)
    return rows, counts


def _classify_unknown_slices(
    payloads: list[bytes], *, include_values: bool = False
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for label, start, end in DEMON_UNKNOWN_SLICE_RANGES:
        values = sorted({payload[start:end] for payload in payloads})
        row: dict[str, Any] = {
            "label": label,
            "start": start,
            "end": end,
            "offset_range": f"+{start:03d}..+{end - 1:03d}",
            "length": end - start,
            "classification": "fixed" if len(values) == 1 else "varies",
            "unique_count": len(values),
        }
        if include_values:
            row["values"] = [_hex_bytes(value) for value in values]
        rows.append(row)
    return rows


def _model_correlated_offsets(
    payloads: list[bytes],
    parsed: list[Any],
    *,
    include_values: bool = False,
) -> list[dict[str, Any]]:
    """Find bytes that are fixed within each monster id but differ by monster id."""

    groups: dict[int, list[bytes]] = {}
    for payload, fields in zip(payloads, parsed):
        groups.setdefault(fields.monster_hcidx, []).append(payload)

    if len(groups) < 2:
        return []

    rows: list[dict[str, Any]] = []
    for offset in range(DEMON_PAYLOAD_LEN):
        values_by_hcidx: dict[int, int] = {}
        for hcidx, group_payloads in sorted(groups.items()):
            values = {payload[offset] for payload in group_payloads}
            if len(values) != 1:
                break
            values_by_hcidx[hcidx] = next(iter(values))
        else:
            if len(set(values_by_hcidx.values())) <= 1:
                continue
            row: dict[str, Any] = {
                "offset": offset,
                "offset_label": f"+{offset:03d}",
                "field": FIELD_BYTE_LABELS.get(offset),
                "group_count": len(values_by_hcidx),
                "payload_count": len(payloads),
            }
            if include_values:
                row["values_by_monster_hcidx"] = {
                    str(hcidx): f"{value:02x}"
                    for hcidx, value in sorted(values_by_hcidx.items())
                }
            rows.append(row)
    return rows


def _is_model_candidate_row(row: dict[str, Any]) -> bool:
    field = row.get("field")
    return field is None or str(field).startswith("unknown")


def build_report(
    inputs: Iterable[Path],
    *,
    include_paths: bool = False,
    include_values: bool = False,
) -> dict[str, Any]:
    files = iter_input_files(inputs)
    records: list[PayloadRecord] = []
    failures: list[LoadFailure] = []

    for file_path in files:
        loaded = load_payload(file_path, include_paths=include_paths)
        if isinstance(loaded, PayloadRecord):
            records.append(loaded)
        else:
            failures.append(loaded)

    payloads = [record.payload for record in records]
    parsed = [parse_demon_payload(payload) for payload in payloads]

    source_kinds = Counter(record.source_kind for record in records)
    failure_reasons = Counter(failure.reason for failure in failures)
    monster_hcidx = Counter(item.monster_hcidx for item in parsed)
    bind_metadata = Counter(item.bind_demon_level for item in parsed)
    affix_tuples = Counter(item.affix_indices.hex() for item in parsed)

    bytes_report, byte_counts = _classify_bytes(
        payloads, include_values=include_values
    ) if payloads else ([], {"fixed": 0, "varies": 0})
    unknown_slices = _classify_unknown_slices(
        payloads, include_values=include_values
    ) if payloads else []
    model_correlated_offsets = _model_correlated_offsets(
        payloads, parsed, include_values=include_values
    ) if payloads else []

    report: dict[str, Any] = {
        "input_count": len(files),
        "payload_count": len(records),
        "load_failure_count": len(failures),
        "source_kinds": _counter_rows(source_kinds),
        "failure_reasons": _counter_rows(failure_reasons),
        "monster_hcidx": _counter_rows(monster_hcidx),
        "bind_metadata": _counter_rows(bind_metadata),
        "affix_tuples": _counter_rows(affix_tuples),
        "byte_class_counts": byte_counts,
        "bytes": bytes_report,
        "unknown_slices": unknown_slices,
        "model_correlated_offsets": model_correlated_offsets,
        "model_candidate_offsets": [
            row for row in model_correlated_offsets if _is_model_candidate_row(row)
        ],
    }

    if include_paths:
        report["sources"] = [
            {"source": record.source_label, "kind": record.source_kind}
            for record in records
        ]
        report["failures"] = [
            {"source": failure.source_label, "reason": failure.reason}
            for failure in failures
        ]

    return report


def _format_counter_section(title: str, rows: list[dict[str, Any]]) -> list[str]:
    lines = [f"{title}:"]
    if not rows:
        return lines + ["  (none)"]
    lines.extend(f"  {row['value']}: {row['count']}" for row in rows)
    return lines


def format_report_text(report: dict[str, Any]) -> str:
    lines = [
        f"input_count={report['input_count']}",
        f"payload_count={report['payload_count']}",
        f"load_failure_count={report['load_failure_count']}",
        "",
    ]
    lines.extend(_format_counter_section("source_kinds", report["source_kinds"]))
    lines.append("")
    lines.extend(
        _format_counter_section("failure_reasons", report["failure_reasons"])
    )
    lines.append("")
    lines.extend(
        _format_counter_section("monster_hcidx", report["monster_hcidx"])
    )
    lines.append("")
    lines.extend(
        _format_counter_section("bind_metadata", report["bind_metadata"])
    )
    lines.append("")
    lines.extend(_format_counter_section("affix_tuples", report["affix_tuples"]))
    lines.append("")

    byte_counts = report["byte_class_counts"]
    lines.extend(
        [
            "byte_class_counts:",
            f"  fixed: {byte_counts['fixed']}",
            f"  varies: {byte_counts['varies']}",
            "varied_offsets:",
        ]
    )
    varied = [
        row
        for row in report["bytes"]
        if row["classification"] == "varies"
    ]
    if varied:
        lines.extend(
            "  {offset_label} {field} unique={unique_count}".format(
                offset_label=row["offset_label"],
                field=row["field"] or "unknown",
                unique_count=row["unique_count"],
            )
            for row in varied
        )
    else:
        lines.append("  (none)")
    lines.append("")

    lines.append("unknown_slices:")
    if report["unknown_slices"]:
        lines.extend(
            "  {offset_range} {label}: {classification} unique={unique_count}".format(
                offset_range=row["offset_range"],
                label=row["label"],
                classification=row["classification"],
                unique_count=row["unique_count"],
            )
            for row in report["unknown_slices"]
        )
    else:
        lines.append("  (none)")

    lines.append("")
    lines.append("model_correlated_offsets:")
    if report["model_correlated_offsets"]:
        for row in report["model_correlated_offsets"]:
            line = "  {offset_label} {field} groups={group_count}".format(
                offset_label=row["offset_label"],
                field=row["field"] or "unknown",
                group_count=row["group_count"],
            )
            if "values_by_monster_hcidx" in row:
                values = ", ".join(
                    f"{hcidx}={value}"
                    for hcidx, value in row["values_by_monster_hcidx"].items()
                )
                line = f"{line} values={values}"
            lines.append(line)
    else:
        lines.append("  (none)")

    lines.append("")
    lines.append("model_candidate_offsets:")
    if report["model_candidate_offsets"]:
        for row in report["model_candidate_offsets"]:
            line = "  {offset_label} {field} groups={group_count}".format(
                offset_label=row["offset_label"],
                field=row["field"] or "unknown",
                group_count=row["group_count"],
            )
            if "values_by_monster_hcidx" in row:
                values = ", ".join(
                    f"{hcidx}={value}"
                    for hcidx, value in row["values_by_monster_hcidx"].items()
                )
                line = f"{line} values={values}"
            lines.append(line)
    else:
        lines.append("  (none)")

    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize Bind Demon follower payloads across saves/payloads."
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        type=Path,
        help="Raw 116-byte payload files, .d2s files, or directories to scan.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a machine-readable JSON report.",
    )
    parser.add_argument(
        "--include-paths",
        action="store_true",
        help="Include local source paths in the report. Keep this local/untracked.",
    )
    parser.add_argument(
        "--include-values",
        action="store_true",
        help="Include raw byte values for byte/slice classifiers. Keep this local/untracked.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report(
        args.inputs,
        include_paths=args.include_paths,
        include_values=args.include_values,
    )
    if args.json:
        json.dump(report, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        print(format_report_text(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
