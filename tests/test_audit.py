import unittest


class TestDamageCalculator(unittest.TestCase):
    def _make_skill_row(self, **overrides):
        """Base skill row with all damage/mana columns defaulting to empty."""
        row = {
            "skill": "TestSkill", "charclass": "sor",
            "MinDam": "", "MaxDam": "",
            "MinLevDam1": "", "MinLevDam2": "", "MinLevDam3": "",
            "MinLevDam4": "", "MinLevDam5": "",
            "MaxLevDam1": "", "MaxLevDam2": "", "MaxLevDam3": "",
            "MaxLevDam4": "", "MaxLevDam5": "",
            "EType": "", "EMin": "", "EMax": "",
            "EMinLev1": "", "EMinLev2": "", "EMinLev3": "",
            "EMinLev4": "", "EMinLev5": "",
            "EMaxLev1": "", "EMaxLev2": "", "EMaxLev3": "",
            "EMaxLev4": "", "EMaxLev5": "",
            "startmana": "", "mana": "", "lvlmana": "",
            "minmana": "", "manashift": "",
            "Param1": "", "Param2": "", "Param3": "", "Param4": "",
            "Param5": "", "Param6": "", "Param7": "", "Param8": "",
        }
        row.update(overrides)
        return row

    def test_physical_damage_at_level_1(self):
        from d2r_mod.audit import compute_damage_at_level

        row = self._make_skill_row(MinDam="10", MaxDam="20")
        lo, hi = compute_damage_at_level(row, 1)
        self.assertAlmostEqual(lo, 10.0)
        self.assertAlmostEqual(hi, 20.0)

    def test_physical_damage_level_scaling(self):
        from d2r_mod.audit import compute_damage_at_level

        row = self._make_skill_row(MinDam="10", MaxDam="20", MinLevDam1="5", MaxLevDam1="8")
        lo, hi = compute_damage_at_level(row, 5)
        # Level 5: base + per_level * (5-1) = 10 + 5*4 = 30, 20 + 8*4 = 52
        self.assertAlmostEqual(lo, 30.0)
        self.assertAlmostEqual(hi, 52.0)

    def test_elemental_damage_at_level_20(self):
        from d2r_mod.audit import compute_damage_at_level

        row = self._make_skill_row(
            EType="fire", EMin="5", EMax="10",
            EMinLev1="2", EMinLev2="3",
            EMaxLev1="4", EMaxLev2="6",
        )
        lo, hi = compute_damage_at_level(row, 12)
        # Level 12: bracket1 (2-8, 7 lvls), bracket2 (9-16, so 12-8=4 lvls)
        # min: 5 + 2*7 + 3*4 = 5 + 14 + 12 = 31
        # max: 10 + 4*7 + 6*4 = 10 + 28 + 24 = 62
        self.assertAlmostEqual(lo, 31.0)
        self.assertAlmostEqual(hi, 62.0)

    def test_empty_damage_returns_zero(self):
        from d2r_mod.audit import compute_damage_at_level

        row = self._make_skill_row()
        lo, hi = compute_damage_at_level(row, 20)
        self.assertAlmostEqual(lo, 0.0)
        self.assertAlmostEqual(hi, 0.0)

    def test_mana_cost_at_level_1(self):
        from d2r_mod.audit import compute_mana_at_level

        row = self._make_skill_row(startmana="1536", mana="0", lvlmana="128",
                                    minmana="1", manashift="8")
        cost = compute_mana_at_level(row, 1)
        # (1536 + 128 * 0) >> 8 = 1536 >> 8 = 6
        self.assertAlmostEqual(cost, 6.0)

    def test_mana_cost_scaling(self):
        from d2r_mod.audit import compute_mana_at_level

        row = self._make_skill_row(startmana="1536", mana="0", lvlmana="128",
                                    minmana="1", manashift="8")
        cost = compute_mana_at_level(row, 10)
        # (1536 + 128 * 9) >> 8 = 2688 >> 8 = 10 (truncated)
        self.assertAlmostEqual(cost, 10.0)

    def test_mana_floor(self):
        from d2r_mod.audit import compute_mana_at_level

        row = self._make_skill_row(startmana="0", mana="0", lvlmana="0",
                                    minmana="5", manashift="8")
        cost = compute_mana_at_level(row, 1)
        self.assertAlmostEqual(cost, 5.0)


