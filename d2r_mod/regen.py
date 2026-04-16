"""Regenerate d2r_chargen/data/*.py from built D2R .txt tables."""

import os
from d2r_mod.tsv import read_tsv_file


_CLASS_CODES = {
    "ama": "ama", "sor": "sor", "nec": "nec", "pal": "pal",
    "bar": "bar", "dru": "dru", "ass": "ass", "wlk": "wlk", "war": "wlk",
    "Amazon": "ama", "Sorceress": "sor", "Necromancer": "nec",
    "Paladin": "pal", "Barbarian": "bar", "Druid": "dru",
    "Assassin": "ass", "Warlock": "wlk",
}

_ITYPE_TO_CATEGORY = {
    # Weapons — broad
    "weap": "Weapon", "mele": "Melee Weapon", "miss": "Missile Weapon",
    # Weapons — specific
    "swor": "Sword", "axe": "Axe", "mace": "Mace", "hamm": "Hammer",
    "club": "Club", "scep": "Scepter", "pole": "Polearm", "spea": "Spear",
    "staf": "Staff", "bow": "Bow", "xbow": "Crossbow",
    "dagg": "Dagger", "knif": "Dagger", "wand": "Wand",
    "orb": "Orb",
    # Weapons — class-specific
    "h2h": "Hand to Hand", "h2h2": "Hand to Hand",
    "abow": "Amazon Bow", "ajav": "Amazon Javelin", "aspe": "Amazon Spear",
    "taxe": "Throwing Axe", "tkni": "Throwing Knife",
    "jave": "Javelin",
    # Armor — broad
    "armo": "Any Armor",
    # Armor — specific
    "tors": "Body Armor", "body": "Body Armor",
    "helm": "Helm", "helx": "Helm", "phlm": "Barbarian Helm", "circ": "Circlet",
    "shld": "Shield", "shie": "Shield", "ashd": "Auric Shields",
    "glov": "Gloves", "boot": "Boots", "belt": "Belt",
    "head": "Voodoo Heads", "pelt": "Pelt", "grim": "Necromancer Shrunken Head",
    # Accessories
    "ring": "Ring", "amul": "Amulet",
    "jewl": "Jewel",
    "scha": "Small Charm", "mcha": "Medium Charm", "lcha": "Large Charm",
    # Runes & gems
    "rune": "Rune",
    "gem0": "Gem", "gem1": "Gem", "gem2": "Gem", "gem3": "Gem", "gem4": "Gem",
    "gema": "Gem", "gemd": "Gem", "geme": "Gem", "gemr": "Gem",
    "gems": "Gem", "gemt": "Gem", "gemz": "Gem",
    # Consumables
    "hpot": "Healing Potion", "mpot": "Mana Potion", "rpot": "Rejuvenation Potion",
    "tpot": "Throwing Potion", "apot": "Antidote Potion", "spot": "Stamina Potion",
    "wpot": "Thawing Potion",
    # Misc
    "book": "Tome", "scro": "Scroll", "key": "Key", "gold": "Gold",
    "ques": "Quest", "bowq": "Bow Quiver", "xboq": "Crossbow Quiver",
}


def regen_unique_items(rows: list[dict]) -> dict:
    """UniqueItems.txt -> UNIQUE_ITEMS dict.
    Format: {uid: {"name": str, "code": str, "qlvl": int}}
    Uses the *ID field from the data file, NOT row index — the game
    skips disabled rows so enumerate() drifts from actual UIDs.
    """
    result = {}
    for row in rows:
        if row.get("disabled", "") == "1":
            continue
        uid_str = row.get("*ID", "")
        if not uid_str:
            continue  # section header row (e.g. "Expansion", "Elite Uniques")
        uid = int(uid_str)
        name = row.get("index", "") or str(uid)
        result[uid] = {
            "name": name,
            "code": row["code"],
            "qlvl": int(row["lvl"]) if row.get("lvl", "") else 0,
        }
    return result


def regen_set_items(rows: list[dict]) -> dict:
    """SetItems.txt -> SET_ITEMS dict.
    Uses the *ID field from the data file, NOT row index.
    """
    result = {}
    for row in rows:
        uid_str = row.get("*ID", "")
        if not uid_str:
            continue  # section header row
        uid = int(uid_str)
        result[uid] = {
            "name": row["index"],
            "code": row["item"],
            "set": row["set"],
            "qlvl": int(row["lvl"]) if row.get("lvl", "") else 0,
        }
    return result


def regen_skills(rows: list[dict]) -> dict:
    """Skills.txt -> SKILLS dict."""
    result = {}
    for row in rows:
        name = row.get("skill", "")
        if not name:
            continue
        skill_id = int(row["*Id"])
        entry = {"name": name}
        charclass = row.get("charclass", "")
        if charclass and charclass in _CLASS_CODES:
            entry["class"] = _CLASS_CODES[charclass]
        result[skill_id] = entry
    return result


