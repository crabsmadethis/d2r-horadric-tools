"""D2R character orchestrator: YAML loading, validation, item building, deployment.

Reads YAML character definitions, builds all items (equipment, charms, merc),
creates/updates the .d2s file, and deploys items in phases.
"""
import os
import shutil
import struct

import yaml
from d2r_chargen.config import (
    SAVES, CHARS_DIR, SLOT_MAP, CLASS_DEFS, PROPERTY_ALIASES, CHARM_DIMS,
)
from d2r_chargen.resolve import (
    resolve_property_name, resolve_skills, resolve_runeword, resolve_unique,
)
from d2r_chargen.items import build_equipment_item, build_charm, build_merc_item
from d2r_chargen.data.item_bases import ITEM_BASES
from d2r_chargen.data.item_stat_cost import STAT_BY_NAME
from d2r_chargen.data.skills import SKILLS

# Known unique charm names -> (type_code, fixed_col, fixed_row)
_UNIQUE_CHARM_POSITIONS = {
    'annihilus':            ('cm1', 9, 2),
    'hellfire torch':      ('cm2', 9, 0),
    'gheed\'s fortune':    ('cm3', 8, 0),
    'crack of the heavens': ('cm3', 8, 0),
    'black cleft':         ('cm3', 8, 0),
}

# Inventory grid: 10 cols x 4 rows
_INV_COLS = 10
_INV_ROWS = 4

# Stash grid: 10 cols x 8 rows
_STASH_COLS = 10
_STASH_ROWS = 8

_REQUIRED_FIELDS = ('name', 'class', 'level', 'stats', 'equipment')
_REQUIRED_STATS = ('strength', 'dexterity', 'vitality', 'energy')


def load_character_yaml(path):
    """Parse a YAML character definition file and validate structure.

    Validates schema_version == 1 and checks all required fields are present.
    If a merc template is referenced, resolves it into inline equipment.

    Args:
        path: Path to the .yaml file.

    Returns:
        Parsed dict with character definition.

    Raises:
        ValueError: If schema_version is wrong or required fields are missing.
        FileNotFoundError: If the YAML file doesn't exist.
    """
    with open(path, 'r') as f:
        char_def = yaml.safe_load(f)

    if not isinstance(char_def, dict):
        raise ValueError(f"YAML file must contain a mapping, got {type(char_def)}")

    # Validate schema version
    sv = char_def.get('schema_version')
    if sv != 1:
        raise ValueError(
            f"Unsupported schema_version: {sv}. Expected 1."
        )

    # Check required fields
    missing = [field for field in _REQUIRED_FIELDS if field not in char_def]
    if missing:
        raise ValueError(
            f"Missing required fields: {', '.join(missing)}"
        )

    # Check required stat sub-fields
    stats = char_def.get('stats', {})
    if not isinstance(stats, dict):
        raise ValueError("'stats' must be a mapping")
    missing_stats = [s for s in _REQUIRED_STATS if s not in stats]
    if missing_stats:
        raise ValueError(
            f"Missing required stats: {', '.join(missing_stats)}"
        )

    # Resolve merc template if referenced
    merc = char_def.get('merc')
    if merc and isinstance(merc, dict) and 'template' in merc:
        _resolve_merc_template(char_def)

    return char_def


def _resolve_merc_template(char_def):
    """Resolve a merc template reference into inline equipment.

    Loads the template from d2r_chars/merc_templates.yaml and merges it
    into the character definition.
    """
    merc = char_def['merc']
    template_name = merc['template']

    templates_path = os.path.join(CHARS_DIR, 'merc_templates.yaml')
    if not os.path.exists(templates_path):
        raise FileNotFoundError(
            f"Merc templates file not found: {templates_path}"
        )

    with open(templates_path, 'r') as f:
        templates = yaml.safe_load(f)

    if template_name not in templates:
        raise ValueError(
            f"Merc template '{template_name}' not found in {templates_path}"
        )

    template = templates[template_name]

    # Merge template into merc definition
    if 'type' not in merc and 'type' in template:
        merc['type'] = template['type']
    if 'equipment' not in merc and 'equipment' in template:
        merc['equipment'] = template['equipment']

    char_def['merc'] = merc


