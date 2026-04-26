"""Pure lookup functions for D2R game data.

Builds reverse indices at import time for fast name-based lookups.
All functions return JSON strings suitable for MCP tool responses.
"""
import json

from d2r_chargen.data.unique_items import UNIQUE_ITEMS
from d2r_chargen.data.unique_item_stats import UNIQUE_ITEM_STATS
from d2r_chargen.data.set_items import SET_ITEMS
from d2r_chargen.data.item_bases import ITEM_BASES
from d2r_chargen.data.runewords import RUNEWORDS, RUNE_CODE_TO_NAME
from d2r_chargen.data.runeword_stats import RUNEWORD_STATS
from d2r_chargen.data.item_stat_cost import ITEM_STAT_COST, STAT_BY_NAME
from d2r_chargen.data.skills import SKILLS
from d2r_chargen.config import PROPERTY_ALIASES

# --- Reverse indices (built once at import time) ---

_UNIQUE_NAME_TO_ID = {v["name"].lower(): k for k, v in UNIQUE_ITEMS.items()}
_SET_NAME_TO_ID = {v["name"].lower(): k for k, v in SET_ITEMS.items()}
_BASE_NAME_TO_CODE = {v["name"].lower(): k for k, v in ITEM_BASES.items()}
_RW_NAME_TO_ID = {v["name"].lower(): k for k, v in RUNEWORDS.items()}

_SKILL_NAME_TO_ID = {}
for _sid, _sinfo in SKILLS.items():
    _sname = _sinfo["name"].lower()
    if _sname not in _SKILL_NAME_TO_ID:
        _SKILL_NAME_TO_ID[_sname] = _sid
    elif "class" in _sinfo:
        _SKILL_NAME_TO_ID[_sname] = _sid

# Reverse alias map: canonical stat name -> list of YAML aliases
_ALIAS_REVERSE = {}
for _alias, _canonical in PROPERTY_ALIASES.items():
    _ALIAS_REVERSE.setdefault(_canonical, []).append(_alias)


# --- Helpers ---

def _fmt(obj):
    """Format a result dict as readable JSON."""
    return json.dumps(obj, indent=2, default=str)


def _substring_matches(query, name_to_id, limit=10):
    """Find entries where query is a case-insensitive substring of the name."""
    q = query.lower()
    return [(name, id_) for name, id_ in name_to_id.items() if q in name][:limit]


# --- Lookup functions ---

def lookup_unique(query):
    """Look up a unique item by name (substring match) or numeric ID.

    Returns JSON with: uid, name, code, qlvl, base_name, stats.
    """
    # Try numeric ID
    try:
        uid = int(query)
        if uid in UNIQUE_ITEMS:
            item = UNIQUE_ITEMS[uid]
            stats = UNIQUE_ITEM_STATS.get(uid, {}).get("stats", [])
            base = ITEM_BASES.get(item["code"], {})
            return _fmt({
                "uid": uid, "name": item["name"], "code": item["code"],
                "qlvl": item["qlvl"], "base_name": base.get("name", "?"),
                "stats": stats,
            })
        return f"No unique item with ID {uid}"
    except ValueError:
        pass

    # Try exact name match (case-insensitive)
    q = query.lower()
    if q in _UNIQUE_NAME_TO_ID:
        return lookup_unique(str(_UNIQUE_NAME_TO_ID[q]))

    # Substring search
    matches = _substring_matches(query, _UNIQUE_NAME_TO_ID)
    if matches:
        results = []
        for name, uid in matches:
            item = UNIQUE_ITEMS[uid]
            results.append({
                "uid": uid, "name": item["name"],
                "code": item["code"], "qlvl": item["qlvl"],
            })
        if len(results) == 1:
            return lookup_unique(str(results[0]["uid"]))
        return _fmt({"matches": results, "count": len(results)})

    return f"No unique item found matching '{query}'"