def regen_runewords(rows: list[dict]) -> dict:
    """Runes.txt -> RUNEWORDS dict."""
    result = {}
    for idx, row in enumerate(rows):
        if row.get("complete", "") != "1":
            continue
        name = row.get("*Rune Name", "") or row.get("Rune Name", "")
        runes = []
        for i in range(1, 7):
            r = row.get(f"Rune{i}", "")
            if r:
                runes.append(r)
        bases = []
        for i in range(1, 7):
            itype = row.get(f"itype{i}", "")
            if itype and itype in _ITYPE_TO_CATEGORY:
                bases.append(_ITYPE_TO_CATEGORY[itype])
        clvl_str = row.get("levelreq", "") or row.get("lvl req", "") or "0"
        result[idx] = {
            "name": name,
            "runes": runes,
            "sockets": len(runes),
            "bases": bases,
            "clvl": int(clvl_str) if clvl_str else 0,
        }
    return result


def _compute_tier(code: str, normcode: str, ubercode: str, ultracode: str) -> str:
    if code == normcode or normcode == "":
        return "normal"
    if code == ubercode:
        return "exceptional"
    if code == ultracode:
        return "elite"
    return "normal"


def _compute_flags(item_class: str, has_quantity: bool = False) -> int:
    flags = 0
    if has_quantity:
        flags |= 1
    if item_class in ("armor", "weapon"):
        flags |= 2
    if item_class == "armor":
        flags |= 4
    return flags


def regen_item_bases(rows: list[dict], item_class: str,
                     type_categories: dict[str, list[str]] | None = None) -> dict:
    """Weapons.txt / Armor.txt / Misc.txt -> ITEM_BASES entries."""
    result = {}
    for row in rows:
        code = row.get("code", "")
        name = row.get("name", "") or row.get("*name", "")
        if not code or not name:
            continue

        width = int(row.get("invwidth", "1") or "1")
        height = int(row.get("invheight", "1") or "1")
        max_sockets = int(row.get("gemsockets", "0") or "0")

        entry = {
            "name": name,
            "width": width,
            "height": height,
            "class": item_class,
            "flags": _compute_flags(item_class, has_quantity=bool(row.get("stackable", ""))),
            "max_sockets": max_sockets,
        }

        levelreq = int(row.get("levelreq", "0") or "0")
        if levelreq:
            entry["levelreq"] = levelreq

        if item_class == "armor":
            entry["min_ac"] = int(row.get("minac", "0") or "0")
            entry["max_ac"] = int(row.get("maxac", "0") or "0")
            entry["durability"] = int(row.get("durability", "0") or "0")
            entry["req_str"] = int(row.get("reqstr", "0") or "0")
            entry["req_dex"] = int(row.get("reqdex", "0") or "0")

        if item_class == "weapon":
            entry["min_dmg"] = int(row.get("mindam", "0") or "0")
            entry["max_dmg"] = int(row.get("maxdam", "0") or "0")
            entry["durability"] = int(row.get("durability", "0") or "0")
            entry["req_str"] = int(row.get("reqstr", "0") or "0")
            entry["req_dex"] = int(row.get("reqdex", "0") or "0")

        if item_class in ("armor", "weapon"):
            entry["tier"] = _compute_tier(
                code, row.get("normcode", ""),
                row.get("ubercode", ""), row.get("ultracode", ""),
            )

        categories = []
        for tc in ("type", "type2"):
            t = row.get(tc, "")
            if t and type_categories and t in type_categories:
                categories.extend(type_categories[t])
            elif t and t in _ITYPE_TO_CATEGORY:
                categories.append(_ITYPE_TO_CATEGORY[t])
        if categories:
            entry["categories"] = list(dict.fromkeys(categories))

        result[code] = entry
    return result


