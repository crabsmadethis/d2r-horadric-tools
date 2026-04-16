"""Magic prefix/suffix data for auto-naming magic items.

Parses MagicPrefix.txt and MagicSuffix.txt at import time.
Provides auto_select_affixes() to pick appropriate prefix/suffix IDs
based on item type and encoded properties.
"""
import csv
import os

# --- itype category mapping ---
# Maps item_bases.py category names to the itype codes used in affix files.
# Order matters: first match wins for affix lookup.
_CATEGORY_TO_ITYPES = {
    # Charms
    'Small Charm': ['scha'],
    'Medium Charm': ['mcha'],
    'Large Charm': ['lcha'],
    # Jewelry
    'Ring': ['ring'],
    'Amulet': ['amul'],
    'Jewel': ['jewl'],
    # Armor types
    'Circlet': ['circ', 'helm', 'armo'],
    'Helm': ['helm', 'armo'],
    'Barbarian Helm': ['phlm', 'helm', 'armo'],
    'Druid Helm': ['pelt', 'helm', 'armo'],
    'Voodoo Heads': ['head', 'shld', 'armo'],
    'Necromancer Shield': ['head', 'shld', 'armo'],
    'Body Armor': ['tors', 'armo'],
    'Armor': ['tors', 'armo'],
    'Boots': ['boot', 'armo'],
    'Gloves': ['glov', 'armo'],
    'Belt': ['belt', 'armo'],
    'Any Shield': ['shld', 'armo'],
    'Shield': ['shld', 'armo'],
    'Auric Shields': ['phlm', 'shld', 'armo'],
    # Weapons
    'Sword': ['swor', 'mele', 'weap'],
    'Axe': ['mele', 'weap'],
    'Mace': ['mace', 'blun', 'mele', 'weap'],
    'Hammer': ['hamm', 'blun', 'mele', 'weap'],
    'Club': ['club', 'blun', 'mele', 'weap'],
    'Scepter': ['scep', 'rod', 'blun', 'mele', 'weap'],
    'Polearm': ['pole', 'spea', 'mele', 'weap'],
    'Spear': ['spea', 'mele', 'weap'],
    'Staff': ['staf', 'mele', 'weap'],
    'Bow': ['miss', 'weap'],
    'Crossbow': ['miss', 'weap'],
    'Dagger': ['knif', 'mele', 'weap'],
    'Knife': ['knif', 'mele', 'weap'],
    'Wand': ['wand', 'rod', 'mele', 'weap'],
    'Hand to Hand': ['h2h', 'mele', 'weap'],
    'Orb': ['mele', 'weap'],
    'Throwing Knife': ['tkni', 'thro', 'mele', 'weap'],
    'Throwing Axe': ['thro', 'mele', 'weap'],
}

# --- Stat name → affix mod code mapping ---
# Maps canonical STAT_BY_NAME keys to the mod codes used in affix files.
_STAT_TO_MOD = {
    'maxhp': 'hp',
    'strength': 'str',
    'dexterity': 'dex',
    'maxmana': 'mana',
    'maxstamina': 'stam',
    'armorclass': 'ac',
    'item_armor_percent': 'ac%',
    'tohit': 'att',
    'item_tohit_percent': 'att',
    'fireresist': 'res-fire',
    'coldresist': 'res-cold',
    'lightresist': 'res-ltng',
    'poisonresist': 'res-pois',
    'item_addskill_tab': 'skilltab',
    'item_magicbonus': 'mag%',
    'item_goldbonus': 'gold%',
    'item_fastermovevelocity': ['move1', 'move2', 'move3'],
    'item_fastergethitrate': ['balance1', 'balance2', 'balance3'],
    'item_fastercastrate': 'fcr',
    'item_fasterattackrate': 'ias',
    'item_fasterblockrate': 'fbr',
    'mindamage': 'dmg-min',
    'maxdamage': 'dmg-max',
    'firemindam': 'fire-min',
    'firemaxdam': 'fire-max',
    'coldmindam': 'cold-min',
    'coldmaxdam': 'cold-max',
    'coldlength': 'cold-len',
    'lightmindam': 'ltng-min',
    'lightmaxdam': 'ltng-max',
    'poisonmindam': 'dmg-pois',
    'normal_damage_reduction': 'red-dmg',
    'lifedrainmindam': 'lifesteal',
    'manadrainmindam': 'manasteal',
    'passive_fire_pierce': 'pierce-fire',
    'passive_cold_pierce': 'pierce-cold',
    'passive_ltng_pierce': 'pierce-ltng',
    'passive_pois_pierce': 'pierce-pois',
    'passive_mag_pierce': 'pierce-mag',
    'passive_dmg_pierce': 'pierce-dmg',
    'item_allskills': 'allskills',
    'item_addclassskills': 'skilltab',
}


