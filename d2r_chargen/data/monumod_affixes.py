"""Monster unique-modifier affix index → display name.

Source: vanilla/data/global/excel/MonUMod.txt (44 entries plus index 0=none).
Names follow the D2R in-game convention where it differs from the raw txt
field (e.g. raw `strong` → display `Extra Strong`). Affixes used by Bind
Demon (Skills.txt:384 par2..par5: 5/6/27/30) match the in-game tooltip
strings exactly.

To regenerate after a vanilla data update, see
scripts/dev/extract_monumod_affixes.py — but the table is small enough that
hand-editing this file is usually faster than re-running the extractor.
"""
from __future__ import annotations

AFFIXES: dict[int, str] = {
    0: 'none',
    1: 'rndname',
    2: 'hpmultiply',
    3: 'Lightning Enchanted',
    4: 'leveladd',
    5: 'Extra Strong',
    6: 'Extra Fast',
    7: 'Cursed',
    8: 'resist',
    9: 'Fire Enchanted',
    10: 'poisondead',
    11: 'durieldead',
    12: 'bloodraven',
    13: 'rage',
    14: 'spcdamage',
    15: 'partydead',
    16: 'Champion',
    17: 'Lightning',
    18: 'Cold Enchanted',
    19: 'hireable',
    20: 'scarab',
    21: 'killself',
    22: 'questcomplete',
    23: 'poisonhit',
    24: 'thief',
    25: 'manahit',
    26: 'Teleportation',
    27: 'Spectral Hit',
    28: 'Stone Skin',
    29: 'Multiple Shots',
    30: 'Aura Enchanted',
    31: 'goboom',
    32: 'firespike_explode',
    33: 'suicideminion_explode',
    34: 'ai_after_death',
    35: 'shatter_on_death',
    36: 'Ghostly',
    37: 'Fanaticism',
    38: 'possessed',
    39: 'Berserk',
    40: 'worms_on_death',
    41: 'always_run_ai',
    42: 'lightningdeath',
    43: 'thinkonce_on_death',
    44: 'hidedead',
}


def affix_name(idx: int) -> str:
    """Return the display name for an affix index, or '?<idx>' if unknown."""
    return AFFIXES.get(idx, f'?{idx}')
