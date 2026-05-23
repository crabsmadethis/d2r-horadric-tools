import hashlib

import pytest

pytest.importorskip(
    "d2r_chargen.data.item_stat_cost",
    reason="game data not extracted (run 'd2r-mod extract')",
)
pytest.importorskip(
    "d2r_chargen.data.item_bases",
    reason="game data not extracted (run 'd2r-mod extract')",
)

from d2r_chargen import items
from d2r_chargen.data import magic_affixes
from d2r_chargen.importer import _decode_rare_name_ids, _decode_single_item


def _patch_rare_names(monkeypatch):
    display = {"amul": [(20, "Beads"), (21, "Heart")]}
    monkeypatch.setattr(magic_affixes, "RARE_LAST_NAMES", display)
    monkeypatch.setattr(
        magic_affixes,
        "RARE_DISPLAY_NAME_BY_NAME",
        {"beads": 20, "heart": 21},
    )


def test_numeric_rare_names_encode_and_import(monkeypatch):
    _patch_rare_names(monkeypatch)

    built = items.build_equipment_item({
        "slot": "neck",
        "rare": True,
        "base": "amu",
        "rare_first_name": 10,
        "rare_last_name": 21,
    })

    item_bytes = built[0][1]
    assert _decode_rare_name_ids(item_bytes, 0, quality=6) == (10, 21)

    imported = _decode_single_item(item_bytes, 0)
    assert imported["rare"] is True
    assert imported["rare_first_name"] == 10
    assert imported["rare_last_name"] == 21


def test_crafted_names_encode_and_import(monkeypatch):
    _patch_rare_names(monkeypatch)

    built = items.build_equipment_item({
        "slot": "neck",
        "crafted": True,
        "base": "amu",
        "rare_first_name": 11,
        "rare_last_name": 20,
    })

    item_bytes = built[0][1]
    assert _decode_rare_name_ids(item_bytes, 0, quality=8) == (11, 20)

    imported = _decode_single_item(item_bytes, 0)
    assert imported["crafted"] is True
    assert imported["rare_first_name"] == 11
    assert imported["rare_last_name"] == 20


def test_auto_rare_name_seed_is_stable(monkeypatch):
    _patch_rare_names(monkeypatch)
    props = [(7, 45), (105, 20)]

    first, last = items._resolve_rare_names(0, 0, "amu", props)

    h = hashlib.blake2s(digest_size=8)
    h.update(b"amu")
    for prop in props:
        h.update(b"\0")
        h.update(repr(prop).encode("ascii", errors="replace"))
    seed = int.from_bytes(h.digest(), "little") & 0x7FFFFFFF

    assert (first, last) == (
        20 + (seed % 2),
        20 + ((seed * 7 + 3) % 2),
    )


def test_rare_name_row_ids_must_fit_8_bits():
    with pytest.raises(ValueError, match="rare_first_name must fit in 8 bits"):
        items._resolve_rare_names(256, 1, "amu", [])


def test_symbolic_rare_names_resolve_through_rare_suffix(monkeypatch):
    _patch_rare_names(monkeypatch)

    first, last = items._resolve_rare_names("Heart", "Beads", "amu", [])

    assert (first, last) == (21, 20)
