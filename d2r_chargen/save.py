#!/usr/bin/env python3
"""D2R Save File Manipulation Functions.

Extracted from build_characters.py — single source of truth for save-file
binary operations: rebuild items, set stats, waypoints, quests, skills,
difficulty, and create new characters from templates.
"""
import os, struct, shutil

from d2r_chargen.build_lib import calc_checksum


# ============================================================
# Helpers
# ============================================================

def find_section(data, marker, start=0):
    """Find a section marker in save data."""
    pos = data.find(marker.encode() if isinstance(marker, str) else marker, start)
    return pos


# ============================================================
# Character Stats
# ============================================================

CHAR_STAT_DEFS = {
    0:  ("Strength",    10),  1:  ("Energy",      10),
    2:  ("Dexterity",   10),  3:  ("Vitality",    10),
    4:  ("StatPoints",  10),  5:  ("SkillPoints",  8),
    6:  ("HP",          21),  7:  ("MaxHP",        21),
    8:  ("Mana",        21),  9:  ("MaxMana",      21),
    10: ("Stamina",     21), 11:  ("MaxStamina",   21),
    12: ("Level",        7), 13:  ("Experience",   32),
    14: ("Gold",        25), 15:  ("StashedGold",  25),
}


_XP_THRESHOLDS = [
    500, 1500, 3750, 7875, 14175,
    22680, 32886, 44396, 57715, 72144,
    90180, 112725, 140906, 176132, 220165,
    275207, 344008, 430010, 537513, 671891,
    839864, 1049830, 1312287, 1640359, 2050449,
    2563061, 3203826, 3902260, 4663553, 5493363,
    6397855, 7383752, 8458379, 9629723, 10906488,
    12298162, 13815086, 15468534, 17270791, 19235252,
    21376515, 23710491, 26254525, 29027522, 32050088,
    35344686, 38935798, 42850109, 47116709, 51767302,
    56836449, 62361819, 68384473, 74949165, 82104680,
    89904191, 98405658, 107672256, 117772849, 128782495,
    140783010, 153863570, 168121381, 183662396, 200602101,
    219066380, 239192444, 261129853, 285041630, 311105466,
    339515048, 370481492, 404234916, 441026148, 481128591,
    524840254, 572485967, 624419793, 681027665, 742730244,
    809986056, 883294891, 963201521, 1050299747, 1145236814,
    1248718217, 1361512946, 1484459201, 1618470619, 1764543065,
    1923762030, 2097310703, 2286478756, 2492671933, 2717422497,
    2962400612, 3229426756, 3520485254,
]

_CLASS_STATS = {
    'amazon':      {'base_str': 20, 'base_dex': 25, 'base_vit': 20, 'base_en': 15, 'hpadd': 30, 'life_per_level': 8,  'life_per_vit': 12, 'mana_per_level': 6, 'mana_per_magic': 6, 'stamina_per_level': 4, 'stamina_per_vit': 4, 'base_stamina': 84},
    'sorceress':   {'base_str': 10, 'base_dex': 25, 'base_vit': 10, 'base_en': 35, 'hpadd': 30, 'life_per_level': 4,  'life_per_vit': 8,  'mana_per_level': 8, 'mana_per_magic': 8, 'stamina_per_level': 4, 'stamina_per_vit': 4, 'base_stamina': 74},
    'necromancer': {'base_str': 15, 'base_dex': 25, 'base_vit': 15, 'base_en': 25, 'hpadd': 30, 'life_per_level': 6,  'life_per_vit': 8,  'mana_per_level': 8, 'mana_per_magic': 8, 'stamina_per_level': 4, 'stamina_per_vit': 4, 'base_stamina': 79},
    'paladin':     {'base_str': 25, 'base_dex': 20, 'base_vit': 25, 'base_en': 15, 'hpadd': 30, 'life_per_level': 8,  'life_per_vit': 12, 'mana_per_level': 6, 'mana_per_magic': 6, 'stamina_per_level': 4, 'stamina_per_vit': 4, 'base_stamina': 89},
    'barbarian':   {'base_str': 30, 'base_dex': 20, 'base_vit': 25, 'base_en': 10, 'hpadd': 30, 'life_per_level': 8,  'life_per_vit': 16, 'mana_per_level': 4, 'mana_per_magic': 4, 'stamina_per_level': 4, 'stamina_per_vit': 4, 'base_stamina': 92},
    'druid':       {'base_str': 15, 'base_dex': 20, 'base_vit': 25, 'base_en': 20, 'hpadd': 30, 'life_per_level': 6,  'life_per_vit': 8,  'mana_per_level': 8, 'mana_per_magic': 8, 'stamina_per_level': 4, 'stamina_per_vit': 4, 'base_stamina': 84},
    'assassin':    {'base_str': 20, 'base_dex': 20, 'base_vit': 20, 'base_en': 25, 'hpadd': 30, 'life_per_level': 8,  'life_per_vit': 12, 'mana_per_level': 6, 'mana_per_magic': 7, 'stamina_per_level': 5, 'stamina_per_vit': 5, 'base_stamina': 95},
    'warlock':     {'base_str': 15, 'base_dex': 20, 'base_vit': 25, 'base_en': 20, 'hpadd': 30, 'life_per_level': 8,  'life_per_vit': 12, 'mana_per_level': 6, 'mana_per_magic': 8, 'stamina_per_level': 4, 'stamina_per_vit': 4, 'base_stamina': 86},
}


