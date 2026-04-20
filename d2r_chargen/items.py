"""Item building for D2R character generation.

Takes resolved item definitions (from YAML + resolve.py) and produces
binary bytes via d2r_build_lib.build_item() + encode_socketed_rune().

All items are tagged with section='char'. Merc gear goes to stash (storage=5)
in the char JM section -- NEVER to the merc JM section (Rule 6: pre-injected
merc JM items cause Error:8).
"""
from d2r_chargen.build_lib import build_item, encode_socketed_rune
from d2r_chargen.config import SLOT_MAP
from d2r_chargen.resolve import (
    resolve_runeword, resolve_unique, resolve_set_item, resolve_properties,
)
from d2r_chargen.data.item_bases import ITEM_BASES
from d2r_chargen.data.magic_affixes import (
    auto_select_affixes, resolve_affix_name, auto_select_rare_names,
)

def _resolve_magic_affixes(prefix_val, suffix_val, type_code, resolved_props):
    """Resolve magic prefix/suffix values to numeric IDs.

    Supports three input forms:
      - int > 0: used as-is (explicit row ID)
      - str: resolved by affix name (e.g., "Entrapping", "of Vita")
      - 0 or missing: auto-selected from item properties

    Args:
        prefix_val: Explicit prefix (int ID, string name, or 0 for auto)
        suffix_val: Explicit suffix (int ID, string name, or 0 for auto)
        type_code: Item type code (e.g., 'cm3', 'xtb')
        resolved_props: List of resolved property tuples

    Returns:
        (prefix_id, suffix_id) tuple of ints
    """
    # Resolve string names to IDs
    if isinstance(prefix_val, str):
        prefix_val = resolve_affix_name(prefix_val, is_prefix=True)
    if isinstance(suffix_val, str):
        suffix_val = resolve_affix_name(suffix_val, is_prefix=False)

    # Auto-select if either is 0
    if not prefix_val or not suffix_val:
        auto_prefix, auto_suffix = auto_select_affixes(type_code, resolved_props)
        if not prefix_val:
            prefix_val = auto_prefix
        if not suffix_val:
            suffix_val = auto_suffix

    return (prefix_val, suffix_val)


def _resolve_rare_names(first_val, last_val, type_code, props):
    """Resolve rare item first/last name values to numeric IDs.

    Supports:
      - int > 0: used as-is (explicit row ID)
      - 0 or missing: auto-selected based on item type

    Args:
        first_val: Explicit first name ID or 0 for auto
        last_val: Explicit last name ID or 0 for auto
        type_code: Item type code (e.g., 'amu', 'xhm')
        props: Resolved properties list (used as seed for variety)

    Returns:
        (first_name_id, last_name_id) tuple of ints
    """
    if not first_val or not last_val:
        # Use a deterministic seed from type_code + properties for variety
        seed = hash((type_code, tuple(str(p) for p in props))) & 0x7FFFFFFF
        auto_first, auto_last = auto_select_rare_names(type_code, seed)
        if not first_val:
            first_val = auto_first
        if not last_val:
            last_val = auto_last
    return (first_val, last_val)


# Default base type codes for rare items when no explicit base is given
RARE_SLOT_BASES = {
    'neck': 'amu',
    'ring_right': 'rin',
    'ring_left': 'rin',
    'feet': 'xtb',    # Battle Boots (exceptional)
    'hands': 'xtg',   # Battle Gauntlets (exceptional)
    'helm': 'xhm',    # Winged Helm (exceptional)
}

# Charm type code mapping
_CHARM_TYPE_CODES = {
    'magic_small_charm': 'cm1',
    'magic_large_charm': 'cm2',
    'magic_grand_charm': 'cm3',
}


def _merge_properties(base_props, extra_props):
    """Merge extra_properties onto base resolved properties.

    For each property in extra_props:
    - If base_props has a property with the same stat_id, remove ALL base
      entries with that stat_id and add ALL extra entries with that stat_id.
    - Otherwise, append it.

    Multiple properties with the same stat_id ARE valid in D2R (e.g., multiple
    auras). When replacing, replace ALL entries with that stat_id from base,
    then add ALL entries from extra.
    """
    # Collect which stat_ids are being overridden
    extra_stat_ids = {p[0] for p in extra_props}
    # Keep base entries whose stat_id is NOT in extra
    result = [p for p in base_props if p[0] not in extra_stat_ids]
    # Append all extra entries
    result.extend(extra_props)
    return result


