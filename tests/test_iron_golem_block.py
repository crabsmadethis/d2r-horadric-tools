"""Tests for Iron Golem tail decoding and preservation."""
from __future__ import annotations

import struct

import pytest

from d2r_chargen.follower_block import decode_follower_block
from d2r_chargen.iron_golem import (
    compare_iron_golem_payloads,
    decode_iron_golem_block,
    split_iron_golem_payload_records,
)
from d2r_chargen.save import calc_checksum, rebuild_items


GOLEM_PAYLOAD = bytes.fromhex(
    "10 00 80 00 0d 11 40 be 22 5c 6e 79 "
    "7c 8c 08 d1 00 00 08 08 8a 04 ff 01"
)


def _save_with_tail(tail: bytes) -> bytes:
    data = bytearray(b"\x55\xaa\x55\xaa" + b"\x00" * 12)
    data.extend(b"PRE")
    data.extend(b"JM\x00\x00")  # empty char items
    data.extend(b"jf")
    data.extend(b"JM\x00\x00")  # empty merc items
    data.extend(tail)
    struct.pack_into("<I", data, 8, len(data))
    data[12:16] = b"\x00\x00\x00\x00"
    struct.pack_into("<I", data, 12, calc_checksum(data))
    return bytes(data)


def test_decode_no_golem_tail():
    data = _save_with_tail(b"kf\x00\x01\x00lf\x00\x00")
    block = decode_iron_golem_block(data)

    assert block.has_markers
    assert block.has_golem is False
    assert block.has_golem_byte == 0
    assert block.bridge_ok is True
    assert block.item_payload == b""


def test_decode_active_golem_payload():
    data = _save_with_tail(b"kf\x01" + GOLEM_PAYLOAD + b"\x01\x00lf\x00\x00")
    block = decode_iron_golem_block(data)

    assert block.has_markers
    assert block.has_golem is True
    assert block.bridge_ok is True
    assert block.payload_len == len(GOLEM_PAYLOAD)
    assert block.item_payload == GOLEM_PAYLOAD


def test_split_single_parent_golem_payload():
    records = split_iron_golem_payload_records(GOLEM_PAYLOAD)

    assert len(records) == 1
    assert records[0].role == "parent"
    assert records[0].offset == 0
    assert records[0].length == len(GOLEM_PAYLOAD)


def test_split_runeword_golem_payload_records():
    pytest.importorskip(
        "d2r_chargen.data.runewords",
        reason="game data not extracted (run 'd2r-mod extract')",
    )
    from d2r_chargen.items import build_iron_golem_item

    payload = build_iron_golem_item({"runeword": "Strength", "base": "flc"})
    records = split_iron_golem_payload_records(payload)

    assert [record.role for record in records] == [
        "parent",
        "socket_filler_0",
        "socket_filler_1",
    ]
    assert [record.offset for record in records] == [0, 32, 43]
    assert [record.length for record in records] == [32, 11, 11]
    assert records[0].is_runeword
    assert records[0].is_socketed
    assert records[1].is_simple
    assert records[1].location == 6
    assert records[1].col == 0
    assert records[2].location == 6
    assert records[2].col == 1


def test_compare_runeword_golem_payload_groups_parent_diffs():
    pytest.importorskip(
        "d2r_chargen.data.runewords",
        reason="game data not extracted (run 'd2r-mod extract')",
    )
    from d2r_chargen.items import build_iron_golem_item

    before = build_iron_golem_item({"runeword": "Strength", "base": "flc"})
    after = bytearray(before)
    after[23] ^= 0x01
    after[27] ^= 0x02

    comparison = compare_iron_golem_payloads(before, bytes(after))

    assert comparison["same_length"] is True
    assert comparison["diff_offsets"] == [23, 27]
    assert comparison["record_groups"] == [{
        "role": "parent",
        "offset": 0,
        "length": 32,
        "diff_count": 2,
        "diff_offsets": [23, 27],
        "relative_offsets": [23, 27],
    }]