def _xp_for_level(level):
    """Return minimum XP to be at the given level (1-99)."""
    if level <= 1:
        return 0
    if level > 99:
        level = 99
    return _XP_THRESHOLDS[level - 2]


def _calc_life_mana_stamina(char_class, level, vitality, energy):
    """Compute HP/Mana/Stamina stored values (×256) from class, level, stats.

    Uses CharStats.txt formulas. Per-level/per-stat values are in quarter-units.
    """
    cs = _CLASS_STATS.get(char_class)
    if cs is None:
        # Fallback for unknown class
        hp = (50 + (level - 1) * 2 + vitality * 2) * 256
        mana = (20 + (level - 1) * 2 + energy * 2) * 256
        stamina = (80 + (level - 1) + vitality) * 256
        return hp, mana, stamina

    # All per-level/per-stat values from CharStats.txt are in quarter-units
    hp = cs['hpadd'] + (level - 1) * cs['life_per_level'] // 4 + \
        (vitality - cs['base_vit']) * cs['life_per_vit'] // 4
    mana = (level - 1) * cs['mana_per_level'] // 4 + \
        (energy - cs['base_en']) * cs['mana_per_magic'] // 4
    stamina = cs['base_stamina'] + (level - 1) * cs['stamina_per_level'] // 4 + \
        (vitality - cs['base_vit']) * cs['stamina_per_vit'] // 4

    return hp * 256, max(mana, 1) * 256, stamina * 256