def validate_char_def(char_def):
    """Run validation checks on a character definition.

    Checks:
    - Class is valid
    - Slot names exist in SLOT_MAP
    - Skill names belong to the character's class
    - Property names are valid (alias or STAT_BY_NAME key)
    - No item has both 'properties' and 'extra_properties'

    Args:
        char_def: Parsed character definition dict.

    Raises:
        ValueError: If any validation check fails.
    """
    errors = []

    # Validate class
    class_name = char_def.get('class', '').lower()
    if class_name not in CLASS_DEFS:
        raise ValueError(
            f"Unknown class: '{char_def.get('class')}'. "
            f"Valid classes: {', '.join(CLASS_DEFS.keys())}"
        )

    # Validate skills
    cdef = CLASS_DEFS[class_name]
    skill_code = cdef['skill_code']
    for skill_name in char_def.get('skills', {}):
        # Check skill exists
        found = False
        for sid, sinfo in SKILLS.items():
            if sinfo['name'] == skill_name:
                found = True
                if sinfo.get('class') != skill_code:
                    if sinfo.get('class'):
                        # Find class name for error
                        actual_class = 'unknown'
                        for cn, cd in CLASS_DEFS.items():
                            if cd['skill_code'] == sinfo['class']:
                                actual_class = cn
                                break
                    else:
                        actual_class = 'generic'
                    errors.append(
                        f"Skill '{skill_name}' belongs to {actual_class}, "
                        f"not {class_name}"
                    )
                break
        if not found:
            errors.append(f"Unknown skill: '{skill_name}'")

    # Validate equipment items
    for item_def in char_def.get('equipment', []):
        _validate_item_def(item_def, errors)

    # Validate inventory (charms)
    inventory = char_def.get('inventory', {})
    if isinstance(inventory, dict):
        for charm_def in inventory.get('charms', []):
            _validate_charm_properties(charm_def, errors)

    # Validate merc equipment
    merc = char_def.get('merc', {})
    if isinstance(merc, dict):
        for item_def in merc.get('equipment', []):
            _validate_item_def(item_def, errors)

    if errors:
        raise ValueError(
            "Validation errors:\n  " + "\n  ".join(errors)
        )

    # Level-req warnings (non-fatal)
    char_level = char_def.get('level', 99)
    _warn_level_reqs(char_def.get('equipment', []), char_level, 'equipment')
    if isinstance(inventory, dict):
        _warn_level_reqs(inventory.get('charms', []), char_level, 'inventory')
    if isinstance(merc, dict):
        _warn_level_reqs(merc.get('equipment', []), char_level, 'merc/stash')


def _warn_level_reqs(items, char_level, section):
    """Warn if any item's base levelreq exceeds the character level."""
    for item_def in items:
        base_code = item_def.get('base', '')
        if not base_code:
            # Resolve from unique/set/runeword
            if 'unique' in item_def:
                try:
                    info = resolve_unique(item_def['unique'])
                    base_code = info['type_code']
                except ValueError:
                    continue
            elif 'runeword' in item_def:
                base_code = item_def.get('base', '')
        if not base_code:
            continue
        base_info = ITEM_BASES.get(base_code.strip())
        if base_info:
            levelreq = base_info.get('levelreq', 0)
            if levelreq > char_level:
                name = item_def.get('unique', item_def.get('runeword',
                       item_def.get('base', '?')))
                print(f"  WARNING: {section} item '{name}' (base {base_code}, "
                      f"levelreq={levelreq}) exceeds character level {char_level}")


def _validate_item_def(item_def, errors):
    """Validate a single equipment item definition. Appends to errors list."""
    # Check slot
    slot = item_def.get('slot')
    if slot and slot not in SLOT_MAP:
        errors.append(f"Unknown slot: '{slot}'")

    # Check properties/extra_properties mutual exclusion
    if 'properties' in item_def and 'extra_properties' in item_def:
        errors.append(
            f"Item in slot '{slot}' has both 'properties' and "
            f"'extra_properties' -- use one or the other"
        )

    # Validate property names
    for key in ('properties', 'extra_properties'):
        props = item_def.get(key)
        if isinstance(props, dict):
            for prop_name in props:
                try:
                    resolve_property_name(prop_name)
                except ValueError:
                    errors.append(f"Unknown property: '{prop_name}'")


def _validate_charm_properties(charm_def, errors):
    """Validate charm property names."""
    for key in ('magic_small_charm', 'magic_large_charm', 'magic_grand_charm'):
        charm_info = charm_def.get(key)
        if isinstance(charm_info, dict):
            props = charm_info.get('properties', {})
            if isinstance(props, dict):
                for prop_name in props:
                    try:
                        resolve_property_name(prop_name)
                    except ValueError:
                        errors.append(f"Unknown charm property: '{prop_name}'")