def _data_dir():
    """Return path to build/data/global/excel/ directory."""
    pkg = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(os.path.dirname(pkg), 'build', 'data', 'global', 'excel')


def _parse_affix_file(filename):
    """Parse a MagicPrefix.txt or MagicSuffix.txt file.

    Returns dict: {itype: {mod_code: [(row_id, name, level, param, vmin, vmax), ...]}}
    sorted by level descending within each group.
    """
    path = os.path.join(_data_dir(), filename)
    result = {}

    try:
        with open(path) as f:
            reader = csv.DictReader(f, delimiter='\t')
            for row_id, row in enumerate(reader, start=1):
                name = row.get('Name', '').strip()
                if not name:
                    continue

                mod1code = row.get('mod1code', '').strip()
                if not mod1code:
                    continue

                level = int(row.get('level', '0') or '0')
                param = row.get('mod1param', '').strip()
                vmin = int(row.get('mod1min', '0') or '0')
                vmax = int(row.get('mod1max', '0') or '0')

                # Collect all matching itypes
                for i in range(1, 8):
                    itype = row.get(f'itype{i}', '').strip()
                    if not itype:
                        continue
                    if itype not in result:
                        result[itype] = {}
                    if mod1code not in result[itype]:
                        result[itype][mod1code] = []
                    result[itype][mod1code].append(
                        (row_id, name, level, param, vmin, vmax)
                    )
    except FileNotFoundError:
        return {}

    # Sort each group by level descending (highest level = best tier)
    for itype_dict in result.values():
        for entries in itype_dict.values():
            entries.sort(key=lambda e: e[2], reverse=True)

    return result


def _build_name_index(parsed):
    """Build name -> row_id lookup from parsed affix data.

    Returns dict: {lowercase_name: row_id} (last-wins for duplicates,
    but we pick highest level when multiple share a name).
    """
    by_name = {}
    for itype_dict in parsed.values():
        for entries in itype_dict.values():
            for row_id, name, level, *_ in entries:
                key = name.lower()
                if key not in by_name or level > by_name[key][1]:
                    by_name[key] = (row_id, level)
    return {k: v[0] for k, v in by_name.items()}


def _parse_rare_name_file(filename):
    """Parse a RarePrefix.txt or RareSuffix.txt file.

    Returns dict: {itype: [(row_id, name), ...]}
    """
    path = os.path.join(_data_dir(), filename)
    result = {}

    try:
        with open(path) as f:
            reader = csv.DictReader(f, delimiter='\t')
            for row_id, row in enumerate(reader, start=1):
                name = row.get('name', '').strip()
                if not name:
                    continue

                for i in range(1, 8):
                    itype = row.get(f'itype{i}', '').strip()
                    if not itype:
                        continue
                    if itype not in result:
                        result[itype] = []
                    result[itype].append((row_id, name))
    except FileNotFoundError:
        return {}

    return result


# Parse at import time
PREFIXES = _parse_affix_file('MagicPrefix.txt')
SUFFIXES = _parse_affix_file('MagicSuffix.txt')
PREFIX_BY_NAME = _build_name_index(PREFIXES)
SUFFIX_BY_NAME = _build_name_index(SUFFIXES)
RARE_FIRST_NAMES = _parse_rare_name_file('RarePrefix.txt')
RARE_LAST_NAMES = _parse_rare_name_file('RareSuffix.txt')