def _write_py_dict(path: str, var_name: str, data: dict, docstring: str,
                   comment: str = "", suffix: str = "") -> None:
    """Write a Python dict to a .py file matching chargen data format."""
    lines = [f'"""{docstring}"""']
    if comment:
        lines.append(comment)
    lines.append("")
    lines.append(f"{var_name} = {{")
    for key in sorted(data.keys()):
        lines.append(f"    {key!r}: {data[key]!r},")
    lines.append("}")
    if suffix:
        lines.append("")
        lines.append(suffix)
    lines.append("")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _write_runewords_py(path: str, runewords: dict) -> None:
    rune_map = (
        "RUNE_NAME_TO_CODE = {\n"
        "    'El': 'r01', 'Eld': 'r02', 'Tir': 'r03', 'Nef': 'r04', 'Eth': 'r05',\n"
        "    'Ith': 'r06', 'Tal': 'r07', 'Ral': 'r08', 'Ort': 'r09', 'Thul': 'r10',\n"
        "    'Amn': 'r11', 'Sol': 'r12', 'Shael': 'r13', 'Dol': 'r14', 'Hel': 'r15',\n"
        "    'Io': 'r16', 'Lum': 'r17', 'Ko': 'r18', 'Fal': 'r19', 'Lem': 'r20',\n"
        "    'Pul': 'r21', 'Um': 'r22', 'Mal': 'r23', 'Ist': 'r24', 'Gul': 'r25',\n"
        "    'Vex': 'r26', 'Ohm': 'r27', 'Lo': 'r28', 'Sur': 'r29', 'Ber': 'r30',\n"
        "    'Jah': 'r31', 'Cham': 'r32', 'Zod': 'r33',\n"
        "}\n\n"
        "RUNE_CODE_TO_NAME = {v: k for k, v in RUNE_NAME_TO_CODE.items()}\n"
    )
    base_cats = (
        "BASE_CATEGORIES = {\n"
        "    'weapon': 'Weapon', 'melee_weapon': 'Melee Weapon',\n"
        "    'missile_weapon': 'Missile Weapon', 'sword': 'Sword', 'axe': 'Axe',\n"
        "    'mace': 'Mace', 'hammer': 'Hammer', 'club': 'Club', 'scepter': 'Scepter',\n"
        "    'polearm': 'Polearm', 'spear': 'Spear', 'staff': 'Staff',\n"
        "    'bow': 'Bow', 'crossbow': 'Crossbow', 'dagger': 'Dagger', 'wand': 'Wand',\n"
        "    'katar': 'Hand to Hand', 'body_armor': 'Body Armor',\n"
        "    'helm': 'Helm', 'shield': 'Shield', 'paladin_shield': 'Auric Shields',\n"
        "    'orb': 'Orb', 'pelt': 'Pelt', 'voodoo_heads': 'Voodoo Heads',\n"
        "}\n"
    )
    lines = [
        '"""Diablo II Resurrected - Runewords Database"""',
        "# Auto-generated by d2r_mod.regen from Runes.txt",
        "",
        rune_map,
        "",
        base_cats,
        "",
    ]
    lines.append("RUNEWORDS = {")
    for key in sorted(runewords.keys()):
        lines.append(f"    {key!r}: {runewords[key]!r},")
    lines.append("}")
    lines.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _write_set_items_py(path: str, set_items: dict) -> None:
    suffix = (
        "# All sets with their item indices\n"
        "SETS = {}\n"
        "for sid, sdata in SET_ITEMS.items():\n"
        "    sn = sdata['set']\n"
        "    if sn not in SETS:\n"
        "        SETS[sn] = []\n"
        "    SETS[sn].append(sid)"
    )
    _write_py_dict(
        path, "SET_ITEMS", set_items,
        "Diablo II Resurrected - Set Items Database",
        "# Auto-generated by d2r_mod.regen from SetItems.txt",
        suffix=suffix,
    )