def build_equipment_item(item_def):
    """Build an equipment item from a YAML definition dict.

    Dispatches based on keys present in item_def:
      - 'runeword' -> runeword item (quality=2, runeword=True) + rune fillers
      - 'unique'   -> unique item (quality=7)
      - 'set'      -> set item (currently NotImplementedError)
      - 'rare'     -> rare item (quality=6)
      - 'magic_prefix'/'magic_suffix' -> magic item (quality=4)
      - 'crafted'  -> crafted item (quality=8)

    Args:
        item_def: Dict with slot, quality type key, and optional properties.

    Returns:
        List of (section, bytes) tuples. Section is always 'char'.
    """
    slot_name = item_def['slot']
    slot = SLOT_MAP[slot_name]

    if 'runeword' in item_def:
        return _build_runeword(item_def, slot)
    elif 'unique' in item_def:
        return _build_unique(item_def, slot)
    elif 'set' in item_def:
        return _build_set(item_def, slot)
    elif 'rare' in item_def:
        return _build_rare(item_def, slot)
    elif 'magic_prefix' in item_def or 'magic_suffix' in item_def:
        return _build_magic(item_def, slot)
    elif 'crafted' in item_def:
        return _build_crafted(item_def, slot)
    else:
        raise ValueError(
            f"Cannot determine item quality type from keys: {list(item_def.keys())}"
        )


def _resolve_final_properties(item_def, auto_props, *, has_canonical=False):
    """Determine final properties list for an item.

    - has_canonical=True  (unique, set, runeword): `properties` merges on
                          top of auto_props; `extra_properties` same.
    - has_canonical=False (rare, magic, crafted):  `properties` replaces,
                          as there's nothing to merge against.
    """
    if 'properties' in item_def:
        user_props = resolve_properties(item_def['properties'])
        if has_canonical:
            return _merge_properties(auto_props, user_props)
        return user_props
    elif 'extra_properties' in item_def:
        extra = resolve_properties(item_def['extra_properties'])
        return _merge_properties(auto_props, extra)
    return auto_props


def _build_runeword(item_def, slot):
    """Build a runeword item: parent + rune fillers."""
    name = item_def['runeword']
    base_code = item_def['base']
    resolved = resolve_runeword(name, base_code)

    props = _resolve_final_properties(item_def, resolved['properties'], has_canonical=True)

    parent_bytes = build_item(
        type_code=base_code,
        col=0, row=0, storage=0,
        location=1, bodyloc=slot['bodyloc'],
        quality=2,
        ilvl=item_def.get('ilvl', 99),
        socketed=True,
        num_sockets=resolved['num_sockets'],
        runeword=True,
        runeword_id=resolved['runeword_id'],
        defense=resolved['defense'],
        max_dur=resolved['max_dur'],
        cur_dur=resolved['max_dur'],
        properties=props,
        ethereal=item_def.get('ethereal', False),
        rune_codes=resolved['rune_codes'],
    )
    items = [('char', parent_bytes)]

    for idx, rune_code in enumerate(resolved['rune_codes']):
        filler = encode_socketed_rune(rune_code, socket_idx=idx)
        items.append(('char', filler))

    return items


def _build_unique(item_def, slot):
    """Build a unique item."""
    name = item_def['unique']
    resolved = resolve_unique(name)

    props = _resolve_final_properties(item_def, resolved['properties'], has_canonical=True)

    item_bytes = build_item(
        type_code=resolved['type_code'],
        col=0, row=0, storage=0,
        location=1, bodyloc=slot['bodyloc'],
        quality=7,
        ilvl=item_def.get('ilvl', 99),
        unique_id=resolved['unique_id'],
        defense=item_def.get('defense', resolved['defense']),
        max_dur=resolved['max_dur'],
        cur_dur=resolved['max_dur'],
        properties=props,
        ethereal=item_def.get('ethereal', False),
    )
    return [('char', item_bytes)]


