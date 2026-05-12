#!/usr/bin/env python3
"""Inspect one Bind Demon template payload without leaking local paths by default.

This helper is for the v1.2 template-derived workflow: inspect a captured
template, see its authorable fields and source-context posture, then decide how
to express player intent in YAML. It does not synthesize a payload.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from d2r_chargen.data.monumod_affixes import affix_name  # noqa: E402
from d2r_chargen.follower_block import (  # noqa: E402
    DEMON_PAYLOAD_LEN,
    DEMON_UNKNOWN_SLICE_RANGES,
    decode_follower_block,
    parse_demon_payload,
)
from tools.d2s_monster_model_compare import build_report as build_model_report  # noqa: E402


AUTHORING_POLICIES = {
    "runtime_stats_24_31": "preserve template; same-model Fallen evidence rewrites zeroes",
    "percent_or_caps_44_51": "preserve template; can persist nonzero source context",
    "bitfields_64_79": "preserve for source-affix context unless proven optional",
    "hash_or_runtime_byte_88": "preserve template; same-model Fallen evidence rewrites to 00",
    "volatile_runtime_89_91": "do not author; D2R may rewrite on save/exit",
    "post_gf_opcode_94": "preserve known 06 opcode; changing it is unsafe",
    "post_gf_tail_95_115": "preserve template tail; final bytes can be load-critical",
}


def _hex(data: bytes) -> str:
    return " ".join(f"{value:02x}" for value in data)


def _load_payload(path: Path) -> tuple[bytes, dict[str, Any]]:
    data = path.read_bytes()
    if len(data) == DEMON_PAYLOAD_LEN:
        return data, {"input_kind": "raw-payload", "follower_count": None}

    block = decode_follower_block(data)
    if block.follower_count == 0:
        raise ValueError("input has no follower payload")
    if block.follower_count != 1:
        raise ValueError(
            f"expected exactly one follower payload, got {block.follower_count}"
        )
    if len(block.payload) != DEMON_PAYLOAD_LEN:
        raise ValueError(
            f"expected {DEMON_PAYLOAD_LEN}-byte demon payload, "
            f"got {len(block.payload)}"
        )
    return block.payload, {"input_kind": "d2s-save", "follower_count": 1}


def _parse_tsv(path: Path) -> list[dict[str, str]]:
    lines = path.read_text(errors="replace").splitlines()
    if not lines:
        raise ValueError(f"{path.name} is empty")
    header = lines[0].split("\t")
    rows: list[dict[str, str]] = []
    for row_index, line in enumerate(lines[1:]):
        cells = line.split("\t")
        row = {
            name: cells[index] if index < len(cells) else ""
            for index, name in enumerate(header)
        }
        row["_row_index"] = str(row_index)
        rows.append(row)
    return rows


def _monstats_context(excel_dir: Path, monster_hcidx: int) -> dict[str, Any]:
    monstats_path = excel_dir / "MonStats.txt"
    if not monstats_path.exists():
        raise FileNotFoundError("missing MonStats.txt under supplied excel directory")

    rows = _parse_tsv(monstats_path)
    if monster_hcidx < 0 or monster_hcidx >= len(rows):
        raise ValueError(
            f"payload monster_hcidx row index {monster_hcidx} not found"
        )
    row = rows[monster_hcidx]
    fields = {
        "id": row.get("Id", ""),
        "monstats_hcidx_column": row.get("*hcIdx", ""),
        "name_str": row.get("NameStr", ""),
        "monstats_ex": row.get("MonStatsEx", ""),
        "mon_type": row.get("MonType", ""),
        "ai": row.get("AI", ""),
        "level_h": row.get("Level(H)", ""),
    }
    return {
        "row_index": monster_hcidx,
        "fields": fields,
        "note": "payload monster_hcidx is this zero-based MonStats row index, not the *hcIdx column",
    }


def _model_comparison(
    excel_dir: Path,
    source_hcidx: int,
    compare_hcidx: list[int],
) -> dict[str, Any]:
    values = list(dict.fromkeys([source_hcidx] + compare_hcidx))
    report = build_model_report(excel_dir, values)
    return {
        "source_hcidx": source_hcidx,
        "compared_hcidx": values,
        "monstats_differences": report["monstats_differences"],
        "monstats2_differences": report["monstats2_differences"],
        "missing_monstats2_ids": report["missing_monstats2_ids"],
        "note": (
            "Differences come from extracted local tables. They narrow model "
            "identity hypotheses but do not prove a generated follower will "
            "load and survive save/exit."
        ),
    }


def _affix_rows(affix_indices: bytes) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for slot, value in enumerate(affix_indices, 1):
        rows.append(
            {
                "slot": slot,
                "id": value,
                "name": affix_name(value),
                "empty": value == 0,
            }
        )
    return rows


def _nonzero_affix_names(affix_indices: bytes) -> list[str]:
    return [affix_name(value) for value in affix_indices if value != 0]


def _unknown_slice_rows(
    payload: bytes, *, include_values: bool = False
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for label, start, end in DEMON_UNKNOWN_SLICE_RANGES:
        data = bytes(payload[start:end])
        row: dict[str, Any] = {
            "label": label,
            "offset_range": f"+{start:03d}..+{end - 1:03d}",
            "length": end - start,
            "all_zero": all(value == 0 for value in data),
            "authoring_policy": AUTHORING_POLICIES[label],
        }
        if include_values:
            row["hex"] = _hex(data)
        rows.append(row)
    return rows


def build_report(
    input_path: Path,
    *,
    excel_dir: Path | None = None,
    compare_hcidx: list[int] | None = None,
    include_path: bool = False,
    include_values: bool = False,
) -> dict[str, Any]:
    payload, source = _load_payload(input_path)
    fields = parse_demon_payload(payload)
    affixes = _affix_rows(fields.affix_indices)

    report: dict[str, Any] = {
        "payload_length": len(payload),
        "input_kind": source["input_kind"],
        "follower_count": source["follower_count"],
        "monster_hcidx": fields.monster_hcidx,
        "bind_metadata": fields.bind_demon_level,
        "affixes": affixes,
        "yaml_authoring_hint": {
            "monster_hcidx": fields.monster_hcidx,
            "raw_affixes": _nonzero_affix_names(fields.affix_indices),
            "composition_note": (
                "raw_affixes are inspection output; split them into "
                "source_affixes and skill_affixes when source context is known"
            ),
        },
        "unknown_slices": _unknown_slice_rows(
            payload,
            include_values=include_values,
        ),
        "warnings": [
            "Template-free bound-demon synthesis remains blocked; preserve template bytes.",
            "Payload +52 is persisted bind metadata, not effective Bind Demon level.",
            "Payload monster_hcidx is a zero-based MonStats row index, not the MonStats *hcIdx column.",
        ],
    }

    if include_path:
        report["source"] = str(input_path)
    if include_values:
        report["monster_seed"] = fields.monster_seed
        report["monster_seed_hex"] = f"0x{fields.monster_seed:08x}"
    if excel_dir is not None:
        report["monstats_row"] = _monstats_context(
            excel_dir,
            fields.monster_hcidx,
        )
    if compare_hcidx:
        if excel_dir is None:
            raise ValueError("--compare-hcidx requires --excel-dir")
        report["model_comparison"] = _model_comparison(
            excel_dir,
            fields.monster_hcidx,
            compare_hcidx,
        )
    return report


def _format_affixes(rows: list[dict[str, Any]]) -> list[str]:
    lines = ["affixes(+80..+86):"]
    for row in rows:
        name = "none" if row["empty"] else row["name"]
        lines.append(f"  slot {row['slot']}: {row['id']} {name}")
    return lines


def _format_unknown_slices(rows: list[dict[str, Any]]) -> list[str]:
    lines = ["unknown_slice_posture:"]
    for row in rows:
        posture = "zero" if row["all_zero"] else "nonzero"
        line = f"  {row['offset_range']} {row['label']}: {posture}"
        if "hex" in row:
            line = f"{line} hex={row['hex']}"
        lines.append(line)
        lines.append(f"    policy: {row['authoring_policy']}")
    return lines


def _format_diff_rows(rows: list[dict[str, Any]]) -> list[str]:
    if not rows:
        return ["  (none)"]
    lines: list[str] = []
    for row in rows:
        values = ", ".join(
            f"{row_id}={value or '<blank>'}"
            for row_id, value in row["values"].items()
        )
        lines.append(f"  {row['field']}: {values}")
    return lines


def format_report_text(report: dict[str, Any]) -> str:
    lines = [
        f"input_kind={report['input_kind']}",
        f"payload_length={report['payload_length']}",
        f"monster_hcidx(row_index)={report['monster_hcidx']}",
        f"bind_metadata(+52)={report['bind_metadata']}",
        "",
    ]
    if "source" in report:
        lines.insert(1, f"source={report['source']}")
    if "monster_seed_hex" in report:
        lines.insert(-1, f"monster_seed(+6)={report['monster_seed_hex']}")

    lines.extend(_format_affixes(report["affixes"]))
    lines.extend(
        [
            "",
            "yaml_authoring_hint:",
            f"  monster_hcidx: {report['yaml_authoring_hint']['monster_hcidx']}",
            "  raw_affixes: "
            + ", ".join(report["yaml_authoring_hint"]["raw_affixes"]),
            "  note: " + report["yaml_authoring_hint"]["composition_note"],
        ]
    )

    if "monstats_row" in report:
        fields = report["monstats_row"]["fields"]
        lines.extend(
            [
                "",
                "monstats_row:",
                f"  row_index: {report['monstats_row']['row_index']}",
                f"  Id: {fields['id'] or '<blank>'}",
                f"  *hcIdx: {fields['monstats_hcidx_column'] or '<blank>'}",
                f"  NameStr: {fields['name_str'] or '<blank>'}",
                f"  MonStatsEx: {fields['monstats_ex'] or '<blank>'}",
                f"  MonType: {fields['mon_type'] or '<blank>'}",
                f"  AI: {fields['ai'] or '<blank>'}",
                f"  Level(H): {fields['level_h'] or '<blank>'}",
                f"  note: {report['monstats_row']['note']}",
            ]
        )

    if "model_comparison" in report:
        comparison = report["model_comparison"]
        lines.extend(
            [
                "",
                "model_comparison:",
                f"  source_hcidx: {comparison['source_hcidx']}",
                "  compared_hcidx: "
                + ", ".join(str(value) for value in comparison["compared_hcidx"]),
                "  monstats_differences:",
            ]
        )
        lines.extend(_format_diff_rows(comparison["monstats_differences"]))
        lines.append("  monstats2_differences:")
        lines.extend(_format_diff_rows(comparison["monstats2_differences"]))
        if comparison["missing_monstats2_ids"]:
            lines.append(
                "  missing_monstats2_ids: "
                + ", ".join(comparison["missing_monstats2_ids"])
            )
        lines.append(f"  note: {comparison['note']}")

    lines.extend([""])
    lines.extend(_format_unknown_slices(report["unknown_slices"]))
    lines.extend(["", "warnings:"])
    lines.extend(f"  - {warning}" for warning in report["warnings"])
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect one Bind Demon template payload or .d2s save."
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Raw 116-byte payload file or .d2s file with one follower.",
    )
    parser.add_argument(
        "--excel-dir",
        type=Path,
        help="Optional directory containing extracted MonStats.txt.",
    )
    parser.add_argument(
        "--compare-hcidx",
        type=int,
        nargs="+",
        help=(
            "Optional target payload row indexes to compare against the "
            "template's monster_hcidx. Requires --excel-dir."
        ),
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON.")
    parser.add_argument(
        "--include-path",
        action="store_true",
        help="Include the local input path. Keep this private.",
    )
    parser.add_argument(
        "--include-values",
        action="store_true",
        help="Include seed and raw unknown-slice bytes. Keep this private.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = build_report(
            args.input,
            excel_dir=args.excel_dir,
            compare_hcidx=args.compare_hcidx,
            include_path=args.include_path,
            include_values=args.include_values,
        )
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        json.dump(report, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        print(format_report_text(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