def set_character_stats(data, strength, dexterity, vitality, energy,
                        level=99, char_class=None, skill_points_spent=0):
    """Set character stats at the given level with correct XP and HP/Mana.

    Calculates remaining stat/skill points from level and allocated values.
    """
    gf = data.find(b'gf')
    if_pos = data.find(b'if')
    if gf < 0 or if_pos < 0:
        print("  WARNING: gf/if markers not found, skipping stats")
        return data

    original_len = if_pos - (gf + 2)

    # Decode existing stats to preserve values we don't explicitly set
    bits_in = []
    for byte in data[gf+2: gf+2+original_len]:
        for b in range(8):
            bits_in.append((byte >> b) & 1)
    old_stats = {}
    pos = 0
    while pos + 9 <= len(bits_in):
        sid = sum(bits_in[pos+i] << i for i in range(9))
        pos += 9
        if sid == 0x1ff:
            break
        if sid not in CHAR_STAT_DEFS:
            break
        w = CHAR_STAT_DEFS[sid][1]
        val = sum(bits_in[pos+i] << i for i in range(w))
        pos += w
        old_stats[CHAR_STAT_DEFS[sid][0]] = val

    # Calculate XP and HP/Mana/Stamina for the target level
    xp = _xp_for_level(level)
    hp_val, mana_val, stamina_val = _calc_life_mana_stamina(
        char_class, level, vitality, energy)

    # Calculate remaining stat points from class base stats
    total_stat_points = 5 * (level - 1)
    stat_points_spent = 0
    cs = _CLASS_STATS.get(char_class)
    if cs:
        stat_points_spent = (
            (strength - cs['base_str']) +
            (dexterity - cs['base_dex']) +
            (vitality - cs['base_vit']) +
            (energy - cs['base_en'])
        )
    stat_points_remaining = max(0, total_stat_points - stat_points_spent)

    # Calculate remaining skill points (1 per level-up)
    total_skill_points = level - 1
    skill_points_remaining = max(0, total_skill_points - skill_points_spent)

    overrides = {
        'Strength': strength, 'Dexterity': dexterity,
        'Vitality': vitality, 'Energy': energy,
        'StatPoints': stat_points_remaining,
        'SkillPoints': skill_points_remaining,
        'Level': level, 'Experience': xp,
        'HP': hp_val, 'MaxHP': hp_val,
        'Mana': mana_val, 'MaxMana': mana_val,
        'Stamina': stamina_val, 'MaxStamina': stamina_val,
        'Gold': 0, 'StashedGold': 2500000,
    }

    # Build stat list. Always include core stats even when zero — the game
    # expects StatPoints, SkillPoints, Gold in the block for validation.
    _ALWAYS_INCLUDE = {0, 1, 2, 3, 4, 5, 12, 13, 14, 15}  # core stats
    stats_list = []
    for sid in sorted(CHAR_STAT_DEFS.keys()):
        name = CHAR_STAT_DEFS[sid][0]
        val = overrides.get(name, old_stats.get(name, 0))
        if val > 0 or sid in _ALWAYS_INCLUDE:
            stats_list.append((sid, val))

    # Encode
    bits = []
    def push(val, n):
        for i in range(n): bits.append((val >> i) & 1)
    for sid, val in stats_list:
        push(sid, 9)
        push(val, CHAR_STAT_DEFS[sid][1])
    push(0x1ff, 9)
    while len(bits) % 8:
        bits.append(0)
    raw = bytearray(sum(bits[i+j] << j for j in range(8)) for i in range(0, len(bits), 8))

    if len(raw) > original_len:
        # Expand the stats section by inserting bytes before 'if'
        extra = len(raw) - original_len
        data = data[:gf+2] + bytes(raw) + data[if_pos:]
        print(f"  Stats section expanded by {extra} bytes")
    else:
        raw += b'\x00' * (original_len - len(raw))
        data[gf+2:gf+2+original_len] = raw

    # Update header level byte (0x1B)
    data[0x1B] = level

    print(f"  Stats set: STR={strength} DEX={dexterity} VIT={vitality} EN={energy} Lv={level} XP={xp} StatPts={stat_points_remaining} SkillPts={skill_points_remaining}")
    return data


# ============================================================
# Waypoints, Quests, Skills, Difficulty
# ============================================================

_DIFF_LEVELS = {'normal': 0, 'nightmare': 1, 'hell': 2}
_DIFF_PROG = {'normal': 0x00, 'nightmare': 0x05, 'hell': 0x0F}
# WP counts per act: Act 1=9, Act 2=9, Act 3=9, Act 4=3, Act 5=9
_WP_COUNTS = [9, 9, 9, 3, 9]


def set_waypoints(data, difficulty='hell'):
    """Set waypoints up to the given difficulty.

    For the target difficulty, sets first WP only (town).
    For all lower difficulties, sets all WPs.
    """
    ws_pos = find_section(data, b'WS')
    if ws_pos < 0:
        print("  WARNING: WS marker not found!")
        return data

    target = _DIFF_LEVELS.get(difficulty, 2)
    for diff in range(3):
        base = ws_pos + 8 + diff * 24
        if diff < target:
            # Lower difficulties: all waypoints
            data[base] = 0x02
            data[base+1] = 0x01
            for i in range(5):
                data[base+2+i] = 0xFF
        elif diff == target:
            # Target difficulty: first WP only (Act 1 town)
            data[base] = 0x02
            data[base+1] = 0x01
            for i in range(5):
                data[base+2+i] = 0x00
        # Higher difficulties: leave as-is (zeros from template)

    print(f"  Waypoints set for difficulty={difficulty}")
    return data


