"""D2R character orchestrator: YAML loading, validation, item building, deployment.

Reads YAML character definitions, builds all items (equipment, charms, merc),
creates/updates the .d2s file, and deploys items in phases.
"""
import os
import shutil
import struct
import sys

from d2r_chargen.config import (
    SAVES, CHARS_DIR, FIXTURES_DIR, SLOT_MAP, CLASS_DEFS, CHARM_DIMS,
)
from d2r_chargen.resolve import (
    bound_demon_synthesis_support_error,
    is_bound_demon_validated_package_request,
    encode_skill_tab_param, resolve_properties, resolve_property_name,
    resolve_runeword, resolve_skills, resolve_unique, resolve_progression,
    resolve_bound_demon,
)
from d2r_chargen.items import (
    build_equipment_item, build_charm, build_merc_item, build_iron_golem_item,
)
from d2r_chargen.data.item_bases import ITEM_BASES
from d2r_chargen.data.item_stat_cost import STAT_BY_NAME
from d2r_chargen.data.skills import SKILLS

# Strict fixed positions — collision is a build error.
_UNIQUE_CHARM_POSITIONS = {
    'annihilus':            ('cm1', 9, 2),
    'hellfire torch':      ('cm2', 9, 0),
    'gheed\'s fortune':    ('cm3', 8, 0),
}

# Preferred positions — placed at (col,row) when free, otherwise fall
# through to generic same-size placement. Multiple sunders from this
# triple can coexist because only the first claims col 8; the rest
# overflow into cols 0-7.
_PREFERRED_CHARM_POSITIONS = {
    'crack of the heavens': ('cm3', 8, 0),
    'black cleft':         ('cm3', 8, 0),
    'flame rift':          ('cm3', 8, 0),
}

# Sunder charm names (all variants). Used by max_level_defaults to warn
# when a build specifies no sunder.
_SUNDER_CHARM_NAMES = frozenset([
    'black cleft',         # magic
    'flame rift',          # fire
    'cold rupture',        # cold
    'crack of the heavens',  # lightning
    'bone break',          # physical
    'rotting fissure',     # poison
])

# Inventory grid: 10 cols x 4 rows
_INV_COLS = 10
_INV_ROWS = 4

# Stash grid: 10 cols x 8 rows
_STASH_COLS = 10
_STASH_ROWS = 8

_REQUIRED_FIELDS = ('name', 'class', 'level', 'stats', 'equipment')
_REQUIRED_STATS = ('strength', 'dexterity', 'vitality', 'energy')

_BIND_DEMON_SKILL_ID = 382
_BIND_DEMON_SKILL_TAB = encode_skill_tab_param(21)
_ACTIVE_SKILL_EQUIPMENT_EXCLUDES = {'switch_weapon', 'switch_shield'}


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
    try:
        import yaml  # type: ignore
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "PyYAML is required to load character YAML (install with 'pip install pyyaml')."
        ) from exc

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

    # Default merc level to match character level when not specified
    merc = char_def.get('merc')
    if merc and isinstance(merc, dict):
        if 'level' not in merc and 'xp' not in merc and merc.get('type'):
            char_level = char_def.get('level', 1)
            merc['level'] = max(1, min(char_level - 1, 98))
            merc['_level_auto_defaulted'] = True

    # Resolve merc.level to merc.xp via the closed-form curve
    if merc and isinstance(merc, dict) and 'level' in merc:
        _resolve_merc_level_to_xp(char_def)

    # Apply max-level defaults (anni/torch/cube) if opted in
    if char_def.get('max_level_defaults'):
        _inject_max_level_defaults(char_def)

    return char_def


def _resolve_merc_level_to_xp(char_def):
    """Convert `merc.level` into `merc.xp` using the closed-form curve.

    Formula: merc_xp = Exp/Lvl × (level + 1) × level²  (see
    d2r_chargen/data/merc_xp_curve.py).

    Precedence: if both `level` and `xp` are set, `xp` wins (explicit
    override) and a warning is printed. If only `level` is set, it's
    converted. If only `xp` is set, no-op. Requires `merc.type` to be
    resolved first (templates supply it automatically).
    """
    from d2r_chargen.data.merc_xp_curve import xp_for_level
    from d2r_chargen.save import MERC_HIRELING_ID

    merc = char_def['merc']
    level = merc.get('level')
    if level is None:
        return

    if 'xp' in merc:
        print(f"  WARNING: merc has both 'level' ({level}) and 'xp' "
              f"({merc['xp']}); using explicit 'xp'.")
        return

    merc_type = merc.get('type')
    if not merc_type:
        raise ValueError(
            "merc.level requires merc.type (or a template that supplies it) "
            "to resolve XP."
        )
    if merc_type not in MERC_HIRELING_ID:
        raise ValueError(
            f"Unknown merc type '{merc_type}'. Known: "
            f"{sorted(MERC_HIRELING_ID.keys())}"
        )
    hireling_id = MERC_HIRELING_ID[merc_type]
    merc['xp'] = xp_for_level(hireling_id, int(level))