def _get_charm_type_code(charm_def):
    """Determine the charm type code from a charm definition.

    Returns:
        String type code: 'cm1', 'cm2', or 'cm3'.
    """
    if 'unique' in charm_def:
        name_lower = charm_def['unique'].lower()
        resolved = resolve_unique(charm_def['unique'])
        return resolved['type_code']
    for key, code in (('magic_small_charm', 'cm1'),
                      ('magic_large_charm', 'cm2'),
                      ('magic_grand_charm', 'cm3')):
        if key in charm_def:
            return code
    raise ValueError(f"Cannot determine charm type from keys: {list(charm_def.keys())}")


def _expand_charms(charms):
    """Expand charm definitions with count: N into individual charm defs.

    A magic charm with count: 8 becomes 8 separate charm defs (count removed).
    Unique charms and charms without count pass through unchanged.

    Returns:
        List of individual charm definition dicts.
    """
    expanded = []
    for charm_def in charms:
        for key in ('magic_small_charm', 'magic_grand_charm', 'magic_large_charm'):
            if key in charm_def:
                charm_info = charm_def[key]
                count = charm_info.get('count', 1)
                # Create individual charm defs without count
                single_info = {k: v for k, v in charm_info.items() if k != 'count'}
                for _ in range(count):
                    expanded.append({key: single_info})
                break
        else:
            # Unique charm or other — pass through as-is
            expanded.append(charm_def)
    return expanded


def _calculate_charm_positions(charms):
    """Calculate inventory grid positions for a list of charms.

    Algorithm:
    1. Unique charms first at fixed positions (Annihilus, Torch, Gheed's, etc.)
    2. Grand charms (cm3, 1x3) in columns 0-7, row 0
    3. Small charms (cm1, 1x1) fill row 3 (cols 0-9), then remaining gaps

    Args:
        charms: List of EXPANDED charm definition dicts (no count: N).

    Returns:
        List of (col, row) tuples, one per charm, in same order as input.

    Raises:
        ValueError: If charms don't fit in the 10x4 inventory grid.
    """
    if not charms:
        return []

    # Track occupied cells
    grid = [[False] * _INV_ROWS for _ in range(_INV_COLS)]

    def occupy(col, row, w, h):
        for dc in range(w):
            for dr in range(h):
                c, r = col + dc, row + dr
                if c >= _INV_COLS or r >= _INV_ROWS:
                    raise ValueError(
                        f"Charm at ({col},{row}) size ({w},{h}) "
                        f"exceeds inventory bounds"
                    )
                if grid[c][r]:
                    raise ValueError(
                        f"Charm collision at ({c},{r})"
                    )
                grid[c][r] = True

    def is_free(col, row, w, h):
        for dc in range(w):
            for dr in range(h):
                c, r = col + dc, row + dr
                if c >= _INV_COLS or r >= _INV_ROWS:
                    return False
                if grid[c][r]:
                    return False
        return True

    # Categorize charms by type, preserving original index
    unique_charms = []  # (index, charm_def, type_code, w, h)
    grand_charms = []
    large_charms = []
    small_charms = []

    for idx, charm_def in enumerate(charms):
        tc = _get_charm_type_code(charm_def)
        w, h = CHARM_DIMS.get(tc, (1, 1))

        if 'unique' in charm_def:
            unique_charms.append((idx, charm_def, tc, w, h))
        elif tc == 'cm3':
            grand_charms.append((idx, charm_def, tc, w, h))
        elif tc == 'cm2':
            large_charms.append((idx, charm_def, tc, w, h))
        else:
            small_charms.append((idx, charm_def, tc, w, h))

    # Result: index -> (col, row)
    positions = [None] * len(charms)

    # 1. Place unique charms at fixed positions
    for idx, charm_def, tc, w, h in unique_charms:
        name_lower = charm_def['unique'].lower()
        if name_lower in _UNIQUE_CHARM_POSITIONS:
            _, fc, fr = _UNIQUE_CHARM_POSITIONS[name_lower]
            occupy(fc, fr, w, h)
            positions[idx] = (fc, fr)
        else:
            # Unknown unique charm -- treat as its size category
            if tc == 'cm3':
                grand_charms.append((idx, charm_def, tc, w, h))
            elif tc == 'cm2':
                large_charms.append((idx, charm_def, tc, w, h))
            else:
                small_charms.append((idx, charm_def, tc, w, h))

    # 2. Place grand charms (1x3) in columns 0-7, row 0
    gc_col = 0
    for idx, charm_def, tc, w, h in grand_charms:
        placed = False
        while gc_col <= 7:
            if is_free(gc_col, 0, w, h):
                occupy(gc_col, 0, w, h)
                positions[idx] = (gc_col, 0)
                gc_col += 1
                placed = True
                break
            gc_col += 1
        if not placed:
            raise ValueError(
                f"No space for grand charm (index {idx}) in inventory. "
                f"Columns 0-7 at row 0 are full."
            )

    # 3. Place large charms (1x2) in remaining space
    for idx, charm_def, tc, w, h in large_charms:
        placed = False
        for col in range(_INV_COLS):
            for row in range(_INV_ROWS):
                if is_free(col, row, w, h):
                    occupy(col, row, w, h)
                    positions[idx] = (col, row)
                    placed = True
                    break
            if placed:
                break
        if not placed:
            raise ValueError(
                f"No space for large charm (index {idx}) in inventory."
            )

    # 4. Place small charms (1x1): row 3 first (cols 0-9), then remaining gaps
    sc_positions = []
    # Row 3 first
    for col in range(_INV_COLS):
        if is_free(col, 3, 1, 1):
            sc_positions.append((col, 3))
    # Then remaining cells row by row
    for row in range(_INV_ROWS - 1):  # rows 0, 1, 2
        for col in range(_INV_COLS):
            if is_free(col, row, 1, 1):
                sc_positions.append((col, row))

    sc_idx = 0
    for idx, charm_def, tc, w, h in small_charms:
        if sc_idx >= len(sc_positions):
            raise ValueError(
                f"No space for small charm (index {idx}) in inventory."
            )
        col, row = sc_positions[sc_idx]
        occupy(col, row, 1, 1)
        positions[idx] = (col, row)
        sc_idx += 1

    return positions


