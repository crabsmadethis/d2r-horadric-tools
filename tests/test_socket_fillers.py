"""Tests for socket parent/filler grouping."""

from __future__ import annotations

import pytest

pytest.importorskip(
    "d2r_chargen.data.item_stat_cost",
    reason="game data not extracted (run 'd2r-mod extract')",
)

from d2r_chargen.build_lib import build_item
from d2r_chargen.importer import _decode_items
from d2r_chargen.resolve import resolve_unique
from d2r_chargen.scanner import summarize_socket_groups


def _socket_parent_with_magic_jewel(*, expected_fillers: int = 1):
    parent = build_item(
        type_code="flc",
        col=0,
        row=0,
        storage=1,
        location=0,
        quality=2,
        ilvl=20,
        socketed=True,
        num_sockets=1,
        socket_filler_count=expected_fillers,
        max_dur=30,
        cur_dur=30,
    )
    jewel = build_item(
        type_code="jew",
        col=0,
        row=0,
        storage=0,
        location=6,
        bodyloc=0,
        quality=4,
        ilvl=20,
        magic_prefix=0,
        magic_suffix=0,
        properties=[(39, 5)],  # fireresist
    )
    return parent, jewel


def _socket_parent_with_unique_cjw(*, expected_fillers: int = 1):
    parent = build_item(
        type_code="flc",
        col=0,
        row=0,
        storage=1,
        location=0,
        quality=2,
        ilvl=25,
        socketed=True,
        num_sockets=1,
        socket_filler_count=expected_fillers,
        max_dur=30,
        cur_dur=30,
    )
    unique = resolve_unique("Guardian's Thunder")
    jewel = build_item(
        type_code=unique["type_code"],
        col=0,
        row=0,
        storage=0,
        location=6,
        bodyloc=0,
        quality=7,
        ilvl=110,
        unique_id=unique["unique_id"],
        properties=unique["properties"],
    )
    return parent, jewel


def test_socket_group_summary_handles_extended_jewel_filler():
    parent, jewel = _socket_parent_with_magic_jewel()
    data = parent + jewel

    groups = summarize_socket_groups(data, [0, len(parent)])

    assert len(groups) == 1
    assert groups[0]["expected"] == 1
    assert groups[0]["actual"] == 1
    assert groups[0]["mismatch"] is False
    assert groups[0]["parent"].type_code == "flc"
    assert groups[0]["fillers"][0].type_code == "jew"
    assert groups[0]["fillers"][0].quality == 4
    assert groups[0]["fillers"][0].location == 6
    assert groups[0]["fillers"][0].col == 0
    assert groups[0]["fillers"][0].is_simple is False


def test_socket_group_summary_reports_parent_count_mismatch():
    parent, jewel = _socket_parent_with_magic_jewel(expected_fillers=2)
    data = parent + jewel

    groups = summarize_socket_groups(data, [0, len(parent)])

    assert groups[0]["expected"] == 2
    assert groups[0]["actual"] == 1
    assert groups[0]["mismatch"] is True


def test_importer_groups_extended_jewel_filler_under_parent():
    parent, jewel = _socket_parent_with_magic_jewel()
    data = b"JM\x01\x00" + parent + jewel + b"jf"

    equipment, inventory, stash, cube, merc_equipment = _decode_items(data)

    assert equipment == []
    assert stash == []
    assert cube == []
    assert merc_equipment == []
    assert len(inventory) == 1
    assert inventory[0]["base"] == "flc"
    assert "fillers" in inventory[0]
    assert inventory[0]["fillers"][0]["socket_index"] == 0
    assert inventory[0]["fillers"][0]["base"] == "jew"
    assert inventory[0]["fillers"][0]["magic"] is True


def test_socket_group_summary_handles_unique_colossal_jewel_filler():
    parent, jewel = _socket_parent_with_unique_cjw()
    data = parent + jewel

    groups = summarize_socket_groups(data, [0, len(parent)])

    assert len(groups) == 1
    assert groups[0]["expected"] == 1
    assert groups[0]["actual"] == 1
    assert groups[0]["mismatch"] is False
    assert groups[0]["parent"].type_code == "flc"
    assert groups[0]["fillers"][0].type_code == "cjw"
    assert groups[0]["fillers"][0].quality == 7
    assert groups[0]["fillers"][0].uid == 421
    assert groups[0]["fillers"][0].location == 6


def test_importer_groups_unique_colossal_jewel_filler_under_parent():
    parent, jewel = _socket_parent_with_unique_cjw()
    data = b"JM\x01\x00" + parent + jewel + b"jf"

    equipment, inventory, stash, cube, merc_equipment = _decode_items(data)

    assert equipment == []
    assert stash == []
    assert cube == []
    assert merc_equipment == []
    assert len(inventory) == 1
    assert inventory[0]["base"] == "flc"
    assert inventory[0]["fillers"][0]["socket_index"] == 0
    assert inventory[0]["fillers"][0]["unique"] == "Guardian's Thunder"
