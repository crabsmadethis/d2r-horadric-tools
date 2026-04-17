"""Tests for d2r_mcp lookup functions."""
import json
import pytest


class TestLookupUnique:
    """Tests for lookup_unique()."""

    def test_lookup_by_id(self):
        from d2r_mcp.lookups import lookup_unique
        result = json.loads(lookup_unique("0"))
        assert result["uid"] == 0
        assert result["name"] == "The Gnasher"
        assert result["code"] == "hax"

    def test_lookup_by_exact_name(self):
        from d2r_mcp.lookups import lookup_unique
        result = json.loads(lookup_unique("The Gnasher"))
        assert result["uid"] == 0

    def test_lookup_by_name_case_insensitive(self):
        from d2r_mcp.lookups import lookup_unique
        result = json.loads(lookup_unique("the gnasher"))
        assert result["uid"] == 0

    def test_lookup_by_substring(self):
        from d2r_mcp.lookups import lookup_unique
        result = json.loads(lookup_unique("harlequin"))
        # Should find Harlequin Crest
        if "matches" in result:
            names = [m["name"] for m in result["matches"]]
            assert any("Harlequin" in n for n in names)
        else:
            assert "Harlequin" in result["name"]

    def test_lookup_no_match(self):
        from d2r_mcp.lookups import lookup_unique
        result = lookup_unique("xyznonexistent")
        assert "No unique" in result

    def test_lookup_includes_stats(self):
        from d2r_mcp.lookups import lookup_unique
        result = json.loads(lookup_unique("0"))
        assert "stats" in result
        assert len(result["stats"]) > 0

    def test_lookup_includes_base_name(self):
        from d2r_mcp.lookups import lookup_unique
        result = json.loads(lookup_unique("0"))
        assert "base_name" in result
        assert result["base_name"] != "?"


class TestLookupSetItem:
    def test_lookup_by_id(self):
        from d2r_mcp.lookups import lookup_set_item
        result = json.loads(lookup_set_item("0"))
        assert result["set_id"] == 0
        assert "name" in result

    def test_lookup_by_name(self):
        from d2r_mcp.lookups import lookup_set_item
        result = json.loads(lookup_set_item("civerb"))
        assert "matches" in result or "name" in result

    def test_lookup_includes_set_name(self):
        from d2r_mcp.lookups import lookup_set_item
        result = json.loads(lookup_set_item("0"))
        assert "set_name" in result

    def test_lookup_no_match(self):
        from d2r_mcp.lookups import lookup_set_item
        result = lookup_set_item("xyznonexistent")
        assert "No set" in result


class TestLookupItemBase:
    def test_lookup_by_code(self):
        from d2r_mcp.lookups import lookup_item_base
        result = json.loads(lookup_item_base("hax"))
        assert result["code"] == "hax"
        assert "name" in result

    def test_lookup_by_name(self):
        from d2r_mcp.lookups import lookup_item_base
        result = json.loads(lookup_item_base("diadem"))
        if "matches" in result:
            codes = [m["code"] for m in result["matches"]]
            assert len(codes) > 0
        else:
            assert "name" in result

    def test_lookup_includes_dimensions(self):
        from d2r_mcp.lookups import lookup_item_base
        result = json.loads(lookup_item_base("hax"))
        assert "width" in result
        assert "height" in result

    def test_lookup_no_match(self):
        from d2r_mcp.lookups import lookup_item_base
        result = lookup_item_base("zzz")
        assert "No base" in result


class TestLookupRuneword:
    def test_lookup_by_id(self):
        from d2r_mcp.lookups import lookup_runeword
        result = json.loads(lookup_runeword("0"))
        assert result["rw_id"] == 0
        assert "name" in result
        assert "runes" in result

    def test_lookup_by_name(self):
        from d2r_mcp.lookups import lookup_runeword
        result = json.loads(lookup_runeword("enigma"))
        if "matches" in result:
            names = [m["name"] for m in result["matches"]]
            assert any("Enigma" in n for n in names)
        else:
            assert "Enigma" in result["name"]

    def test_lookup_includes_stats(self):
        from d2r_mcp.lookups import lookup_runeword
        result = json.loads(lookup_runeword("0"))
        assert "stats" in result
        assert "rune_names" in result

    def test_lookup_includes_valid_bases(self):
        from d2r_mcp.lookups import lookup_runeword
        result = json.loads(lookup_runeword("0"))
        assert "bases" in result

    def test_lookup_no_match(self):
        from d2r_mcp.lookups import lookup_runeword
        result = lookup_runeword("xyznonexistent")
        assert "No runeword" in result


class TestLookupStat:
    def test_lookup_by_id(self):
        from d2r_mcp.lookups import lookup_stat
        result = json.loads(lookup_stat("0"))
        assert result["stat_id"] == 0
        assert result["name"] == "strength"

    def test_lookup_by_canonical_name(self):
        from d2r_mcp.lookups import lookup_stat
        result = json.loads(lookup_stat("strength"))
        assert result["stat_id"] == 0

    def test_lookup_by_alias(self):
        from d2r_mcp.lookups import lookup_stat
        result = json.loads(lookup_stat("fcr"))
        assert result["stat_id"] is not None
        assert "save_bits" in result

    def test_lookup_includes_encoding_info(self):
        from d2r_mcp.lookups import lookup_stat
        result = json.loads(lookup_stat("0"))
        assert "save_bits" in result
        assert "save_add" in result

    def test_lookup_includes_aliases(self):
        from d2r_mcp.lookups import lookup_stat
        result = json.loads(lookup_stat("strength"))
        assert "aliases" in result

    def test_lookup_no_match(self):
        from d2r_mcp.lookups import lookup_stat
        result = lookup_stat("xyznonexistent")
        assert "No stat" in result


class TestLookupSkill:
    def test_lookup_by_id(self):
        from d2r_mcp.lookups import lookup_skill
        result = json.loads(lookup_skill("0"))
        assert result["skill_id"] == 0
        assert result["name"] == "Attack"

    def test_lookup_by_name(self):
        from d2r_mcp.lookups import lookup_skill
        result = json.loads(lookup_skill("Frozen Orb"))
        assert "skill_id" in result

    def test_lookup_by_name_case_insensitive(self):
        from d2r_mcp.lookups import lookup_skill
        result = json.loads(lookup_skill("frozen orb"))
        assert "skill_id" in result

    def test_lookup_class_skill_includes_class(self):
        from d2r_mcp.lookups import lookup_skill
        result = json.loads(lookup_skill("Frozen Orb"))
        if "matches" not in result:
            assert "char_class" in result

    def test_lookup_no_match(self):
        from d2r_mcp.lookups import lookup_skill
        result = lookup_skill("xyznonexistent")
        assert "No skill" in result


class TestSearchAll:
    def test_finds_unique(self):
        from d2r_mcp.lookups import search_all
        result = json.loads(search_all("gnasher"))
        assert any(r.get("type") == "unique" for r in result["results"])

    def test_finds_runeword(self):
        from d2r_mcp.lookups import search_all
        result = json.loads(search_all("enigma"))
        types = [r["type"] for r in result["results"]]
        assert "runeword" in types

    def test_finds_across_categories(self):
        from d2r_mcp.lookups import search_all
        result = json.loads(search_all("ring"))
        types = set(r["type"] for r in result["results"])
        assert len(types) >= 1

    def test_no_match(self):
        from d2r_mcp.lookups import search_all
        result = json.loads(search_all("xyznonexistent"))
        assert result["count"] == 0

    def test_result_limit(self):
        from d2r_mcp.lookups import search_all
        result = json.loads(search_all("the"))
        assert result["count"] <= 20
