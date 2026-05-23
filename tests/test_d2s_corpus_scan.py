import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.d2s_corpus_scan import CorpusSummary, calc_checksum, summarize_file  # noqa: E402
from tools.d2s_corpus_scan import render_merc_status_report  # noqa: E402
from tools.d2s_corpus_scan import render_merc_status_context_report  # noqa: E402
from tools.d2s_corpus_scan import render_merc_status_report_payload  # noqa: E402


def _put_u16(data: bytearray, offset: int, value: int) -> None:
    struct.pack_into("<H", data, offset, value)


def _put_u32(data: bytearray, offset: int, value: int) -> None:
    struct.pack_into("<I", data, offset, value)


def _make_payload(*, extra_gf_offset: int | None = None) -> bytes:
    payload = bytearray(116)
    _put_u16(payload, 0, 24)
    _put_u16(payload, 2, 3)
    _put_u16(payload, 4, 20)
    _put_u32(payload, 24, 2)
    _put_u32(payload, 28, 85)
    _put_u32(payload, 44, 100)
    _put_u32(payload, 48, 100)
    _put_u32(payload, 52, 7)
    payload[64:80] = bytes.fromhex(
        "00 00 00 00 00 01 00 01 01 00 00 00 00 00 00 00"
    )
    payload[80:85] = bytes.fromhex("19 06 05 1b 1e")
    _put_u32(payload, 88, 0x03B8C400)
    payload[92:94] = b"gf"
    if extra_gf_offset is not None:
        payload[extra_gf_offset : extra_gf_offset + 2] = b"gf"
    payload[95:116] = bytes.fromhex(
        "d0 29 48 00 0e a0 53 90 00 30 c0 02 00 00 68 80 3d 51 00 f0 1f"
    )
    return bytes(payload)


def _make_save(
    payload: bytes,
    *,
    follower_count: int = 1,
    include_jf: bool = True,
    merc_item_count: int = 3,
) -> bytes:
    lf_offset = 0x2A5
    data = bytearray(lf_offset + 4 + len(payload))
    data[:4] = b"\x55\xaa\x55\xaa"
    _put_u32(data, 0x04, 105)
    data[0x14] = 0x20
    data[0x15] = 15
    data[0x18] = 7
    data[0x1B] = 90
    data[0x98] = 2
    _put_u16(data, 0xA7, 11)
    _put_u16(data, 0xA9, 271)
    _put_u32(data, 0xAB, 123456)

    data[0x250:0x252] = b"gf"
    data[0x260:0x262] = b"if"
    data[0x270:0x272] = b"JM"
    if include_jf:
        data[0x280:0x282] = b"jf"
    data[0x290:0x292] = b"JM"
    _put_u16(data, 0x292, merc_item_count)
    data[0x2A0:0x2A2] = b"kf"
    data[0x2A2] = 0
    data[lf_offset : lf_offset + 2] = b"lf"
    _put_u16(data, lf_offset + 2, follower_count)
    data[lf_offset + 4 :] = payload

    _put_u32(data, 0x08, len(data))
    _put_u32(data, 0x0C, calc_checksum(data))
    return bytes(data)


def test_corpus_scan_reports_follower_payload_and_grouped_counters(tmp_path):
    save = tmp_path / "probe.d2s"
    save.write_bytes(_make_save(_make_payload()))

    summary = CorpusSummary()
    summarize_file(summary, tmp_path, save)
    counters = summary.as_dict()["counters"]

    assert counters["follower_payload_ok"] == {"true": 1}
    assert counters["follower_payloads_decoded"] == {"true": 1}
    assert counters["follower_payload_gf_offsets"] == {"92": 1}
    assert counters["follower_payload_has_gf_at_92"] == {"true": 1}
    assert counters["follower_payload_runtime_u32_24"] == {"2": 1}
    assert counters["follower_payload_hashlike_u32_88"] == {str(0x03B8C400): 1}
    assert counters["follower_payload_hashlike_u32_88_by_class_id"] == {
        f"{0x03B8C400}|7": 1
    }
    assert counters["follower_payload_bitfield_64_79"] == {
        "00 00 00 00 00 01 00 01 01 00 00 00 00 00 00 00": 1
    }
    assert counters["follower_payload_bitfield_64_79_by_source_bucket"] == {
        "00 00 00 00 00 01 00 01 01 00 00 00 00 00 00 00|single_file_or_root": 1
    }
    assert counters["merc_status_by_hireling_id"] == {"11|271": 1}
    assert counters["merc_status_by_merc_item_count"] == {"11|3": 1}
    assert counters["jf_presence_by_class_id"] == {"true|7": 1}
    assert counters["jf_presence_by_follower_count"] == {"true|1": 1}


