"""Name-to-ID resolution for D2R character generation.

Resolves human-readable names (runeword names, unique names, skill names,
property aliases) into numeric IDs and property tuples suitable for
build_item(properties=...).
"""
import re

from d2r_chargen.config import PROPERTY_ALIASES, CLASS_DEFS, RW_BASE_CATEGORIES
try:
    from d2r_chargen.data.item_stat_cost import STAT_BY_NAME, ITEM_STAT_COST
    from d2r_chargen.data.runewords import RUNEWORDS
    from d2r_chargen.data.runeword_stats import RUNEWORD_STATS
    from d2r_chargen.data.unique_item_stats import UNIQUE_ITEM_STATS
    from d2r_chargen.data.item_bases import ITEM_BASES
    from d2r_chargen.data.skills import SKILLS
    _DATA_AVAILABLE = True
except ImportError:
    STAT_BY_NAME = ITEM_STAT_COST = RUNEWORDS = RUNEWORD_STATS = None
    UNIQUE_ITEM_STATS = ITEM_BASES = SKILLS = None
    _DATA_AVAILABLE = False

# Use canonical expansion map from config.py
_RW_BASE_EXPANSION = RW_BASE_CATEGORIES


def encode_skill_tab_param(global_tab):
    """Convert a global skill tab index (0-23) to D2R binary encoding.

    Data files use sequential global indices: 0-2=Amazon, 3-5=Sorc, 6-8=Necro,
    9-11=Pally, 12-14=Barb, 15-17=Druid, 18-20=Assassin, 21-23=Warlock.

    D2R binary format packs as: (class_id << 3) | tab_within_class.
    """
    class_id = global_tab // 3
    tab_within_class = global_tab % 3
    return (class_id << 3) | tab_within_class


def _build_lookups():
    """Build reverse lookup dicts at import time."""
    skill_name_to_id = {}
    for sid, sinfo in SKILLS.items():
        name = sinfo["name"]
        if name not in skill_name_to_id:
            skill_name_to_id[name] = sid
        else:
            # If duplicate name, prefer the one with a class (class skill over generic)
            if "class" in sinfo and "class" not in SKILLS.get(skill_name_to_id[name], {}):
                skill_name_to_id[name] = sid

    skill_code_to_class = {}
    for cname, cdef in CLASS_DEFS.items():
        if cdef['skill_code']:
            skill_code_to_class[cdef['skill_code']] = cname

    rw_name_to_id = {}
    for rwid, rwinfo in RUNEWORDS.items():
        rw_name_to_id[rwinfo['name'].lower()] = rwid

    unique_name_to_id = {}
    for uid, uinfo in UNIQUE_ITEM_STATS.items():
        unique_name_to_id[uinfo['name'].lower()] = uid

    return skill_name_to_id, skill_code_to_class, rw_name_to_id, unique_name_to_id


if _DATA_AVAILABLE:
    _SKILL_NAME_TO_ID, _SKILL_CODE_TO_CLASS, _RUNEWORD_NAME_TO_ID, _UNIQUE_NAME_TO_ID = _build_lookups()
else:
    _SKILL_NAME_TO_ID = _SKILL_CODE_TO_CLASS = _RUNEWORD_NAME_TO_ID = _UNIQUE_NAME_TO_ID = {}


def resolve_property_name(name):
    """Resolve a property alias or raw STAT_BY_NAME key to its canonical name.

    Args:
        name: A property alias (e.g. "fcr") or raw stat name (e.g. "item_fastercastrate")

    Returns:
        The canonical STAT_BY_NAME key string.

    Raises:
        ValueError: If name is not a known alias or STAT_BY_NAME key.
    """
    # Check aliases first
    if name in PROPERTY_ALIASES:
        return PROPERTY_ALIASES[name]
    # Check if it's already a valid STAT_BY_NAME key
    if name in STAT_BY_NAME:
        return name
    raise ValueError(
        f"Unknown property name: '{name}'. "
        f"Not a known alias or STAT_BY_NAME key."
    )


