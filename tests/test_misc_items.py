"""Tests for normal stash quest and misc item authoring."""

from __future__ import annotations

import os
import shutil
import tempfile

import pytest

pytest.importorskip(
    "d2r_chargen.data.item_stat_cost",
    reason="game data not extracted (run 'd2r-mod extract')",
)

from d2r_chargen.build_lib import get_base_flags
from d2r_chargen.items import build_merc_item
from d2r_chargen.save import rebuild_items
from d2r_chargen.scanner import (
    bits_at,
    decode_huff4,
    decode_item_header,
    scan_character_data,
    validate_item_properties,
)


TEMPLATE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "d2r_chargen",
    "data",
    "template.d2s",
)


def _decode_quantity(item_bytes: bytes) -> int | None:
    pos = 0
    flags32 = int.from_bytes(item_bytes[:4], "little")
    br = pos * 8
    br += 32  # flags
    br += 3   # D2R ext
    br += 3   # location
    br += 4   # bodyloc
    br += 4   # col
    br += 3   # row
    br += 1   # unknown
    br += 3   # storage

    type_code, br = decode_huff4(item_bytes, br)
    base = get_base_flags(type_code)

    br += 3   # nr_in_sockets
    br += 32  # item_id
    br += 7   # ilvl
    quality = bits_at(item_bytes, br, 4)
    br += 4
    assert quality == 2

    multi_pic = bits_at(item_bytes, br, 1)
    br += 1
    if multi_pic:
        br += 3
    class_spec = bits_at(item_bytes, br, 1)
    br += 1
    if class_spec:
        br += 11

    if flags32 & (1 << 24):
        raise AssertionError("personalized item not expected")
    if base & 8:
        br += 5
    ext_body = bits_at(item_bytes, br, 1)
    br += 1
    if ext_body:
        br += 96
    if base & 4:
        br += 11
    if base & 6:
        max_dur = bits_at(item_bytes, br, 8)
        br += 8
        if max_dur > 0:
            br += 9

    if not (base & 1):
        return None
    has_qty = bits_at(item_bytes, br, 1)
    br += 1
    if not has_qty:
        return None
    return bits_at(item_bytes, br, 9)


@pytest.mark.parametrize(
    ("base", "quantity"),
    [
        ("toa", 1),  # Token of Absolution
        ("tes", 3),  # Twisted Essence of Suffering
        ("pk1", 4),  # Key of Terror
        ("xa1", 7),  # Western Worldstone Shard
    ],
)
def test_normal_stash_misc_items_encode_requested_quantity(base, quantity):
    built = build_merc_item(
        {"normal": True, "base": base, "quantity": quantity},
        stash_col=0,
        stash_row=0,
    )

    assert len(built) == 1
    assert _decode_quantity(built[0][1]) == quantity


@pytest.mark.parametrize("base", ["toa", "tes", "pk1", "xa1"])
def test_misc_quantity_items_warn_quantity_may_not_persist(base):
    from d2r_chargen.build_lib import set_build_warnings
    from d2r_chargen.warnings import BuildWarnings

    warnings = BuildWarnings()
    set_build_warnings(warnings)
    try:
        build_merc_item(
            {"normal": True, "base": base, "quantity": 2},
            stash_col=0,
            stash_row=0,
        )
    finally:
        set_build_warnings(None)

    assert warnings.warnings
    assert any(
        ctx == base and "may clear misc/quest item quantity" in msg
        for ctx, msg in warnings.warnings
    )


def test_normal_stash_tome_keeps_book_field_aligned():
    built = build_merc_item(
        {"normal": True, "base": "tbk", "quantity": 20},
        stash_col=0,
        stash_row=0,
    )
    item_bytes = built[0][1]
    hdr = decode_item_header(item_bytes, 0)
    itype, _ilvl, quality, _uid, _storage, _col, _row, _bodyloc, _location, _ext = hdr
    flags32 = int.from_bytes(item_bytes[:4], "little")

    assert get_base_flags("tbk") & 8
    assert _decode_quantity(item_bytes) == 20
    ok, error, _end = validate_item_properties(
        item_bytes,
        0,
        itype,
        quality,
        bool(flags32 & (1 << 26)),
        bool(flags32 & (1 << 11)),
        flags32,
    )
    assert ok is True
    assert error is None