_PROP_TO_STAT = {
    "ac%": "item_armor_percent", "ac": "armorclass",
    "str": "strength", "dex": "dexterity", "vit": "vitality", "enr": "energy",
    "hp": "maxhp", "mana": "maxmana",
    "fcr": "item_fastercastrate", "fhr": "item_fastergethitrate",
    "frw": "item_fastermovevelocity", "ias": "item_fasterattackrate",
    "res-fire": "fireresist", "res-ltng": "lightresist",
    "res-cold": "coldresist", "res-pois": "poisonresist",
    # res-all handled specially in _PROP_MULTI_STAT
    "allskills": "item_allskills",
    "skilltab": "item_addskill_tab",
    "dmg%": "item_maxdamage_percent",
    "att%": "item_tohit_percent",
    "manasteal": "manadrainmindam", "lifesteal": "lifedrainmindam",
    "deadly": "item_deadlystrike", "crush": "item_crushingblow",
    "openwounds": "item_openwounds",
    "swing1": "item_fasterattackrate",
    "dmg-fire": "firemindam", "dmg-ltng": "lightmindam",
    "dmg-cold": "coldmindam", "dmg-pois": "poisonmindam",
    "regen": "hpregen", "regen-mana": "manarecoverybonus",
    "red-dmg%": "damageresist",
    "nofreeze": "item_cannotbefrozen",
    "half-freeze": "item_halffreezeduration",
    "skillaura": "item_aura",
    "skill": "item_nonclassskill",
    "charged": "item_charged_skill",
    "oskill": "item_nonclassskill",
    "gethit-skill": "item_skillongethit",
    "hit-skill": "item_skillonhit",
    "att-skill": "item_skillonattack",
    "kill-skill": "item_skillonkill",
    "death-skill": "item_skillondeath",
    "levelup-skill": "item_skillonlevelup",
    "aura": "item_aura",
    "dmg-ac": "armorclass",
    "red-dmg": "item_normaldamage_reduction",
    "red-mag": "item_magicdamage_reduction",
    "balance1": "item_fastergethitrate",
    "move1": "item_fastermovevelocity",
    "howl": "item_howl",
    "stupidity": "item_stupidity",
    "knock": "item_knockback",
    "dmg-demon": "item_demondamage_percent",
    "dmg-undead": "item_undeaddamage_percent",
    "att-demon": "item_demon_tohit",
    "att-undead": "item_undead_tohit",
    "abs-fire%": "item_absorbfire_percent",
    "abs-ltng%": "item_absorblight_percent",
    "abs-cold%": "item_absorbcold_percent",
    "ease": "item_req_percent",
    "indestruct": "item_indesctructible",
    "light": "item_lightradius",
    "block1": "toblock",
    "magicarrow": "item_magicarrow",
    "pierce": "item_pierce",
    "bloody": "item_openwounds",
    "sock": "item_numsockets",
    "extra-fire": "passive_fire_mastery",
    "extra-ltng": "passive_ltng_mastery",
    "extra-cold": "passive_cold_mastery",
    "extra-pois": "passive_pois_mastery",
    "addxp": "item_addexperience",
    # Magic find and gold bonus
    "mag%": "item_magicbonus",
    # Ignore target defense
    "ignore-ac": "item_ignoretargetac",
    # Absorb (flat)
    "abs-mag": "item_absorbmagic",
    # AC vs missile
    "ac-miss": "armorclass_vs_missile",
    # Repair / replenish
    "rep-quant": "item_replenish_quantity",
    # Kill on heal
    "heal-kill": "item_healafterkill",
    # Class-specific skills (param = class ID comes from the prop code itself)
    "ama": "item_addclassskills",
    "sor": "item_addclassskills",
    "nec": "item_addclassskills",
    "pal": "item_addclassskills",
    "bar": "item_addclassskills",
    "dru": "item_addclassskills",
    "ass": "item_addclassskills",
    "war": "item_addclassskills",
    # Faster cast rate variants
    "cast1": "item_fastercastrate",
    "cast2": "item_fastercastrate",
    "cast3": "item_fastercastrate",
    # Per-level and percent stats
    "mana/lvl": "item_mana_perlevel",
    "mana%": "item_maxmana_percent",
    "hp%": "item_maxhp_percent",
    "hp/lvl": "item_hp_perlevel",
    # Elemental damage ranges
    "ltng-min": "lightmindam",
    "ltng-max": "lightmaxdam",
    "cold-min": "coldmindam",
    "cold-max": "coldmaxdam",
    "cold-len": "coldlength",
    "fire-min": "firemindam",
    "fire-max": "firemaxdam",
    "pois-min": "poisonmindam",
    "pois-max": "poisonmaxdam",
    "pois-len": "poisonlength",
    # Attack and speed variants
    "att": "tohit",
    "att/lvl": "item_tohit_perlevel",
    "att%/lvl": "item_tohitpercent_perlevel",
    "swing2": "item_fasterattackrate",
    "swing3": "item_fasterattackrate",
    "move2": "item_fastermovevelocity",
    "move3": "item_fastermovevelocity",
    "balance2": "item_fastergethitrate",
    "balance3": "item_fastergethitrate",
    # Per-level stats
    "ac/lvl": "item_armor_perlevel",
    "str/lvl": "item_strength_perlevel",
    "dex/lvl": "item_dexterity_perlevel",
    "vit/lvl": "item_vitality_perlevel",
    "dmg/lvl": "item_maxdamage_perlevel",
    # Resistances and absorb
    "res-mag": "magicresist",
    "abs-fire": "item_absorbfire",
    "abs-ltng": "item_absorblight",
    "abs-cold": "item_absorbcold",
    # Penetration (pierce)
    "pierce-ltng": "passive_ltng_pierce",
    "pierce-fire": "passive_fire_pierce",
    "pierce-cold": "passive_cold_pierce",
    "pierce-pois": "passive_pois_pierce",
    "pierce-mag": "passive_mag_pierce",
    # Misc
    "gold%": "item_goldbonus",
    "thorns": "item_attackertakesdamage",
    "slow": "item_slow",
    "freeze": "item_freeze",
    "regen-stam": "staminarecoverybonus",
    "dur": "maxdurability",
    "rep-dur": "item_replenish_durability",
    # Absorb flat (remaining)
    "abs-mag": "item_absorbmagic",
    # AC variants
    "ac-miss": "armorclass_vs_missile",
    "ac-hth": "armorclass_vs_hth",
    # Repair / replenish
    "rep-quant": "item_replenish_quantity",
    # Kill / heal effects
    "heal-kill": "item_healafterkill",
    "mana-kill": "item_manaafterkill",
    "demon-heal": "item_healafterdemonkill",
    # Elemental damage (named variants)
    "dmg": "item_normaldamage",
    "dmg-norm": "mindamage",
    "dmg-mag": "magicmindam",
    "dmg-elem": "firemindam",
    "dmg%/lvl": "item_maxdamage_percent_perlevel",
    "dmg-dem/lvl": "item_damage_demon_perlevel",
    "dmg-und/lvl": "item_damage_undead_perlevel",
    # Attack per-level
    "att-dem/lvl": "item_tohit_demon_perlevel",
    "att-und/lvl": "item_tohit_undead_perlevel",
    # Block
    "block": "toblock",
    "block2": "item_fasterblockrate",
    "block3": "item_fasterblockrate",
    # Per-level resist/stam/etc
    "res-ltng/lvl": "item_resist_ltng_perlevel",
    "regen-stam/lvl": "item_regenstamina_perlevel",
    "stam": "maxstamina",
    "stam/lvl": "item_stamina_perlevel",
    "stamdrain": "item_staminadrainpct",
    "thorns/lvl": "item_thorns_perlevel",
    "deadly/lvl": "item_deadlystrike_perlevel",
    "gold%/lvl": "item_find_gold_perlevel",
    "mag%/lvl": "item_find_magic_perlevel",
    "abs-cold/lvl": "item_absorb_cold_perlevel",
    "abs-fire/lvl": "item_absorb_fire_perlevel",
    # Max resistance
    "res-fire-max": "maxfireresist",
    "res-ltng-max": "maxlightresist",
    "res-cold-max": "maxcoldresist",
    "res-pois-max": "maxpoisonresist",
    "res-all-max": "maxfireresist",
    "res-pois-len": "item_poisonlengthresist",
    # Immunity pierce
    "pierce-immunity-cold": "item_pierce_cold_immunity",
    "pierce-immunity-damage": "item_pierce_damage_immunity",
    "pierce-immunity-fire": "item_pierce_fire_immunity",
    "pierce-immunity-light": "item_pierce_light_immunity",
    "pierce-immunity-magic": "item_pierce_magic_immunity",
    "pierce-immunity-poison": "item_pierce_poison_immunity",
    # Misc item effects
    "noheal": "item_preventheal",
    "rip": "item_restinpeace",
    "cheap": "item_reducedprices",
    "stack": "item_extra_stack",
    "charge-noconsume": "item_charge_noconsume",
    "explosivearrow": "item_explosivearrow",
    "fireskill": "item_elemskill",
    "extra-mag": "passive_mag_mastery",
    "reduce-ac": "item_fractionaltargetac",
    "dmg-to-mana": "item_damagetomana",
    "reanimate": "item_reanimate",
    "light-thorns": "item_attackertakeslightdamage",
}