def _lookup_skill_id(skill_name):
    """Look up a skill ID by name.

    Args:
        skill_name: Skill name string (e.g. "Teleport", "Chain Lightning")

    Returns:
        Integer skill ID.

    Raises:
        ValueError: If skill name not found.
    """
    if skill_name not in _SKILL_NAME_TO_ID:
        raise ValueError(f"Unknown skill name: '{skill_name}'")
    return _SKILL_NAME_TO_ID[skill_name]


def _resolve_stat_entry(stat_entry, use_max=True):
    """Convert a stat entry from runeword_stats/unique_item_stats into a property tuple.

    Args:
        stat_entry: Dict with 'stat', 'min', 'max', and optional 'param_type', 'param'.
        use_max: If True, use max roll; if False, use min roll.

    Returns:
        A tuple: (stat_id, value) or (stat_id, value, param)
        For grouped stats (np > 0): (stat_id, [val1, val2, ...])
    """
    stat_name = stat_entry['stat']
    if stat_name not in STAT_BY_NAME:
        raise ValueError(f"Unknown stat name in data: '{stat_name}'")
    stat_id = STAT_BY_NAME[stat_name]
    value = stat_entry['max'] if use_max else stat_entry['min']

    # Check for grouped stats (np > 0).  D2R encodes these as one stat ID
    # followed by np values back-to-back (no intermediate stat IDs).
    # Examples:
    #   item_maxdamage_percent (17, np=2): [maxdmg%, mindmg%]
    #   firemindam (48, np=2): [mindam, maxdam]
    #   coldmindam (54, np=3): [mindam, maxdam, length]
    #   poisonmindam (57, np=3): [mindam, maxdam, length]
    stat_info = ITEM_STAT_COST.get(stat_id, {})
    np_count = stat_info.get('np', 0)
    if np_count > 0:
        min_val = stat_entry['min']
        max_val = stat_entry['max']
        if np_count == 2:
            # Group of 2: [first_value, second_value]
            # e.g. enhanced_dmg: [max%, min%], fire: [mindam, maxdam]
            return (stat_id, [max_val if use_max else min_val,
                              max_val if use_max else min_val])
        elif np_count == 3:
            # Group of 3: [first_value, second_value, duration]
            # Duration comes from 'param' field
            duration = int(stat_entry.get('param', 0))
            return (stat_id, [max_val if use_max else min_val,
                              max_val if use_max else min_val,
                              duration])

    param_type = stat_entry.get('param_type')
    if param_type is None:
        # Simple stat, no param
        return (stat_id, value)

    param_raw = stat_entry['param']

    if param_type == 'skill':
        # param is a skill name (string), numeric string ('77'), or skill ID (int)
        if isinstance(param_raw, str):
            try:
                skill_id = int(param_raw)
            except ValueError:
                skill_id = _lookup_skill_id(param_raw)
        else:
            skill_id = int(param_raw)
        return (stat_id, value, skill_id)

    elif param_type == 'skill_tab':
        # Convert global tab index to D2R binary encoding
        return (stat_id, value, encode_skill_tab_param(int(param_raw)))

    elif param_type == 'class':
        # param is a class ID (int) or "varies" (special case)
        if param_raw == "varies":
            # Default to 0 (Amazon); caller should override
            return (stat_id, value, 0)
        return (stat_id, value, int(param_raw))

    elif param_type == 'ctc':
        # In runeword_stats: descriptive string like "level 17 Chain Lightning on striking"
        # In unique_item_stats: expression string like "(15 << 10) | 92"
        #   or plain numeric skill ID like "93" (min=chance, max=level)
        if isinstance(param_raw, str):
            # Try to parse as expression first: "(level << 10) | skill_id"
            expr_match = re.match(r'\((\d+)\s*<<\s*10\)\s*\|\s*(\d+)', param_raw)
            if expr_match:
                level = int(expr_match.group(1))
                skill_id = int(expr_match.group(2))
                encoded_param = (level << 10) | skill_id
                return (stat_id, value, encoded_param)

            # Plain numeric skill ID (e.g. '93'): min=chance, max=level
            try:
                skill_id = int(param_raw)
                chance = stat_entry['min']
                level = stat_entry['max']
                encoded_param = (level << 10) | skill_id
                return (stat_id, chance, encoded_param)
            except (ValueError, TypeError):
                pass

            # Parse descriptive format: "level N SkillName on striking/when struck"
            desc_match = re.match(
                r'level\s+(\d+)\s+(.+?)\s+(?:on\s+striking|when\s+struck|on\s+attack|on\s+kill)',
                param_raw, re.IGNORECASE
            )
            if desc_match:
                level = int(desc_match.group(1))
                skill_name = desc_match.group(2).strip()
                skill_id = _lookup_skill_id(skill_name)
                encoded_param = (level << 10) | skill_id
                return (stat_id, value, encoded_param)

            # Format 3: plain skill name (e.g. "Confuse", "Decrepify")
            # Look up skill ID directly — level comes from min/max fields
            try:
                skill_id = _lookup_skill_id(param_raw)
                return (stat_id, value, skill_id)
            except ValueError:
                pass  # Fall through to the error below

            raise ValueError(f"Cannot parse CTC param: '{param_raw}'")
        else:
            # Already an integer
            return (stat_id, value, int(param_raw))

    elif param_type == 'charges':
        # In unique_item_stats: expression string like "(3 << 10) | 278"
        #   or plain numeric skill ID like "54" (min=max_charges, max=level)
        #   or plain skill name (e.g. "Venom") — level comes from min/max fields
        if isinstance(param_raw, str):
            expr_match = re.match(r'\((\d+)\s*<<\s*10\)\s*\|\s*(\d+)', param_raw)
            if expr_match:
                level = int(expr_match.group(1))
                skill_id = int(expr_match.group(2))
                encoded_param = (level << 10) | skill_id
                # For charges, value is the charge count (max_charges << 8 | current_charges)
                # From the data file, 'value' is stored as 'min'/'max' representing max_charges
                # current_charges defaults to same as max
                charge_val = (value << 8) | value
                return (stat_id, charge_val, encoded_param)
            # Plain numeric skill ID (e.g. '54'): min=max_charges, max=level
            try:
                skill_id = int(param_raw)
                max_charges = stat_entry['min']
                level = stat_entry['max']
                encoded_param = (level << 10) | skill_id
                charge_val = (max_charges << 8) | max_charges
                return (stat_id, charge_val, encoded_param)
            except (ValueError, TypeError):
                pass
            # Plain skill name (e.g. "Venom") — look up skill ID, use level from max/min
            try:
                skill_id = _lookup_skill_id(param_raw)
                charge_val = (value << 8) | value
                return (stat_id, charge_val, skill_id)
            except ValueError:
                pass
            raise ValueError(f"Cannot parse charges param: '{param_raw}'")
        else:
            charge_val = (value << 8) | value
            return (stat_id, charge_val, int(param_raw))

    else:
        raise ValueError(f"Unknown param_type: '{param_type}'")