def set_all_waypoints(data):
    """Set all waypoints for all 3 difficulties (backward compat)."""
    ws_pos = find_section(data, b'WS')
    if ws_pos < 0:
        print("  WARNING: WS marker not found!")
        return data

    for diff in range(3):
        base = ws_pos + 8 + diff * 24
        data[base] = 0x02
        data[base+1] = 0x01
        for i in range(5):
            data[base+2+i] = 0xFF

    print("  All waypoints set for Normal/Nightmare/Hell")
    return data


def set_quests(data, difficulty='hell'):
    """Set quests completed up through the given difficulty.

    For difficulties below the target: all quests completed.
    Target difficulty and above: untouched (fresh).
    """
    woo_pos = find_section(data, b'Woo!')
    if woo_pos < 0:
        print("  WARNING: Woo! marker not found!")
        return data

    target = _DIFF_LEVELS.get(difficulty, 2)
    for diff in range(3):
        base = woo_pos + 10 + diff * 96
        if diff < target:
            # Lower difficulties: all quests completed
            for quest in range(48):
                offset = base + quest * 2
                if offset + 1 < len(data):
                    data[offset] = 0x01
                    data[offset+1] = 0x10
        # Target difficulty and above: leave fresh

    print(f"  Quests set for difficulty={difficulty}")
    return data


def set_all_quests(data):
    """Set all quests completed for all 3 difficulties (backward compat)."""
    woo_pos = find_section(data, b'Woo!')
    if woo_pos < 0:
        print("  WARNING: Woo! marker not found!")
        return data

    for diff in range(3):
        base = woo_pos + 10 + diff * 96
        for quest in range(48):  # 6 acts × 8 quests
            offset = base + quest * 2
            if offset + 1 < len(data):
                data[offset] = 0x01      # quest complete
                data[offset+1] = 0x10    # reward collected

    print("  All quests set to completed for Normal/Nightmare/Hell")
    return data


# Quests per act: 8 quests per act × 6 acts = 48 quests per difficulty
_QUESTS_PER_ACT = 8
_WP_ACT_NAMES = ['act1', 'act2', 'act3', 'act4', 'act5']
_QUEST_ACT_NAMES = ['act1', 'act2', 'act3', 'act4', 'act5', 'act6']


def set_waypoints_granular(data, waypoints_dict):
    """Set waypoints from a resolved progression dict.

    Args:
        data: bytearray of .d2s file
        waypoints_dict: dict mapping difficulty -> True (all WPs) / False (none)
                        / dict of act_name -> bool

    Returns:
        Modified bytearray.
    """
    ws_pos = find_section(data, b'WS')
    if ws_pos < 0:
        print("  WARNING: WS marker not found!")
        return data

    diff_names = ['normal', 'nightmare', 'hell']
    for diff_idx, diff_name in enumerate(diff_names):
        base = ws_pos + 8 + diff_idx * 24
        val = waypoints_dict.get(diff_name, False)

        if val is True:
            data[base] = 0x02
            data[base+1] = 0x01
            for i in range(5):
                data[base+2+i] = 0xFF
        elif val is False:
            data[base] = 0x02
            data[base+1] = 0x01
            for i in range(5):
                data[base+2+i] = 0x00
        elif isinstance(val, dict):
            data[base] = 0x02
            data[base+1] = 0x01
            mask = 0
            bit_offset = 0
            for act_idx, act_name in enumerate(_WP_ACT_NAMES):
                act_wps = _WP_COUNTS[act_idx]
                if val.get(act_name, False):
                    for b in range(act_wps):
                        mask |= (1 << (bit_offset + b))
                bit_offset += act_wps
            for i in range(5):
                data[base+2+i] = (mask >> (i * 8)) & 0xFF

    print(f"  Waypoints set (granular)")
    return data