def _inject_max_level_defaults(char_def):
    """Inject default charms/items for max-level characters (opt-in via
    `max_level_defaults: true` in YAML).

    Injects only items NOT already specified:
      - Annihilus (unique small charm) -> inventory.charms
      - Hellfire Torch matched to char class -> inventory.charms
      - Empty Horadric Cube -> stash_items

    Emits a WARNING if no sunder charm is specified (user must pick one
    per build — no default sunder).

    Mutates char_def in place.
    """
    class_name = char_def.get('class', '').lower()

    inventory = char_def.setdefault('inventory', {})
    if not isinstance(inventory, dict):
        return  # malformed — let validation catch it
    charms = inventory.setdefault('charms', [])
    stash_items = char_def.setdefault('stash_items', [])

    # Detect what's already present (case-insensitive match on unique names)
    def _has_unique(items, name):
        target = name.lower()
        for it in items:
            if isinstance(it, dict) and str(it.get('unique', '')).lower() == target:
                return True
        return False

    # 1. Annihilus
    if not _has_unique(charms, 'Annihilus'):
        charms.append({'unique': 'Annihilus'})

    # 2. Hellfire Torch — class-matched via extra_properties
    if not _has_unique(charms, 'Hellfire Torch'):
        torch = {
            'unique': 'Hellfire Torch',
            'extra_properties': {
                'class_skills': [3, class_name],
            },
        }
        charms.append(torch)

    # 3. Empty Horadric Cube in stash (normal-quality base 'box', 2x2)
    def _has_cube(items):
        for it in items:
            if not isinstance(it, dict):
                continue
            if it.get('base') == 'box':
                return True
        return False

    merc_equip = []
    merc = char_def.get('merc')
    if isinstance(merc, dict):
        merc_equip = merc.get('equipment', []) or []

    if not _has_cube(stash_items) and not _has_cube(merc_equip):
        stash_items.append({'normal': True, 'base': 'box'})

    # 4. Sunder warning (no auto-inject — build-specific)
    has_sunder = any(
        isinstance(it, dict) and str(it.get('unique', '')).lower() in _SUNDER_CHARM_NAMES
        for it in charms
    )
    if not has_sunder:
        print(f"  WARNING: max_level_defaults enabled but no sunder charm "
              f"specified. Consider adding one of: "
              f"{', '.join(sorted(_SUNDER_CHARM_NAMES))}")


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
        equipment_mode = merc.get('equipment_mode')
        if equipment_mode is not None and equipment_mode not in ('stash', 'direct'):
            raise ValueError(
                f"Invalid merc.equipment_mode: '{equipment_mode}'. "
                f"Must be 'stash' or 'direct'."
            )

    # Validate Iron Golem item properties early. Class/skill prerequisites are
    # checked at build/deploy time, where we can produce the payload or None.
    iron_golem = char_def.get('iron_golem')
    if iron_golem is not None:
        item_def = iron_golem.get('item') if isinstance(iron_golem, dict) else None
        if not isinstance(item_def, dict):
            errors.append("iron_golem must contain an item mapping")
        else:
            _validate_item_def(item_def, errors)

    bound_demon_error = bound_demon_synthesis_support_error(
        char_def.get('bound_demon')
    )
    if bound_demon_error:
        errors.append(bound_demon_error)

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
        # Use merc's own level for merc item levelreq checks.
        merc_level = merc.get('level', char_level)
        _warn_level_reqs(merc.get('equipment', []), merc_level, 'merc')
        _validate_merc_equipment(merc)
    _warn_bound_demon_source_context(char_def)
    _note_bound_demon_validated_package(char_def)


def _has_bound_demon_source_affixes(bound_demon_spec):
    source_affixes = bound_demon_spec.get('source_affixes')
    if source_affixes is None:
        return False
    if isinstance(source_affixes, str):
        return any(part.strip() for part in source_affixes.split(','))
    if isinstance(source_affixes, (list, tuple)):
        return bool(source_affixes)
    return True


def _warn_bound_demon_source_context(char_def):
    bound_demon_spec = char_def.get('bound_demon')
    if not isinstance(bound_demon_spec, dict):
        return
    if not _has_bound_demon_source_affixes(bound_demon_spec):
        return
    print(
        "  WARNING: bound_demon.source_affixes require template-derived or "
        "validated package context; public chargen authors the seven MonUMod "
        "bytes but does not synthesize arbitrary source effects, aura flavor, "
        "generated names, or hidden support branches. Inspect the template with "
        "tools/d2s_demon_template_inspect.py and record validation in "
        "docs/bound-demon-template-recipes.md before treating this recipe as "
        "portable."
    )


