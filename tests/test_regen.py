import unittest
from d2r_mod.regen import regen_unique_items, regen_set_items, regen_skills, regen_runewords, regen_item_bases
from d2r_mod.regen import regen_unique_item_stats, regen_runeword_stats
from d2r_mod.regen import regen_item_dimensions, regen_item_stat_cost


class TestRegenUniqueItems(unittest.TestCase):
    def test_basic_regen(self):
        rows = [
            {"index": "The Gnasher", "*ID": "0", "code": "hax", "lvl": "7", "enabled": "1",
             "prop1": "", "par1": "", "min1": "", "max1": ""},
            {"index": "Deathspade", "*ID": "1", "code": "axe", "lvl": "9", "enabled": "1",
             "prop1": "", "par1": "", "min1": "", "max1": ""},
        ]
        result = regen_unique_items(rows)
        self.assertEqual(result[0], {"name": "The Gnasher", "code": "hax", "qlvl": 7})
        self.assertEqual(result[1], {"name": "Deathspade", "code": "axe", "qlvl": 9})

    def test_skips_disabled(self):
        rows = [
            {"index": "Item A", "*ID": "0", "code": "abc", "lvl": "5", "enabled": "1",
             "prop1": "", "par1": "", "min1": "", "max1": ""},
            {"index": "Disabled", "*ID": "1", "code": "xyz", "lvl": "0", "disabled": "1",
             "prop1": "", "par1": "", "min1": "", "max1": ""},
            {"index": "Item C", "*ID": "2", "code": "def", "lvl": "10", "enabled": "1",
             "prop1": "", "par1": "", "min1": "", "max1": ""},
        ]
        result = regen_unique_items(rows)
        self.assertIn(0, result)
        self.assertNotIn(1, result)
        self.assertIn(2, result)

    def test_uses_star_id_not_row_index(self):
        """Regression: regen must use *ID field, not enumerate index.
        A disabled row or section header causes index drift."""
        rows = [
            {"index": "Item A", "*ID": "0", "code": "abc", "lvl": "5",
             "prop1": "", "par1": "", "min1": "", "max1": ""},
            {"index": "Section Header", "*ID": "", "code": "", "lvl": "",
             "prop1": "", "par1": "", "min1": "", "max1": ""},
            {"index": "Item B", "*ID": "1", "code": "def", "lvl": "10",
             "prop1": "", "par1": "", "min1": "", "max1": ""},
        ]
        result = regen_unique_items(rows)
        # Item B should be at UID 1 (from *ID), not 2 (from row index)
        self.assertIn(1, result)
        self.assertEqual(result[1]["name"], "Item B")
        self.assertNotIn(2, result)


class TestRegenSetItems(unittest.TestCase):
    def test_basic_regen(self):
        rows = [
            {"index": "Civerb's Ward", "*ID": "0", "item": "lrg", "set": "Civerb's Vestments",
             "lvl": "9", "prop1": "", "par1": "", "min1": "", "max1": ""},
        ]
        result = regen_set_items(rows)
        self.assertEqual(result[0], {
            "name": "Civerb's Ward", "code": "lrg",
            "set": "Civerb's Vestments", "qlvl": 9,
        })


class TestRegenSkills(unittest.TestCase):
    def test_basic_regen(self):
        rows = [
            {"skill": "Attack", "charclass": "", "*Id": "0"},
            {"skill": "Magic Arrow", "charclass": "ama", "*Id": "6"},
        ]
        result = regen_skills(rows)
        self.assertEqual(result[0], {"name": "Attack"})
        self.assertEqual(result[6], {"name": "Magic Arrow", "class": "ama"})

    def test_skips_empty_names(self):
        rows = [
            {"skill": "", "charclass": "", "*Id": "5"},
            {"skill": "Kick", "charclass": "", "*Id": "1"},
        ]
        result = regen_skills(rows)
        self.assertNotIn(5, result)
        self.assertIn(1, result)