def _build_set(item_def, slot):
    """Build a set item (quality=5).

    Requires explicit 'properties:' in the YAML (no auto-resolved stats).
    """
    name = item_def['set']
    resolved = resolve_set_item(name)

    if 'properties' not in item_def:
        raise ValueError(
            f"Set item '{name}' requires explicit 'properties:' "
            f"(no auto-resolved stats for set items)"
        )
    props = resolve_properties(item_def['properties'])

    item_bytes = build_item(
        type_code=resolved['type_code'],
        col=0, row=0, storage=0,
        location=1, bodyloc=slot['bodyloc'],
        quality=5,
        ilvl=item_def.get('ilvl', 99),
        set_id=resolved['set_id'],
        defense=resolved['defense'],
        max_dur=resolved['max_dur'],
        cur_dur=resolved['max_dur'],
        properties=props,
        ethereal=item_def.get('ethereal', False),
    )
    return [('char', item_bytes)]


def _build_rare(item_def, slot):
    """Build a rare item (quality=6)."""
    props = resolve_properties(item_def.get('properties', {}))

    base_code = item_def.get('base', RARE_SLOT_BASES.get(item_def['slot']))
    if base_code is None:
        raise ValueError(
            f"No base code for rare item in slot '{item_def['slot']}'. "
            f"Specify 'base' in the item definition."
        )

    base_info = ITEM_BASES[base_code]

    first, last = _resolve_rare_names(
        item_def.get('rare_first_name', 0),
        item_def.get('rare_last_name', 0),
        base_code, props,
    )

    item_bytes = build_item(
        type_code=base_code,
        col=0, row=0, storage=0,
        location=1, bodyloc=slot['bodyloc'],
        quality=6,
        ilvl=item_def.get('ilvl', 99),
        defense=item_def.get('defense', base_info.get('max_ac', 0)),
        max_dur=base_info.get('durability', 0),
        cur_dur=base_info.get('durability', 0),
        properties=props,
        rare_first_name=first,
        rare_last_name=last,
        ethereal=item_def.get('ethereal', False),
    )
    return [('char', item_bytes)]


def _build_magic(item_def, slot):
    """Build a magic item (quality=4)."""
    props = resolve_properties(item_def.get('properties', {}))

    base_code = item_def.get('base', RARE_SLOT_BASES.get(item_def['slot']))
    if base_code is None:
        raise ValueError(
            f"No base code for magic item in slot '{item_def['slot']}'. "
            f"Specify 'base' in the item definition."
        )

    base_info = ITEM_BASES[base_code]

    prefix, suffix = _resolve_magic_affixes(
        item_def.get('magic_prefix', 0),
        item_def.get('magic_suffix', 0),
        base_code, props,
    )

    item_bytes = build_item(
        type_code=base_code,
        col=0, row=0, storage=0,
        location=1, bodyloc=slot['bodyloc'],
        quality=4,
        ilvl=item_def.get('ilvl', 99),
        defense=item_def.get('defense', base_info.get('max_ac', 0)),
        max_dur=base_info.get('durability', 0),
        cur_dur=base_info.get('durability', 0),
        properties=props,
        magic_prefix=prefix,
        magic_suffix=suffix,
        ethereal=item_def.get('ethereal', False),
    )
    return [('char', item_bytes)]


def _build_crafted(item_def, slot):
    """Build a crafted item (quality=8)."""
    props = resolve_properties(item_def.get('properties', {}))

    base_code = item_def.get('base', RARE_SLOT_BASES.get(item_def['slot']))
    if base_code is None:
        raise ValueError(
            f"No base code for crafted item in slot '{item_def['slot']}'. "
            f"Specify 'base' in the item definition."
        )

    base_info = ITEM_BASES[base_code]

    first, last = _resolve_rare_names(
        item_def.get('rare_first_name', 0),
        item_def.get('rare_last_name', 0),
        base_code, props,
    )

    item_bytes = build_item(
        type_code=base_code,
        col=0, row=0, storage=0,
        location=1, bodyloc=slot['bodyloc'],
        quality=8,
        ilvl=item_def.get('ilvl', 99),
        defense=base_info.get('max_ac', 0),
        max_dur=base_info.get('durability', 0),
        cur_dur=base_info.get('durability', 0),
        properties=props,
        rare_first_name=first,
        rare_last_name=last,
        ethereal=item_def.get('ethereal', False),
    )
    return [('char', item_bytes)]