def lookup_set_item(query):
    """Look up a set item by name (substring match) or numeric ID.

    Returns JSON with: set_id, name, code, set_name, qlvl.
    """
    try:
        sid = int(query)
        if sid in SET_ITEMS:
            item = SET_ITEMS[sid]
            base = ITEM_BASES.get(item["code"], {})
            return _fmt({
                "set_id": sid, "name": item["name"], "code": item["code"],
                "set_name": item["set"], "qlvl": item["qlvl"],
                "base_name": base.get("name", "?"),
            })
        return f"No set item with ID {sid}"
    except ValueError:
        pass

    q = query.lower()
    if q in _SET_NAME_TO_ID:
        return lookup_set_item(str(_SET_NAME_TO_ID[q]))

    matches = _substring_matches(query, _SET_NAME_TO_ID)
    if matches:
        results = []
        for name, sid in matches:
            item = SET_ITEMS[sid]
            results.append({
                "set_id": sid, "name": item["name"],
                "set_name": item["set"], "code": item["code"],
            })
        if len(results) == 1:
            return lookup_set_item(str(results[0]["set_id"]))
        return _fmt({"matches": results, "count": len(results)})

    return f"No set item found matching '{query}'"


def lookup_item_base(query):
    """Look up a base item by 3-char code or name (substring match).

    Returns JSON with: code, name, width, height, class, max_sockets, etc.
    """
    # Try exact code match
    if query in ITEM_BASES:
        item = ITEM_BASES[query]
        return _fmt({
            "code": query, "name": item["name"],
            "width": item.get("width", 1), "height": item.get("height", 1),
            "item_class": item.get("class", "?"),
            "max_sockets": item.get("max_sockets", 0),
            "req_str": item.get("req_str", 0),
            "req_dex": item.get("req_dex", 0),
            "durability": item.get("durability", 0),
            "tier": item.get("tier", "?"),
            "categories": item.get("categories", []),
        })

    # Try exact name match
    q = query.lower()
    if q in _BASE_NAME_TO_CODE:
        return lookup_item_base(_BASE_NAME_TO_CODE[q])

    # Also try case-insensitive code match
    for code in ITEM_BASES:
        if code.lower() == q:
            return lookup_item_base(code)

    # Substring search
    matches = _substring_matches(query, _BASE_NAME_TO_CODE)
    if matches:
        results = []
        for name, code in matches:
            item = ITEM_BASES[code]
            results.append({
                "code": code, "name": item["name"],
                "item_class": item.get("class", "?"),
            })
        if len(results) == 1:
            return lookup_item_base(results[0]["code"])
        return _fmt({"matches": results, "count": len(results)})

    return f"No base item found matching '{query}'"


def lookup_runeword(query):
    """Look up a runeword by name (substring match) or numeric ID.

    Returns JSON with: rw_id, name, runes, rune_names, sockets, bases, stats.
    """
    try:
        rwid = int(query)
        if rwid in RUNEWORDS:
            rw = RUNEWORDS[rwid]
            stats = RUNEWORD_STATS.get(rwid, {}).get("stats", [])
            rune_names = [RUNE_CODE_TO_NAME.get(r, r) for r in rw["runes"]]
            return _fmt({
                "rw_id": rwid, "name": rw["name"],
                "runes": rw["runes"], "rune_names": rune_names,
                "sockets": rw["sockets"], "bases": rw["bases"],
                "clvl": rw.get("clvl", 0), "stats": stats,
            })
        return f"No runeword with ID {rwid}"
    except ValueError:
        pass

    q = query.lower()
    if q in _RW_NAME_TO_ID:
        return lookup_runeword(str(_RW_NAME_TO_ID[q]))

    matches = _substring_matches(query, _RW_NAME_TO_ID)
    if matches:
        results = []
        for name, rwid in matches:
            rw = RUNEWORDS[rwid]
            results.append({
                "rw_id": rwid, "name": rw["name"],
                "sockets": rw["sockets"],
            })
        if len(results) == 1:
            return lookup_runeword(str(results[0]["rw_id"]))
        return _fmt({"matches": results, "count": len(results)})

    return f"No runeword found matching '{query}'"