class TestRegenRunewords(unittest.TestCase):
    def test_basic_regen(self):
        rows = [
            {
                "Name": "Runeword1", "*Rune Name": "Ancient's Pledge",
                "complete": "1", "levelreq": "21",
                "itype1": "shld", "itype2": "", "itype3": "",
                "itype4": "", "itype5": "", "itype6": "",
                "Rune1": "r08", "Rune2": "r09", "Rune3": "r07",
                "Rune4": "", "Rune5": "", "Rune6": "",
                "*Runes": "RalOrtTal",
                "T1Code1": "", "T1Param1": "", "T1Min1": "", "T1Max1": "",
            },
        ]
        result = regen_runewords(rows)
        self.assertEqual(len(result), 1)
        rw_id = list(result.keys())[0]
        entry = result[rw_id]
        self.assertEqual(entry["name"], "Ancient's Pledge")
        self.assertEqual(entry["runes"], ["r08", "r09", "r07"])
        self.assertEqual(entry["sockets"], 3)
        self.assertIn("Shield", entry["bases"])
        self.assertEqual(entry["clvl"], 21)

    def test_skips_incomplete(self):
        rows = [
            {
                "Name": "Disabled", "*Rune Name": "Bad",
                "complete": "0", "levelreq": "0",
                "itype1": "weap", "itype2": "", "itype3": "",
                "itype4": "", "itype5": "", "itype6": "",
                "Rune1": "r01", "Rune2": "", "Rune3": "",
                "Rune4": "", "Rune5": "", "Rune6": "",
                "*Runes": "El",
                "T1Code1": "", "T1Param1": "", "T1Min1": "", "T1Max1": "",
            },
        ]
        result = regen_runewords(rows)
        self.assertEqual(len(result), 0)


class TestRegenItemBases(unittest.TestCase):
    def test_armor_regen(self):
        rows = [
            {
                "name": "Cap", "code": "cap",
                "invwidth": "2", "invheight": "2",
                "type": "helm", "type2": "",
                "gemsockets": "3",
                "minac": "3", "maxac": "5",
                "durability": "12",
                "reqstr": "0", "reqdex": "0",
                "normcode": "cap", "ubercode": "xap", "ultracode": "uap",
            },
        ]
        result = regen_item_bases(rows, item_class="armor")
        self.assertIn("cap", result)
        entry = result["cap"]
        self.assertEqual(entry["name"], "Cap")
        self.assertEqual(entry["width"], 2)
        self.assertEqual(entry["height"], 2)
        self.assertEqual(entry["class"], "armor")
        self.assertEqual(entry["max_sockets"], 3)