def resolve_runeword(name, base_code):
    """Resolve a runeword by name and validate against a base item code.

    Args:
        name: Runeword name (e.g. "Crescent Moon")
        base_code: Item base type code (e.g. "9ls")

    Returns:
        Dict with keys: runeword_id, rune_codes, num_sockets, base_code,
        max_dur, defense, properties.

    Raises:
        ValueError: If runeword not found, base not in ITEM_BASES, base
            incompatible with runeword, or stats not available.
    """
    # Find runeword by name
    rw_key = name.lower()
    if rw_key not in _RUNEWORD_NAME_TO_ID:
        raise ValueError(f"Runeword not found: '{name}'")
    rw_id = _RUNEWORD_NAME_TO_ID[rw_key]
    rw_info = RUNEWORDS[rw_id]

    # Validate base code exists
    if base_code not in ITEM_BASES:
        raise ValueError(f"Unknown base item code: '{base_code}'")
    base_info = ITEM_BASES[base_code]

    # Validate base compatibility (expand runeword required base types to all matching categories)
    rw_bases = rw_info['bases']  # e.g. ['Axe', 'Sword', 'Polearm']
    base_categories = base_info.get('categories', [])
    # Build the full set of acceptable categories for this runeword
    acceptable_cats = set()
    for rb in rw_bases:
        acceptable_cats.update(_RW_BASE_EXPANSION.get(rb, [rb]))
    compatible = any(cat in acceptable_cats for cat in base_categories)
    if not compatible:
        raise ValueError(
            f"Base '{base_code}' ({base_info['name']}) is not compatible with "
            f"runeword '{name}'. Required base types: {', '.join(rw_bases)}. "
            f"Item categories: {', '.join(base_categories)}"
        )

    # Validate socket count
    max_sockets = base_info.get('max_sockets', 0)
    required_sockets = rw_info['sockets']
    if max_sockets < required_sockets:
        raise ValueError(
            f"Base '{base_code}' ({base_info['name']}) has max {max_sockets} sockets, "
            f"but runeword '{name}' requires {required_sockets}"
        )

    # Get stats from runeword_stats
    if rw_id not in RUNEWORD_STATS:
        raise ValueError(
            f"No stat data available for runeword '{name}' (id={rw_id})"
        )
    rw_stats = RUNEWORD_STATS[rw_id]

    # Build properties list (max rolls); skip stats that can't be encoded
    properties = []
    for stat_entry in rw_stats['stats']:
        try:
            prop = _resolve_stat_entry(stat_entry, use_max=True)
            properties.append(prop)
        except (ValueError, KeyError):
            pass

    # Get base item durability and defense
    max_dur = base_info.get('durability', 0)
    defense = base_info.get('max_ac', 0)

    return {
        'runeword_id': rw_id,
        'rune_codes': rw_info['runes'],
        'num_sockets': required_sockets,
        'base_code': base_code,
        'max_dur': max_dur,
        'defense': defense,
        'properties': properties,
    }