_PROP_MULTI_STAT = {
    "res-all": ["fireresist", "lightresist", "coldresist", "poisonresist"],
    "all-stats": ["strength", "dexterity", "vitality", "energy"],
}

_RUNE_CODE_TO_NAME = {
    'r01': 'El', 'r02': 'Eld', 'r03': 'Tir', 'r04': 'Nef', 'r05': 'Eth',
    'r06': 'Ith', 'r07': 'Tal', 'r08': 'Ral', 'r09': 'Ort', 'r10': 'Thul',
    'r11': 'Amn', 'r12': 'Sol', 'r13': 'Shael', 'r14': 'Dol', 'r15': 'Hel',
    'r16': 'Io', 'r17': 'Lum', 'r18': 'Ko', 'r19': 'Fal', 'r20': 'Lem',
    'r21': 'Pul', 'r22': 'Um', 'r23': 'Mal', 'r24': 'Ist', 'r25': 'Gul',
    'r26': 'Vex', 'r27': 'Ohm', 'r28': 'Lo', 'r29': 'Sur', 'r30': 'Ber',
    'r31': 'Jah', 'r32': 'Cham', 'r33': 'Zod',
}


def _parse_props(row: dict, prefix: str, max_props: int) -> list[dict]:
    """Parse propN/parN/minN/maxN or T1CodeN/T1ParamN/T1MinN/T1MaxN columns into stat entries."""
    stats = []
    is_t1 = prefix.startswith("T1")

    for i in range(1, max_props + 1):
        if is_t1:
            prop_code = row.get(f"T1Code{i}", "")
            param = row.get(f"T1Param{i}", "")
            min_val = row.get(f"T1Min{i}", "")
            max_val = row.get(f"T1Max{i}", "")
        else:
            prop_code = row.get(f"{prefix}{i}", "")
            param = row.get(f"par{i}", "")
            min_val = row.get(f"min{i}", "")
            max_val = row.get(f"max{i}", "")

        if not prop_code:
            continue

        # Multi-stat properties (e.g., res-all → 4 resist stats)
        if prop_code in _PROP_MULTI_STAT:
            for stat_name in _PROP_MULTI_STAT[prop_code]:
                stats.append({
                    "stat": stat_name,
                    "min": int(min_val) if min_val else 0,
                    "max": int(max_val) if max_val else 0,
                })
            continue

        # Class-specific skill props: class ID is implicit in prop code
        _CLASS_SKILL_CODES = {
            "ama": 0, "sor": 1, "nec": 2, "pal": 3,
            "bar": 4, "dru": 5, "ass": 6, "war": 7,
        }
        if prop_code in _CLASS_SKILL_CODES:
            stats.append({
                "stat": "item_addclassskills",
                "min": int(min_val) if min_val else 0,
                "max": int(max_val) if max_val else 0,
                "param_type": "class",
                "param": _CLASS_SKILL_CODES[prop_code],
            })
            continue

        stat_name = _PROP_TO_STAT.get(prop_code, prop_code)
        entry = {
            "stat": stat_name,
            "min": int(min_val) if min_val else 0,
            "max": int(max_val) if max_val else 0,
        }

        if param:
            if prop_code in ("skilltab",):
                entry["param_type"] = "skill_tab"
                entry["param"] = int(param) if param.isdigit() else param
            elif prop_code in ("skill", "oskill", "aura", "skillaura"):
                entry["param_type"] = "skill"
                entry["param"] = param
            elif prop_code in ("charged",):
                entry["param_type"] = "charges"
                entry["param"] = param
            elif prop_code in ("hit-skill", "gethit-skill", "att-skill",
                               "kill-skill", "death-skill", "levelup-skill"):
                entry["param_type"] = "ctc"
                entry["param"] = param
            else:
                entry["param"] = param

        stats.append(entry)
    return stats