def _get_itypes(type_code):
    """Get matching itype codes for an item type code."""
    from d2r_chargen.data.item_bases import ITEM_BASES
    base_info = ITEM_BASES.get(type_code, {})
    categories = base_info.get('categories', [])

    itypes = []
    for cat in categories:
        if cat in _CATEGORY_TO_ITYPES:
            for it in _CATEGORY_TO_ITYPES[cat]:
                if it not in itypes:
                    itypes.append(it)
    return itypes


def _find_best_affix(affix_db, itypes, mod_code, value=None, param=None):
    """Find the best-matching affix entry.

    Searches itypes in order (most specific first). Picks the entry
    whose value range includes the given value, or the highest-level
    entry if no exact range match.

    Args:
        affix_db: PREFIXES or SUFFIXES dict
        itypes: List of itype codes to search
        mod_code: The mod code to match
        value: Optional stat value to match against ranges
        param: Optional param to match (e.g., skill tab index)

    Returns:
        row_id or 0 if no match found
    """
    candidates = []
    for itype in itypes:
        entries = affix_db.get(itype, {}).get(mod_code, [])
        candidates.extend(entries)

    if not candidates:
        return 0

    # Filter by param if specified (e.g., skilltab param)
    if param is not None:
        param_str = str(param)
        param_filtered = [c for c in candidates if c[3] == param_str]
        if param_filtered:
            candidates = param_filtered
        elif mod_code == 'skilltab':
            # Skilltab MUST match param — wrong tab gives wrong class name
            return 0

    # Try to find range match for value
    if value is not None:
        for row_id, name, level, _p, vmin, vmax in candidates:
            if vmin <= value <= vmax:
                return row_id

    # No range match — return highest-level entry
    return candidates[0][0]


def resolve_affix_name(name, is_prefix=True):
    """Resolve an affix name string to a row ID.

    Args:
        name: Affix name (e.g., "Entrapping", "of Vita")
        is_prefix: True for prefix lookup, False for suffix

    Returns:
        Row ID, or 0 if not found
    """
    db = PREFIX_BY_NAME if is_prefix else SUFFIX_BY_NAME
    return db.get(name.lower(), 0)