def resolve_unique(name):
    """Resolve a unique item by name.

    Args:
        name: Unique item name (e.g. "Griffon's Eye")

    Returns:
        Dict with keys: unique_id, type_code, max_dur, defense, properties.

    Raises:
        ValueError: If unique item not found or base code not in ITEM_BASES.
    """
    ukey = name.lower()
    if ukey not in _UNIQUE_NAME_TO_ID:
        raise ValueError(f"Unique item not found: '{name}'")
    uid = _UNIQUE_NAME_TO_ID[ukey]
    uinfo = UNIQUE_ITEM_STATS[uid]

    base_code = uinfo['base']
    if base_code not in ITEM_BASES:
        raise ValueError(
            f"Unknown base item code '{base_code}' for unique '{name}'"
        )
    base_info = ITEM_BASES[base_code]

    # Build properties list (max rolls); skip stats that can't be encoded
    properties = []
    for stat_entry in uinfo['stats']:
        try:
            prop = _resolve_stat_entry(stat_entry, use_max=True)
            properties.append(prop)
        except (ValueError, KeyError):
            pass

    max_dur = base_info.get('durability', 0)
    defense = base_info.get('max_ac', 0)

    return {
        'unique_id': uid,
        'type_code': base_code,
        'max_dur': max_dur,
        'defense': defense,
        'properties': properties,
    }