def test_merc_status_report_renders_grouped_sections(tmp_path):
    save = tmp_path / "merc-probe.d2s"
    save.write_bytes(_make_save(_make_payload(), merc_item_count=0))

    summary = CorpusSummary()
    summarize_file(summary, tmp_path, save)

    report = "\n".join(render_merc_status_report(summary, top=5))
    assert "merc_status:" in report
    assert "11: 1" in report
    assert "merc_status_by_merc_item_count:" in report
    assert "11|0: 1" in report


def test_merc_status_context_report_renders_combined_sections(tmp_path):
    save = tmp_path / "merc-context-probe.d2s"
    save.write_bytes(_make_save(_make_payload(), merc_item_count=0))

    summary = CorpusSummary()
    summarize_file(summary, tmp_path, save)

    report = "\n".join(render_merc_status_context_report(summary, top=5))
    assert "merc_status:" in report
    assert "11: 1" in report
    assert "merc_status_by_progression_difficulty:" in report
    assert "11|15|2: 1" in report
    assert "merc_status_by_hireling_id_merc_item_count:" in report
    assert "11|271|0: 1" in report


def test_merc_status_report_payload_emits_aggregate_json(tmp_path):
    save = tmp_path / "merc-json-probe.d2s"
    save.write_bytes(_make_save(_make_payload(), merc_item_count=0))

    summary = CorpusSummary()
    summarize_file(summary, tmp_path, save)

    payload = render_merc_status_report_payload(summary, top=5, context=False)
    assert payload["report"] == "merc-status"
    assert payload["valid_d2s"] == 1
    assert payload["sections"]["merc_status"] == [{"value": "11", "count": 1}]
    assert payload["sections"]["merc_status_by_merc_item_count"] == [
        {"value": "11|0", "count": 1}
    ]


def test_merc_status_context_report_payload_emits_combined_sections(tmp_path):
    save = tmp_path / "merc-json-context-probe.d2s"
    save.write_bytes(_make_save(_make_payload(), merc_item_count=0))

    summary = CorpusSummary()
    summarize_file(summary, tmp_path, save)

    payload = render_merc_status_report_payload(summary, top=5, context=True)
    assert payload["report"] == "merc-status-context"
    assert payload["sections"]["merc_status"] == [{"value": "11", "count": 1}]
    assert payload["sections"]["merc_status_by_progression_difficulty"] == [
        {"value": "11|15|2", "count": 1}
    ]
    assert payload["sections"]["merc_status_by_hireling_id_merc_item_count"] == [
        {"value": "11|271|0", "count": 1}
    ]


def test_corpus_scan_accepts_missing_jf_with_empty_merc_and_no_follower(tmp_path):
    save = tmp_path / "no-jf.d2s"
    save.write_bytes(
        _make_save(b"", follower_count=0, include_jf=False, merc_item_count=0)
    )

    summary = CorpusSummary()
    summarize_file(summary, tmp_path, save)
    counters = summary.as_dict()["counters"]

    assert counters["tail_markers_ok"] == {"true": 1}
    assert counters["has_jf_before_merc_jm"] == {"false": 1}
    assert counters["follower_payload_ok"] == {"true": 1}
    assert counters["jf_presence_by_merc_item_count"] == {"false|0": 1}


def test_corpus_scan_reports_invalid_follower_count_without_payload(tmp_path):
    save = tmp_path / "invalid-follower.d2s"
    save.write_bytes(_make_save(b"", follower_count=1))

    summary = CorpusSummary(examples_limit=2)
    summarize_file(summary, tmp_path, save)
    data = summary.as_dict()

    assert data["counters"]["follower_payload_ok"] == {"false": 1}
    assert data["counters"]["trailing_payload_bytes"] == {"0": 1}
    assert data["examples"]["invalid_followers"] == ["invalid-follower.d2s"]


def test_corpus_scan_decodes_multiple_synthetic_follower_payloads(tmp_path):
    save = tmp_path / "two-followers.d2s"
    save.write_bytes(_make_save(_make_payload() * 2, follower_count=2))

    summary = CorpusSummary()
    summarize_file(summary, tmp_path, save)
    counters = summary.as_dict()["counters"]

    assert counters["follower_payload_ok"] == {"true": 1}
    assert counters["follower_payloads_decoded"] == {"true": 2}
    assert counters["follower_payload_gf_offsets"] == {"92": 2}
    assert counters["jf_presence_by_follower_count"] == {"true|2": 1}


def test_corpus_scan_reports_all_gf_offsets_inside_payload(tmp_path):
    save = tmp_path / "extra-gf.d2s"
    save.write_bytes(_make_save(_make_payload(extra_gf_offset=10)))

    summary = CorpusSummary()
    summarize_file(summary, tmp_path, save)
    counters = summary.as_dict()["counters"]

    assert counters["follower_payload_gf_offsets"] == {"10,92": 1}
    assert counters["follower_payload_has_gf_at_92"] == {"true": 1}
