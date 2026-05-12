import json
import subprocess
import sys
from pathlib import Path

from tools.d2s_monster_model_compare import build_report, format_report_text


SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "d2s_monster_model_compare.py"


def _write_tables(excel_dir: Path, *, missing_monstats2: bool = False) -> None:
    excel_dir.joinpath("MonStats.txt").write_text(
        "\t".join(("*hcIdx", "Id", "MonStatsEx", "TransLvl", "AI", "Velocity"))
        + "\n"
        + "\n".join(
            (
                "\tfallen1\tfallen1\t0\tFallen\t5",
                "\tfallen2\tfallen2\t1\tFallen\t5",
                "\tfallen3\tfallen3\t2\tFallen\t6",
            )
        )
        + "\n"
    )
    monstats2_rows = [
        "fallen1\t1\t64\tssd,clb,axe",
        "fallen2\t1\t64\tssd,clb,axe",
    ]
    if not missing_monstats2:
        monstats2_rows.append("fallen3\t1\t64\tssd,clb,axe")
    excel_dir.joinpath("MonStats2.txt").write_text(
        "\t".join(("Id", "Height", "pixHeight", "RHv"))
        + "\n"
        + "\n".join(monstats2_rows)
        + "\n"
    )


def test_build_report_uses_row_index_as_blank_hcidx(tmp_path):
    _write_tables(tmp_path)

    report = build_report(
        tmp_path,
        [0, 1, 2],
        monstats_fields=("TransLvl", "Velocity"),
        monstats2_fields=("Height", "pixHeight", "RHv"),
    )

    assert report["hcidx"] == [0, 1, 2]
    assert report["monstats_differences"] == [
        {
            "field": "TransLvl",
            "values": {"fallen1": "0", "fallen2": "1", "fallen3": "2"},
        },
        {
            "field": "Velocity",
            "values": {"fallen1": "5", "fallen2": "5", "fallen3": "6"},
        },
    ]
    assert report["monstats2_differences"] == []
    assert report["missing_monstats2_ids"] == []


def test_build_report_ignores_monstats_hcidx_column_for_payload_lookup(tmp_path):
    excel_dir = tmp_path
    excel_dir.joinpath("MonStats.txt").write_text(
        "\t".join(("*hcIdx", "Id", "MonStatsEx", "TransLvl", "AI", "Velocity"))
        + "\n"
        + "\n".join(
            (
                "500\twrong-by-column\twrong-by-column\t9\tWrong\t1",
                "501\tpayload-row\tpayload-row\t1\tRight\t5",
            )
        )
        + "\n"
    )
    excel_dir.joinpath("MonStats2.txt").write_text(
        "\t".join(("Id", "Height", "pixHeight", "RHv"))
        + "\n"
        + "wrong-by-column\t1\t64\taxe\n"
        + "payload-row\t2\t96\tpik\n"
    )

    report = build_report(
        excel_dir,
        [1],
        monstats_fields=("Id", "AI"),
        monstats2_fields=("Height", "RHv"),
    )

    assert report["hcidx"] == [1]
    assert report["monstats_rows"] == [
        {
            "hcidx": 1,
            "monstats_hcidx": "501",
            "fields": {"Id": "payload-row", "AI": "Right"},
        }
    ]
    assert report["monstats2_rows"] == [
        {"id": "payload-row", "fields": {"Height": "2", "RHv": "pik"}}
    ]


def test_text_output_omits_local_table_paths(tmp_path):
    _write_tables(tmp_path)

    text = format_report_text(
        build_report(
            tmp_path,
            [0, 1],
            monstats_fields=("TransLvl",),
            monstats2_fields=("Height",),
        )
    )

    assert "monster_hcidx(row_index)=0,1" in text
    assert "monstats_differences:" in text
    assert str(tmp_path) not in text
    assert "MonStats.txt" not in text


def test_missing_monstats2_ids_are_reported(tmp_path):
    _write_tables(tmp_path, missing_monstats2=True)

    report = build_report(
        tmp_path,
        [2],
        monstats_fields=("Id",),
        monstats2_fields=("Height",),
    )

    assert report["missing_monstats2_ids"] == ["fallen3"]
    assert "missing_monstats2_ids: fallen3" in format_report_text(report)


def test_cli_json_output_is_serializable(tmp_path):
    _write_tables(tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--excel-dir",
            str(tmp_path),
            "--hcidx",
            "0",
            "1",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    decoded = json.loads(result.stdout)
    assert decoded["hcidx"] == [0, 1]
