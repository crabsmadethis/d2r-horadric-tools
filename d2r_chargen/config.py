"""Single source of truth for D2R chargen constants."""
import os


def _detect_saves_dir():
    """Auto-detect D2R saves directory, or use D2R_SAVES env var."""
    if 'D2R_SAVES' in os.environ:
        return os.environ['D2R_SAVES']

    candidates = [
        # Steam Deck / Linux (Proton)
        os.path.expanduser(
            "~/.local/share/Steam/steamapps/compatdata/2536520/pfx"
            "/drive_c/users/steamuser/Saved Games/Diablo II Resurrected"
        ),
        # Windows
        os.path.expanduser(
            "~/Saved Games/Diablo II Resurrected"
        ),
        # macOS (if it ever gets a native port)
        os.path.expanduser(
            "~/Library/Application Support/Diablo II Resurrected"
        ),
    ]
    for path in candidates:
        if os.path.isdir(path):
            return path

    # Fallback to first candidate (will error at use time if missing)
    return candidates[0]


def _detect_chars_dir():
    """Character YAML directory. Override with D2R_CHARS env var."""
    if 'D2R_CHARS' in os.environ:
        return os.environ['D2R_CHARS']
    return os.path.join(os.getcwd(), 'chars')


SAVES = _detect_saves_dir()
CHARS_DIR = _detect_chars_dir()

# Equipment slot name -> (bodyloc, storage, location) for equipped items
SLOT_MAP = {
    'helm':           {'bodyloc': 1,  'storage': 0, 'location': 1},
    'neck':           {'bodyloc': 2,  'storage': 0, 'location': 1},
    'body':           {'bodyloc': 3,  'storage': 0, 'location': 1},
    'weapon':         {'bodyloc': 4,  'storage': 0, 'location': 1},
    'shield':         {'bodyloc': 5,  'storage': 0, 'location': 1},
    'ring_right':     {'bodyloc': 6,  'storage': 0, 'location': 1},
    'ring_left':      {'bodyloc': 7,  'storage': 0, 'location': 1},
    'belt':           {'bodyloc': 8,  'storage': 0, 'location': 1},
    'feet':           {'bodyloc': 9,  'storage': 0, 'location': 1},
    'hands':          {'bodyloc': 10, 'storage': 0, 'location': 1},
    'switch_weapon':  {'bodyloc': 11, 'storage': 0, 'location': 1},
    'switch_shield':  {'bodyloc': 12, 'storage': 0, 'location': 1},
}

# Runeword base category expansion map: runeword required base type → all
# matching item categories from item_bases.py.  Single source of truth used by
# resolve.py (YAML validation), build_lib.py (binary build validation), and
# scanner.py (post-write verification).
RW_BASE_CATEGORIES = {
    'Body Armor': ['Body Armor', 'Armor'],
    'Shield': ['Shield', 'Any Shield', 'Auric Shields'],
    'Helm': ['Helm'],
    'Dagger': ['Dagger', 'Knife'],
    'Weapon': [
        'Weapon', 'Melee Weapon', 'Missile Weapon',
        'Sword', 'Axe', 'Mace', 'Hammer', 'Club', 'Scepter',
        'Polearm', 'Spear', 'Staff', 'Bow', 'Crossbow',
        'Dagger', 'Knife', 'Wand', 'Hand to Hand', 'Orb',
    ],
    'Melee Weapon': [
        'Melee Weapon', 'Weapon',
        'Sword', 'Axe', 'Mace', 'Hammer', 'Club', 'Scepter',
        'Polearm', 'Spear', 'Staff', 'Dagger', 'Knife', 'Hand to Hand',
    ],
    'Missile Weapon': ['Missile Weapon', 'Bow', 'Crossbow'],
    'Sword': ['Sword'],
    'Axe': ['Axe'],
    'Scepter': ['Scepter'],
    'Hammer': ['Hammer'],
    'Club': ['Club'],
    'Mace': ['Mace'],
    'Polearm': ['Polearm'],
    'Spear': ['Spear'],
    'Staff': ['Staff'],
    'Bow': ['Bow'],
    'Crossbow': ['Crossbow'],
    'Wand': ['Wand'],
    'Hand to Hand': ['Hand to Hand'],
    'Auric Shields': ['Auric Shields'],
    'Orb': ['Orb'],
}