def _get_merc_item_dimensions(item_def):
    """Get (width, height) for a merc item based on its type code.

    For unique items, looks up the base from resolve_unique.
    For runeword items, uses the 'base' key directly.
    For rare/magic items, uses the 'base' key.
    """
    if 'unique' in item_def:
        resolved = resolve_unique(item_def['unique'])
        tc = resolved['type_code']
    elif 'base' in item_def:
        tc = item_def['base']
    else:
        raise ValueError(f"Cannot determine base type for merc item: {item_def}")

    base_info = ITEM_BASES.get(tc)
    if not base_info:
        raise ValueError(f"Unknown base type code: '{tc}'")
    return (base_info.get('width', 1), base_info.get('height', 1))


def _calculate_merc_stash_positions(merc_items):
    """Calculate stash grid positions for merc items.

    Places items left-to-right, top-to-bottom in the 10x8 stash grid.

    Args:
        merc_items: List of merc item definition dicts.

    Returns:
        List of (col, row) tuples, one per item.

    Raises:
        ValueError: If items don't fit in the stash grid.
    """
    if not merc_items:
        return []

    grid = [[False] * _STASH_ROWS for _ in range(_STASH_COLS)]
    positions = []

    def is_free(col, row, w, h):
        for dc in range(w):
            for dr in range(h):
                c, r = col + dc, row + dr
                if c >= _STASH_COLS or r >= _STASH_ROWS:
                    return False
                if grid[c][r]:
                    return False
        return True

    def occupy(col, row, w, h):
        for dc in range(w):
            for dr in range(h):
                grid[col + dc][row + dr] = True

    for item_def in merc_items:
        w, h = _get_merc_item_dimensions(item_def)
        placed = False
        # Scan left-to-right, top-to-bottom
        for row in range(_STASH_ROWS):
            for col in range(_STASH_COLS):
                if is_free(col, row, w, h):
                    occupy(col, row, w, h)
                    positions.append((col, row))
                    placed = True
                    break
            if placed:
                break
        if not placed:
            raise ValueError(
                f"No space in stash for merc item: {item_def}"
            )

    return positions