def _note_bound_demon_validated_package(char_def):
    bound_demon_spec = char_def.get('bound_demon')
    if not is_bound_demon_validated_package_request(bound_demon_spec):
        return

    from d2r_chargen.bound_demon_registry import get_bound_demon_package

    package = get_bound_demon_package(str(bound_demon_spec.get('package_id')))
    if package is None:
        return
    unsupported = ", ".join(package.unsupported_dimensions) or "none"
    print(
        "  INFO: bound_demon.synthesis_validated "
        f"{package.package_id}: {package.summary} Unsupported dimensions: "
        f"{unsupported}."
    )


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
                who = 'merc' if section == 'merc' else 'character'
                print(f"  WARNING: {section} item '{name}' (base {base_code}, "
                      f"levelreq={levelreq}) exceeds {who} level {char_level}")


# Merc class → allowed equipment slots and weapon categories.
# Keyed by Hireling.txt Id ranges (MERC_HIRELING_ID values).
#
# Slots: Act 3 Iron Wolves can wear shield; others cannot.
# Weapons: each merc class has a narrow weapon type restriction.
_MERC_CLASS_RULES = {
    'act1_rogue': {
        'ids': range(0, 6),
        'slots': {'weapon', 'helm', 'body'},
        'weapon_categories': {'Bow', 'Crossbow'},
    },
    'act2_desert': {
        'ids': set(range(6, 15)) | {33, 34, 35},
        'slots': {'weapon', 'helm', 'body'},
        'weapon_categories': {'Spear', 'Polearm'},
    },
    'act3_ironwolf': {
        'ids': range(15, 24),
        'slots': {'weapon', 'shield', 'helm', 'body'},
        'weapon_categories': {'Sword'},
    },
    'act5_barb': {
        'ids': set(range(24, 30)),
        'slots': {'weapon', 'helm', 'body'},
        'weapon_categories': {'Sword', 'Axe', 'Mace', 'Hammer', 'Club'},
    },
}


def _merc_class_for_hireling(hireling_id):
    """Return the _MERC_CLASS_RULES key for a given hireling_id, or None."""
    for cls, rules in _MERC_CLASS_RULES.items():
        if hireling_id in rules['ids']:
            return cls
    return None


def _validate_merc_equipment(merc):
    """Warn on merc equipment that the merc class cannot use.

    Checks: slot validity per merc class (e.g. shield only on Act 3),
    weapon category per merc class (bows for Act 1, polearms for Act 2, etc.).

    Non-fatal — prints WARNING lines. Game will refuse invalid gear,
    but chargen should catch it before deploy to save a relaunch cycle.
    """
    from d2r_chargen.save import MERC_HIRELING_ID

    merc_type = merc.get('type')
    if not merc_type or merc_type not in MERC_HIRELING_ID:
        return
    hireling_id = MERC_HIRELING_ID[merc_type]
    cls = _merc_class_for_hireling(hireling_id)
    if cls is None:
        return
    rules = _MERC_CLASS_RULES[cls]

    for item_def in merc.get('equipment', []):
        slot = item_def.get('slot')
        if slot and slot not in rules['slots']:
            name = item_def.get('unique', item_def.get('runeword',
                   item_def.get('base', '?')))
            print(f"  WARNING: merc item '{name}' slot '{slot}' not usable by "
                  f"{cls} merc (allowed: {sorted(rules['slots'])})")
            continue

        # Weapon category check — resolve item base code then look up categories.
        if slot == 'weapon':
            base_code = item_def.get('base', '')
            if not base_code and 'unique' in item_def:
                try:
                    base_code = resolve_unique(item_def['unique'])['type_code']
                except ValueError:
                    continue
            if not base_code:
                continue
            base_info = ITEM_BASES.get(base_code.strip())
            if not base_info:
                continue
            categories = set(base_info.get('categories', []))
            if not categories & rules['weapon_categories']:
                name = item_def.get('unique', item_def.get('runeword',
                       item_def.get('base', '?')))
                print(f"  WARNING: merc weapon '{name}' ({base_code}, "
                      f"{sorted(categories)}) not usable by {cls} merc "
                      f"(allowed: {sorted(rules['weapon_categories'])})")


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

    # Warn if properties: exactly matches canonical on a unique item
    _warn_redundant_unique_properties(item_def)


