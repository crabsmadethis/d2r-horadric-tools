#!/usr/bin/env python3
"""Compare MonStats/MonStats2 fields for bound-demon model-swap research.

This helper reads extracted game tables supplied by the caller. It does not
ship or require bundled table data, and its default output omits local paths.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable


MONSTATS_DEFAULT_FIELDS = (
    "Id",
    "BaseId",
    "NextInClass",
    "TransLvl",
    "NameStr",
    "MonStatsEx",
    "MonProp",
    "MonType",
    "AI",
    "Code",
    "Velocity",
    "Run",
    "Rarity",
    "Level",
    "Level(N)",
    "Level(H)",
    "threat",
    "aidel",
    "aidist",
    "aip1",
    "aip2",
    "aip3",
    "aip4",
    "aip5",
    "aip6",
    "aip7",
    "aip8",
    "Align",
    "isSpawn",
    "isMelee",
    "SizeX",
    "ResFi",
    "ResLi",
    "ResCo",
    "ResPo",
    "ResMa",
    "ResDm",
    "Drain",
    "Drain(N)",
    "Drain(H)",
    "ToBlock",
    "Crit",
    "minHP",
    "maxHP",
    "AC",
    "A1MinD",
    "A1MaxD",
    "A1TH",
    "A2MinD",
    "A2MaxD",
    "El1Mode",
    "El1Type",
    "El1Pct",
    "El1MinD",
    "El1MaxD",
    "El1Dur",
)

MONSTATS2_DEFAULT_FIELDS = (
    "Id",
    "Height",
    "OverlayHeight",
    "pixHeight",
    "SizeX",
    "SizeY",
    "spawnCol",
    "MeleeRng",
    "BaseW",
    "HitClass",
    "HDv",
    "TRv",
    "LGv",
    "Rav",
    "Lav",
    "RHv",
    "LHv",
    "HD",
    "TR",
    "LG",
    "RA",
    "LA",
    "RH",
    "LH",
    "SH",
    "S1",
    "S2",
    "S3",
    "S4",
    "TotalPieces",
    "mDT",
    "mNU",
    "mWL",
    "mGH",
    "mA1",
    "mA2",
    "mBL",
    "mSC",
    "mS1",
    "mS2",
    "mS3",
    "mS4",
    "mDD",
    "mKB",
    "mSQ",
    "mRN",
)


def parse_tsv(path: Path) -> list[dict[str, str]]:
    """Read a tab-delimited D2R text table into row dictionaries."""
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
        row["_monstats_hcidx"] = row.get("*hcIdx", "")
        rows.append(row)
    return rows


def _table_path(excel_dir: Path, name: str) -> Path:
    path = excel_dir / name
    if not path.exists():
        raise FileNotFoundError(f"missing {name} under supplied excel directory")
    return path


def _pick(row: dict[str, str], fields: Iterable[str]) -> dict[str, str]:
    return {field: row.get(field, "") for field in fields}


def _diff_fields(rows: list[dict[str, str]], fields: Iterable[str]) -> list[dict[str, Any]]:
    diffs: list[dict[str, Any]] = []
    for field in fields:
        values = {row["Id"]: row.get(field, "") for row in rows}
        if len(set(values.values())) > 1:
            diffs.append({"field": field, "values": values})
    return diffs


def _rows_by_payload_hcidx(
    rows: list[dict[str, str]], hcidx_values: Iterable[int]
) -> list[dict[str, str]]:
    # The bound-demon payload field named `monster_hcidx` is a zero-based
    # MonStats row index. It is not the separate `*hcIdx` column in MonStats.txt.
    by_row_index = {int(row["_row_index"]): row for row in rows}
    selected: list[dict[str, str]] = []
    for hcidx in hcidx_values:
        if hcidx not in by_row_index:
            raise ValueError(f"payload monster_hcidx row index {hcidx} not found")
        selected.append(by_row_index[hcidx])
    return selected


def build_report(
    excel_dir: Path,
    hcidx_values: Iterable[int],
    *,
    monstats_fields: Iterable[str] = MONSTATS_DEFAULT_FIELDS,
    monstats2_fields: Iterable[str] = MONSTATS2_DEFAULT_FIELDS,
) -> dict[str, Any]:
    """Build a public-safe model comparison report."""
    monstats = parse_tsv(_table_path(excel_dir, "MonStats.txt"))
    monstats2 = parse_tsv(_table_path(excel_dir, "MonStats2.txt"))

    selected = _rows_by_payload_hcidx(monstats, hcidx_values)
    monstats2_by_id = {row["Id"]: row for row in monstats2}
    selected_monstats2 = []
    missing_monstats2_ids: list[str] = []
    for row in selected:
        monstats2_id = row.get("MonStatsEx", "")
        if monstats2_id in monstats2_by_id:
            selected_monstats2.append(monstats2_by_id[monstats2_id])
        else:
            missing_monstats2_ids.append(monstats2_id)

    return {
        "hcidx": [int(row["_row_index"]) for row in selected],
        "monstats_rows": [
            {
                "hcidx": int(row["_row_index"]),
                "monstats_hcidx": row["_monstats_hcidx"],
                "fields": _pick(row, monstats_fields),
            }
            for row in selected
        ],
        "monstats_differences": _diff_fields(selected, monstats_fields),
        "monstats2_rows": [
            {"id": row["Id"], "fields": _pick(row, monstats2_fields)}
            for row in selected_monstats2
        ],
        "monstats2_differences": _diff_fields(selected_monstats2, monstats2_fields),
        "missing_monstats2_ids": missing_monstats2_ids,
    }


def _format_diff_section(title: str, diffs: list[dict[str, Any]]) -> list[str]:
    lines = [f"{title}:"]
    if not diffs:
        return lines + ["  (none)"]
    for diff in diffs:
        rendered = ", ".join(
            f"{row_id}={value or '<blank>'}"
            for row_id, value in diff["values"].items()
        )
        lines.append(f"  {diff['field']}: {rendered}")
    return lines


def format_report_text(report: dict[str, Any]) -> str:
    """Render a concise text report without local paths."""
    lines = [
        f"monster_hcidx(row_index)={','.join(str(value) for value in report['hcidx'])}",
        "",
    ]
    lines.extend(_format_diff_section("monstats_differences", report["monstats_differences"]))
    lines.append("")
    lines.extend(_format_diff_section("monstats2_differences", report["monstats2_differences"]))
    if report["missing_monstats2_ids"]:
        missing = ", ".join(value or "<blank>" for value in report["missing_monstats2_ids"])
        lines.extend(["", f"missing_monstats2_ids: {missing}"])
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare MonStats/MonStats2 rows for monster model research."
    )
    parser.add_argument(
        "--excel-dir",
        type=Path,
        required=True,
        help="Directory containing extracted MonStats.txt and MonStats2.txt.",
    )
    parser.add_argument(
        "--hcidx",
        type=int,
        nargs="+",
        required=True,
        help=(
            "Payload monster_hcidx values to compare. These are zero-based "
            "MonStats.txt row indexes, not the MonStats *hcIdx column."
        ),
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report(args.excel_dir, args.hcidx)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(format_report_text(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