def build_all_items(char_def):
    """Build all items for a character definition.

    Iterates:
    1. Equipment -> build_equipment_item()
    2. Inventory charms -> build_charm() with auto-calculated grid positions
    3. Merc equipment -> build_merc_item() with stash positions

    Args:
        char_def: Validated character definition dict.

    Returns:
        List of (section, bytes) tuples. Section is always 'char'.
    """
    all_items = []

    # 1. Build equipment items
    for item_def in char_def.get('equipment', []):
        items = build_equipment_item(item_def)
        all_items.extend(items)

    # 2. Build inventory charms (expand count: N into individual defs)
    inventory = char_def.get('inventory', {})
    raw_charms = inventory.get('charms', []) if isinstance(inventory, dict) else []
    charms = _expand_charms(raw_charms)
    if charms:
        positions = _calculate_charm_positions(charms)
        for i, charm_def in enumerate(charms):
            col, row = positions[i]
            items = build_charm(charm_def, col=col, row=row)
            all_items.extend(items)

    # 3. Build merc items (placed in stash)
    merc = char_def.get('merc', {})
    merc_equipment = []
    if isinstance(merc, dict):
        merc_equipment = merc.get('equipment', [])
    if merc_equipment:
        stash_positions = _calculate_merc_stash_positions(merc_equipment)
        for i, item_def in enumerate(merc_equipment):
            col, row = stash_positions[i]
            items = build_merc_item(item_def, stash_col=col, stash_row=row)
            all_items.extend(items)

    return all_items