def lookup_stat(query):
    """Look up a stat by ID, canonical name, or YAML alias.

    Returns JSON with: stat_id, name, save_bits, save_add, save_param_bits,
    value_shift, aliases.
    """
    stat_id = None

    # Try numeric ID
    try:
        stat_id = int(query)
    except ValueError:
        pass

    if stat_id is None:
        q = query.lower()
        # Try YAML alias
        if q in PROPERTY_ALIASES:
            canonical = PROPERTY_ALIASES[q]
            stat_id = STAT_BY_NAME.get(canonical)
        # Try canonical name
        elif q in STAT_BY_NAME:
            stat_id = STAT_BY_NAME[q]
        else:
            # Substring search across canonical names
            matches = [(name, STAT_BY_NAME[name]) for name in STAT_BY_NAME
                        if q in name][:10]
            if matches:
                results = [{"stat_id": sid, "name": name} for name, sid in matches]
                if len(results) == 1:
                    stat_id = results[0]["stat_id"]
                else:
                    return _fmt({"matches": results, "count": len(results)})
            else:
                return f"No stat found matching '{query}'"

    if stat_id is not None and stat_id in ITEM_STAT_COST:
        info = ITEM_STAT_COST[stat_id]
        canonical = info.get("s", "?")
        aliases = _ALIAS_REVERSE.get(canonical, [])
        return _fmt({
            "stat_id": stat_id, "name": canonical,
            "save_bits": info.get("sB", 0), "save_add": info.get("sA", 0),
            "save_param_bits": info.get("sP", 0), "signed": info.get("sS", 0),
            "value_shift": info.get("vS", 0),
            "csv_bits": info.get("cB", 0),
            "aliases": aliases,
        })

    return f"No stat found matching '{query}'"


def lookup_skill(query):
    """Look up a skill by name (substring match) or numeric ID.

    Returns JSON with: skill_id, name, char_class (if class-specific).
    """
    try:
        sid = int(query)
        if sid in SKILLS:
            skill = SKILLS[sid]
            result = {"skill_id": sid, "name": skill["name"]}
            if "class" in skill:
                result["char_class"] = skill["class"]
            return _fmt(result)
        return f"No skill with ID {sid}"
    except ValueError:
        pass

    q = query.lower()
    if q in _SKILL_NAME_TO_ID:
        return lookup_skill(str(_SKILL_NAME_TO_ID[q]))

    matches = [(name, sid) for name, sid in _SKILL_NAME_TO_ID.items() if q in name][:10]
    if matches:
        results = []
        for name, sid in matches:
            skill = SKILLS[sid]
            entry = {"skill_id": sid, "name": skill["name"]}
            if "class" in skill:
                entry["char_class"] = skill["class"]
            results.append(entry)
        if len(results) == 1:
            return lookup_skill(str(results[0]["skill_id"]))
        return _fmt({"matches": results, "count": len(results)})

    return f"No skill found matching '{query}'"


def search_all(query, limit=20):
    """Search across all item types: uniques, sets, runewords, bases.

    Returns JSON with results tagged by type, capped at limit.
    """
    q = query.lower()
    results = []

    for name, uid in _UNIQUE_NAME_TO_ID.items():
        if q in name:
            results.append({"type": "unique", "id": uid,
                            "name": UNIQUE_ITEMS[uid]["name"]})

    for name, sid in _SET_NAME_TO_ID.items():
        if q in name:
            results.append({"type": "set_item", "id": sid,
                            "name": SET_ITEMS[sid]["name"],
                            "set": SET_ITEMS[sid]["set"]})

    for name, rwid in _RW_NAME_TO_ID.items():
        if q in name:
            results.append({"type": "runeword", "id": rwid,
                            "name": RUNEWORDS[rwid]["name"]})

    for name, code in _BASE_NAME_TO_CODE.items():
        if q in name:
            results.append({"type": "base", "code": code,
                            "name": ITEM_BASES[code]["name"]})

    results = results[:limit]
    return _fmt({"results": results, "count": len(results), "query": query})