def set_quests_granular(data, quests_dict):
    """Set quests from a resolved progression dict.

    Args:
        data: bytearray of .d2s file
        quests_dict: dict mapping difficulty -> True (all quests) / False (none)
                     / dict of act_name -> bool

    Returns:
        Modified bytearray.
    """
    woo_pos = find_section(data, b'Woo!')
    if woo_pos < 0:
        print("  WARNING: Woo! marker not found!")
        return data

    diff_names = ['normal', 'nightmare', 'hell']
    for diff_idx, diff_name in enumerate(diff_names):
        base = woo_pos + 10 + diff_idx * 96
        val = quests_dict.get(diff_name, False)

        if val is True:
            for quest in range(48):
                offset = base + quest * 2
                if offset + 1 < len(data):
                    data[offset] = 0x01
                    data[offset+1] = 0x10
        elif val is False:
            for quest in range(48):
                offset = base + quest * 2
                if offset + 1 < len(data):
                    data[offset] = 0x00
                    data[offset+1] = 0x00
        elif isinstance(val, dict):
            for act_idx, act_name in enumerate(_QUEST_ACT_NAMES):
                act_start = act_idx * _QUESTS_PER_ACT
                act_complete = val.get(act_name, False)
                for q in range(_QUESTS_PER_ACT):
                    offset = base + (act_start + q) * 2
                    if offset + 1 < len(data):
                        if act_complete:
                            data[offset] = 0x01
                            data[offset+1] = 0x10
                        else:
                            data[offset] = 0x00
                            data[offset+1] = 0x00

    print(f"  Quests set (granular)")
    return data


def set_skills(data, skill_levels):
    """Set skill levels (30 skills, 1 byte each after 'if' marker)."""
    if_pos = data.find(b'if')
    if if_pos < 0:
        print("  WARNING: if marker not found, skipping skills")
        return data
    for i, lvl in enumerate(skill_levels[:30]):
        data[if_pos + 2 + i] = lvl
    print(f"  Skills set: {sum(skill_levels[:30])} total points allocated")
    return data


def set_difficulty(data, difficulty='hell'):
    """Set character to the given difficulty, Act 1.

    For HC characters (status bit 2), does NOT set the act byte —
    the game validates act vs quest state and rejects mismatches.
    """
    prog = _DIFF_PROG.get(difficulty, 0x0F)
    data[0x15] = prog
    is_hc = bool(data[0x14] & 0x04)

    if not is_hc and len(data) > 0xAA:
        act_index = _DIFF_LEVELS.get(difficulty, 2) * 5  # 0=Normal A1, 5=NM A1, 10=Hell A1
        data[0xA8] = 0x00
        data[0xA9] = act_index
        data[0xAA] = 0x00

    print(f"  Difficulty set to {difficulty} (prog=0x{prog:02X}, HC={is_hc})")
    return data


def set_difficulty_hell(data):
    """Set character to Hell difficulty, Act 1 (backward compat)."""
    return set_difficulty(data, 'hell')


# ============================================================
# Mercenary header
# ============================================================

