"""Tests for YAML-driven Iron Golem payload generation."""
from __future__ import annotations

import struct

import pytest

pytest.importorskip(
    "d2r_chargen.data.item_stat_cost",
    reason="game data not extracted (run 'd2r-mod extract')",
)

from d2r_chargen.iron_golem import (
    decode_iron_golem_block,
    decode_iron_golem_item_header,
)
from d2r_chargen.items import build_iron_golem_item
from d2r_chargen.save import calc_checksum, rebuild_items


def _save_with_tail(tail: bytes) -> bytes:
    data = bytearray(b"\x55\xaa\x55\xaa" + b"\x00" * 12)
    data.extend(b"PRE")
    data.extend(b"JM\x00\x00")
    data.extend(b"jf")
    data.extend(b"JM\x00\x00")
    data.extend(tail)
    struct.pack_into("<I", data, 8, len(data))
    data[12:16] = b"\x00\x00\x00\x00"
    struct.pack_into("<I", data, 12, calc_checksum(data))
    return bytes(data)


def _necromancer_with_golem(item):
    return {
        "class": "necromancer",
        "skills": {"IronGolem": 1},
        "iron_golem": {"item": item},
    }


def test_build_normal_iron_golem_item_header():
    payload = build_iron_golem_item({"normal": True, "base": "flc"})
    header = decode_iron_golem_item_header(payload)

    assert header is not None
    assert header.type_code == "flc"
    assert header.quality == 2
    assert header.storage == 0
    assert header.location == 1
    assert header.bodyloc == 4


def test_build_magic_iron_golem_item_header():
    normal = build_iron_golem_item({"normal": True, "base": "flc"})
    magic = build_iron_golem_item({
        "magic": True,
        "base": "flc",
        "properties": {"fire_res": 10},
    })
    header = decode_iron_golem_item_header(magic)

    assert header is not None
    assert header.type_code == "flc"
    assert header.quality == 4
    assert header.storage == 0
    assert header.location == 1
    assert header.bodyloc == 4
    assert len(magic) > len(normal)


def test_normal_iron_golem_item_rejects_properties():
    with pytest.raises(ValueError, match="normal items cannot specify properties"):
        build_iron_golem_item({
            "normal": True,
            "base": "flc",
            "properties": {"fire_res": 10},
        })


def test_resolve_iron_golem_payload_from_char_def():
    pytest.importorskip("yaml")
    from d2r_chargen.character import resolve_iron_golem_payload

    payload = resolve_iron_golem_payload(_necromancer_with_golem({
        "magic": True,
        "base": "flc",
        "properties": {"fire_res": 10},
    }))
    header = decode_iron_golem_item_header(payload)

    assert header is not None
    assert header.type_code == "flc"
    assert header.quality == 4


def test_resolve_iron_golem_payload_rejects_non_necromancer():
    pytest.importorskip("yaml")
    from d2r_chargen.character import resolve_iron_golem_payload

    char_def = _necromancer_with_golem({"normal": True, "base": "flc"})
    char_def["class"] = "sorceress"

    with pytest.raises(ValueError, match="requires class=necromancer"):
        resolve_iron_golem_payload(char_def)


def test_resolve_iron_golem_payload_accepts_case_insensitive_class():
    pytest.importorskip("yaml")
    from d2r_chargen.character import resolve_iron_golem_payload

    char_def = _necromancer_with_golem({"normal": True, "base": "flc"})
    char_def["class"] = "Necromancer"

    payload = resolve_iron_golem_payload(char_def)

    assert decode_iron_golem_item_header(payload).type_code == "flc"


def test_resolve_iron_golem_payload_requires_skill():
    pytest.importorskip("yaml")
    from d2r_chargen.character import resolve_iron_golem_payload

    char_def = _necromancer_with_golem({"normal": True, "base": "flc"})
    char_def["skills"] = {}

    with pytest.raises(ValueError, match="requires IronGolem skill"):
        resolve_iron_golem_payload(char_def)


def test_iron_golem_payload_injects_into_rebuild_tail(tmp_path):
    pytest.importorskip("yaml")
    from d2r_chargen.character import resolve_iron_golem_payload

    payload = resolve_iron_golem_payload(_necromancer_with_golem({
        "normal": True,
        "base": "flc",
    }))
    src = tmp_path / "no_golem.d2s"
    src.write_bytes(_save_with_tail(b"kf\x00\x01\x00lf\x00\x00"))

    rebuilt = rebuild_items(str(src), [], [], iron_golem_payload=payload)
    block = decode_iron_golem_block(bytes(rebuilt))

    assert block.has_golem is True
    assert block.item_payload == payload