class TestLnInterpolation(unittest.TestCase):
    def test_build_calc_context(self):
        from d2r_mod.audit import build_calc_context

        row = {"Param1": "3", "Param2": "5", "Param3": "10", "Param4": "2",
               "Param5": "", "Param6": "", "Param7": "100", "Param8": "12"}
        ctx = build_calc_context(row, level=20)
        # ln12 = 3 + 5 * (20-1) = 98
        self.assertAlmostEqual(ctx["ln12"], 98.0)
        # ln34 = 10 + 2 * (20-1) = 48
        self.assertAlmostEqual(ctx["ln34"], 48.0)
        # ln56 = 0 + 0 * 19 = 0 (empty params)
        self.assertAlmostEqual(ctx["ln56"], 0.0)
        # par8 = 12
        self.assertAlmostEqual(ctx["par8"], 12.0)
        self.assertAlmostEqual(ctx["lvl"], 20.0)


class TestSkillCategorization(unittest.TestCase):
    def test_damage_skill(self):
        from d2r_mod.audit import categorize_skill

        row = {"EMin": "5", "EMax": "10", "passive": "", "aura": "",
               "summon": "", "passivestat1": ""}
        self.assertEqual(categorize_skill(row), "damage")

    def test_passive_skill(self):
        from d2r_mod.audit import categorize_skill

        row = {"EMin": "", "EMax": "", "passive": "1", "aura": "",
               "summon": "", "passivestat1": "passive_critical_strike",
               "MinDam": "", "MaxDam": ""}
        self.assertEqual(categorize_skill(row), "passive")

    def test_aura_skill(self):
        from d2r_mod.audit import categorize_skill

        row = {"EMin": "", "EMax": "", "passive": "", "aura": "1",
               "summon": "", "passivestat1": "", "aurastat1": "maxhp",
               "MinDam": "", "MaxDam": ""}
        self.assertEqual(categorize_skill(row), "aura")

    def test_summon_skill(self):
        from d2r_mod.audit import categorize_skill

        row = {"EMin": "", "EMax": "", "passive": "", "aura": "",
               "summon": "Skeleton A1", "passivestat1": "", "aurastat1": "",
               "MinDam": "", "MaxDam": ""}
        self.assertEqual(categorize_skill(row), "summon")