def _warn_redundant_unique_properties(item_def):
    """Check if a unique item's properties: block redundantly duplicates canonical stats.

    If a unique item specifies 'properties:' and every key/value pair exactly matches
    the canonical stats from unique_item_stats, the block is likely redundant.
    Emit a warning to stderr suggesting 'extra_properties:' or removal instead.
    """
    # Only check unique items with 'properties:' block
    if 'unique' not in item_def or 'properties' not in item_def:
        return

    try:
        unique_name = item_def['unique']
        user_props = item_def.get('properties', {})
        if not isinstance(user_props, dict) or not user_props:
            return

        # Resolve the unique item to get canonical properties
        canonical_data = resolve_unique(unique_name)
        canonical_props = canonical_data.get('properties', [])

        # Convert canonical props (list of [stat_id, value]) to a dict for comparison
        # Canonical props can be grouped (e.g., [stat_id, [val1, val2]])
        canonical_dict = _build_canonical_props_dict(canonical_props)

        # Convert user properties to canonical stat format
        user_stat_dict = _build_user_props_dict(user_props)

        # Check if user properties exactly match canonical
        if _props_match_exactly(user_stat_dict, canonical_dict):
            item_name = unique_name
            slot = item_def.get('slot', '?')
            sys.stderr.write(
                f"WARNING: {item_name} (slot: {slot}): "
                f"'properties:' block duplicates canonical stats exactly. "
                f"Consider removing it or using 'extra_properties:' for overrides.\n"
            )
    except Exception:
        # Silently ignore errors during warning logic; don't fail validation
        pass


def _build_canonical_props_dict(canonical_props):
    """Convert canonical props list format to dict for comparison.

    Canonical format: [[stat_id, value], [stat_id, [v1, v2]], ...]
    Returns dict mapping stat_id -> value (or [value_list] for grouped stats)
    """
    result = {}
    for entry in canonical_props:
        if len(entry) >= 2:
            stat_id = entry[0]
            value = entry[1]
            result[stat_id] = value
    return result


def _build_user_props_dict(user_props):
    """Convert user properties dict to canonical stat format.

    User properties use aliases (e.g., 'fcr', 'fire_min', 'fire_max')
    Returns dict mapping stat_id -> value (or [value_list] for grouped stats)
    """
    result = {}

    for alias, user_value in user_props.items():
        try:
            # Resolve alias to canonical stat name
            canonical_stat_name = resolve_property_name(alias)
            stat_id = STAT_BY_NAME.get(canonical_stat_name)
            if stat_id is None:
                continue

            # Handle special case: elemental damage grouped stats
            # fire_min/fire_max, light_min/light_max, etc. combine into grouped format
            if alias in ('fire_min', 'fire_max', 'light_min', 'light_max',
                        'cold_min', 'cold_max', 'poison_min', 'poison_max',
                        'magic_min', 'magic_max'):
                # These will be accumulated in a second pass
                continue

            # For most properties, just map directly
            if stat_id not in result:
                result[stat_id] = user_value
        except Exception:
            # Unknown alias or resolution error — skip silently
            continue

    # Handle grouped damage stats (fire_min/fire_max, etc.)
    _accumulate_grouped_damage_stats(user_props, result)

    return result


def _accumulate_grouped_damage_stats(user_props, result_dict):
    """Accumulate grouped damage stat pairs (min/max, duration) into result dict.

    E.g., fire_min=1, fire_max=6 become stat_id 48 -> [1, 6]
    """
    # Map of damage types to (stat_id, (min_alias, max_alias, [duration_alias]))
    damage_groups = {
        'fire': (48, ('fire_min', 'fire_max'), None),
        'light': (50, ('light_min', 'light_max'), None),
        'magic': (52, ('magic_min', 'magic_max'), None),  # stat 52 is magicmindam
        'cold': (54, ('cold_min', 'cold_max'), ('cold_len',)),
        'poison': (57, ('poison_min', 'poison_max'), ('poison_len',)),
    }

    for damage_type, (stat_id, (min_alias, max_alias), duration_info) in damage_groups.items():
        min_val = user_props.get(min_alias)
        max_val = user_props.get(max_alias)

        if min_val is not None or max_val is not None:
            # Build grouped value
            values = []
            if min_val is not None:
                values.append(min_val)
            if max_val is not None:
                values.append(max_val)

            if duration_info:
                dur_alias = duration_info[0]
                dur_val = user_props.get(dur_alias)
                if dur_val is not None:
                    values.append(dur_val)

            if values:
                result_dict[stat_id] = values if len(values) > 1 else values[0]


def _props_match_exactly(user_dict, canonical_dict):
    """Check if user properties dict exactly matches canonical dict.

    Handles both simple values and grouped (list) values.
    Returns True only if every canonical key/value exists in user dict with same value.
    """
    # User dict must contain all canonical keys with exact same values
    for stat_id, canonical_value in canonical_dict.items():
        if stat_id not in user_dict:
            return False

        user_value = user_dict[stat_id]

        # Compare values (handle both single values and grouped lists)
        if isinstance(canonical_value, list) and isinstance(user_value, list):
            # Grouped stat — must match exactly (same length and values)
            if len(canonical_value) != len(user_value):
                return False
            if canonical_value != user_value:
                return False
        elif isinstance(canonical_value, list) or isinstance(user_value, list):
            # One is grouped, one is not — mismatch
            return False
        else:
            # Both are simple values
            if canonical_value != user_value:
                return False

    # All canonical properties matched; now check no extra user properties
    for stat_id in user_dict:
        if stat_id not in canonical_dict:
            return False

    return True


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