def build_charm(charm_def, col, row):
    """Build a charm item from a YAML definition.

    Charms are stored in inventory (storage=1, location=0).

    Args:
        charm_def: Dict with either 'unique' key or one of
            'magic_small_charm', 'magic_large_charm', 'magic_grand_charm'.
        col: Inventory grid column (0-based).
        row: Inventory grid row (0-based).

    Returns:
        List of (section, bytes) tuples. Section is always 'char'.
    """
    if 'unique' in charm_def:
        resolved = resolve_unique(charm_def['unique'])
        props = _resolve_final_properties(charm_def, resolved['properties'], has_canonical=True)
        charm_bytes = build_item(
            type_code=resolved['type_code'],
            col=col, row=row, storage=1,  # inventory
            location=0,
            quality=7,
            unique_id=resolved['unique_id'],
            defense=0,
            max_dur=0,
            cur_dur=0,
            properties=props,
        )
        return [('char', charm_bytes)]

    for key in ('magic_small_charm', 'magic_large_charm', 'magic_grand_charm'):
        if key in charm_def:
            charm_info = charm_def[key]
            type_code = _CHARM_TYPE_CODES[key]
            props = resolve_properties(charm_info.get('properties', {}))

            prefix, suffix = _resolve_magic_affixes(
                charm_info.get('magic_prefix', 0),
                charm_info.get('magic_suffix', 0),
                type_code, props,
            )

            charm_bytes = build_item(
                type_code=type_code,
                col=col, row=row, storage=1,  # inventory
                location=0,
                quality=4,  # magic
                properties=props,
                magic_prefix=prefix,
                magic_suffix=suffix,
            )
            return [('char', charm_bytes)]

    raise ValueError(
        f"Cannot determine charm type from keys: {list(charm_def.keys())}"
    )


def build_merc_item(item_def, stash_col, stash_row):
    """Build a merc item placed in stash for manual equipping.

    CRITICAL (Rule 6): Merc gear MUST go in the char JM section (storage=5,
    stash) -- NOT the merc JM section. Pre-injected merc JM items cause
    Error:8. User equips merc gear in-game from stash.

    Args:
        item_def: Dict with slot, quality type key, and optional properties.
            Same format as build_equipment_item.
        stash_col: Stash grid column (0-based).
        stash_row: Stash grid row (0-based).

    Returns:
        List of (section, bytes) tuples. Section is always 'char'.
    """
    if 'runeword' in item_def:
        return _build_merc_runeword(item_def, stash_col, stash_row)
    elif 'unique' in item_def:
        return _build_merc_unique(item_def, stash_col, stash_row)
    elif 'set' in item_def:
        return _build_merc_set(item_def, stash_col, stash_row)
    elif 'rare' in item_def:
        return _build_merc_rare(item_def, stash_col, stash_row)
    elif 'magic_prefix' in item_def or 'magic_suffix' in item_def:
        return _build_merc_magic(item_def, stash_col, stash_row)
    elif 'normal' in item_def:
        return _build_merc_normal(item_def, stash_col, stash_row)
    else:
        raise ValueError(
            f"Cannot determine merc item quality type from keys: "
            f"{list(item_def.keys())}"
        )


def _build_merc_runeword(item_def, col, row):
    """Build a merc runeword item in stash."""
    name = item_def['runeword']
    base_code = item_def['base']
    resolved = resolve_runeword(name, base_code)

    props = _resolve_final_properties(item_def, resolved['properties'], has_canonical=True)

    parent_bytes = build_item(
        type_code=base_code,
        col=col, row=row, storage=5,  # stash
        location=0, bodyloc=0,
        quality=2,
        ilvl=item_def.get('ilvl', 99),
        socketed=True,
        num_sockets=resolved['num_sockets'],
        runeword=True,
        runeword_id=resolved['runeword_id'],
        defense=resolved['defense'],
        max_dur=resolved['max_dur'],
        cur_dur=resolved['max_dur'],
        properties=props,
        ethereal=item_def.get('ethereal', False),
        rune_codes=resolved['rune_codes'],
    )
    items = [('char', parent_bytes)]

    for idx, rune_code in enumerate(resolved['rune_codes']):
        filler = encode_socketed_rune(rune_code, socket_idx=idx)
        items.append(('char', filler))

    return items