def regen_unique_item_stats(rows: list[dict]) -> dict:
    """UniqueItems.txt -> UNIQUE_ITEM_STATS dict.
    Format: {uid: {"name": str, "base": str, "stats": [stat_entries]}}
    Uses the *ID field from the data file, NOT row index.
    """
    result = {}
    for row in rows:
        if row.get("disabled", "") == "1":
            continue
        uid_str = row.get("*ID", "")
        if not uid_str:
            continue  # section header row
        uid = int(uid_str)
        stats = _parse_props(row, "prop", 12)
        if not stats:
            continue
        name = row.get("index", "") or str(uid)
        result[uid] = {
            "name": name,
            "base": row.get("code", ""),
            "stats": stats,
        }
    return result


def regen_runeword_stats(rows: list[dict]) -> dict:
    """Runes.txt -> RUNEWORD_STATS dict.
    Format: {rw_id: {"name": str, "runes": [str], "stats": [stat_entries]}}
    """
    result = {}
    for idx, row in enumerate(rows):
        if row.get("complete", "") != "1":
            continue
        stats = _parse_props(row, "T1Code", 7)
        if not stats:
            continue
        name = row.get("*Rune Name", "") or row.get("Rune Name", "")
        runes = []
        for i in range(1, 7):
            r = row.get(f"Rune{i}", "")
            if r:
                runes.append(r)
        rune_names = [_RUNE_CODE_TO_NAME.get(rc, rc) for rc in runes]
        result[idx] = {
            "name": name,
            "runes": rune_names,
            "stats": stats,
        }
    return result


def regen_item_dimensions(rows: list[dict]) -> dict:
    """Weapons/Armor/Misc.txt rows -> {code: (width, height)} dict."""
    result = {}
    for row in rows:
        code = row.get("code", "")
        if not code:
            continue
        w = int(row.get("invwidth", "1") or "1")
        h = int(row.get("invheight", "1") or "1")
        result[code] = (w, h)
    return result