def test_misc_quantity_stash_items_scan_in_full_character_save():
    pytest.importorskip("yaml", reason="PyYAML is required for full chargen imports")
    from d2r_chargen.character import build_all_items

    char_def = {
        "name": "Miscqty",
        "class": "necromancer",
        "level": 90,
        "stats": {
            "strength": 100,
            "dexterity": 60,
            "vitality": 250,
            "energy": 80,
        },
        "skills": {},
        "equipment": [],
        "stash_items": [
            {"normal": True, "base": "toa", "quantity": 1},
            {"normal": True, "base": "pk1", "quantity": 4},
            {"normal": True, "base": "tbk", "quantity": 20},
        ],
    }
    items = [item_bytes for _section, item_bytes in build_all_items(char_def)]

    with tempfile.NamedTemporaryFile(suffix=".d2s", delete=False) as handle:
        tmp_path = handle.name
    try:
        shutil.copy2(TEMPLATE_PATH, tmp_path)
        rebuilt = rebuild_items(tmp_path, items, [])
        with open(tmp_path, "wb") as handle:
            handle.write(rebuilt)

        scan = scan_character_data(tmp_path)
    finally:
        os.unlink(tmp_path)

    assert scan["checksum_ok"] is True
    assert scan["size_ok"] is True
    assert scan["errors"] == []
    assert scan["item_count"] == 3


def test_misc_quantity_stash_items_import_back_from_full_character_save():
    pytest.importorskip("yaml", reason="PyYAML is required for full chargen imports")
    from d2r_chargen.character import build_all_items
    from d2r_chargen.importer import import_character

    char_def = {
        "name": "Miscqty",
        "class": "necromancer",
        "level": 90,
        "stats": {
            "strength": 100,
            "dexterity": 60,
            "vitality": 250,
            "energy": 80,
        },
        "skills": {},
        "equipment": [],
        "stash_items": [
            {"normal": True, "base": "toa", "quantity": 1},
            {"normal": True, "base": "pk1", "quantity": 4},
            {"normal": True, "base": "tbk", "quantity": 20},
        ],
    }
    items = [item_bytes for _section, item_bytes in build_all_items(char_def)]

    with tempfile.NamedTemporaryFile(suffix=".d2s", delete=False) as handle:
        tmp_path = handle.name
    try:
        shutil.copy2(TEMPLATE_PATH, tmp_path)
        rebuilt = rebuild_items(tmp_path, items, [])
        with open(tmp_path, "wb") as handle:
            handle.write(rebuilt)

        imported = import_character(tmp_path)
    finally:
        os.unlink(tmp_path)

    stash = imported.get("stash", [])
    assert [(item.get("base"), item.get("quantity")) for item in stash] == [
        ("toa", 1),
        ("pk1", 4),
        ("tbk", 20),
    ]


def test_organ_quest_stash_items_scan_in_full_character_save():
    pytest.importorskip("yaml", reason="PyYAML is required for full chargen imports")
    from d2r_chargen.character import build_all_items

    char_def = {
        "name": "Miscorg",
        "class": "necromancer",
        "level": 90,
        "stats": {
            "strength": 100,
            "dexterity": 60,
            "vitality": 250,
            "energy": 80,
        },
        "skills": {},
        "equipment": [],
        "stash_items": [
            {"normal": True, "base": "mbr"},
            {"normal": True, "base": "bey"},
            {"normal": True, "base": "dhn"},
        ],
    }
    items = [item_bytes for _section, item_bytes in build_all_items(char_def)]

    with tempfile.NamedTemporaryFile(suffix=".d2s", delete=False) as handle:
        tmp_path = handle.name
    try:
        shutil.copy2(TEMPLATE_PATH, tmp_path)
        rebuilt = rebuild_items(tmp_path, items, [])
        with open(tmp_path, "wb") as handle:
            handle.write(rebuilt)

        scan = scan_character_data(tmp_path)
    finally:
        os.unlink(tmp_path)

    assert scan["checksum_ok"] is True
    assert scan["size_ok"] is True
    assert scan["errors"] == []
    assert scan["item_count"] == 3