class TestRegenUniqueItemStats(unittest.TestCase):
    def test_basic_stat_regen(self):
        rows = [
            {
                "index": "Magefist", "*ID": "0", "code": "tgl", "enabled": "1", "lvl": "23",
                "prop1": "ac%", "par1": "", "min1": "20", "max1": "30",
                "prop2": "ac", "par2": "", "min2": "10", "max2": "10",
                "prop3": "fcr", "par3": "", "min3": "20", "max3": "20",
                "prop4": "", "par4": "", "min4": "", "max4": "",
            },
        ]
        result = regen_unique_item_stats(rows)
        self.assertIn(0, result)
        entry = result[0]
        self.assertEqual(entry["name"], "Magefist")
        self.assertEqual(entry["base"], "tgl")
        self.assertEqual(len(entry["stats"]), 3)
        self.assertEqual(entry["stats"][0]["min"], 20)
        self.assertEqual(entry["stats"][0]["max"], 30)

    def test_skips_disabled(self):
        rows = [
            {
                "index": "Disabled", "*ID": "0", "code": "xyz", "disabled": "1", "lvl": "0",
                "prop1": "ac%", "par1": "", "min1": "10", "max1": "20",
                "prop2": "", "par2": "", "min2": "", "max2": "",
            },
        ]
        result = regen_unique_item_stats(rows)
        self.assertEqual(len(result), 0)

    def test_skips_items_with_no_props(self):
        rows = [
            {
                "index": "Empty", "*ID": "0", "code": "abc", "enabled": "1", "lvl": "1",
                "prop1": "", "par1": "", "min1": "", "max1": "",
            },
        ]
        result = regen_unique_item_stats(rows)
        self.assertEqual(len(result), 0)

    def test_res_all_expands_to_four_stats(self):
        """res-all property expands to fire/light/cold/poison resist."""
        rows = [
            {
                "index": "Ring", "*ID": "0", "code": "rin", "enabled": "1", "lvl": "10",
                "prop1": "res-all", "par1": "", "min1": "30", "max1": "30",
                "prop2": "", "par2": "", "min2": "", "max2": "",
            },
        ]
        result = regen_unique_item_stats(rows)
        stats = result[0]["stats"]
        self.assertEqual(len(stats), 4)
        stat_names = [s["stat"] for s in stats]
        self.assertIn("fireresist", stat_names)
        self.assertIn("lightresist", stat_names)
        self.assertIn("coldresist", stat_names)
        self.assertIn("poisonresist", stat_names)

    def test_lightning_min_max_pair_merges_to_grouped(self):
        """ltng-min + ltng-max in adjacent props merge into one grouped lightmindam entry.

        Mindrend (UID 3) shape: prop3=ltng-min,min=1,max=1 + prop4=ltng-max,min=12,max=15.
        The D2S encoder expects a single 'lightmindam' entry where entry.min is the
        damage range lower bound and entry.max is the upper bound. Two separate
        entries silently drop the maxdam half in resolve._resolve_stat_entry.
        """
        rows = [
            {
                "index": "Mindrend-like", "*ID": "0", "code": "mpi", "enabled": "1", "lvl": "1",
                "prop1": "ltng-min", "par1": "", "min1": "1", "max1": "1",
                "prop2": "ltng-max", "par2": "", "min2": "12", "max2": "15",
            },
        ]
        stats = regen_unique_item_stats(rows)[0]["stats"]
        self.assertEqual(len(stats), 1, f"expected single grouped entry, got: {stats}")
        self.assertEqual(stats[0]["stat"], "lightmindam")
        self.assertEqual(stats[0]["min"], 1)
        self.assertEqual(stats[0]["max"], 15)

    def test_cold_min_max_len_triple_merges_with_param(self):
        """cold-min + cold-max + cold-len merge into one coldmindam entry with param=duration.

        Gravenspine (UID 12) shape. Resolver expects np=3 grouped form where param
        is the freeze duration. Three separate entries lose damage_max and length.
        """
        rows = [
            {
                "index": "Gravenspine-like", "*ID": "0", "code": "bwn", "enabled": "1", "lvl": "1",
                "prop1": "cold-min", "par1": "", "min1": "4", "max1": "4",
                "prop2": "cold-max", "par2": "", "min2": "8", "max2": "8",
                "prop3": "cold-len", "par3": "", "min3": "75", "max3": "75",
            },
        ]
        stats = regen_unique_item_stats(rows)[0]["stats"]
        self.assertEqual(len(stats), 1, f"expected single grouped entry, got: {stats}")
        self.assertEqual(stats[0]["stat"], "coldmindam")
        self.assertEqual(stats[0]["min"], 4)
        self.assertEqual(stats[0]["max"], 8)
        self.assertEqual(str(stats[0]["param"]), "75")

    def test_fire_min_max_pair_merges(self):
        """fire-min + fire-max merge into one firemindam entry (Bladebone, Felloak, etc.)."""
        rows = [
            {
                "index": "Felloak-like", "*ID": "0", "code": "clb", "enabled": "1", "lvl": "1",
                "prop1": "fire-min", "par1": "", "min1": "1", "max1": "1",
                "prop2": "fire-max", "par2": "", "min2": "20", "max2": "20",
            },
        ]
        stats = regen_unique_item_stats(rows)[0]["stats"]
        self.assertEqual(len(stats), 1)
        self.assertEqual(stats[0]["stat"], "firemindam")
        self.assertEqual(stats[0]["min"], 1)
        self.assertEqual(stats[0]["max"], 20)

    def test_poison_min_max_len_triple_merges_with_param(self):
        """pois-min + pois-max + pois-len merge into one poisonmindam entry (Rakescar, Hellplague)."""
        rows = [
            {
                "index": "Rakescar-like", "*ID": "0", "code": "clw", "enabled": "1", "lvl": "1",
                "prop1": "pois-min", "par1": "", "min1": "5", "max1": "5",
                "prop2": "pois-max", "par2": "", "min2": "10", "max2": "10",
                "prop3": "pois-len", "par3": "", "min3": "100", "max3": "100",
            },
        ]
        stats = regen_unique_item_stats(rows)[0]["stats"]
        self.assertEqual(len(stats), 1)
        self.assertEqual(stats[0]["stat"], "poisonmindam")
        self.assertEqual(stats[0]["min"], 5)
        self.assertEqual(stats[0]["max"], 10)
        self.assertEqual(str(stats[0]["param"]), "100")

    def test_single_ltng_min_still_grouped_form(self):
        """SoJ-style single ltng-min column must keep its single-entry grouped form (no regression)."""
        rows = [
            {
                "index": "SoJ-like", "*ID": "0", "code": "rin", "enabled": "1", "lvl": "1",
                "prop1": "ltng-min", "par1": "", "min1": "1", "max1": "30",
            },
        ]
        stats = regen_unique_item_stats(rows)[0]["stats"]
        self.assertEqual(len(stats), 1)
        self.assertEqual(stats[0]["stat"], "lightmindam")
        self.assertEqual(stats[0]["min"], 1)
        self.assertEqual(stats[0]["max"], 30)

    def test_non_adjacent_ltng_pair_still_merges(self):
        """SoJ-style: ltng-min in prop3, ltng-max in prop5, with allskills in prop4 between them.

        Vanilla SoJ TSV (UID 122) puts allskills between the lightning min/max columns.
        The merge must skip over unrelated stats and still produce a single grouped lightmindam entry.
        """
        rows = [
            {
                "index": "SoJ-real", "*ID": "0", "code": "rin", "enabled": "1", "lvl": "1",
                "prop1": "mana", "par1": "", "min1": "20", "max1": "20",
                "prop2": "mana%", "par2": "", "min2": "25", "max2": "25",
                "prop3": "ltng-min", "par3": "", "min3": "1", "max3": "1",
                "prop4": "allskills", "par4": "", "min4": "2", "max4": "2",
                "prop5": "ltng-max", "par5": "", "min5": "30", "max5": "30",
            },
        ]
        stats = regen_unique_item_stats(rows)[0]["stats"]
        stat_names = [s["stat"] for s in stats]
        self.assertEqual(stat_names, ["maxmana", "item_maxmana_percent", "lightmindam", "item_allskills"])
        light = next(s for s in stats if s["stat"] == "lightmindam")
        self.assertEqual((light["min"], light["max"]), (1, 30))

    def test_pair_merge_preserves_other_props(self):
        """Pair merging must not drop or reorder unrelated props (Mindrend has stupidity, regen-mana, att, dmg%, openwounds around the ltng pair)."""
        rows = [
            {
                "index": "Mindrend", "*ID": "0", "code": "mpi", "enabled": "1", "lvl": "1",
                "prop1": "stupidity", "par1": "", "min1": "2", "max1": "2",
                "prop2": "regen-mana", "par2": "", "min2": "20", "max2": "20",
                "prop3": "ltng-min", "par3": "", "min3": "1", "max3": "1",
                "prop4": "ltng-max", "par4": "", "min4": "12", "max4": "15",
                "prop5": "att", "par5": "", "min5": "50", "max5": "100",
            },
        ]
        stats = regen_unique_item_stats(rows)[0]["stats"]
        stat_names = [s["stat"] for s in stats]
        self.assertEqual(stat_names, ["item_stupidity", "manarecoverybonus", "lightmindam", "tohit"])
        light = next(s for s in stats if s["stat"] == "lightmindam")
        self.assertEqual((light["min"], light["max"]), (1, 15))