def deploy_character(char_name, phase=4, force=False):
    """Build and deploy a character from YAML definition.

    Pipeline:
    1. Load and validate YAML
    2. Build all items
    3. Find or create the .d2s file
    4. Set stats, skills, waypoints, quests, difficulty
    5. Deploy items in phases (equipped -> swap -> inventory -> stash)

    Args:
        char_name: Character name (matches d2r_chars/{char_name}.yaml).
        phase: Deploy up to this phase (1-4). Default: 4.
        force: Skip freshness gate check. Default: False.

    Returns:
        True on success, False on failure.
    """
    from d2r_chargen.save import (
        create_new_character, set_character_stats, set_skills,
        set_waypoints, set_quests, set_difficulty,
        rebuild_items, calc_checksum,
    )
    from d2r_chargen.scanner import decode_item_header, bits_at

    # Load and validate
    yaml_path = os.path.join(CHARS_DIR, f"{char_name}.yaml")

    # Freshness gate: peek at raw YAML for import metadata before full validation.
    # This must happen before load_character_yaml (which requires 'equipment').
    if not force:
        with open(yaml_path, 'r') as _f:
            _raw = yaml.safe_load(_f)
        if isinstance(_raw, dict) and '_imported_at' in _raw and '_imported_checksum' in _raw:
            _char_name_in_yaml = _raw.get('name', char_name)
            _d2s_path = os.path.join(SAVES, f"{_char_name_in_yaml}.d2s")
            if os.path.exists(_d2s_path):
                _current_data = open(_d2s_path, 'rb').read()
                _current_cs = f"0x{struct.unpack_from('<I', _current_data, 12)[0]:08X}"
                _stored_cs = _raw['_imported_checksum']
                if _current_cs != _stored_cs:
                    print(f"  ERROR: {_char_name_in_yaml}.d2s has changed since "
                          f"{os.path.basename(yaml_path)} was imported.")
                    print(f"  Stored checksum: {_stored_cs}, current: {_current_cs}")
                    print(f"  Game progress would be lost. Run "
                          f"'python3 -m d2r_chargen import {_char_name_in_yaml}' first.")
                    print(f"  (Use --force to override)")
                    return False

    char_def = load_character_yaml(yaml_path)
    validate_char_def(char_def)

    # Build all items
    all_items = build_all_items(char_def)

    # Find or create the .d2s file
    char_path = os.path.join(SAVES, f"{char_def['name']}.d2s")

    # Determine template (use existing character as template if available)
    is_new_character = not os.path.exists(char_path)
    if is_new_character:
        template = char_def.get('template')
        if template:
            template_path = os.path.join(SAVES, template)
        else:
            # Try to find any existing .d2s, fall back to bundled blank template
            existing = [f for f in os.listdir(SAVES) if f.endswith('.d2s')]
            if existing:
                template_path = os.path.join(SAVES, existing[0])
            else:
                template_path = os.path.join(
                    os.path.dirname(__file__), 'data', 'template.d2s'
                )
                print(f"  Using bundled blank template")

        class_id = CLASS_DEFS[char_def['class']]['id']
        char_path = create_new_character(template_path, char_def['name'], class_id)

    # Set character data (stats, skills, waypoints, quests, difficulty)
    data = bytearray(open(char_path, 'rb').read())

    skill_array = resolve_skills(char_def['class'], char_def.get('skills', {}))
    skill_points_spent = sum(skill_array)

    stats = char_def['stats']
    data = set_character_stats(
        data, stats['strength'], stats['dexterity'],
        stats['vitality'], stats['energy'],
        level=char_def.get('level', 99),
        char_class=char_def['class'],
        skill_points_spent=skill_points_spent,
    )
    data = set_skills(data, skill_array)

    # Only set waypoints/quests/difficulty for NEW characters.
    # Existing characters preserve their in-game progress.
    difficulty = char_def.get('difficulty', 'hell')
    if is_new_character:
        data = set_waypoints(data, difficulty)
        data = set_quests(data, difficulty)
        data = set_difficulty(data, difficulty)
    else:
        print(f"  Preserving existing WP/quest/difficulty progress")

    # Write updated base data
    struct.pack_into('<I', data, 8, len(data))
    data[12:16] = b'\x00\x00\x00\x00'
    cs = calc_checksum(data)
    struct.pack_into('<I', data, 12, cs)

    # Backup (Rule 3)
    bak = f"{char_path}.pre_chargen_bak"
    shutil.copy2(char_path, bak)

    with open(char_path, 'wb') as f:
        f.write(data)

    # Deploy items in phases
    # Phase 1: equipped (storage=0, bodyloc not in 11,12)
    # Phase 2: + swap (bodyloc 11,12)
    # Phase 3: + inventory charms (storage=1)
    # Phase 4: + merc stash items (storage=5)

    def get_phase_items(all_items, phase_num):
        result = []
        parent_included = False
        for section, item_bytes in all_items:
            is_filler = bits_at(item_bytes, 21, 1) if len(item_bytes) > 3 else 0
            if is_filler:
                if parent_included:
                    result.append(item_bytes)
                continue
            hdr = decode_item_header(item_bytes, 0)
            itype, ilvl, quality, uid, storage, col, row, bodyloc, location, ext = hdr
            include = False
            if storage == 0 and bodyloc not in (11, 12):
                include = True  # equipped
            if storage == 0 and bodyloc in (11, 12) and phase_num >= 2:
                include = True  # swap
            if storage == 1 and phase_num >= 3:
                include = True  # inventory
            if storage == 5 and phase_num >= 4:
                include = True  # merc stash
            parent_included = include
            if include:
                result.append(item_bytes)
        return result

    for p in range(1, phase + 1):
        phase_items = get_phase_items(all_items, p)

        # Backup before each phase (Rule 3)
        bak = f"{char_path}.pre_phase{p}_bak"
        shutil.copy2(char_path, bak)

        # Write to temp, verify, then overwrite (Rule 10)
        temp_path = f"/tmp/{char_def['name']}_phase{p}.d2s"
        try:
            shutil.copy2(char_path, temp_path)

            # CRITICAL: All items go as char_items, empty merc list (Rule 6)
            result = rebuild_items(temp_path, phase_items, [])

            with open(temp_path, 'wb') as f:
                f.write(result)

            # Verify checksum (Rule 5)
            cs_stored = struct.unpack_from('<I', result, 12)[0]
            cs_calc = calc_checksum(result)
            if cs_stored != cs_calc:
                print(f"  CHECKSUM MISMATCH in phase {p}")
                return False

            shutil.copy2(temp_path, char_path)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
        print(f"  Phase {p}: deployed {len(phase_items)} items, checksum OK")

        # Run scanner after each phase (Rule 4)
        try:
            from d2r_chargen.scanner import scan_character_data
            result = scan_character_data(char_path)
            scan_errors = result.get('errors', [])
            scan_warnings = result.get('warnings', [])
            if scan_errors:
                print(f"  SCANNER ERRORS in phase {p}:")
                for err in scan_errors:
                    print(f"    {err}")
                print(f"  Restoring from backup: {bak}")
                shutil.copy2(bak, char_path)
                return False
            if scan_warnings:
                for w in scan_warnings:
                    print(f"  WARNING: {w}")
            print(f"  Phase {p}: scanner passed ({result['item_count']} items, checksum {'OK' if result['checksum_ok'] else 'FAIL'})")
        except ImportError:
            print(f"  WARNING: d2r_scanner not available, skipping scan")

    print(f"\n  {char_def['name']} deployed successfully!")
    print(f"  ** Fully restart D2R to test (Rule 7) **")
    return True