def test_compare_runeword_golem_payload_groups_socket_filler_diffs():
    pytest.importorskip(
        "d2r_chargen.data.runewords",
        reason="game data not extracted (run 'd2r-mod extract')",
    )
    from d2r_chargen.items import build_iron_golem_item

    before = build_iron_golem_item({"runeword": "Strength", "base": "flc"})
    after = bytearray(before)
    after[36] ^= 0x01
    after[48] ^= 0x02

    comparison = compare_iron_golem_payloads(before, bytes(after))

    assert comparison["same_length"] is True
    assert comparison["diff_offsets"] == [36, 48]
    assert comparison["record_groups"] == [
        {
            "role": "socket_filler_0",
            "offset": 32,
            "length": 11,
            "diff_count": 1,
            "diff_offsets": [36],
            "relative_offsets": [4],
        },
        {
            "role": "socket_filler_1",
            "offset": 43,
            "length": 11,
            "diff_count": 1,
            "diff_offsets": [48],
            "relative_offsets": [5],
        },
    ]


def test_compare_unique_helm_golem_payload_groups_d2r_bodyloc_rewrite():
    pytest.importorskip(
        "d2r_chargen.data.item_bases",
        reason="game data not extracted (run 'd2r-mod extract')",
    )
    from d2r_chargen.items import build_iron_golem_item

    before = build_iron_golem_item({
        "unique": "Tarnhelm",
        "allow_canonicalized": True,
    })
    after = bytearray(before)
    after[4] = 0x4D
    after[5] = 0x04

    comparison = compare_iron_golem_payloads(before, bytes(after))

    assert comparison["same_length"] is True
    assert comparison["diff_offsets"] == [4, 5]
    assert comparison["record_groups"] == [{
        "role": "parent",
        "offset": 0,
        "length": 28,
        "diff_count": 2,
        "diff_offsets": [4, 5],
        "relative_offsets": [4, 5],
    }]


def test_compare_unique_axe_golem_payload_groups_d2r_canonicalization_rewrite():
    pytest.importorskip(
        "d2r_chargen.data.item_bases",
        reason="game data not extracted (run 'd2r-mod extract')",
    )
    from d2r_chargen.items import build_iron_golem_item

    before = build_iron_golem_item({
        "unique": "The Gnasher",
        "allow_canonicalized": True,
    })
    after = bytearray(before)
    for offset in range(20, 28):
        after[offset] ^= 0x01

    comparison = compare_iron_golem_payloads(before, bytes(after))

    assert comparison["same_length"] is True
    assert comparison["diff_offsets"] == list(range(20, 28))
    assert comparison["record_groups"] == [{
        "role": "parent",
        "offset": 0,
        "length": len(before),
        "diff_count": 8,
        "diff_offsets": list(range(20, 28)),
        "relative_offsets": list(range(20, 28)),
    }]


def test_follower_decoder_allows_active_golem_gap():
    payload = b"D" * 116
    data = _save_with_tail(
        b"kf\x01" + GOLEM_PAYLOAD + b"\x01\x00lf\x01\x00" + payload
    )

    followers = decode_follower_block(data)

    assert followers.follower_count == 1
    assert followers.payload == payload


def test_rebuild_items_preserves_active_golem_by_default(tmp_path):
    src = tmp_path / "golem.d2s"
    src.write_bytes(_save_with_tail(b"kf\x01" + GOLEM_PAYLOAD + b"\x01\x00lf\x00\x00"))

    rebuilt = rebuild_items(str(src), [], [])
    block = decode_iron_golem_block(bytes(rebuilt))

    assert block.has_golem is True
    assert block.item_payload == GOLEM_PAYLOAD


def test_rebuild_items_can_strip_golem(tmp_path):
    src = tmp_path / "golem.d2s"
    src.write_bytes(_save_with_tail(b"kf\x01" + GOLEM_PAYLOAD + b"\x01\x00lf\x00\x00"))

    rebuilt = rebuild_items(str(src), [], [], preserve_golem=False)
    block = decode_iron_golem_block(bytes(rebuilt))

    assert block.has_golem is False
    assert block.item_payload == b""


def test_rebuild_items_can_inject_golem_payload(tmp_path):
    src = tmp_path / "no_golem.d2s"
    src.write_bytes(_save_with_tail(b"kf\x00\x01\x00lf\x00\x00"))

    rebuilt = rebuild_items(str(src), [], [], iron_golem_payload=GOLEM_PAYLOAD)
    block = decode_iron_golem_block(bytes(rebuilt))

    assert block.has_golem is True
    assert block.item_payload == GOLEM_PAYLOAD


def test_rebuild_items_rejects_empty_golem_payload(tmp_path):
    src = tmp_path / "no_golem.d2s"
    src.write_bytes(_save_with_tail(b"kf\x00\x01\x00lf\x00\x00"))

    with pytest.raises(ValueError, match="iron_golem_payload"):
        rebuild_items(str(src), [], [], iron_golem_payload=b"")