def resolve_skills(class_name, skill_dict):
    """Resolve a dict of skill names and levels into a 30-element skill array.

    Args:
        class_name: Class name (e.g. "sorceress")
        skill_dict: Dict mapping skill name -> level (e.g. {"Lightning": 20})

    Returns:
        List of 30 ints representing skill levels at each offset.

    Raises:
        ValueError: If class unknown, skill not found, or skill belongs
            to a different class.
    """
    class_name_lower = class_name.lower()
    if class_name_lower not in CLASS_DEFS:
        raise ValueError(f"Unknown class: '{class_name}'")

    cdef = CLASS_DEFS[class_name_lower]
    skill_base = cdef['skill_base']
    skill_code = cdef['skill_code']

    if skill_base is None or skill_code is None:
        raise ValueError(
            f"Class '{class_name}' has no skill data available"
        )

    arr = [0] * 30

    for skill_name, level in skill_dict.items():
        if skill_name not in _SKILL_NAME_TO_ID:
            raise ValueError(f"Unknown skill: '{skill_name}'")
        skill_id = _SKILL_NAME_TO_ID[skill_name]
        skill_info = SKILLS[skill_id]
        skill_class = skill_info.get('class')

        if skill_class != skill_code:
            # Find the class name for the error message
            if skill_class:
                actual_class = _SKILL_CODE_TO_CLASS.get(skill_class, skill_class)
            else:
                actual_class = "generic (no class)"
            raise ValueError(
                f"Skill '{skill_name}' belongs to {actual_class}, "
                f"not {class_name_lower}"
            )

        offset = skill_id - skill_base
        if offset < 0 or offset >= 30:
            raise ValueError(
                f"Skill '{skill_name}' (id={skill_id}) offset {offset} "
                f"out of range for class '{class_name}'"
            )
        arr[offset] = level

    return arr


def resolve_properties(prop_dict):
    """Resolve a YAML properties dict into a list of property tuples.

    Handles the following value formats:
      - Simple int:              stat_name: value -> (stat_id, value)
      - Skill bonus [lv, name]: -> (stat_id, level, skill_id)
      - Multiple auras [[lv, name], ...]: -> multiple (stat_id, level, skill_id)
      - CTC [chance, lv, name]: -> (stat_id, chance, (level << 10) | skill_id)
      - Charges [cur, max, lv, name]: -> (stat_id, (max << 8) | cur, (level << 10) | skill_id)
      - Class skills [value, class_name]: -> (stat_id, value, class_id)
      - Skill tab [value, tab_idx]: -> (stat_id, value, tab_idx)

    Args:
        prop_dict: Dict mapping property names (aliases or raw) to values.

    Returns:
        List of tuples suitable for build_item(properties=...).

    Raises:
        ValueError: If property name unknown, skill not found, or class unknown.
    """
    result = []

    for name, value in prop_dict.items():
        # Resolve the property name to canonical stat name
        canonical = resolve_property_name(name)
        stat_id = STAT_BY_NAME[canonical]
        stat_info = ITEM_STAT_COST.get(stat_id, {})
        encoding = stat_info.get('e', 0)

        if isinstance(value, (int, float)) and not isinstance(value, bool):
            # Simple value — but check for grouped stats (np > 0)
            np_count = stat_info.get('np', 0)
            if np_count > 0:
                # Grouped stat: auto-expand scalar to list of np values.
                # e.g. 'enhanced_dmg': 300 → (17, [300, 300]) for np=2
                # All group members get the same value (typical for ED,
                # elemental min/max).  Duration defaults to 0.
                group_vals = [int(value)] * np_count
                result.append((stat_id, group_vals))
            else:
                result.append((stat_id, int(value)))

        elif isinstance(value, list):
            # Check for grouped stats first: if np_count matches list length
            # and all elements are plain numbers, treat as raw grouped values.
            np_count = stat_info.get('np', 0)
            if np_count > 0 and len(value) == np_count and all(
                isinstance(v, (int, float)) and not isinstance(v, bool)
                for v in value
            ):
                result.append((stat_id, [int(v) for v in value]))
            # Check if it's a list of lists (multiple entries for same stat)
            elif len(value) > 0 and isinstance(value[0], list):
                # Multiple entries: [[lv, name], [lv, name], ...]
                for subval in value:
                    tup = _resolve_list_property(stat_id, canonical, subval)
                    result.append(tup)
            else:
                # Single list entry (skill bonus, CTC, charges)
                tup = _resolve_list_property(stat_id, canonical, value)
                result.append(tup)

        else:
            raise ValueError(
                f"Unsupported value type for property '{name}': {type(value)}"
            )

    return result