def _build_merc_unique(item_def, col, row):
    """Build a merc unique item in stash."""
    name = item_def['unique']
    resolved = resolve_unique(name)

    props = _resolve_final_properties(item_def, resolved['properties'], has_canonical=True)

    item_bytes = build_item(
        type_code=resolved['type_code'],
        col=col, row=row, storage=5,  # stash
        location=0, bodyloc=0,
        quality=7,
        ilvl=item_def.get('ilvl', 99),
        unique_id=resolved['unique_id'],
        defense=item_def.get('defense', resolved['defense']),
        max_dur=resolved['max_dur'],
        cur_dur=resolved['max_dur'],
        properties=props,
        ethereal=item_def.get('ethereal', False),
    )
    return [('char', item_bytes)]


def _build_merc_set(item_def, col, row):
    """Build a merc set item in stash."""
    name = item_def['set']
    resolved = resolve_set_item(name)

    if 'properties' not in item_def:
        raise ValueError(
            f"Set item '{name}' requires explicit 'properties:' "
            f"(no auto-resolved stats for set items)"
        )
    props = resolve_properties(item_def['properties'])

    item_bytes = build_item(
        type_code=resolved['type_code'],
        col=col, row=row, storage=5,  # stash
        location=0, bodyloc=0,
        quality=5,
        ilvl=item_def.get('ilvl', 99),
        set_id=resolved['set_id'],
        defense=resolved['defense'],
        max_dur=resolved['max_dur'],
        cur_dur=resolved['max_dur'],
        properties=props,
        ethereal=item_def.get('ethereal', False),
    )
    return [('char', item_bytes)]


def _build_merc_rare(item_def, col, row):
    """Build a merc rare item in stash."""
    props = resolve_properties(item_def.get('properties', {}))

    base_code = item_def.get('base')
    if base_code is None:
        raise ValueError("Merc rare items must specify 'base' code.")

    base_info = ITEM_BASES[base_code]

    first, last = _resolve_rare_names(
        item_def.get('rare_first_name', 0),
        item_def.get('rare_last_name', 0),
        base_code, props,
    )

    item_bytes = build_item(
        type_code=base_code,
        col=col, row=row, storage=5,  # stash
        location=0, bodyloc=0,
        quality=6,
        ilvl=item_def.get('ilvl', 99),
        defense=item_def.get('defense', base_info.get('max_ac', 0)),
        max_dur=base_info.get('durability', 0),
        cur_dur=base_info.get('durability', 0),
        properties=props,
        rare_first_name=first,
        rare_last_name=last,
        ethereal=item_def.get('ethereal', False),
    )
    return [('char', item_bytes)]


def _build_merc_magic(item_def, col, row):
    """Build a merc magic item in stash."""
    props = resolve_properties(item_def.get('properties', {}))

    base_code = item_def.get('base')
    if base_code is None:
        raise ValueError("Merc magic items must specify 'base' code.")

    base_info = ITEM_BASES[base_code]

    prefix, suffix = _resolve_magic_affixes(
        item_def.get('magic_prefix', 0),
        item_def.get('magic_suffix', 0),
        base_code, props,
    )

    item_bytes = build_item(
        type_code=base_code,
        col=col, row=row, storage=5,  # stash
        location=0, bodyloc=0,
        quality=4,
        ilvl=item_def.get('ilvl', 99),
        defense=base_info.get('max_ac', 0),
        max_dur=base_info.get('durability', 0),
        cur_dur=base_info.get('durability', 0),
        properties=props,
        magic_prefix=prefix,
        magic_suffix=suffix,
        ethereal=item_def.get('ethereal', False),
    )
    return [('char', item_bytes)]


def _build_merc_normal(item_def, col, row):
    """Build a normal (quality=2) item in stash.

    Used for quest/misc items like Worldstone Shards, essences,
    Uber Ancient materials, etc.
    """
    base_code = item_def.get('base')
    if base_code is None:
        raise ValueError("Normal items must specify 'base' code.")

    base_info = ITEM_BASES[base_code]

    item_bytes = build_item(
        type_code=base_code,
        col=col, row=row, storage=5,  # stash
        location=0, bodyloc=0,
        quality=2,
        ilvl=item_def.get('ilvl', 99),
        defense=base_info.get('max_ac', 0),
        max_dur=base_info.get('durability', 0),
        cur_dur=base_info.get('durability', 0),
    )
    return [('char', item_bytes)]
