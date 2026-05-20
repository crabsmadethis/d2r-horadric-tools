"""Tests for the custom unique build script."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "new_uniques.py"
TABLE_KEY = "data/global/excel/UniqueItems.txt"


def _load_module():
    spec = importlib.util.spec_from_file_location("new_uniques", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _base_tables():
    return {
        TABLE_KEY: [
            {
                "index": "Crafted Black Cleft",
                "*ID": "437",
                "code": "cs2",
                "lvl": "69",
                "prop1": "item_pierce_magic_immunity",
                "par1": "",
                "min1": "300",
                "max1": "300",
                "*eol": "0",
            }
        ]
    }


def test_appends_historical_custom_uniques_at_stable_ids():
    module = _load_module()
    tables = _base_tables()

    warnings = module.apply(tables)
    rows_by_name = {row["index"]: row for row in tables[TABLE_KEY]}

    assert [item["index"] for item in module.NEW_ITEMS] == [
        "Flamekeeper's Antlers",
        "Thunderhurler's Grip",
        "Hawkeye's Sight",
        "Deathgrip Scepter",
        "Crusader's Vengeance",
        "Manoomin",
    ]
    assert rows_by_name["Flamekeeper's Antlers"]["*ID"] == "438"
    assert rows_by_name["Thunderhurler's Grip"]["*ID"] == "439"
    assert rows_by_name["Hawkeye's Sight"]["*ID"] == "440"
    assert rows_by_name["Deathgrip Scepter"]["*ID"] == "441"
    assert rows_by_name["Crusader's Vengeance"]["*ID"] == "442"
    assert rows_by_name["Manoomin"]["*ID"] == "443"
    assert rows_by_name["Crusader's Vengeance"]["code"] == "7cr"
    assert rows_by_name["Manoomin"]["code"] == "cm1"
    assert len(warnings) == 6


def test_script_rejects_conflicting_stable_id():
    module = _load_module()
    tables = _base_tables()
    tables[TABLE_KEY].append({"index": "Other Custom", "*ID": "442"})

    with pytest.raises(ValueError, match=r"\*ID 442"):
        module.apply(tables)


def test_script_rejects_existing_name_at_wrong_id():
    module = _load_module()
    tables = _base_tables()
    tables[TABLE_KEY].append({"index": "Crusader's Vengeance", "*ID": "500"})

    with pytest.raises(ValueError, match="expected 442"):
        module.apply(tables)


def test_run_script_requires_allow_add_for_new_rows():
    from d2r_mod.scripts import run_script

    with pytest.raises(ValueError, match="changed row count"):
        run_script(str(SCRIPT_PATH), _base_tables(), allow_add=False)


def test_restored_rows_regenerate_chargen_unique_data():
    from d2r_mod.regen import regen_unique_item_stats, regen_unique_items

    module = _load_module()
    tables = _base_tables()
    module.apply(tables)

    unique_items = regen_unique_items(tables[TABLE_KEY])
    unique_stats = regen_unique_item_stats(tables[TABLE_KEY])

    assert unique_items[442] == {
        "name": "Crusader's Vengeance",
        "code": "7cr",
        "qlvl": 82,
    }
    assert unique_items[443] == {
        "name": "Manoomin",
        "code": "cm1",
        "qlvl": 1,
    }
    crusader_stats = unique_stats[442]["stats"]
    assert {"stat": "item_ignoretargetac", "min": 1, "max": 1, "param": "1"} in crusader_stats
    assert {
        "stat": "item_addskill_tab",
        "min": 3,
        "max": 3,
        "param_type": "skill_tab",
        "param": 9,
    } in crusader_stats