class TestRegenRunewordStats(unittest.TestCase):
    def test_basic_stat_regen(self):
        rows = [
            {
                "Name": "RW1", "*Rune Name": "Test Word",
                "complete": "1", "levelreq": "57",
                "Rune1": "r11", "Rune2": "r08", "Rune3": "",
                "Rune4": "", "Rune5": "", "Rune6": "",
                "itype1": "weap", "itype2": "", "itype3": "",
                "itype4": "", "itype5": "", "itype6": "",
                "T1Code1": "allskills", "T1Param1": "", "T1Min1": "1", "T1Max1": "1",
                "T1Code2": "ias", "T1Param2": "", "T1Min2": "40", "T1Max2": "40",
                "T1Code3": "", "T1Param3": "", "T1Min3": "", "T1Max3": "",
            },
        ]
        result = regen_runeword_stats(rows)
        self.assertEqual(len(result), 1)
        rw_id = list(result.keys())[0]
        entry = result[rw_id]
        self.assertEqual(entry["name"], "Test Word")
        self.assertEqual(len(entry["stats"]), 2)


class TestRegenItemDimensions(unittest.TestCase):
    def test_basic_dimensions(self):
        rows = [
            {"code": "cap", "name": "Cap", "invwidth": "2", "invheight": "2"},
            {"code": "hax", "name": "Hand Axe", "invwidth": "1", "invheight": "3"},
            {"code": "", "name": "Empty"},  # should be skipped
        ]
        result = regen_item_dimensions(rows)
        self.assertEqual(result, {"cap": (2, 2), "hax": (1, 3)})

    def test_missing_dimensions_default_to_1(self):
        rows = [
            {"code": "xyz", "name": "Test"},  # no invwidth/invheight at all
            {"code": "abc", "name": "Test2", "invwidth": "", "invheight": ""},
        ]
        result = regen_item_dimensions(rows)
        self.assertEqual(result["xyz"], (1, 1))
        self.assertEqual(result["abc"], (1, 1))