def _normalized_skill_key(name):
    return str(name).lower().replace('_', ' ').replace(' ', '')


def _hard_bind_demon_level(char_def):
    for key, value in char_def.get('skills', {}).items():
        if _normalized_skill_key(key) == 'binddemon':
            try:
                return int(value)
            except (TypeError, ValueError):
                return 0
    return 0


def _merge_bonus_properties(base_props, extra_props):
    extra_stat_ids = {prop[0] for prop in extra_props}
    merged = [prop for prop in base_props if prop[0] not in extra_stat_ids]
    merged.extend(extra_props)
    return merged


def _item_skill_bonus_properties(item_def):
    """Return resolved item properties relevant to skill bonus calculation."""
    for charm_key in ('magic_small_charm', 'magic_large_charm', 'magic_grand_charm'):
        charm_info = item_def.get(charm_key)
        if isinstance(charm_info, dict):
            return resolve_properties(charm_info.get('properties', {}))

    base_props = []
    has_canonical = False
    if 'unique' in item_def:
        base_props = resolve_unique(item_def['unique']).get('properties', [])
        has_canonical = True
    elif 'runeword' in item_def:
        base_code = item_def.get('base')
        if base_code:
            base_props = resolve_runeword(
                item_def['runeword'],
                base_code,
            ).get('properties', [])
            has_canonical = True

    if 'properties' in item_def:
        user_props = resolve_properties(item_def['properties'])
        if has_canonical:
            return _merge_bonus_properties(base_props, user_props)
        return user_props
    if 'extra_properties' in item_def:
        extra_props = resolve_properties(item_def['extra_properties'])
        if has_canonical:
            return _merge_bonus_properties(base_props, extra_props)
        return extra_props
    return base_props


def _iter_player_skill_bonus_items(char_def):
    for item_def in char_def.get('equipment', []) or []:
        if not isinstance(item_def, dict):
            continue
        slot = item_def.get('slot')
        if slot in _ACTIVE_SKILL_EQUIPMENT_EXCLUDES:
            continue
        yield item_def

    inventory = char_def.get('inventory', {})
    charms = inventory.get('charms', []) if isinstance(inventory, dict) else []
    for charm_def in _expand_charms(charms):
        if isinstance(charm_def, dict):
            yield charm_def


def _bind_demon_item_skill_bonuses(char_def):
    all_class_tab_bonus = 0
    specific_bonus = 0
    warlock_class_id = CLASS_DEFS['warlock']['id']
    stat_all_skills = STAT_BY_NAME['item_allskills']
    stat_class_skills = STAT_BY_NAME['item_addclassskills']
    stat_skill_tab = STAT_BY_NAME['item_addskill_tab']
    stat_nonclass_skill = STAT_BY_NAME['item_nonclassskill']
    stat_single_skill = STAT_BY_NAME.get('item_singleskill')

    for item_def in _iter_player_skill_bonus_items(char_def):
        for prop in _item_skill_bonus_properties(item_def):
            if len(prop) < 2:
                continue
            stat_id = prop[0]
            param = prop[2] if len(prop) >= 3 else None
            if stat_id not in (
                stat_all_skills,
                stat_class_skills,
                stat_skill_tab,
                stat_nonclass_skill,
                stat_single_skill,
            ):
                continue
            value = int(prop[1])
            if stat_id == stat_all_skills:
                all_class_tab_bonus += value
            elif (
                stat_id == stat_class_skills
                and param is not None
                and int(param) == warlock_class_id
            ):
                all_class_tab_bonus += value
            elif (
                stat_id == stat_skill_tab
                and param is not None
                and int(param) == _BIND_DEMON_SKILL_TAB
            ):
                all_class_tab_bonus += value
            elif (
                stat_id in (stat_nonclass_skill, stat_single_skill)
                and param is not None
                and int(param) == _BIND_DEMON_SKILL_ID
            ):
                specific_bonus += value

    return all_class_tab_bonus, specific_bonus