# YAML property name aliases -> item_stat_cost.py STAT_BY_NAME keys
# Raw STAT_BY_NAME keys are also accepted (pass through unchanged)
# Stat IDs verified against d2r_build_lib.py constants (CLAUDE.md Rule 14)
PROPERTY_ALIASES = {
    # Core stats (0-9)
    'strength': 'strength',              # 0
    'dexterity': 'dexterity',            # 2
    'vitality': 'vitality',              # 3
    'energy': 'energy',                  # 1
    'life': 'maxhp',                     # 7
    'maxhp': 'maxhp',                    # 7
    'mana': 'maxmana',                   # 9
    'maxmana': 'maxmana',                # 9
    'mana_pct': 'item_maxmana_percent',  # 77
    # Resistances (39-46)
    'fire_res': 'fireresist',            # 39
    'cold_res': 'coldresist',            # 43
    'light_res': 'lightresist',          # 41
    'poison_res': 'poisonresist',        # 45
    'max_fire_res': 'maxfireresist',     # 40
    'max_cold_res': 'maxcoldresist',     # 44
    'max_light_res': 'maxlightresist',   # 42
    'max_poison_res': 'maxpoisonresist', # 46
    # Speed (93-105)
    'fcr': 'item_fastercastrate',        # 105
    'fhr': 'item_fastergethitrate',      # 99
    'frw': 'item_fastermovevelocity',    # 96
    'ias': 'item_fasterattackrate',      # 93
    'fbr': 'item_fasterblockrate',       # 102
    # Damage (16-17, 21-22, 48-59)
    'ed': 'item_armor_percent',          # 16  Enhanced Defense (NOT 17!)
    'enhanced_def': 'item_armor_percent',  # 16  (alias for ed)
    'enhanced_dmg': 'item_maxdamage_percent',  # 17  Enhanced Max Damage
    'min_dmg': 'mindamage',              # 21
    'max_dmg': 'maxdamage',              # 22
    'fire_min': 'firemindam',            # 48
    'fire_max': 'firemaxdam',            # 49
    'light_min': 'lightmindam',          # 50
    'light_max': 'lightmaxdam',          # 51
    'cold_min': 'coldmindam',            # 54
    'cold_max': 'coldmaxdam',            # 55
    'cold_len': 'coldlength',            # 56
    'poison_min': 'poisonmindam',        # 57
    'poison_max': 'poisonmaxdam',        # 58
    'poison_len': 'poisonlength',        # 59
    # Leech / absorb (60-62, 142-148)
    'life_leech': 'lifedrainmindam',     # 60
    'mana_leech': 'manadrainmindam',     # 62
    'absorb_fire_pct': 'item_absorbfire_percent',   # 142
    'absorb_cold_pct': 'item_absorbcold_percent',   # 148
    'absorb_light_pct': 'item_absorblight_percent', # 144
    'magic_absorb': 'item_absorbmagic',  # 147
    # Skills (83, 97, 127, 188)
    'all_skills': 'item_allskills',      # 127
    'class_skills': 'item_addclassskills',  # 83
    'skill_tab': 'item_addskill_tab',    # 188
    'non_class_skill': 'item_nonclassskill',  # 97
    # Aura / procs (151, 196-204)
    'item_aura': 'item_aura',           # 151
    'ctc_hit': 'item_skillonhit',        # 198
    'ctc_struck': 'item_skillongethit',  # 201
    'ctc_kill': 'item_skillonkill',      # 196
    'charges': 'item_charged_skill',     # 204
    # Defense (20, 31, 34-35)
    'defense': 'armorclass',             # 31
    'block': 'toblock',                  # 20
    'dr_pct': 'damageresist',            # 36
    'mdr': 'magic_damage_reduction',     # 35
    # Misc
    'mf': 'item_magicbonus',             # 80
    'gold_find': 'item_goldbonus',       # 79
    'light_radius': 'item_lightradius',  # 89
    'add_exp': 'item_addexperience',     # 85
    'mana_regen': 'manarecoverybonus',   # 27
    'replenish_life': 'hpregen',         # 74
    'slow_target': 'item_slow',          # 150
    'cannot_frozen': 'item_cannotbefrozen',  # 153
    'crush_blow': 'item_crushingblow',   # 136
    'open_wounds': 'item_openwounds',    # 135
    'deadly_strike': 'item_deadlystrike',  # 141
    'ar_pct': 'item_tohit_percent',      # 119
    'indestructible': 'item_indesctructible',  # 152
    'sockets': 'item_numsockets',        # 194
    'dmg_undead': 'item_undeaddamage_percent',  # 122
    # Pierce / enemy res (305-307, 333-335)
    'pierce_fire': 'passive_fire_pierce',  # 333
    'pierce_cold': 'passive_cold_pierce',  # 335
    'pierce_ltng': 'passive_ltng_pierce',  # 334
    'enemy_fire_res': 'item_pierce_fire',  # 306
    'enemy_cold_res': 'item_pierce_cold',  # 305
    'enemy_ltng_res': 'item_pierce_ltng',  # 307
    # Immunity pierce (sunder charms, 187-192)
    'item_pierce_cold_immunity': 'item_pierce_cold_immunity',     # 187
    'item_pierce_fire_immunity': 'item_pierce_fire_immunity',     # 189
    'item_pierce_light_immunity': 'item_pierce_light_immunity',   # 190
    'item_pierce_poison_immunity': 'item_pierce_poison_immunity', # 191
    'item_pierce_damage_immunity': 'item_pierce_damage_immunity', # 192
    # Skill damage mastery (329-331)
    'fire_skill_dmg': 'passive_fire_mastery',   # 329
    'ltng_skill_dmg': 'passive_ltng_mastery',   # 330
    'cold_skill_dmg': 'passive_cold_mastery',   # 331
    # Kill bonuses
    'item_healafterkill': 'item_healafterkill',  # 86
    'item_manaafterkill': 'item_manaafterkill',  # 138
    'maxstamina': 'maxstamina',          # 11
    # Item properties (misc)
    'ignore_target_ac': 'item_ignoretargetac',      # 115
    'req_percent': 'item_req_percent',              # 91
    'replenish_dur': 'item_replenish_durability',   # 252
    'dmg_demon': 'item_demondamage_percent',        # 121
    # Note: ar_percent intentionally omitted — ar_pct already covers item_tohit_percent (119)
    # Per-level scaling (value * char_level / 8)
    'max_dmg_per_lvl': 'item_maxdamage_perlevel',  # 218
    'ar_per_lvl': 'item_tohit_perlevel',            # 224
    'hp_per_lvl': 'item_hp_perlevel',               # 216
    'def_per_lvl': 'item_armor_perlevel',           # 214
}