class TestSkillsAudit(unittest.TestCase):
    def test_ranks_skills_by_damage_per_mana(self):
        from d2r_mod.audit import audit_skills

        skills = [
            {"skill": "Good Skill", "charclass": "sor", "*Id": "1", "InGame": "1",
             "EType": "fire", "EMin": "100", "EMax": "200",
             "EMinLev1": "10", "EMaxLev1": "20",
             "EMinLev2": "", "EMinLev3": "", "EMinLev4": "", "EMinLev5": "",
             "EMaxLev2": "", "EMaxLev3": "", "EMaxLev4": "", "EMaxLev5": "",
             "MinDam": "", "MaxDam": "",
             "MinLevDam1": "", "MinLevDam2": "", "MinLevDam3": "",
             "MinLevDam4": "", "MinLevDam5": "",
             "MaxLevDam1": "", "MaxLevDam2": "", "MaxLevDam3": "",
             "MaxLevDam4": "", "MaxLevDam5": "",
             "startmana": "256", "lvlmana": "0", "minmana": "1", "manashift": "8",
             "passive": "", "aura": "", "summon": "",
             "passivestat1": "", "aurastat1": "",
             "calc1": "", "EDmgSymPerCalc": "", "DmgSymPerCalc": "",
             "Param1": "", "Param2": "", "Param3": "", "Param4": "",
             "Param5": "", "Param6": "", "Param7": "", "Param8": ""},
            {"skill": "Bad Skill", "charclass": "sor", "*Id": "2", "InGame": "1",
             "EType": "fire", "EMin": "5", "EMax": "10",
             "EMinLev1": "1", "EMaxLev1": "2",
             "EMinLev2": "", "EMinLev3": "", "EMinLev4": "", "EMinLev5": "",
             "EMaxLev2": "", "EMaxLev3": "", "EMaxLev4": "", "EMaxLev5": "",
             "MinDam": "", "MaxDam": "",
             "MinLevDam1": "", "MinLevDam2": "", "MinLevDam3": "",
             "MinLevDam4": "", "MinLevDam5": "",
             "MaxLevDam1": "", "MaxLevDam2": "", "MaxLevDam3": "",
             "MaxLevDam4": "", "MaxLevDam5": "",
             "startmana": "2560", "lvlmana": "0", "minmana": "1", "manashift": "8",
             "passive": "", "aura": "", "summon": "",
             "passivestat1": "", "aurastat1": "",
             "calc1": "", "EDmgSymPerCalc": "", "DmgSymPerCalc": "",
             "Param1": "", "Param2": "", "Param3": "", "Param4": "",
             "Param5": "", "Param6": "", "Param7": "", "Param8": ""},
        ]
        tables = {"data/global/excel/Skills.txt": skills}
        results = audit_skills(tables, eval_level=20)
        sor_results = [r for r in results if r["charclass"] == "sor"]
        self.assertEqual(sor_results[0]["skill"], "Good Skill")
        self.assertTrue(sor_results[0]["flagged"] is False)

    def test_flags_bottom_quartile(self):
        from d2r_mod.audit import audit_skills

        skills = []
        for i, dmg in enumerate([100, 80, 60, 10]):
            skills.append({
                "skill": f"Skill{i}", "charclass": "sor", "*Id": str(i), "InGame": "1",
                "EType": "fire", "EMin": str(dmg), "EMax": str(dmg * 2),
                "EMinLev1": "1", "EMaxLev1": "2",
                **{f"EMinLev{j}": "" for j in range(2, 6)},
                **{f"EMaxLev{j}": "" for j in range(2, 6)},
                "MinDam": "", "MaxDam": "",
                **{f"MinLevDam{j}": "" for j in range(1, 6)},
                **{f"MaxLevDam{j}": "" for j in range(1, 6)},
                "startmana": "256", "lvlmana": "0", "minmana": "1", "manashift": "8",
                "passive": "", "aura": "", "summon": "",
                "passivestat1": "", "aurastat1": "",
                "calc1": "", "EDmgSymPerCalc": "", "DmgSymPerCalc": "",
                "Param1": "", "Param2": "", "Param3": "", "Param4": "",
                "Param5": "", "Param6": "", "Param7": "", "Param8": "",
            })
        tables = {"data/global/excel/Skills.txt": skills}
        results = audit_skills(tables, eval_level=20)
        flagged = [r for r in results if r["flagged"]]
        self.assertTrue(any(r["skill"] == "Skill3" for r in flagged))


class TestItemStatExtraction(unittest.TestCase):
    def test_extract_unique_stats(self):
        from d2r_mod.audit import extract_item_stats

        row = {
            "prop1": "str", "par1": "", "min1": "8", "max1": "8",
            "prop2": "dmg%", "par2": "", "min2": "60", "max2": "70",
            "prop3": "", "par3": "", "min3": "", "max3": "",
        }
        stats = extract_item_stats(row, prefix="prop", count=3)
        self.assertEqual(len(stats), 2)
        self.assertEqual(stats[0], {"prop": "str", "par": "", "min": 8, "max": 8})
        self.assertEqual(stats[1], {"prop": "dmg%", "par": "", "min": 60, "max": 70})

    def test_extract_runeword_stats(self):
        from d2r_mod.audit import extract_item_stats

        row = {
            "T1Code1": "ac%", "T1Param1": "", "T1Min1": "35", "T1Max1": "35",
            "T1Code2": "res-all", "T1Param2": "", "T1Min2": "30", "T1Max2": "30",
            "T1Code3": "", "T1Param3": "", "T1Min3": "", "T1Max3": "",
        }
        stats = extract_item_stats(row, prefix="T1Code", count=3,
                                    par_prefix="T1Param", min_prefix="T1Min",
                                    max_prefix="T1Max")
        self.assertEqual(len(stats), 2)
        self.assertEqual(stats[0]["prop"], "ac%")