def auto_select_affixes(type_code, properties):
    """Auto-select magic prefix and suffix IDs based on item properties.

    Examines the resolved properties list and picks appropriate prefix
    and suffix names from the affix database. The affix names are purely
    cosmetic — they determine the displayed name but the actual stats
    come from the encoded properties.

    Args:
        type_code: Item type code (e.g., 'cm3', 'xtb')
        properties: List of resolved property tuples from resolve_properties()
            Each tuple is (stat_id, value) or (stat_id, value, param) etc.

    Returns:
        (prefix_id, suffix_id) tuple of 11-bit IDs
    """
    from d2r_chargen.data.item_stat_cost import STAT_BY_NAME

    # Reverse lookup: stat_id -> canonical name
    id_to_name = {v: k for k, v in STAT_BY_NAME.items()}

    itypes = _get_itypes(type_code)
    if not itypes:
        return (0, 0)

    # Collect (mod_code, value, param) for each property
    prop_mods = []
    for prop in properties:
        stat_id = prop[0]
        canonical = id_to_name.get(stat_id)
        if not canonical:
            continue
        mod_codes = _STAT_TO_MOD.get(canonical)
        if not mod_codes:
            continue

        # Normalize to list (some stats map to multiple mod codes)
        if isinstance(mod_codes, str):
            mod_codes = [mod_codes]

        # Extract value and param
        if isinstance(prop[1], list):
            value = prop[1][0] if prop[1] else 0
        else:
            value = prop[1]
        param = prop[2] if len(prop) > 2 else None

        for mod_code in mod_codes:
            # Skilltab: convert binary encoding (class<<3|tab) to global tab index
            # Affix files use global indices: 0-2=Ama, 3-5=Sor, 6-8=Nec, etc.
            affix_param = param
            if mod_code == 'skilltab' and affix_param is not None:
                class_id = affix_param >> 3
                tab_within = affix_param & 7
                affix_param = class_id * 3 + tab_within

            prop_mods.append((mod_code, value, affix_param))

    prefix_id = 0
    suffix_id = 0
    prefix_mod = None

    # Try to find a prefix — prefer skilltab, then res, then others
    priority_prefix_mods = ['skilltab', 'res-all', 'res-fire', 'res-cold',
                            'res-ltng', 'res-pois', 'mana', 'att', 'ac',
                            'ac%', 'stam', 'mag%']
    # Try priority mods first
    for pmod in priority_prefix_mods:
        for mod_code, value, param in prop_mods:
            if mod_code == pmod:
                rid = _find_best_affix(PREFIXES, itypes, mod_code, value, param)
                if rid:
                    prefix_id = rid
                    prefix_mod = mod_code
                    break
        if prefix_id:
            break

    # If no priority match, try all mods
    if not prefix_id:
        for mod_code, value, param in prop_mods:
            rid = _find_best_affix(PREFIXES, itypes, mod_code, value, param)
            if rid:
                prefix_id = rid
                prefix_mod = mod_code
                break

    # Try to find a suffix — prefer hp, then str/dex, then others
    priority_suffix_mods = ['hp', 'str', 'dex', 'balance1', 'balance2',
                            'balance3', 'move1', 'move2', 'move3', 'gold%',
                            'mag%']
    # Try priority mods first, but skip the mod used for prefix
    for smod in priority_suffix_mods:
        if smod == prefix_mod:
            continue
        for mod_code, value, param in prop_mods:
            if mod_code == smod:
                rid = _find_best_affix(SUFFIXES, itypes, mod_code, value, param)
                if rid:
                    suffix_id = rid
                    break
        if suffix_id:
            break

    # If no priority match, try all mods (skip prefix mod)
    if not suffix_id:
        for mod_code, value, param in prop_mods:
            if mod_code == prefix_mod:
                continue
            rid = _find_best_affix(SUFFIXES, itypes, mod_code, value, param)
            if rid:
                suffix_id = rid
                break

    # Last resort: if we have neither, try the other direction
    # (e.g., hp can be a prefix-less item with just "of Vita")
    if not prefix_id and not suffix_id and prop_mods:
        # Try any mod as prefix
        for mod_code, value, param in prop_mods:
            rid = _find_best_affix(PREFIXES, itypes, mod_code, value, param)
            if rid:
                prefix_id = rid
                break
        if not prefix_id:
            # Try any mod as suffix
            for mod_code, value, param in prop_mods:
                rid = _find_best_affix(SUFFIXES, itypes, mod_code, value, param)
                if rid:
                    suffix_id = rid
                    break

    return (prefix_id, suffix_id)


def auto_select_rare_names(type_code, seed=0):
    """Auto-select rare first and last name IDs for an item.

    Rare names are purely cosmetic — they don't correspond to stats.
    Picks names valid for the item's type, using a seed for variety.

    Args:
        type_code: Item type code (e.g., 'amu', 'xhm', 'uvg')
        seed: Integer seed for deterministic variety (e.g., hash of properties).
            Different seeds produce different name combos for the same item type.

    Returns:
        (first_name_id, last_name_id) tuple of 8-bit IDs
    """
    itypes = _get_itypes(type_code)
    if not itypes:
        return (0, 0)

    # Collect candidate first names (from RarePrefix.txt)
    first_candidates = []
    for itype in itypes:
        first_candidates.extend(RARE_FIRST_NAMES.get(itype, []))
    # Deduplicate by row_id
    seen = set()
    first_unique = []
    for rid, name in first_candidates:
        if rid not in seen:
            seen.add(rid)
            first_unique.append((rid, name))

    # Collect candidate last names (from RareSuffix.txt)
    last_candidates = []
    for itype in itypes:
        last_candidates.extend(RARE_LAST_NAMES.get(itype, []))
    seen = set()
    last_unique = []
    for rid, name in last_candidates:
        if rid not in seen:
            seen.add(rid)
            last_unique.append((rid, name))

    first_id = 0
    last_id = 0

    if first_unique:
        idx = seed % len(first_unique)
        first_id = first_unique[idx][0]

    if last_unique:
        # Use a different offset to avoid always pairing the same names
        idx = (seed * 7 + 3) % len(last_unique)
        last_id = last_unique[idx][0]

    return (first_id, last_id)
