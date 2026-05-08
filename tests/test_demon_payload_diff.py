from pathlib import Path

import pytest

from tools.d2s_demon_payload_diff import diff_offsets, load_payload


FIX = Path(__file__).resolve().parent / "fixtures"


def test_diff_offsets_reports_changed_bytes():
    left = bytearray(b"\x00" * 116)
    right = bytearray(left)
    right[89] = 1
    right[95] = 2

    assert diff_offsets([bytes(left), bytes(right)]) == [
        (89, [0, 1]),
        (95, [0, 2]),
    ]


def test_load_payload_accepts_raw_payload_bin():
    payload = load_payload(FIX / "demon_block_b.bin")

    assert len(payload) == 116
    assert payload == (FIX / "demon_block_b.bin").read_bytes()


def test_load_payload_accepts_d2s_with_bound_demon(tmp_path):
    payload = (FIX / "demon_block_b.bin").read_bytes()
    d2s = tmp_path / "probe.d2s"
    d2s.write_bytes(b"prefix kf\x00\x01\x00lf" + (1).to_bytes(2, "little") + payload)

    assert load_payload(d2s) == payload


def test_load_payload_rejects_non_payload_file(tmp_path):
    bogus = tmp_path / "bogus.bin"
    bogus.write_bytes(b"not a payload")

    with pytest.raises(ValueError, match="116-byte payload"):
        load_payload(bogus)