# Class definitions: name -> id, skill_base, skill_code (for skills.py lookup)
CLASS_DEFS = {
    'amazon':      {'id': 0, 'skill_base': 6,   'skill_code': 'ama'},
    'sorceress':   {'id': 1, 'skill_base': 36,  'skill_code': 'sor'},
    'necromancer': {'id': 2, 'skill_base': 66,  'skill_code': 'nec'},
    'paladin':     {'id': 3, 'skill_base': 96,  'skill_code': 'pal'},
    'barbarian':   {'id': 4, 'skill_base': 126, 'skill_code': 'bar'},
    'druid':       {'id': 5, 'skill_base': 221, 'skill_code': 'dru'},
    'assassin':    {'id': 6, 'skill_base': 251, 'skill_code': 'ass'},
    'warlock':     {'id': 7, 'skill_base': 373, 'skill_code': 'wlk'},
}

# Charm dimensions: type_code -> (width, height)
CHARM_DIMS = {
    'cm1': (1, 1),  # small charm
    'cm2': (1, 2),  # large charm
    'cm3': (1, 3),  # grand charm
}


def validate_aliases():
    """Validate all property aliases point to valid STAT_BY_NAME keys. Call at startup."""
    try:
        from d2r_chargen.data.item_stat_cost import STAT_BY_NAME
    except ImportError:
        return  # Data not extracted yet — skip validation
    errors = []
    for alias, canonical in PROPERTY_ALIASES.items():
        if canonical not in STAT_BY_NAME:
            errors.append(f"Alias '{alias}' -> '{canonical}' not in STAT_BY_NAME")
    if errors:
        raise ValueError("Invalid property aliases:\n  " + "\n  ".join(errors))


# Module-level cache for reverse alias lookup (stat_id -> shortest alias)
_REVERSE_ALIAS_CACHE = None

def reverse_resolve_alias(stat_id):
    """Return the shortest YAML alias for a stat ID.

    Falls back to the canonical STAT_BY_NAME key, then 'stat_<id>'.
    """
    global _REVERSE_ALIAS_CACHE
    if _REVERSE_ALIAS_CACHE is None:
        from d2r_chargen.data.item_stat_cost import STAT_BY_NAME
        # Build reverse map: stat_id -> list of alias strings
        by_id = {}
        for alias, canonical in PROPERTY_ALIASES.items():
            sid = STAT_BY_NAME.get(canonical)
            if sid is not None:
                by_id.setdefault(sid, []).append(alias)
        # Also add canonical names as fallback
        for name, sid in STAT_BY_NAME.items():
            by_id.setdefault(sid, []).append(name)
        # Pick shortest alias per stat_id
        _REVERSE_ALIAS_CACHE = {}
        for sid, aliases in by_id.items():
            _REVERSE_ALIAS_CACHE[sid] = min(aliases, key=len)

    return _REVERSE_ALIAS_CACHE.get(stat_id, f'stat_{stat_id}')
