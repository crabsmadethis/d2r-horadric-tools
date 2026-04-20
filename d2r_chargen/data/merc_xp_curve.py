"""Merc XP ↔ level — closed-form formula.

Formula derived from the Phrozen Keep D2 modding forum (thread 37484),
cross-confirmed 2026-04-20 against 17 D2R-era character saves plus the
in-code reference at `d2common.#11084` (v1.10) / `d2common.#11023` (v1.11b):

    merc_xp_threshold[level] = Hireling.Exp/Lvl × (level + 1) × level²

The value is the XP at which the merc "ticks over" to the given level
— i.e. the minimum XP that displays as `level` in the merc UI. A merc
whose XP is below the threshold for N+1 is displayed as level N.

`Exp/Lvl` is an integer from `Hireling.txt` column 13, NOT a percentage.
Typical values:
  100 (Act 1 Rogue Normal), 120 (Hell Rogue / Act 2 Defensive NM),
  130 (Act 2 Hell variants), 150 (Act 5 Barbarian Hell).

**Max level: 98** (Amazon MaxLvl 99 − 1). The game caps all mercs at
char-level minus 1 via a JGE in d2common; writing a higher XP has no
effect on the displayed level.
"""

# Hireling.Exp/Lvl column values, keyed by Hireling.txt Id.
# Populated from build/data/global/excel/Hireling.txt.
_EXP_PER_LVL: dict[int, int] = {
    # Act 1 Rogue Scouts
    0:  100,  # Fire — Normal
    1:  105,  # Ice  — Normal
    2:  110,  # Fire — Nightmare
    3:  115,  # Ice  — Nightmare
    4:  120,  # Fire — Hell
    5:  125,  # Ice  — Hell
    # Act 2 Desert Mercenaries (classic auras: Combat/Offensive/Defensive)
    6:  110,  # Comb — Normal
    7:  110,  # Off  — Normal
    8:  110,  # Def  — Normal
    9:  120,  # Comb — NM
    10: 120,  # Off  — NM
    11: 120,  # Def  — NM
    12: 130,  # Comb — Hell
    13: 130,  # Off  — Hell
    14: 130,  # Def  — Hell
    # Act 2 Desert (expansion aura overrides — Hell tier)
    33: 130,  # Thorns
    34: 130,  # HolyFreeze
    35: 130,  # Might
    # Act 3 Iron Wolves
    15: 100,  # Fire — Normal
    16: 100,  # Cold — Normal
    17: 100,  # Ltng — Normal
    18: 110,  # Fire — NM
    19: 110,  # Cold — NM
    20: 110,  # Ltng — NM
    21: 120,  # Fire — Hell
    22: 120,  # Cold — Hell
    23: 120,  # Ltng — Hell
    # Act 5 Barbarians
    24: 140,  # Normal 2H
    25: 150,  # Alt pool — Normal
    26: 140,  # NM 2H
    27: 150,  # NM alt
    28: 120,  # Hell 2H (observed on Warchief save)
    29: 150,  # Hell alt
    # Mod-added (Reign of the Warlock)
    38: 120,  # Act 5 1H Hell
    41: 130,  # Act 4 Smite Hell
}

# Max merc level: Amazon MaxLvl (99) − 1 per d2common JGE.
MAX_MERC_LEVEL = 98


class MercXPError(ValueError):
    """Raised when merc XP can't be resolved from (hireling_id, level)."""


def xp_for_level(hireling_id: int, level: int) -> int:
    """Return the raw u32 XP value to write at .d2s offset 0xAB so that
    the game displays the merc at exactly `level`.

    Formula: `Exp/Lvl × (level + 1) × level²`

    Raises MercXPError if hireling_id is unknown or level is out of
    range [1, MAX_MERC_LEVEL=98].
    """
    if hireling_id not in _EXP_PER_LVL:
        raise MercXPError(
            f"Unknown Hireling.Id={hireling_id}. Add its Exp/Lvl value "
            f"from Hireling.txt to d2r_chargen/data/merc_xp_curve.py::_EXP_PER_LVL."
        )
    if not (1 <= level <= MAX_MERC_LEVEL):
        raise MercXPError(
            f"level={level} out of range [1, {MAX_MERC_LEVEL}]. "
            f"D2R caps mercs at char_MaxLvl-1 = 98."
        )
    exp_per_lvl = _EXP_PER_LVL[hireling_id]
    return exp_per_lvl * (level + 1) * level * level


def level_for_xp(hireling_id: int, xp: int) -> int:
    """Inverse: return the level the game would display for a merc with
    the given raw XP value. Useful for verifying saves after deployment.

    Level L is displayed when threshold[L] ≤ xp < threshold[L+1].
    """
    if hireling_id not in _EXP_PER_LVL:
        raise MercXPError(f"Unknown Hireling.Id={hireling_id}.")
    if xp < 0:
        raise MercXPError(f"xp={xp} cannot be negative.")
    # Binary search across [1, MAX_MERC_LEVEL]; monotonic by construction.
    lo, hi = 1, MAX_MERC_LEVEL
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if xp_for_level(hireling_id, mid) <= xp:
            lo = mid
        else:
            hi = mid - 1
    # If xp < threshold[1], the merc is lv1 (fresh hire has xp=0 or small).
    if xp < xp_for_level(hireling_id, 1):
        return 1
    return lo
