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


def _flags(payload: bytes) -> int:
    return struct.unpack_from("<I", payload, 0)[0]


def _flags_at(payload: bytes, offset: int) -> int:
    return struct.unpack_from("<I", payload, offset)[0]


def _bits_at(payload: bytes, bit_offset: int, width: int) -> int:
    value = 0
    for idx in range(width):
        pos = bit_offset + idx
        value |= ((payload[pos >> 3] >> (pos & 7)) & 1) << idx
    return value


def test_build_normal_iron_golem_item_header():
    payload = build_iron_golem_item({"normal": True, "base": "flc"})
    header = decode_iron_golem_item_header(payload)

    assert header is not None
    assert header.type_code == "flc"
    assert header.quality == 2
    assert header.storage == 0
    assert header.location == 1
    assert header.bodyloc == 4


def test_build_ethereal_normal_iron_golem_item_sets_flag():
    payload = build_iron_golem_item({
        "normal": True,
        "base": "flc",
        "ethereal": True,
    })
    header = decode_iron_golem_item_header(payload)

    assert header is not None
    assert header.quality == 2
    assert _flags(payload) & (1 << 22)


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


@pytest.mark.parametrize(
    ("item", "quality", "type_code"),
    [
        (
            {"set": "Civerb's Cudgel", "properties": {"enhanced_dmg": 50}},
            5,
            "gsc",
        ),
        (
            {
                "rare": True,
                "base": "flc",
                "rare_first_name": 0,
                "rare_last_name": 0,
                "properties": {"fire_res": 10},
            },
            6,
            "flc",
        ),
        (
            {
                "crafted": True,
                "base": "flc",
                "rare_first_name": 0,
                "rare_last_name": 0,
                "properties": {"fire_res": 10},
            },
            8,
            "flc",
        ),
        (
            {"unique": "The Gnasher", "allow_canonicalized": True},
            7,
            "hax",
        ),
        (
            {"unique": "Tarnhelm", "allow_canonicalized": True},
            7,
            "skp",
        ),
    ],
)
def test_build_proven_single_parent_iron_golem_families(item, quality, type_code):
    payload = build_iron_golem_item(item)
    header = decode_iron_golem_item_header(payload)

    assert header is not None
    assert header.type_code == type_code
    assert header.quality == quality
    assert header.storage == 0
    assert header.location == 1
    assert header.col == header.bodyloc


def test_build_socketed_normal_iron_golem_parent_without_fillers():
    payload = build_iron_golem_item({
        "normal": True,
        "base": "flc",
        "socketed": True,
        "num_sockets": 1,
    })
    header = decode_iron_golem_item_header(payload)

    assert header is not None
    assert header.quality == 2
    assert header.type_code == "flc"
    assert _flags(payload) & (1 << 11)


def test_normal_iron_golem_item_rejects_properties():
    with pytest.raises(ValueError, match="normal items cannot specify properties"):
        build_iron_golem_item({
            "normal": True,
            "base": "flc",
            "properties": {"fire_res": 10},
        })


def test_unique_iron_golem_requires_canonicalization_opt_in():
    with pytest.raises(ValueError, match="allow_canonicalized"):
        build_iron_golem_item({"unique": "The Gnasher"})


def test_build_runeword_iron_golem_item_includes_socket_fillers():
    payload = build_iron_golem_item({
        "runeword": "Strength",
        "base": "flc",
    })
    header = decode_iron_golem_item_header(payload)

    assert header is not None
    assert header.type_code == "flc"
    assert header.quality == 2
    assert header.storage == 0
    assert header.location == 1
    assert header.col == header.bodyloc
    assert _flags(payload) & (1 << 11)
    assert _flags(payload) & (1 << 26)

    # Live validation proved the golem block expects a JM-less parent followed
    # immediately by socket filler records before the `01 00 lf` bridge.
    parent_len = 32
    filler_len = 11
    assert len(payload) == parent_len + (2 * filler_len)
    for idx, offset in enumerate((parent_len, parent_len + filler_len)):
        flags = _flags_at(payload, offset)
        assert flags & (1 << 21)
        assert _bits_at(payload, (offset * 8) + 35, 3) == 6
        assert _bits_at(payload, (offset * 8) + 42, 4) == idx


def test_runeword_iron_golem_rejects_manual_socket_overrides():
    with pytest.raises(ValueError, match="sockets are derived"):
        build_iron_golem_item({
            "runeword": "Strength",
            "base": "flc",
            "socketed": True,
            "num_sockets": 2,
        })


@pytest.mark.parametrize(
    "key",
    ["rune_codes", "runes", "fillers", "jewels", "socket_fillers"],
)
def test_iron_golem_rejects_manual_socket_filler_keys(key):
    with pytest.raises(ValueError, match="socket filler keys"):
        build_iron_golem_item({
            "normal": True,
            "base": "flc",
            key: ["r01"],
        })


def test_socketed_magic_iron_golem_remains_blocked():
    with pytest.raises(ValueError, match="socketed support is limited to normal"):
        build_iron_golem_item({
            "magic": True,
            "base": "flc",
            "socketed": True,
            "num_sockets": 1,
            "properties": {"fire_res": 10},
        })


def test_iron_golem_num_sockets_requires_socketed_flag():
    with pytest.raises(ValueError, match="num_sockets requires socketed"):
        build_iron_golem_item({
            "normal": True,
            "base": "flc",
            "num_sockets": 1,
        })


def test_socketed_iron_golem_rejects_over_max_socket_count():
    with pytest.raises(ValueError, match="supports at most"):
        build_iron_golem_item({
            "normal": True,
            "base": "flc",
            "socketed": True,
            "num_sockets": 3,
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