# Mapping of merc template `type:` strings to Hireling.txt Id column values.
# The Id column encodes (class, element, difficulty) — see
# docs/superpowers/specs/2026-04-19-merc-disk-encoding.md for derivation.
# Hell-tier is the default since chargen builds are Hell-capable; NM/Normal
# variants are explicit via the _nm_/_normal_ suffix.
MERC_HIRELING_ID: dict = {
    # Act 1 Rogue
    'act1_fire':             4,   # Fire-Hell
    'act1_cold':             5,   # Ice-Hell
    'act1_fire_nm':          2,   # Fire-Nightmare
    'act1_cold_nm':          3,   # Ice-Nightmare
    # Act 2 Desert (classic auras)
    'act2_combat':          12,   # Comb-Hell (Prayer/Thorns in Hell)
    'act2_defensive':       13,   # Def-Hell (Defiance/HolyFreeze in Hell)
    'act2_offensive':       14,   # Off-Hell (BlessedAim/Might in Hell)
    'act2_nm_combat':        9,   # Comb-NM
    'act2_nm_defensive':    10,   # Def-NM
    'act2_nm_offensive':    11,   # Off-NM (Might)
    # Act 2 Desert (expansion aura overrides — Hell tier)
    'act2_thorns':          33,   # Thorns-Hell
    'act2_holyfreeze':      34,   # HolyFreeze-Hell
    'act2_might':           35,   # Might-Hell
    # Act 3 Iron Wolf
    'act3_fire':            21,   # Fire-Hell
    'act3_cold':            22,   # Cold-Hell
    'act3_ltng':            23,   # Ltng-Hell
    'act3_fire_nm':         18,
    'act3_cold_nm':         19,
    'act3_ltng_nm':         20,
    # Act 5 Barbarian
    'act5_2hs':             28,   # 2H-Hell
    'act5_2hs_alt':         29,   # 2H-Hell (alt name pool)
    'act5_1hs':             38,   # 1H-Hell (mod-added)
    # Act 4 Holy Warrior (mod-added)
    'act4_smite':           41,   # Smite-Hell
    'act4_smite_nm':        40,   # Smite-NM
}


def set_merc_header(data, hireling_id: int, seed: int | None = None,
                    xp: int = 0, field_a7: int = 0):
    """Write the merc header fields at offsets 0xa3-0xae.

    Fields (all little-endian):
      0xa3  u32  name seed (RNG for Hireling.NameFirst/NameLast picks)
      0xa7  u16  unknown (kept zero/default; semantics TBD)
      0xa9  u16  Hireling.txt Id column (class+element+difficulty)
      0xab  u32  merc XP

    Args:
        data: bytearray of the .d2s file (modified in place)
        hireling_id: Hireling.txt Id column value (0-41 in rebalance mod)
        seed: u32 name seed (None → random)
        xp: initial merc XP (default 0 — D2R will accrue on kills)
        field_a7: u16 at 0xa7 (default 0; live values seen: 10 for Geshef, 13 for Elexa)

    Returns: modified bytearray
    """
    import random
    if seed is None:
        seed = random.getrandbits(32)
    if not (0 <= hireling_id < 0x10000):
        raise ValueError(f"hireling_id {hireling_id} outside u16 range")

    struct.pack_into('<I', data, 0xa3, seed & 0xFFFFFFFF)
    struct.pack_into('<H', data, 0xa7, field_a7 & 0xFFFF)
    struct.pack_into('<H', data, 0xa9, hireling_id & 0xFFFF)
    struct.pack_into('<I', data, 0xab, xp & 0xFFFFFFFF)
    return data


# ============================================================
# Character Creation
# ============================================================

def create_new_character(template_path, new_name, class_id):
    """Create a new character file by copying a template and changing name/class."""
    save_dir = os.path.dirname(template_path)
    template_base = os.path.splitext(os.path.basename(template_path))[0]

    new_d2s = os.path.join(save_dir, f"{new_name}.d2s")
    shutil.copy2(template_path, new_d2s)

    # Copy companion files
    for ext in ['.ctl', '.key', '.ma0', '.map']:
        src = os.path.join(save_dir, template_base + ext)
        dst = os.path.join(save_dir, new_name + ext)
        if os.path.exists(src):
            shutil.copy2(src, dst)

    # Modify the .d2s: set name and class
    data = bytearray(open(new_d2s, 'rb').read())

    # Set class ID
    data[0x18] = class_id

    # Set name at 0x12B
    name_bytes = new_name.encode('ascii') + b'\x00'
    for i in range(0x12B, min(0x12B + 16, len(data))):
        data[i] = 0
    data[0x12B:0x12B + len(name_bytes)] = name_bytes

    # Recalculate checksum
    data[12:16] = b'\x00\x00\x00\x00'
    cs = calc_checksum(data)
    struct.pack_into('<I', data, 12, cs)

    with open(new_d2s, 'wb') as f:
        f.write(data)

    print(f"  Created new character file: {new_name}.d2s (class={class_id})")
    return new_d2s


# ============================================================
# Item Rebuilding
# ============================================================

