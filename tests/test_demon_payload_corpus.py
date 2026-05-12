from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.d2s_demon_payload_corpus import (  # noqa: E402
    build_report,
    format_report_text,
)


def _payload(
    *,
    monster_hcidx: int = 20,
    seed: int = 0x12345678,
    bind_metadata: int = 7,
    affixes: bytes = b"\x01\x02\x03\x00\x00",
) -> bytes:
    payload = bytearray(116)
    payload[0:2] = b"\x18\x00"
    struct.pack_into("<H", payload, 4, monster_hcidx)
    struct.pack_into("<I", payload, 6, seed)
    struct.pack_into("<I", payload, 52, bind_metadata)
    payload[80:85] = affixes
    payload[92:94] = b"gf"
    return bytes(payload)


def _save_with_single_follower(payload: bytes) -> bytes:
    return b"\x00" * 0x40 + b"kf\x00\x01\x00lf" + b"\x01\x00" + payload


def test_corpus_report_accepts_raw_payloads_and_saves_without_path_leakage(tmp_path):
    raw_payload = tmp_path / "raw.bin"
    save = tmp_path / "bound.d2s"
    bad = tmp_path / "empty.d2s"
    raw_payload.write_bytes(_payload(seed=0x11111111))
    save.write_bytes(
        _save_with_single_follower(
            _payload(seed=0x22222222, affixes=b"\x04\x05\x06\x00\x00")
        )
    )
    bad.write_bytes(b"\x00" * 128)

    report = build_report([raw_payload, save, bad])
    rendered = format_report_text(report)

    assert report["input_count"] == 3
    assert report["payload_count"] == 2
    assert report["load_failure_count"] == 1
    assert report["monster_hcidx"] == [{"value": 20, "count": 2}]
    assert {"value": "01020300000000", "count": 1} in report["affix_tuples"]
    assert {"value": "04050600000000", "count": 1} in report["affix_tuples"]
    assert str(tmp_path) not in rendered
    assert "raw.bin" not in rendered
    assert "bound.d2s" not in rendered


def test_corpus_json_is_serializable_and_omits_sources_by_default(tmp_path):
    payload_path = tmp_path / "payload.bin"
    payload_path.write_bytes(_payload())

    report = build_report([payload_path])

    assert "sources" not in report
    assert "failures" not in report
    json.dumps(report, sort_keys=True)


def test_corpus_unknown_slices_classify_variation(tmp_path):
    first = bytearray(_payload())
    second = bytearray(_payload())
    first[24] = 0x10
    second[24] = 0x20
    first_path = tmp_path / "first.bin"
    second_path = tmp_path / "second.bin"
    first_path.write_bytes(bytes(first))
    second_path.write_bytes(bytes(second))

    report = build_report([first_path, second_path])
    runtime_slice = next(
        row for row in report["unknown_slices"] if row["label"] == "runtime_stats_24_31"
    )

    assert runtime_slice["classification"] == "varies"
    assert runtime_slice["unique_count"] == 2


def test_corpus_reports_model_correlated_offsets(tmp_path):
    fallen_a = bytearray(_payload(monster_hcidx=20, seed=0x11111111))
    fallen_b = bytearray(_payload(monster_hcidx=20, seed=0x22222222))
    wraith_a = bytearray(_payload(monster_hcidx=42, seed=0x33333333))
    wraith_b = bytearray(_payload(monster_hcidx=42, seed=0x44444444))
    for payload in (fallen_a, fallen_b):
        payload[24] = 0xAA
    for payload in (wraith_a, wraith_b):
        payload[24] = 0xBB
    fallen_a[89] = 0x01
    fallen_b[89] = 0x02

    paths = []
    for index, payload in enumerate((fallen_a, fallen_b, wraith_a, wraith_b), 1):
        path = tmp_path / f"payload{index}.bin"
        path.write_bytes(bytes(payload))
        paths.append(path)

    report = build_report(paths, include_values=True)
    correlated = {
        row["offset"]: row for row in report["model_correlated_offsets"]
    }
    candidates = {
        row["offset"]: row for row in report["model_candidate_offsets"]
    }

    assert correlated[24]["values_by_monster_hcidx"] == {"20": "aa", "42": "bb"}
    assert 6 not in correlated
    assert 89 not in correlated
    assert 4 in correlated
    assert 4 not in candidates
    assert candidates[24]["values_by_monster_hcidx"] == {"20": "aa", "42": "bb"}
    assert "+024 unknown:runtime_stats_24_31 groups=2 values=20=aa, 42=bb" in (
        format_report_text(report)
    )
    assert "model_candidate_offsets:" in format_report_text(report)
