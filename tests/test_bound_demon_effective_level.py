"""Tests for Bind Demon effective-level derivation used by bound_demon YAML."""

from d2r_chargen.character import _effective_bind_demon_level


def test_effective_bind_demon_level_counts_active_player_skill_bonuses():
    char_def = {
        "class": "warlock",
        "skills": {"Bind Demon": 10},
        "equipment": [
            {
                "slot": "helm",
                "rare": True,
                "base": "ci3",
                "properties": {"all_skills": 2},
            },
            {
                "slot": "body",
                "rare": True,
                "base": "utp",
                "properties": {"class_skills": [3, "warlock"]},
            },
            {
                "slot": "weapon",
                "rare": True,
                "base": "72h",
                "properties": {"skill_tab": [4, 21]},
            },
        ],
        "inventory": {
            "charms": [
                {
                    "magic_small_charm": {
                        "count": 2,
                        "properties": {"all_skills": 1},
                    }
                }
            ]
        },
    }

    assert _effective_bind_demon_level(char_def) == 21


def test_effective_bind_demon_level_ignores_weapon_swap_bonuses():
    char_def = {
        "class": "warlock",
        "skills": {"Bind Demon": 5},
        "equipment": [
            {
                "slot": "switch_weapon",
                "rare": True,
                "base": "72h",
                "properties": {"all_skills": 10},
            }
        ],
    }

    assert _effective_bind_demon_level(char_def) == 5


def test_effective_bind_demon_level_requires_hard_point_for_general_plus_skills():
    char_def = {
        "class": "warlock",
        "skills": {"Bind Demon": 0},
        "equipment": [
            {
                "slot": "helm",
                "rare": True,
                "base": "ci3",
                "properties": {"all_skills": 10},
            }
        ],
    }

    assert _effective_bind_demon_level(char_def) == 0


def test_effective_bind_demon_level_counts_direct_bind_demon_item_skill():
    char_def = {
        "class": "warlock",
        "skills": {"Bind Demon": 0},
        "equipment": [
            {
                "slot": "weapon",
                "rare": True,
                "base": "7di",
                "properties": {"non_class_skill": [3, "Bind Demon"]},
            }
        ],
    }

    assert _effective_bind_demon_level(char_def) == 3


def test_effective_bind_demon_level_ignores_grouped_non_skill_properties():
    char_def = {
        "class": "warlock",
        "skills": {"Bind Demon": 20},
        "equipment": [
            {
                "slot": "weapon",
                "rare": True,
                "base": "72h",
                "properties": {
                    "item_maxdamage_percent": 300,
                    "all_skills": 2,
                },
            }
        ],
    }

    assert _effective_bind_demon_level(char_def) == 22