def _effective_bind_demon_level(char_def):
    """Return hard Bind Demon level plus active player-carried item bonuses."""
    hard_level = _hard_bind_demon_level(char_def)
    general_bonus, specific_bonus = _bind_demon_item_skill_bonuses(char_def)
    if hard_level <= 0:
        return specific_bonus
    return hard_level + general_bonus + specific_bonus


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
        elif name_lower in _PREFERRED_CHARM_POSITIONS:
            _, fc, fr = _PREFERRED_CHARM_POSITIONS[name_lower]
            if is_free(fc, fr, w, h):
                occupy(fc, fr, w, h)
                positions[idx] = (fc, fr)
            else:
                if tc == 'cm3':
                    grand_charms.append((idx, charm_def, tc, w, h))
                elif tc == 'cm2':
                    large_charms.append((idx, charm_def, tc, w, h))
                else:
                    small_charms.append((idx, charm_def, tc, w, h))
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

    Pre-encode warnings are collected and printed before the scanner runs,
    giving the user earlier diagnostic info. Warnings never halt the build.

    Args:
        char_def: Validated character definition dict.

    Returns:
        List of (section, bytes) tuples. Section is always 'char'.
    """
    from d2r_chargen.warnings import BuildWarnings
    from d2r_chargen.build_lib import set_build_warnings

    bw = BuildWarnings()
    set_build_warnings(bw)
    try:
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

        # 3. Build merc items: either injected into JM[merc] (direct mode) or
        # placed in character stash for manual equip (stash mode).
        #
        # equipment_mode resolution priority:
        #   1. Explicit merc.equipment_mode field ('stash' | 'direct')
        #   2. Legacy merc.inject bool (inject: true → 'direct', false → 'stash')
        #   3. Default: 'direct' when merc.type is set (merc is hired/being
        #      hired); 'stash' otherwise (merc section used as stash overflow
        #      for items without slots, no merc actually hired).
        merc = char_def.get('merc', {})
        merc_equipment = []
        equipment_mode = 'direct' if (isinstance(merc, dict) and merc.get('type')) else 'stash'
        if isinstance(merc, dict):
            merc_equipment = merc.get('equipment', [])
            explicit_mode = merc.get('equipment_mode')
            legacy_inject = merc.get('inject')
            if explicit_mode is not None and legacy_inject is not None:
                print(
                    f"  WARNING: merc has both 'equipment_mode' and legacy 'inject' fields; "
                    f"using 'equipment_mode: {explicit_mode}'"
                )
            if explicit_mode is not None:
                equipment_mode = explicit_mode
            elif legacy_inject is not None:
                equipment_mode = 'direct' if bool(legacy_inject) else 'stash'
        if equipment_mode not in ('stash', 'direct'):
            raise ValueError(
                f"Invalid merc.equipment_mode: '{equipment_mode}'. "
                f"Must be 'stash' or 'direct'."
            )
        if merc_equipment:
            if equipment_mode == 'direct':
                # Build as equipped-on-merc.  Merc-owned items use the same
                # encoding as char-equipped items EXCEPT that `col` carries
                # the merc equip-slot index (== bodyloc).  Char-equipped uses
                # col=0.  Observed in golden fixture hexshade_lv98_haseen:
                # Insight 7wc col=4 (bodyloc=4), Andariel's usk col=1
                # (bodyloc=1), Fortitude utp col=3 (bodyloc=3).
                # See tests/test_merc_encoding.py for round-trip coverage.
                for item_def in merc_equipment:
                    built = build_equipment_item(item_def, is_merc=True)
                    for _section, item_bytes in built:
                        all_items.append(('merc', item_bytes))

        # 4. Build stash_items (non-merc items placed in stash, e.g. cube).
        # Combined with merc stash items into a single placement pass so they
        # don't collide.
        stash_items = char_def.get('stash_items', []) or []
        stash_merc = merc_equipment if (merc_equipment and equipment_mode == 'stash') else []
        combined_stash = list(stash_merc) + list(stash_items)
        if combined_stash:
            stash_positions = _calculate_merc_stash_positions(combined_stash)
            # First: merc items via build_merc_item
            for i, item_def in enumerate(stash_merc):
                col, row = stash_positions[i]
                items = build_merc_item(item_def, stash_col=col, stash_row=row)
                all_items.extend(items)
            # Then: stash_items (non-merc) via same builder
            for j, item_def in enumerate(stash_items):
                col, row = stash_positions[len(stash_merc) + j]
                items = build_merc_item(item_def, stash_col=col, stash_row=row)
                all_items.extend(items)

        return all_items
    finally:
        set_build_warnings(None)
        if bw.has_warnings():
            bw.dump()

def resolve_iron_golem_payload(char_def):
    """Resolve a YAML `iron_golem:` block to one JM-less item payload.

    V1 intentionally requires a Necromancer with IronGolem skill >= 1 and
    supports generated normal/magic items only.
    """
    spec = char_def.get('iron_golem')
    if spec is None:
        return None
    if not isinstance(spec, dict):
        raise ValueError("iron_golem must be a mapping")

    class_name = str(char_def.get('class', '')).lower()
    if class_name != 'necromancer':
        raise ValueError(
            f"iron_golem: requires class=necromancer, got {char_def.get('class')!r}"
        )

    iron_golem_lvl = 0
    for key, value in char_def.get('skills', {}).items():
        if _normalized_skill_key(key) == 'irongolem':
            try:
                iron_golem_lvl = int(value)
            except (TypeError, ValueError):
                iron_golem_lvl = 0
            break
    if iron_golem_lvl < 1:
        raise ValueError(
            f"iron_golem: requires IronGolem skill >= 1, got {iron_golem_lvl}"
        )

    item_def = spec.get('item')
    if not isinstance(item_def, dict):
        raise ValueError("iron_golem must specify item")
    return build_iron_golem_item(item_def)


def resolve_bound_demon_payload(char_def):
    """Resolve a YAML `bound_demon:` block to one 116-byte follower payload."""
    bound_demon_spec = char_def.get('bound_demon')
    if bound_demon_spec is None:
        return None

    # D2R can load borrowed follower blocks on other classes, but save/exit
    # strips them. Keep normal chargen authoring on the Warlock-only path.
    if char_def['class'] != 'warlock':
        raise ValueError(
            f"bound_demon: requires class=warlock, got {char_def['class']!r}"
        )

    effective_bind_level = _effective_bind_demon_level(char_def)
    if isinstance(bound_demon_spec, dict) and 'effective_bind_level' in bound_demon_spec:
        try:
            effective_bind_level = int(bound_demon_spec['effective_bind_level'])
        except (TypeError, ValueError):
            effective_bind_level = 0
    if effective_bind_level < 1:
        raise ValueError(
            f"bound_demon: requires effective Bind Demon skill >= 1, got {effective_bind_level}"
        )

    return resolve_bound_demon(
        bound_demon_spec,
        FIXTURES_DIR,
        effective_bind_level=effective_bind_level,
    )


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
        set_difficulty,
        set_waypoints_granular, set_quests_granular,
        rebuild_items, calc_checksum,
        set_merc_header, MERC_HIRELING_ID,
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
        char_path = create_new_character(
            template_path, char_def['name'], class_id, output_dir=SAVES
        )

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

    # Set waypoints/quests/difficulty from YAML progression field.
    # Only for NEW characters — existing characters preserve in-game progress.
    if is_new_character:
        progression_raw = char_def.get('progression', 'hell_start')
        progression = resolve_progression(progression_raw)
        data = set_waypoints_granular(data, progression['waypoints'])
        data = set_quests_granular(data, progression['quests'])
        data = set_difficulty(data, progression['difficulty'])
    else:
        print(f"  Preserving existing WP/quest/difficulty progress")

    # Write merc header (type/seed/XP) if merc is specified
    merc = char_def.get('merc')
    if merc and isinstance(merc, dict):
        merc_type = merc.get('type')
        if merc_type:
            if merc_type not in MERC_HIRELING_ID:
                raise ValueError(
                    f"Unknown merc type '{merc_type}'. Known types: "
                    f"{sorted(MERC_HIRELING_ID.keys())}"
                )
            hireling_id = MERC_HIRELING_ID[merc_type]
            merc_xp = int(merc.get('xp', 0))
            # Preserve earned XP when the level was auto-defaulted (not
            # explicit YAML). User hires in-game, plays, rebuilds — we
            # shouldn't reset their merc's progress.
            if merc.get('_level_auto_defaulted'):
                existing_xp = struct.unpack_from('<I', data, 0xab)[0]
                existing_hireling_id = struct.unpack_from('<H', data, 0xa9)[0]
                if existing_hireling_id == hireling_id and existing_xp > merc_xp:
                    print(f"  Preserving existing merc XP {existing_xp} "
                          f"(> auto-default {merc_xp})")
                    merc_xp = existing_xp
            data = set_merc_header(data, hireling_id, xp=merc_xp)
            print(f"  Merc header: type={merc_type!r} hireling_id={hireling_id} xp={merc_xp}")

    # Finalize stats/checksum in memory.
    struct.pack_into('<I', data, 8, len(data))
    data[12:16] = b'\x00\x00\x00\x00'
    cs = calc_checksum(data)
    struct.pack_into('<I', data, 12, cs)

    # Rule #3: backup the live save BEFORE any write. On OSError (full
    # disk, permission denied), refuse to proceed — the live save is still
    # untouched at this point.
    bak = f"{char_path}.pre_chargen_bak"
    try:
        shutil.copy2(char_path, bak)
    except OSError as ex:
        print(f"  BACKUP FAILED: {type(ex).__name__}: {ex}")
        print(f"  Refusing to proceed. Live save untouched at {char_path}")
        return False

    # Rules #10 + #17: write the stats-updated file to a staging temp,
    # not directly to the live save.  The phase loop reads from this
    # staging temp and updates it in-place as each phase succeeds.
    # The live save (char_path) is only written once ALL scanner checks pass.
    staging_path = f"/tmp/{char_def['name']}_staging.d2s"
    # keep_staging: retain staging file on failure paths for post-mortem
    # inspection; set to False so the finally always cleans up on success.
    keep_staging = False
    with open(staging_path, 'wb') as f:
        f.write(data)

    # Deploy items in phases
    # Phase 1: equipped (storage=0, bodyloc not in 11,12)
    # Phase 2: + swap (bodyloc 11,12)
    # Phase 3: + inventory charms (storage=1)
    # Phase 4: + merc stash items (storage=5)

    def get_phase_items(all_items, phase_num):
        """Returns (char_items, merc_items) — two separate lists for rebuild_items.

        Routes by section tag: 'char' items into char JM, 'merc' items into merc JM.
        """
        char_result = []
        merc_result = []
        char_parent_included = False
        merc_parent_included = False
        for section, item_bytes in all_items:
            is_filler = bits_at(item_bytes, 21, 1) if len(item_bytes) > 3 else 0
            if is_filler:
                # Filler rides along with its parent into whichever list the
                # parent landed in. Track per-section parent state.
                if section == 'merc' and merc_parent_included:
                    merc_result.append(item_bytes)
                elif section != 'merc' and char_parent_included:
                    char_result.append(item_bytes)
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
                include = True  # stash (includes merc-gear stash)
            if section == 'merc':
                merc_parent_included = include
                if include:
                    merc_result.append(item_bytes)
            else:
                char_parent_included = include
                if include:
                    char_result.append(item_bytes)
        return char_result, merc_result

    # Resolve follower/golem payload blocks once outside the phase loop. The
    # payloads are identical across phases; None means preserve or omit.
    follower_payload = resolve_bound_demon_payload(char_def)
    iron_golem_payload = resolve_iron_golem_payload(char_def)

    try:
        for p in range(1, phase + 1):
            char_phase_items, merc_phase_items = get_phase_items(all_items, p)

            # Rules #10 + #17: read from staging_path, write to a per-phase
            # temp, scan the temp, and ONLY update staging_path if the scanner
            # passes.  The live save (char_path) is never touched during this
            # loop — it is promoted from staging_path only after all phases pass.
            temp_path = f"/tmp/{char_def['name']}_phase{p}.d2s"
            # keep_temp: retain temp on failure paths for post-mortem inspection.
            keep_temp = False
            try:
                shutil.copy2(staging_path, temp_path)

                # Section-routed items: 'char' → JM[char], 'merc' → JM[merc].
                # Historically merc list was always empty (Rule 6); with the new
                # merc header now setting a valid Hireling.Id, pre-injection
                # should work when the YAML opts in via `merc: inject: true`.
                result = rebuild_items(
                    temp_path, char_phase_items, merc_phase_items,
                    follower_payload=follower_payload,
                    iron_golem_payload=iron_golem_payload,
                )

                with open(temp_path, 'wb') as f:
                    f.write(result)

                # Rule #5: verify checksum on the temp before anything else.
                cs_stored = struct.unpack_from('<I', result, 12)[0]
                cs_calc = calc_checksum(result)
                if cs_stored != cs_calc:
                    print(f"  CHECKSUM MISMATCH in phase {p} (temp)")
                    keep_temp = True    # retain for inspection
                    keep_staging = True  # retain staging too
                    return False

                # Rule #4 / #17: scan the TEMP, not the live save.
                from d2r_chargen.scanner import scan_character_data
                scan_result = scan_character_data(temp_path)
                scan_errors = scan_result.get('errors', [])
                scan_warnings = scan_result.get('warnings', [])
                if scan_errors:
                    print(f"  SCANNER ERRORS in phase {p} (temp not promoted):")
                    for err in scan_errors:
                        print(f"    {err}")
                    print(f"  Live save untouched. Temp retained at {temp_path}")
                    keep_temp = True    # retain for inspection
                    keep_staging = True  # retain staging too
                    return False
                for w in scan_warnings:
                    print(f"  WARNING: {w}")

                # Scan passed — advance staging to this phase's output.
                shutil.copy2(temp_path, staging_path)
                print(
                    f"  Phase {p}: deployed {len(char_phase_items)} char items "
                    f"+ {len(merc_phase_items)} merc items, "
                    f"scanner passed ({scan_result['item_count']} items, "
                    f"checksum {'OK' if scan_result['checksum_ok'] else 'FAIL'})"
                )
            finally:
                # Keep temp on failure for inspection; remove on success.
                if os.path.exists(temp_path) and not keep_temp:
                    os.unlink(temp_path)

        # All phases passed — promote staging to live in a single atomic copy.
        # This is the only moment char_path is modified.
        shutil.copy2(staging_path, char_path)
    finally:
        # Keep staging on failure for inspection; remove on success.
        if os.path.exists(staging_path) and not keep_staging:
            os.unlink(staging_path)

    print(f"\n  {char_def['name']} deployed successfully!")
    print(f"  ** Fully restart D2R to test (Rule 7) **")
    return True