def test_organ_quest_stash_items_import_back_from_full_character_save():
    pytest.importorskip("yaml", reason="PyYAML is required for full chargen imports")
    from d2r_chargen.character import build_all_items
    from d2r_chargen.importer import import_character

    char_def = {
        "name": "Miscorg",
        "class": "necromancer",
        "level": 90,
        "stats": {
            "strength": 100,
            "dexterity": 60,
            "vitality": 250,
            "energy": 80,
        },
        "skills": {},
        "equipment": [],
        "stash_items": [
            {"normal": True, "base": "mbr"},
            {"normal": True, "base": "bey"},
            {"normal": True, "base": "dhn"},
        ],
    }
    items = [item_bytes for _section, item_bytes in build_all_items(char_def)]

    with tempfile.NamedTemporaryFile(suffix=".d2s", delete=False) as handle:
        tmp_path = handle.name
    try:
        shutil.copy2(TEMPLATE_PATH, tmp_path)
        rebuilt = rebuild_items(tmp_path, items, [])
        with open(tmp_path, "wb") as handle:
            handle.write(rebuilt)

        imported = import_character(tmp_path)
    finally:
        os.unlink(tmp_path)

    stash = imported.get("stash", [])
    assert [item.get("base") for item in stash] == ["mbr", "bey", "dhn"]
    assert [item.get("col", 0) for item in stash] == [0, 1, 2]
    assert [item.get("row", 0) for item in stash] == [0, 0, 0]


def test_quest_weapon_and_reward_stash_items_scan_and_import():
    pytest.importorskip("yaml", reason="PyYAML is required for full chargen imports")
    from d2r_chargen.character import build_all_items
    from d2r_chargen.importer import import_character

    char_def = {
        "name": "Miscqst",
        "class": "necromancer",
        "level": 90,
        "stats": {
            "strength": 100,
            "dexterity": 60,
            "vitality": 250,
            "energy": 80,
        },
        "skills": {},
        "equipment": [],
        "stash_items": [
            {"normal": True, "base": "hdm"},  # Horadric Malus
            {"normal": True, "base": "msf"},  # Staff of Kings
            {"normal": True, "base": "hst"},  # Horadric Staff
            {"normal": True, "base": "qf1"},  # Khalim's Flail
            {"normal": True, "base": "qf2"},  # Khalim's Will
            {"normal": True, "base": "qhr"},  # Khalim's Heart
            {"normal": True, "base": "bbb"},  # Lam Esen's Tome
            {"normal": True, "base": "j34"},  # A Jade Figurine
            {"normal": True, "base": "leg"},  # Wirt's Leg
            {"normal": True, "base": "tr2"},  # Scroll of Resistance
        ],
    }
    items = [item_bytes for _section, item_bytes in build_all_items(char_def)]

    with tempfile.NamedTemporaryFile(suffix=".d2s", delete=False) as handle:
        tmp_path = handle.name
    try:
        shutil.copy2(TEMPLATE_PATH, tmp_path)
        rebuilt = rebuild_items(tmp_path, items, [])
        with open(tmp_path, "wb") as handle:
            handle.write(rebuilt)

        scan = scan_character_data(tmp_path)
        imported = import_character(tmp_path)
    finally:
        os.unlink(tmp_path)

    assert scan["checksum_ok"] is True
    assert scan["size_ok"] is True
    assert scan["errors"] == []
    assert scan["item_count"] == 10
    stash = imported.get("stash", [])
    assert [item.get("base") for item in stash] == [
        "hdm",
        "msf",
        "hst",
        "qf1",
        "qf2",
        "qhr",
        "bbb",
        "j34",
        "leg",
        "tr2",
    ]


def test_normal_stash_quantity_validation():
    with pytest.raises(ValueError, match="quantity must fit in 9 bits"):
        build_merc_item(
            {"normal": True, "base": "toa", "quantity": 512},
            stash_col=0,
            stash_row=0,
        )

    with pytest.raises(ValueError, match="does not support quantity"):
        build_merc_item(
            {"normal": True, "base": "flc", "quantity": 1},
            stash_col=0,
            stash_row=0,
        )