def regen_item_stat_cost(rows: list[dict]) -> tuple[dict, dict]:
    """ItemStatCost.txt rows -> (ITEM_STAT_COST, STAT_BY_NAME) dicts."""
    isc = {}
    sbn = {}
    for row in rows:
        stat_id = row.get("*ID", "")
        stat_name = row.get("Stat", "")
        if not stat_id or not stat_name:
            continue
        stat_id = int(stat_id)

        entry = {"s": stat_name}

        for csv_col, key, as_type in [
            ("Save Bits", "sB", int),
            ("Save Add", "sA", int),
            ("Save Param Bits", "sP", int),
            ("Signed", "sS", int),
            ("CSvBits", "cB", int),
            ("CSvSigned", "cS", int),
            ("ValShift", "vS", int),
            ("Encode", "e", int),
            ("op", "o", int),
            ("op param", "oP", int),
            ("descpriority", "so", int),
            ("descfunc", "dF", int),
            ("descval", "dV", int),
            ("dgrp", "dg", int),
            ("dgrpfunc", "dgF", int),
            ("dgrpval", "dgV", int),
        ]:
            val = row.get(csv_col, "")
            if val:
                entry[key] = as_type(val)

        for csv_col, key in [
            ("op base", "oB"),
            ("descstrpos", "dP"),
            ("descstrneg", "dN"),
            ("descstr2", "dR"),
            ("dgrpstrpos", "dgP"),
            ("dgrpstrneg", "dgN"),
        ]:
            val = row.get(csv_col, "")
            if val:
                entry[key] = val

        op_stats = []
        for i in range(1, 4):
            os_val = row.get(f"op stat{i}", "")
            if os_val:
                op_stats.append(os_val)
        if op_stats:
            entry["os"] = op_stats

        isc[stat_id] = entry
        sbn[stat_name] = stat_id

    # Inject np (group count) values for grouped stats.
    # The D2S binary format encodes these as one stat ID header followed by
    # np consecutive values.  This is hardcoded format knowledge — the
    # vanilla ItemStatCost.txt doesn't export an np column.
    _NP_VALUES = {17: 2, 48: 2, 50: 2, 52: 2, 54: 3, 57: 3}
    for sid, np_val in _NP_VALUES.items():
        if sid in isc:
            isc[sid]['np'] = np_val

    return isc, sbn


def _write_item_dimensions_py(path: str, dims: dict) -> None:
    """Write ITEM_DIMENSIONS dict to a .py file."""
    with open(path, "w", encoding="utf-8") as f:
        f.write('"""Diablo II Resurrected - Item Inventory Dimensions"""\n')
        f.write("# Auto-generated by d2r_mod.regen from Weapons.txt + Armor.txt + Misc.txt\n")
        f.write("# Critical for inventory collision detection when placing items\n\n")
        f.write("# Format: code -> (width, height)\n")
        f.write("ITEM_DIMENSIONS = {\n")
        for code in sorted(dims):
            w, h = dims[code]
            f.write(f"    {code!r}: ({w}, {h}),\n")
        f.write("}\n")


def _write_item_stat_cost_py(path: str, isc: dict, sbn: dict) -> None:
    """Write ITEM_STAT_COST and STAT_BY_NAME dicts to a .py file."""
    with open(path, "w", encoding="utf-8") as f:
        f.write('"""\n')
        f.write("Diablo II Resurrected - ItemStatCost data (magical_properties)\n")
        f.write("Auto-generated by d2r_mod.regen from ItemStatCost.txt\n\n")
        f.write("Each entry maps a stat ID (int) to a dict with fields:\n")
        f.write("  s   = stat name (internal)\n")
        f.write("  sB  = Save Bits - how many bits the value occupies in item save data\n")
        f.write("  sA  = Save Add - offset added before saving (subtract when reading)\n")
        f.write("  sP  = Save Param Bits - param bits for skills/class/etc\n")
        f.write("  sS  = Signed - 1 if value is signed\n")
        f.write("  cB  = CSV Bits - bits used in character stat section (attributes)\n")
        f.write("  cS  = CSV Signed\n")
        f.write("  vS  = Value Shift - right shift applied (e.g., 8 for HP/mana fixed-point)\n")
        f.write("  e   = Encoding type\n")
        f.write("  o   = Operator (for derived stats)\n")
        f.write("  oP  = Op Param\n")
        f.write("  oB  = Op Base stat name\n")
        f.write("  os  = Op Stats (list of stats affected by operator)\n")
        f.write("  so  = Sort Order for display (descpriority)\n")
        f.write("  dF  = Description Function\n")
        f.write("  dV  = Description Value\n")
        f.write("  dP  = Description Positive format string\n")
        f.write("  dN  = Description Negative format string\n")
        f.write("  dR  = Description Range format string (descstr2)\n")
        f.write("  dg  = Description Group\n")
        f.write("  dgF = Description Group Function\n")
        f.write("  dgV = Description Group Value\n")
        f.write("  dgP = Description Group Positive format string\n")
        f.write("  dgN = Description Group Negative format string\n")
        f.write('"""\n\n\n')
        f.write("# Maps stat ID -> properties dict.\n")
        f.write("ITEM_STAT_COST = {\n")
        for stat_id in sorted(isc):
            f.write(f"    {stat_id}: {isc[stat_id]!r},\n")
        f.write("}\n\n")
        f.write("STAT_BY_NAME = {\n")
        for name in sorted(sbn):
            f.write(f"    {name!r}: {sbn[name]},\n")
        f.write("}\n")


