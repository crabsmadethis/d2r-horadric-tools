"""Regression tests for properties: merge-by-default behavior in chargen.

Covers Task 2.1 from 2026-04-19-chargen-mod-fixes.md.

Bug A root cause: `properties:` on unique/set/runeword items silently
dropped canonical stats because _resolve_final_properties treated it
as a full override instead of a merge.
"""
import pytest

# Skip entire file if game data not extracted
pytest.importorskip("d2r_chargen.data.item_stat_cost",
                     reason="game data not extracted (run 'd2r-mod extract')")

from d2r_chargen.resolve import resolve_unique, resolve_properties
from d2r_chargen.items import _resolve_final_properties


def _stat_id(prop_tuple):
    """Extract the stat ID (first element) from a property tuple."""
    return prop_tuple[0]


class TestMergeByDefault:
    """_resolve_final_properties with has_canonical=True must merge, not replace."""

    def test_unique_properties_merge_with_canonical_by_default(self):
        """When properties: is specified on a unique item, the canonical
        stats must still apply — properties should MERGE, not replace."""
        magefist = resolve_unique("Magefist")
        auto_props = magefist["properties"]

        item_def = {
            "unique": "Magefist",
            "properties": {"fcr": 20, "mana_regen": 25, "ed": 30},
        }
        merged = _resolve_final_properties(item_def, auto_props, has_canonical=True)
        stat_ids_merged = {_stat_id(p) for p in merged}
        stat_ids_canonical = {_stat_id(p) for p in auto_props}
        missing = stat_ids_canonical - stat_ids_merged
        assert not missing, f"canonical stats dropped: {missing}"

    def test_unique_extra_properties_still_merges(self):
        """extra_properties: keeps existing merge behavior (no regression)."""
        magefist = resolve_unique("Magefist")
        auto_props = magefist["properties"]

        item_def = {
            "unique": "Magefist",
            "extra_properties": {"life": 50},
        }
        merged = _resolve_final_properties(item_def, auto_props, has_canonical=True)
        stat_ids_merged = {_stat_id(p) for p in merged}
        stat_ids_canonical = {_stat_id(p) for p in auto_props}

        # All canonical stats must still be present
        missing = stat_ids_canonical - stat_ids_merged
        assert not missing, f"canonical stats dropped by extra_properties: {missing}"

        # The extra property (life = stat 7) must also be present
        from d2r_chargen.data.item_stat_cost import STAT_BY_NAME
        life_stat_id = STAT_BY_NAME["maxhp"]
        assert life_stat_id in stat_ids_merged, "extra_properties life stat missing"

    def test_rare_properties_replaces_as_before(self):
        """On rare/magic/crafted (no canonical), properties: still specifies
        the full stat set. No regression."""
        item_def = {
            "rare": "some_rare",
            "slot": "neck",
            "properties": {"fcr": 20, "life": 100},
        }
        # For rare: auto_props is empty (no canonical source)
        auto_props = []
        result = _resolve_final_properties(item_def, auto_props, has_canonical=False)

        user_props = resolve_properties({"fcr": 20, "life": 100})
        result_stat_ids = {_stat_id(p) for p in result}
        user_stat_ids = {_stat_id(p) for p in user_props}

        # Result must be exactly the user-specified properties (no extras)
        assert result_stat_ids == user_stat_ids, (
            f"rare item result stat IDs {result_stat_ids} != "
            f"user specified stat IDs {user_stat_ids}"
        )

    def test_no_properties_returns_auto_props_unchanged(self):
        """When no properties: or extra_properties:, auto_props returned as-is."""
        magefist = resolve_unique("Magefist")
        auto_props = magefist["properties"]

        item_def = {"unique": "Magefist"}
        result = _resolve_final_properties(item_def, auto_props, has_canonical=True)
        assert result is auto_props, "auto_props should be returned unchanged when no override"

    def test_properties_override_replaces_overlapping_stats(self):
        """When properties: overrides a stat that exists in canonical,
        the overriding value wins (not duplicated)."""
        magefist = resolve_unique("Magefist")
        auto_props = magefist["properties"]

        from d2r_chargen.data.item_stat_cost import STAT_BY_NAME
        from d2r_chargen.config import PROPERTY_ALIASES
        fcr_stat_id = STAT_BY_NAME[PROPERTY_ALIASES["fcr"]]

        # Override FCR with a different value
        item_def = {
            "unique": "Magefist",
            "properties": {"fcr": 30},  # canonical is 20
        }
        merged = _resolve_final_properties(item_def, auto_props, has_canonical=True)

        # FCR must appear exactly once
        fcr_entries = [p for p in merged if _stat_id(p) == fcr_stat_id]
        assert len(fcr_entries) == 1, (
            f"FCR appears {len(fcr_entries)} times in merged result, expected 1"
        )
        # Value must be the user override (30), not canonical (20)
        assert fcr_entries[0][1] == 30, (
            f"FCR value is {fcr_entries[0][1]}, expected override value 30"
        )