def _resolve_list_property(stat_id, canonical, value_list):
    """Resolve a list-format property value into a property tuple.

    Dispatches by list length and stat name:
      2-element: skill bonus or class skills or skill tab
      3-element: chance-to-cast
      4-element: charges

    Args:
        stat_id: Integer stat ID.
        canonical: Canonical stat name string.
        value_list: List of values (2, 3, or 4 elements).

    Returns:
        Property tuple.
    """
    if len(value_list) == 2:
        # Could be: [level, SkillName], [value, class_name], or [value, tab_idx]
        val, param = value_list

        if canonical == 'item_addclassskills':
            # [value, class_name] -> (stat_id, value, class_id)
            if isinstance(param, str):
                param_lower = param.lower()
                if param_lower not in CLASS_DEFS:
                    raise ValueError(f"Unknown class: '{param}'")
                class_id = CLASS_DEFS[param_lower]['id']
                return (stat_id, int(val), class_id)
            else:
                return (stat_id, int(val), int(param))

        elif canonical == 'item_addskill_tab':
            # [value, global_tab_index] -> (stat_id, value, binary_param)
            return (stat_id, int(val), encode_skill_tab_param(int(param)))

        else:
            # [level, SkillName] -> (stat_id, level, skill_id)
            # Used for item_nonclassskill, item_aura, item_singleskill, etc.
            if isinstance(param, str):
                skill_id = _lookup_skill_id(param)
                return (stat_id, int(val), skill_id)
            else:
                return (stat_id, int(val), int(param))

    elif len(value_list) == 3:
        # CTC: [chance, level, SkillName] -> (stat_id, chance, (level << 10) | skill_id)
        chance, level, skill_name = value_list
        if isinstance(skill_name, str):
            skill_id = _lookup_skill_id(skill_name)
        else:
            skill_id = int(skill_name)
        encoded_param = (int(level) << 10) | skill_id
        return (stat_id, int(chance), encoded_param)

    elif len(value_list) == 4:
        # Charges: [cur, max, level, SkillName]
        # -> (stat_id, (max << 8) | cur, (level << 10) | skill_id)
        cur, max_charges, level, skill_name = value_list
        if isinstance(skill_name, str):
            skill_id = _lookup_skill_id(skill_name)
        else:
            skill_id = int(skill_name)
        encoded_value = (int(max_charges) << 8) | int(cur)
        encoded_param = (int(level) << 10) | skill_id
        return (stat_id, encoded_value, encoded_param)

    else:
        raise ValueError(
            f"Unsupported list length {len(value_list)} for stat '{canonical}'"
        )


def resolve_set_item(name):
    """Resolve a set item name to its set_id, type_code, and base info.

    Set items don't have auto-resolved stats (no set_item_stats.py yet),
    so callers MUST provide explicit 'properties:' in the YAML.

    Args:
        name: Set item name, e.g. "Trang-Oul's Claws"

    Returns:
        Dict with 'set_id', 'type_code', 'defense', 'max_dur'.

    Raises:
        ValueError: If set item name not found.
    """
    from d2r_chargen.data.set_items import SET_ITEMS

    name_lower = name.lower()
    for sid, sinfo in SET_ITEMS.items():
        if sinfo['name'].lower() == name_lower:
            code = sinfo['code']
            base_info = ITEM_BASES.get(code, {})
            return {
                'set_id': sid,
                'type_code': code,
                'defense': base_info.get('max_ac', 0),
                'max_dur': base_info.get('durability', 0),
            }

    raise ValueError(
        f"Unknown set item: '{name}'. Check d2r_data/set_items.py."
    )