class TestRegenItemStatCost(unittest.TestCase):
    def test_basic_stat_cost(self):
        rows = [
            {"*ID": "0", "Stat": "strength", "CSvBits": "10", "CSvSigned": "",
             "Save Bits": "8", "Save Add": "32", "Save Param Bits": "",
             "Signed": "", "Send Param Bits": "",
             "Encode": "", "op": "", "op param": "", "op base": "", "op stat1": "",
             "op stat2": "", "op stat3": "",
             "descfunc": "19", "descval": "", "descstrpos": "%+d to Strength",
             "descstrneg": "", "dgrp": "1", "dgrpfunc": "19",
             "dgrpstrpos": "%+d to all Attributes", "descpriority": "67",
             "ValShift": "", "descstr2": "", "dgrpval": ""},
        ]
        isc, sbn = regen_item_stat_cost(rows)
        self.assertIn(0, isc)
        self.assertEqual(isc[0]["s"], "strength")
        self.assertEqual(isc[0]["sB"], 8)
        self.assertEqual(isc[0]["sA"], 32)
        self.assertEqual(isc[0]["so"], 67)
        self.assertEqual(isc[0]["dF"], 19)
        self.assertEqual(isc[0]["dP"], "%+d to Strength")
        self.assertEqual(isc[0]["dg"], 1)
        self.assertEqual(isc[0]["dgF"], 19)
        self.assertEqual(isc[0]["dgP"], "%+d to all Attributes")
        self.assertEqual(sbn["strength"], 0)

    def test_skips_empty_rows(self):
        rows = [
            {"*ID": "", "Stat": "", "Save Bits": "", "Save Add": ""},
            {"*ID": "5", "Stat": "", "Save Bits": "", "Save Add": ""},
        ]
        isc, sbn = regen_item_stat_cost(rows)
        self.assertEqual(len(isc), 0)
        self.assertEqual(len(sbn), 0)

    def test_op_stats(self):
        rows = [
            {"*ID": "1", "Stat": "energy", "CSvBits": "10", "CSvSigned": "",
             "Save Bits": "7", "Save Add": "32", "Save Param Bits": "",
             "Signed": "", "Send Param Bits": "",
             "Encode": "", "op": "8", "op param": "", "op base": "maxmana",
             "op stat1": "maxmana", "op stat2": "", "op stat3": "",
             "descfunc": "19", "descval": "", "descstrpos": "%+d to Energy",
             "descstrneg": "", "dgrp": "1", "dgrpfunc": "19",
             "dgrpstrpos": "%+d to all Attributes", "descpriority": "61",
             "ValShift": "", "descstr2": "", "dgrpval": ""},
        ]
        isc, sbn = regen_item_stat_cost(rows)
        self.assertEqual(isc[1]["o"], 8)
        self.assertEqual(isc[1]["os"], ["maxmana"])
        self.assertEqual(isc[1]["oB"], "maxmana")

    def test_csv_bits(self):
        rows = [
            {"*ID": "0", "Stat": "strength", "CSvBits": "10", "CSvSigned": "0",
             "Save Bits": "8", "Save Add": "32", "Save Param Bits": "",
             "Signed": "", "Send Param Bits": "",
             "Encode": "", "op": "", "op param": "", "op base": "",
             "op stat1": "", "op stat2": "", "op stat3": "",
             "descfunc": "", "descval": "", "descstrpos": "",
             "descstrneg": "", "dgrp": "", "dgrpfunc": "",
             "dgrpstrpos": "", "descpriority": "",
             "ValShift": "", "descstr2": "", "dgrpval": ""},
        ]
        isc, sbn = regen_item_stat_cost(rows)
        self.assertEqual(isc[0]["cB"], 10)
        self.assertEqual(isc[0]["cS"], 0)


if __name__ == "__main__":
    unittest.main()