class TestItemScoring(unittest.TestCase):
    def test_score_with_weights(self):
        from d2r_mod.audit import score_item

        stats = [
            {"prop": "str", "par": "", "min": 20, "max": 20},
            {"prop": "res-all", "par": "", "min": 30, "max": 30},
        ]
        weights = {"str": 60.0, "res-all": 75.0}
        score = score_item(stats, weights)
        self.assertAlmostEqual(score, 0.733, places=2)

    def test_derive_weights_from_endgame(self):
        from d2r_mod.audit import derive_stat_weights

        items = [
            {"stats": [{"prop": "str", "min": 20, "max": 20},
                        {"prop": "res-all", "min": 75, "max": 75}], "level": 65},
            {"stats": [{"prop": "str", "min": 60, "max": 60},
                        {"prop": "res-all", "min": 30, "max": 30}], "level": 70},
            {"stats": [{"prop": "str", "min": 10, "max": 10}], "level": 25},
        ]
        weights = derive_stat_weights(items, min_level=60)
        self.assertAlmostEqual(weights["str"], 60.0)
        self.assertAlmostEqual(weights["res-all"], 75.0)


class TestItemsAudit(unittest.TestCase):
    def test_flags_weak_items(self):
        from d2r_mod.audit import audit_items

        uniques = [
            {"index": f"Item{i}", "*ID": str(i), "disabled": "", "lvl": "65",
             "lvl req": "60", "code": "uap",
             "prop1": "str", "par1": "", "min1": str(v), "max1": str(v),
             "prop2": "res-all", "par2": "", "min2": str(v * 2), "max2": str(v * 2),
             **{f"prop{j}": "" for j in range(3, 13)},
             **{f"par{j}": "" for j in range(3, 13)},
             **{f"min{j}": "" for j in range(3, 13)},
             **{f"max{j}": "" for j in range(3, 13)},
             }
            for i, v in enumerate([50, 40, 30, 5])
        ]
        tables = {
            "data/global/excel/UniqueItems.txt": uniques,
            "data/global/excel/SetItems.txt": [],
            "data/global/excel/Runes.txt": [],
        }
        results = audit_items(tables)
        flagged = [r for r in results if r["flagged"]]
        self.assertTrue(any(r["name"] == "Item3" for r in flagged))


class TestReportGeneration(unittest.TestCase):
    def test_skills_report_contains_headers(self):
        from d2r_mod.audit import generate_skills_report

        results = [
            {"skill": "Fireball", "charclass": "sor", "class_name": "Sorceress",
             "category": "damage", "damage_avg": 500.0, "mana_cost": 10.0,
             "damage_per_mana": 50.0, "rank_in_class": 1,
             "flagged": False, "flag_reason": "", "damage_lo": 400, "damage_hi": 600},
        ]
        report = generate_skills_report(results)
        self.assertIn("# Skills Audit Report", report)
        self.assertIn("Sorceress", report)
        self.assertIn("Fireball", report)

    def test_items_report_contains_brackets(self):
        from d2r_mod.audit import generate_items_report

        results = [
            {"name": "Shako", "type": "unique", "level": 69,
             "bracket": "endgame", "score": 5.2, "stats": [],
             "flagged": False, "flag_reason": ""},
        ]
        report = generate_items_report(results)
        self.assertIn("# Items Audit Report", report)
        self.assertIn("endgame", report)
        self.assertIn("Shako", report)

    def test_flagged_items_highlighted(self):
        from d2r_mod.audit import generate_items_report

        results = [
            {"name": "BadItem", "type": "unique", "level": 65,
             "bracket": "endgame", "score": 0.5, "stats": [],
             "flagged": True, "flag_reason": "too weak"},
        ]
        report = generate_items_report(results)
        self.assertIn("BadItem", report)
        self.assertIn("too weak", report)
