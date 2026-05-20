from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest

from tools.d2s_demon_template_inspect import (
    _yaml_snippet,
    build_report,
    extract_payload,
    format_report_text,
)


def _payload(
    *,
    monster_hcidx: int = 1,
    seed: int = 0x12345678,
    bind_metadata: int = 7,
    affixes: bytes = b"\x25\x1e\x07\x1c\x05\x06\x1b",
) -> bytes:
    payload = bytearray(116)
    payload[0:2] = b"\x18\x00"
    struct.pack_into("<H", payload, 4, monster_hcidx)
    struct.pack_into("<I", payload, 6, seed)
    struct.pack_into("<I", payload, 52, bind_metadata)
    payload[64:80] = b"\x00\x01" * 8
    payload[80:87] = affixes
    payload[89:92] = b"\xaa\xbb\xcc"
    payload[92:94] = b"gf"
    payload[94] = 0x06
    payload[114:116] = b"\xf0\x1f"
    return bytes(payload)


def _save_with_single_follower(payload: bytes) -> bytes:
    return b"\x00" * 0x40 + b"kf\x00\x01\x00lf" + b"\x01\x00" + payload


def _write_monstats(excel_dir: Path) -> None:
    excel_dir.joinpath("MonStats.txt").write_text(
        "\t".join(
            (
                "*hcIdx",
                "Id",
                "NameStr",
                "MonStatsEx",
                "MonType",
                "AI",
                "Level(H)",
            )
        )
        + "\n"
        + "500\twrong-by-column\tWrongName\twrong2\tDemon\tWrongAI\t1\n"
        + "501\tpayload-row\tPayloadName\tpayload2\tDemon\tRightAI\t88\n"
    )
    excel_dir.joinpath("MonStats2.txt").write_text(
        "\t".join(("Id", "Height", "pixHeight", "RHv"))
        + "\n"
        + "wrong2\t1\t64\taxe\n"
        + "payload2\t2\t96\tpik\n"
    )


def test_template_inspect_reports_yaml_fields_without_path_or_seed(tmp_path):
    path = tmp_path / "template.bin"
    path.write_bytes(_payload())

    report = build_report(path)
    rendered = format_report_text(report)

    assert report["payload_length"] == 116
    assert report["input_kind"] == "raw-payload"
    assert report["monster_hcidx"] == 1
    assert report["bind_metadata"] == 7
    assert report["yaml_authoring_hint"]["raw_affixes"] == [
        "Fanaticism",
        "Aura Enchanted",
        "Cursed",
        "Stone Skin",
        "Extra Strong",
        "Extra Fast",
        "Spectral Hit",
    ]
    assert "source" not in report
    assert "monster_seed" not in report
    assert str(tmp_path) not in rendered
    assert "0x12345678" not in rendered
    assert "monster_hcidx(row_index)=1" in rendered
    assert "Payload monster_hcidx is a zero-based MonStats row index" in rendered


def test_template_inspect_can_include_local_values_on_request(tmp_path):
    path = tmp_path / "template.bin"
    path.write_bytes(_payload())

    report = build_report(path, include_path=True, include_values=True)
    rendered = format_report_text(report)

    assert report["source"] == str(path)
    assert report["monster_seed"] == 0x12345678
    assert report["monster_seed_hex"] == "0x12345678"
    assert any("hex" in row for row in report["unknown_slices"])
    assert str(path) in rendered
    assert "monster_seed(+6)=0x12345678" in rendered


def test_template_inspect_uses_payload_row_index_for_monstats_context(tmp_path):
    payload_path = tmp_path / "template.bin"
    payload_path.write_bytes(_payload(monster_hcidx=1))
    _write_monstats(tmp_path)

    report = build_report(payload_path, excel_dir=tmp_path)
    row = report["monstats_row"]

    assert row["row_index"] == 1
    assert row["fields"]["id"] == "payload-row"
    assert row["fields"]["monstats_hcidx_column"] == "501"
    assert row["fields"]["ai"] == "RightAI"
    assert "wrong-by-column" not in format_report_text(report)


def test_template_inspect_compares_candidate_model_rows(tmp_path):
    payload_path = tmp_path / "template.bin"
    payload_path.write_bytes(_payload(monster_hcidx=1))
    _write_monstats(tmp_path)

    report = build_report(payload_path, excel_dir=tmp_path, compare_hcidx=[0])
    comparison = report["model_comparison"]
    rendered = format_report_text(report)

    assert comparison["source_hcidx"] == 1
    assert comparison["compared_hcidx"] == [1, 0]
    assert {
        "field": "AI",
        "values": {"payload-row": "RightAI", "wrong-by-column": "WrongAI"},
    } in comparison["monstats_differences"]
    assert {
        "field": "RHv",
        "values": {"payload2": "pik", "wrong2": "axe"},
    } in comparison["monstats2_differences"]
    assert "model_comparison:" in rendered
    assert "AI: payload-row=RightAI, wrong-by-column=WrongAI" in rendered


def test_template_inspect_compare_requires_excel_dir(tmp_path):
    path = tmp_path / "template.bin"
    path.write_bytes(_payload())

    with pytest.raises(ValueError, match="requires --excel-dir"):
        build_report(path, compare_hcidx=[0])


def test_template_inspect_accepts_d2s_with_single_follower(tmp_path):
    path = tmp_path / "template.d2s"
    path.write_bytes(_save_with_single_follower(_payload()))

    report = build_report(path)

    assert report["input_kind"] == "d2s-save"
    assert report["follower_count"] == 1
    json.dumps(report, sort_keys=True)


def test_template_inspect_extracts_raw_payload_template(tmp_path):
    path = tmp_path / "template.d2s"
    output = tmp_path / "local-template.bin"
    payload = _payload(monster_hcidx=724)
    path.write_bytes(_save_with_single_follower(payload))

    result = extract_payload(path, output)

    assert output.read_bytes() == payload
    assert result["payload_length"] == 116
    assert result["monster_hcidx"] == 724
    assert "local template output" in result["privacy_note"]


def test_template_inspect_formats_extraction_yaml_snippet(tmp_path):
    path = tmp_path / "template.bin"
    output = tmp_path / "local-template.bin"
    path.write_bytes(_payload(monster_hcidx=724))

    report = build_report(path)
    report["extraction"] = extract_payload(path, output)
    report["yaml_snippet"] = _yaml_snippet(str(output), 724)

    rendered = format_report_text(report)
    assert "extraction:" in rendered
    assert f"template_path: {output}" in rendered
    assert "monster_hcidx: 724" in rendered
    assert "skill_affixes: auto" not in rendered