def _find_project_root() -> str:
    d = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    while d != os.path.dirname(d):
        if os.path.exists(os.path.join(d, "pyproject.toml")):
            return d
        d = os.path.dirname(d)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def regen_all(build_dir: str, chargen_data_dir: str | None = None) -> None:
    """Regenerate all chargen data files from built .txt tables."""
    if chargen_data_dir is None:
        project_root = _find_project_root()
        chargen_data_dir = os.path.join(project_root, "d2r_chargen", "data")

    excel_dir = os.path.join(build_dir, "data", "global", "excel")

    # UniqueItems.txt — read once, regen both unique_items and unique_item_stats
    ui_path = os.path.join(excel_dir, "UniqueItems.txt")
    if os.path.exists(ui_path):
        ui_rows = read_tsv_file(ui_path)
        _write_py_dict(
            os.path.join(chargen_data_dir, "unique_items.py"),
            "UNIQUE_ITEMS", regen_unique_items(ui_rows),
            "Diablo II Resurrected - Unique Items Database",
            "# Auto-generated by d2r_mod.regen from UniqueItems.txt",
        )
        stats_data = regen_unique_item_stats(ui_rows)
        if stats_data:
            _write_py_dict(
                os.path.join(chargen_data_dir, "unique_item_stats.py"),
                "UNIQUE_ITEM_STATS", stats_data,
                "Diablo II Resurrected - Unique Item Stats Database",
                "# Auto-generated by d2r_mod.regen from UniqueItems.txt",
            )

    si_path = os.path.join(excel_dir, "SetItems.txt")
    if os.path.exists(si_path):
        rows = read_tsv_file(si_path)
        _write_set_items_py(os.path.join(chargen_data_dir, "set_items.py"), regen_set_items(rows))

    sk_path = os.path.join(excel_dir, "Skills.txt")
    if os.path.exists(sk_path):
        rows = read_tsv_file(sk_path)
        _write_py_dict(
            os.path.join(chargen_data_dir, "skills.py"),
            "SKILLS", regen_skills(rows),
            "Diablo II Resurrected - Skills Database",
            "# Auto-generated by d2r_mod.regen from Skills.txt",
        )

    # Runes.txt — read once, regen both runewords and runeword_stats
    rw_path = os.path.join(excel_dir, "Runes.txt")
    if os.path.exists(rw_path):
        rw_rows = read_tsv_file(rw_path)
        _write_runewords_py(os.path.join(chargen_data_dir, "runewords.py"), regen_runewords(rw_rows))
        stats_data = regen_runeword_stats(rw_rows)
        if stats_data:
            _write_py_dict(
                os.path.join(chargen_data_dir, "runeword_stats.py"),
                "RUNEWORD_STATS", stats_data,
                "Diablo II Resurrected - Runeword Stats Database",
                "# Auto-generated by d2r_mod.regen from Runes.txt",
            )

    bases = {}
    all_equip_rows = []
    for fname, cls in [("Weapons.txt", "weapon"), ("Armor.txt", "armor"), ("Misc.txt", "misc")]:
        fpath = os.path.join(excel_dir, fname)
        if os.path.exists(fpath):
            rows = read_tsv_file(fpath)
            bases.update(regen_item_bases(rows, item_class=cls))
            all_equip_rows.extend(rows)
    if bases:
        _write_py_dict(
            os.path.join(chargen_data_dir, "item_bases.py"),
            "ITEM_BASES", bases,
            "Diablo II Resurrected - Item Base Types Database",
            "# Auto-generated by d2r_mod.regen from Weapons.txt + Armor.txt + Misc.txt",
        )

    # Item dimensions from same Weapons/Armor/Misc tables
    if all_equip_rows:
        dims = regen_item_dimensions(all_equip_rows)
        if dims:
            _write_item_dimensions_py(
                os.path.join(chargen_data_dir, "item_dimensions.py"), dims
            )

    # ItemStatCost.txt
    isc_path = os.path.join(excel_dir, "ItemStatCost.txt")
    if os.path.exists(isc_path):
        isc_rows = read_tsv_file(isc_path)
        isc_data, sbn_data = regen_item_stat_cost(isc_rows)
        if isc_data:
            _write_item_stat_cost_py(
                os.path.join(chargen_data_dir, "item_stat_cost.py"), isc_data, sbn_data
            )

    print(f"Regenerated chargen data in {chargen_data_dir}")
