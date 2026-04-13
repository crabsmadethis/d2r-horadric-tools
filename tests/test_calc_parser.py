import unittest


class TestTokenizer(unittest.TestCase):
    def test_simple_arithmetic(self):
        from d2r_mod.calc_parser import tokenize

        tokens = tokenize("1 + 2 * 3")
        values = [(t.type, t.value) for t in tokens]
        self.assertEqual(values, [
            ("NUMBER", "1"), ("OP", "+"), ("NUMBER", "2"),
            ("OP", "*"), ("NUMBER", "3"),
        ])

    def test_variable_names(self):
        from d2r_mod.calc_parser import tokenize

        tokens = tokenize("lvl * par8 + ln12")
        values = [(t.type, t.value) for t in tokens]
        self.assertEqual(values, [
            ("IDENT", "lvl"), ("OP", "*"), ("IDENT", "par8"),
            ("OP", "+"), ("IDENT", "ln12"),
        ])

    def test_skill_reference(self):
        from d2r_mod.calc_parser import tokenize

        tokens = tokenize("skill('Fire Bolt'.blvl)")
        types = [t.type for t in tokens]
        self.assertEqual(types, [
            "IDENT", "LPAREN", "STRING", "DOT", "IDENT", "RPAREN",
        ])
        self.assertEqual(tokens[2].value, "Fire Bolt")

    def test_quoted_expression(self):
        from d2r_mod.calc_parser import tokenize

        tokens = tokenize('"min(ln12,24)"')
        # Outer quotes stripped, inner content parsed
        self.assertEqual(tokens[0].type, "IDENT")
        self.assertEqual(tokens[0].value, "min")

    def test_negative_number_after_operator(self):
        from d2r_mod.calc_parser import tokenize

        tokens = tokenize("100 + -5")
        values = [(t.type, t.value) for t in tokens]
        self.assertEqual(values, [
            ("NUMBER", "100"), ("OP", "+"), ("NUMBER", "-5"),
        ])

    def test_comparison_operators(self):
        from d2r_mod.calc_parser import tokenize

        tokens = tokenize("lvl < 4")
        self.assertEqual(tokens[1].value, "<")

        tokens = tokenize("lvl >= 10")
        self.assertEqual(tokens[1].value, ">=")

    def test_ternary_tokens(self):
        from d2r_mod.calc_parser import tokenize

        tokens = tokenize("(lvl < 4) ? 0 : 1")
        ops = [t.value for t in tokens if t.type == "OP"]
        self.assertIn("<", ops)
        self.assertIn("?", ops)
        self.assertIn(":", ops)


class TestEvaluator(unittest.TestCase):
    def test_basic_arithmetic(self):
        from d2r_mod.calc_parser import eval_expr

        self.assertAlmostEqual(eval_expr("2 + 3", {}), 5.0)
        self.assertAlmostEqual(eval_expr("10 - 4", {}), 6.0)
        self.assertAlmostEqual(eval_expr("3 * 7", {}), 21.0)
        self.assertAlmostEqual(eval_expr("20 / 4", {}), 5.0)

    def test_operator_precedence(self):
        from d2r_mod.calc_parser import eval_expr

        self.assertAlmostEqual(eval_expr("2 + 3 * 4", {}), 14.0)
        self.assertAlmostEqual(eval_expr("(2 + 3) * 4", {}), 20.0)

    def test_variables(self):
        from d2r_mod.calc_parser import eval_expr

        ctx = {"lvl": 20, "par1": 3, "par2": 5}
        self.assertAlmostEqual(eval_expr("par1 + lvl / par2", ctx), 7.0)

    def test_unknown_variable_defaults_to_zero(self):
        from d2r_mod.calc_parser import eval_expr

        self.assertAlmostEqual(eval_expr("unknown + 5", {}), 5.0)

    def test_min_max_functions(self):
        from d2r_mod.calc_parser import eval_expr

        ctx = {"ln12": 30}
        self.assertAlmostEqual(eval_expr("min(ln12, 24)", ctx), 24.0)
        self.assertAlmostEqual(eval_expr("max(ln12, 24)", ctx), 30.0)

    def test_skill_reference(self):
        from d2r_mod.calc_parser import eval_expr

        ctx = {"skill_levels": {"Fire Bolt": 20, "Meteor": 15}}
        result = eval_expr("skill('Fire Bolt'.blvl) * 16", ctx)
        self.assertAlmostEqual(result, 320.0)

    def test_skill_reference_missing_defaults_zero(self):
        from d2r_mod.calc_parser import eval_expr

        ctx = {"skill_levels": {}}
        result = eval_expr("skill('Fire Bolt'.blvl) * 16", ctx)
        self.assertAlmostEqual(result, 0.0)

    def test_ternary(self):
        from d2r_mod.calc_parser import eval_expr

        ctx = {"lvl": 2}
        result = eval_expr("(lvl < 4) ? 0 : (lvl - 2) / 2", ctx)
        self.assertAlmostEqual(result, 0.0)

        ctx = {"lvl": 10}
        result = eval_expr("(lvl < 4) ? 0 : (lvl - 2) / 2", ctx)
        self.assertAlmostEqual(result, 4.0)

    def test_complex_synergy_expression(self):
        """Real expression from Strafe: synergy calc with multiple skill refs."""
        from d2r_mod.calc_parser import eval_expr

        expr = "ln12 + (skill('Guided Arrow'.blvl)*par8) + (skill('Multiple Shot'.blvl)*par9)"
        ctx = {
            "ln12": 100,
            "par8": 12,
            "par9": 12,
            "skill_levels": {"Guided Arrow": 20, "Multiple Shot": 20},
        }
        # 100 + (20*12) + (20*12) = 100 + 240 + 240 = 580
        self.assertAlmostEqual(eval_expr(expr, ctx), 580.0)

    def test_complex_conditional(self):
        """Real expression from Raise Skeletal Mage summon calc."""
        from d2r_mod.calc_parser import eval_expr

        expr = "max(skill('Skeleton Mastery'.lvl) + ((lvl < 4)?0:((lvl-2)/2)),1)"
        ctx = {"lvl": 10, "skill_levels": {"Skeleton Mastery": 15}}
        # max(15 + ((10<4)?0:((10-2)/2)), 1) = max(15 + 4, 1) = 19
        self.assertAlmostEqual(eval_expr(expr, ctx), 19.0)

    def test_empty_expression_returns_zero(self):
        from d2r_mod.calc_parser import eval_expr

        self.assertAlmostEqual(eval_expr("", {}), 0.0)
        self.assertAlmostEqual(eval_expr('""', {}), 0.0)
        self.assertAlmostEqual(eval_expr("  ", {}), 0.0)

    def test_negative_values(self):
        from d2r_mod.calc_parser import eval_expr

        self.assertAlmostEqual(eval_expr("-5 + 10", {}), 5.0)
        self.assertAlmostEqual(eval_expr("100 + -dm12", {"dm12": 30}), 70.0)

    def test_division_by_zero_returns_zero(self):
        from d2r_mod.calc_parser import eval_expr

        self.assertAlmostEqual(eval_expr("10 / 0", {}), 0.0)