def rebuild_items(filepath, char_items_bytes, merc_items_bytes):
    """Replace all items in a save file."""
    data = bytearray(open(filepath, 'rb').read())

    # Find first JM (character items)
    jm0 = data.find(b'JM')
    if jm0 < 0:
        raise ValueError("No JM marker found")

    # Find all JM sections to determine structure
    jm_positions = []
    pos = 0
    while True:
        pos = data.find(b'JM', pos)
        if pos < 0: break
        count = struct.unpack_from('<H', data, pos+2)[0]
        jm_positions.append((pos, count))
        pos += 2


    if len(jm_positions) < 2:
        raise ValueError("Expected at least 2 JM sections")

    # Find jf (corpse marker) and kf (iron golem)
    jf_pos = data.find(b'jf', jm_positions[0][0])

    # Everything before first JM
    pre_items = data[:jm0]

    # D2R JM count only includes parent/standalone items, NOT socket fillers.
    # Socket fillers have location=6 (bits 35-37 of the item bitstream).
    def count_parents(items_list):
        count = 0
        for item in items_list:
            loc = (item[4] >> 3) & 0x7  # bits 35-37: location field
            if loc != 6:  # 6 = socketed filler
                count += 1
        return count

    char_count = count_parents(char_items_bytes)
    char_jm = struct.pack('<2sH', b'JM', char_count)
    char_data = char_jm + b''.join(char_items_bytes)
    print(f"  Char items: {len(char_items_bytes)} total, {char_count} parents (JM count)")

    # Build merc items (if any)
    merc_count = count_parents(merc_items_bytes)
    if merc_items_bytes:
        print(f"  Merc items: {len(merc_items_bytes)} total, {merc_count} parents (JM count)")

    # Always construct a clean end section to avoid stale merc items (Rule 6).
    # D2S structure after char items (verified against working Tempest save):
    #   JM[0] (corpse) | jf | [JM[n] merc_items] | kf | \x00 (golem) | \x01\x00 | lf[count]
    lf_count = 1 if merc_items_bytes else 0
    merc_jm = struct.pack('<2sH', b'JM', merc_count)
    merc_section = merc_jm + b''.join(merc_items_bytes)
    end_section = (
        struct.pack('<2sH', b'JM', 0) +      # empty corpse/dead body items
        b'jf' +                              # corpse marker (after corpse JM)
        merc_section +                        # JM[merc] between jf and kf (always present, even if empty)
        b'kf' +                              # iron golem marker
        b'\x00' +                            # no iron golem
        b'\x01\x00' +                        # constant
        struct.pack('<2sH', b'lf', lf_count)  # merc: 0=not hired, 1=hired
    )

    # Rebuild
    new_data = bytearray(
        pre_items +
        char_data +
        end_section
    )

    # Update file size
    struct.pack_into('<I', new_data, 8, len(new_data))

    # Update checksum
    new_data[12:16] = b'\x00\x00\x00\x00'
    cs = calc_checksum(new_data)
    struct.pack_into('<I', new_data, 12, cs)

    return new_data


# ============================================================
# Template Validation
# ============================================================

def validate_template(path: str) -> list:
    """Validate a .d2s template for corruption.

    Returns list of error strings. Empty list = valid.
    """
    errors = []
    try:
        data = open(path, 'rb').read()
    except OSError as e:
        return [f"Cannot read file: {e}"]

    if len(data) < 335:
        errors.append(f"File too small: {len(data)} bytes (min 335)")
        return errors

    # Magic byte check — D2S files start with 0x55 0xAA 0x55 0xAA
    if data[0:4] != b'\x55\xaa\x55\xaa':
        errors.append(f"Bad magic bytes: {data[0:4].hex()} (expected 55aa55aa)")

    # File size field (offset 8, little-endian uint32) should match actual
    stored_size = struct.unpack_from('<I', data, 8)[0]
    if stored_size != len(data):
        errors.append(f"Size mismatch: header says {stored_size}, file is {len(data)}")

    # Required section markers
    required_markers = [b'Woo!', b'WS']
    for marker in required_markers:
        if marker not in data:
            errors.append(f"Missing section marker: {marker}")

    return errors