# ============================================================
# Progression Resolution
# ============================================================

_PROGRESSION_PRESETS = {
    'hell_complete':      {'difficulty': 'hell',      'complete_through': 'hell'},
    'hell_start':         {'difficulty': 'hell',      'complete_through': 'nightmare'},
    'nightmare_complete': {'difficulty': 'nightmare', 'complete_through': 'nightmare'},
    'nightmare_start':    {'difficulty': 'nightmare', 'complete_through': 'normal'},
    'normal_complete':    {'difficulty': 'normal',    'complete_through': 'normal'},
    'normal_start':       {'difficulty': 'normal',    'complete_through': None},
}

_DIFF_ORDER = ['normal', 'nightmare', 'hell']
_WP_ACT_NAMES = ['act1', 'act2', 'act3', 'act4', 'act5']
_QUEST_ACT_NAMES = ['act1', 'act2', 'act3', 'act4', 'act5', 'act6']


def resolve_progression(progression_value):
    """Resolve a YAML progression field into structured waypoint/quest config.

    Args:
        progression_value: Either a preset string (e.g. 'hell_complete')
            or a dict with 'preset' key and optional 'waypoints'/'quests' overrides.

    Returns:
        Dict with keys:
            'difficulty': str ('normal', 'nightmare', 'hell')
            'waypoints': dict mapping difficulty -> True (all) / False (none) / dict of act->bool
            'quests': dict mapping difficulty -> True / False / dict of act->bool

    Raises:
        ValueError: If preset name is unknown.
    """
    if isinstance(progression_value, str):
        preset_name = progression_value
        overrides = {}
    elif isinstance(progression_value, dict):
        preset_name = progression_value.get('preset', 'hell_start')
        overrides = progression_value
    else:
        raise ValueError(f"progression must be a string or dict, got {type(progression_value)}")

    if preset_name not in _PROGRESSION_PRESETS:
        raise ValueError(
            f"Unknown progression preset: '{preset_name}'. "
            f"Valid presets: {', '.join(_PROGRESSION_PRESETS.keys())}"
        )

    preset = _PROGRESSION_PRESETS[preset_name]
    complete_through = preset['complete_through']

    waypoints = {}
    quests = {}
    for diff in _DIFF_ORDER:
        if complete_through and _DIFF_ORDER.index(diff) <= _DIFF_ORDER.index(complete_through):
            waypoints[diff] = True
            quests[diff] = True
        else:
            waypoints[diff] = False
            quests[diff] = False

    # Apply overrides: acts not listed inherit from preset
    wp_overrides = overrides.get('waypoints', {})
    for diff, acts in wp_overrides.items():
        if diff not in _DIFF_ORDER:
            raise ValueError(f"Unknown difficulty in waypoints override: '{diff}'")
        if isinstance(acts, dict):
            base_val = waypoints[diff]
            act_dict = {act: base_val for act in _WP_ACT_NAMES}
            for act, val in acts.items():
                if act not in _WP_ACT_NAMES:
                    raise ValueError(f"Unknown act in waypoints override: '{act}'")
                act_dict[act] = bool(val)
            waypoints[diff] = act_dict

    quest_overrides = overrides.get('quests', {})
    for diff, acts in quest_overrides.items():
        if diff not in _DIFF_ORDER:
            raise ValueError(f"Unknown difficulty in quests override: '{diff}'")
        if isinstance(acts, dict):
            base_val = quests[diff]
            act_dict = {act: base_val for act in _QUEST_ACT_NAMES}
            for act, val in acts.items():
                if act not in _QUEST_ACT_NAMES:
                    raise ValueError(f"Unknown act in quests override: '{act}'")
                act_dict[act] = bool(val)
            quests[diff] = act_dict

    return {
        'difficulty': preset['difficulty'],
        'waypoints': waypoints,
        'quests': quests,
    }
