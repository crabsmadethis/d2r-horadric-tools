"""Import a .d2s binary save file into a YAML-compatible dict."""
import os
import struct
from datetime import datetime

from d2r_chargen.scanner import (
    bits_at, decode_item_header, navigate_item_structure,
)
from d2r_chargen.decoder import decode_item_properties
from d2r_chargen.config import (
    CLASS_DEFS, reverse_resolve_alias,
)
from d2r_chargen.data.item_stat_cost import ITEM_STAT_COST
from d2r_chargen.data.unique_items import UNIQUE_ITEMS
from d2r_chargen.data.set_items import SET_ITEMS
from d2r_chargen.data.runewords import RUNEWORDS, RUNE_CODE_TO_NAME
from d2r_chargen.data.skills import SKILLS


_CLASS_BY_ID = {v['id']: name for name, v in CLASS_DEFS.items()}

_SLOT_MAP = {
    1: 'helm', 2: 'neck', 3: 'body', 4: 'weapon', 5: 'shield',
    6: 'ring_right', 7: 'ring_left', 8: 'belt', 9: 'feet', 10: 'hands',
    11: 'switch_weapon', 12: 'switch_shield',
}

_RUNE_CODES = {f'r{i:02d}' for i in range(1, 34)}


def import_character(filepath):
    """Import a .d2s file into a YAML-compatible dict."""
    data = bytearray(open(filepath, 'rb').read())

    result = {
        'schema_version': 1,
        '_imported_at': datetime.now().isoformat(),
        '_imported_from': os.path.basename(filepath),
        '_imported_checksum': f"0x{struct.unpack_from('<I', data, 12)[0]:08X}",
    }

    result['name'] = _read_name(data)
    result['class'] = _CLASS_BY_ID.get(data[0x18], f'class_{data[0x18]}')
    result['level'] = data[0x1B]

    prog = data[0x15]
    result['progression'] = {0x00: 'normal', 0x05: 'nightmare', 0x0F: 'hell'}.get(
        prog, f'0x{prog:02X}'
    )

    result['stats'] = _decode_character_stats(data)

    skills = _decode_skills(data, result['class'])
    if skills:
        result['skills'] = skills

    equipment, inventory, stash, cube, merc_equipment = _decode_items(data)

    if equipment:
        result['equipment'] = equipment
    if inventory:
        result['inventory'] = inventory
    if stash:
        result['stash'] = stash
    if cube:
        result['cube'] = cube
    if merc_equipment:
        result['merc'] = {'equipment': merc_equipment}

    return result


def dict_to_yaml(d):
    """Serialize an import dict to a YAML string."""
    import yaml

    class OrderedDumper(yaml.SafeDumper):
        pass

    def _dict_representer(dumper, data):
        return dumper.represent_mapping('tag:yaml.org,2002:map', data.items())
    OrderedDumper.add_representer(dict, _dict_representer)

    return yaml.dump(d, Dumper=OrderedDumper, default_flow_style=False,
                     sort_keys=False, allow_unicode=True)


def _read_name(data):
    """Read character name from offset 0x12B (null-terminated)."""
    name_bytes = data[0x12B:0x12B + 16]
    return name_bytes.split(b'\x00')[0].decode('ascii', errors='replace')


def _decode_character_stats(data):
    """Decode the bit-packed character stats after the 'gf' marker."""
    gf_pos = data.find(b'gf')
    if gf_pos == -1:
        return {}

    br = (gf_pos + 2) * 8
    stats = {}
    stat_names = {0: 'strength', 1: 'energy', 2: 'dexterity', 3: 'vitality'}
    total_bits = len(data) * 8

    for _ in range(16):
        if br + 9 > total_bits:
            break
        stat_id = bits_at(data, br, 9)
        br += 9
        if stat_id == 0x1FF:
            break

        info = ITEM_STAT_COST.get(stat_id)
        if info is None:
            break
        cB = info.get('cB', 0)
        if cB == 0:
            break

        raw = bits_at(data, br, cB)
        br += cB

        vS = info.get('vS', 0)
        value = raw >> vS if vS else raw

        if stat_id in stat_names:
            stats[stat_names[stat_id]] = value

    return stats


def _decode_skills(data, char_class):
    """Decode skills from the 'if' marker section."""
    if_pos = data.find(b'if')
    if if_pos == -1:
        return {}

    skill_bytes = data[if_pos + 2: if_pos + 2 + 30]
    class_info = CLASS_DEFS.get(char_class)
    if not class_info:
        return {}

    skill_base = class_info['skill_base']
    skills = {}
    for i, level in enumerate(skill_bytes):
        if level > 0:
            skill_id = skill_base + i
            skill_info = SKILLS.get(skill_id)
            if skill_info:
                skills[skill_info['name']] = level
            else:
                skills[f'skill_{skill_id}'] = level

    return skills


def _find_items_by_signature(data, start_byte, end_byte):
    """Find item byte positions by scanning for 2-byte item signature."""
    positions = []
    for pos in range(start_byte, min(end_byte, len(data) - 2)):
        if data[pos] == 0x10 and data[pos + 2] in (0x80, 0xa0, 0xc0, 0xe0):
            positions.append(pos)
    return positions


def _decode_items(data):
    """Decode all items from the JM sections."""
    jm_pos = data.find(b'JM')
    if jm_pos == -1:
        return [], [], [], [], []

    item_count = struct.unpack_from('<H', data, jm_pos + 2)[0]

    jf_pos = data.find(b'jf', jm_pos + 4)
    if jf_pos == -1:
        jf_pos = len(data)

    char_item_positions = _find_items_by_signature(data, jm_pos + 4, jf_pos)

    equipment = []
    inventory = []
    stash = []
    cube = []
    current_parent = None

    for pos in char_item_positions:
        item_dict = _decode_single_item(data, pos)
        if item_dict is None:
            continue

        is_filler = item_dict.pop('_is_filler', False)

        if is_filler:
            if current_parent is not None:
                current_parent.setdefault('fillers', []).append(item_dict)
            continue

        storage = item_dict.pop('_storage', 0)
        bodyloc = item_dict.pop('_bodyloc', 0)
        location = item_dict.pop('_location', 0)

        if storage == 0 and bodyloc > 0:
            # Equipped: scanner uses storage==0 and bodyloc>=1 (location field unreliable)
            item_dict['slot'] = _SLOT_MAP.get(bodyloc, f'bodyloc_{bodyloc}')
            equipment.append(item_dict)
            current_parent = item_dict
        elif storage == 1:
            inventory.append(item_dict)
            current_parent = item_dict
        elif storage == 5:
            stash.append(item_dict)
            current_parent = item_dict
        elif storage == 4:
            cube.append(item_dict)
            current_parent = item_dict
        else:
            inventory.append(item_dict)
            current_parent = item_dict

    # Parse merc items
    merc_equipment = []
    jm2_search_start = jf_pos + 2 if jf_pos < len(data) else jm_pos + 4
    jm2_pos = data.find(b'JM', jm2_search_start)
    if jm2_pos != -1 and jm2_pos < len(data) - 4:
        merc_count = struct.unpack_from('<H', data, jm2_pos + 2)[0]
        merc_end = min(jm2_pos + 4 + merc_count * 500, len(data))
        merc_positions = _find_items_by_signature(data, jm2_pos + 4, merc_end)

        for pos in merc_positions:
            item_dict = _decode_single_item(data, pos)
            if item_dict is None:
                continue
            item_dict.pop('_is_filler', None)
            item_dict.pop('_storage', None)
            item_dict.pop('_location', None)
            bodyloc = item_dict.pop('_bodyloc', 0)
            if bodyloc > 0:
                item_dict['slot'] = _SLOT_MAP.get(bodyloc, f'bodyloc_{bodyloc}')
            merc_equipment.append(item_dict)

    return equipment, inventory, stash, cube, merc_equipment


def _decode_single_item(data, pos):
    """Decode one item at BYTE position pos."""
    try:
        hdr = decode_item_header(data, pos)
    except Exception:
        return None

    itype, ilvl, quality, uid, storage, col, row, bodyloc, location, ext = hdr
    tc = itype.strip()

    flags32 = struct.unpack_from('<I', data, pos)[0]
    is_simple = bool(flags32 & (1 << 21))
    is_socketed = bool(flags32 & (1 << 11))
    is_runeword = bool(flags32 & (1 << 26))

    item_dict = {}

    item_dict['_storage'] = storage
    item_dict['_bodyloc'] = bodyloc
    item_dict['_location'] = location
    item_dict['_is_filler'] = is_simple and location == 6

    if item_dict['_is_filler'] and tc in _RUNE_CODES:
        rune_name = RUNE_CODE_TO_NAME.get(tc, tc)
        item_dict['rune'] = rune_name
        return item_dict

    if storage in (1, 4, 5) and (col > 0 or row > 0):
        item_dict['col'] = col
        item_dict['row'] = row

    if flags32 & (1 << 22):
        item_dict['ethereal'] = True

    if ilvl > 0:
        item_dict['ilvl'] = ilvl

    rw_id = None
    prop_start_bit = None
    if not is_simple:
        nav = navigate_item_structure(
            data, pos, quality, is_runeword, is_socketed, flags32
        )
        if nav[0] is not None:
            prop_start_bit, rw_id = nav

    if is_runeword and rw_id is not None:
        rw_info = RUNEWORDS.get(rw_id)
        if rw_info:
            item_dict['runeword'] = rw_info['name']
        else:
            item_dict['runeword'] = f'runeword_{rw_id}'
        item_dict['base'] = tc

    elif quality == 7:
        u_info = UNIQUE_ITEMS.get(uid)
        if u_info:
            item_dict['unique'] = u_info['name']
        else:
            item_dict['unique'] = f'unique_{uid}'

    elif quality == 5:
        s_info = SET_ITEMS.get(uid)
        if s_info:
            item_dict['set'] = s_info['name']
        else:
            item_dict['set'] = f'set_{uid}'

    elif quality == 6:
        item_dict['rare'] = True
        item_dict['base'] = tc

    elif quality == 4:
        item_dict['magic'] = True
        item_dict['base'] = tc

    elif quality == 3:
        item_dict['superior'] = True
        item_dict['base'] = tc

    else:
        item_dict['base'] = tc

    if prop_start_bit is not None:
        num_terminators = 2 if is_runeword else 1
        try:
            props, prop_end = decode_item_properties(
                data, prop_start_bit, num_terminators
            )
            if props:
                item_dict['properties'] = _props_to_yaml(props)
        except (ValueError, IndexError):
            pass

    return item_dict


def _props_to_yaml(prop_tuples):
    """Convert decoded property tuples to YAML-friendly dict."""
    result = {}

    for tup in prop_tuples:
        stat_id = tup[0]
        alias = reverse_resolve_alias(stat_id)
        info = ITEM_STAT_COST.get(stat_id, {})
        e = info.get('e', 0)

        if len(tup) == 2:
            value = tup[1]
            if isinstance(value, list):
                if len(set(value)) == 1:
                    result[alias] = value[0]
                else:
                    result[alias] = value
            else:
                result[alias] = value

        elif len(tup) == 3:
            value, param = tup[1], tup[2]

            if e == 2:
                skill_id = param & 0x3FF
                skill_level = (param >> 10) & 0x3F
                skill_name = SKILLS.get(skill_id, {}).get('name', f'skill_{skill_id}')
                entry = [value, skill_level, skill_name]
                if alias in result:
                    existing = result[alias]
                    if isinstance(existing[0], list):
                        existing.append(entry)
                    else:
                        result[alias] = [existing, entry]
                else:
                    result[alias] = entry

            elif e == 3:
                skill_id = param & 0x3FF
                skill_level = (param >> 10) & 0x3F
                cur = value & 0xFF
                max_charges = (value >> 8) & 0xFF
                skill_name = SKILLS.get(skill_id, {}).get('name', f'skill_{skill_id}')
                result[alias] = [cur, max_charges, skill_level, skill_name]

            elif stat_id == 83:
                class_name = _CLASS_BY_ID.get(param, f'class_{param}')
                result[alias] = [value, class_name]

            elif stat_id == 188:
                tab = param & 0x7
                result[alias] = [value, tab]

            else:
                skill_name = SKILLS.get(param, {}).get('name', f'skill_{param}')
                entry = [value, skill_name]
                if alias in result:
                    existing = result[alias]
                    if isinstance(existing[0], list):
                        existing.append(entry)
                    else:
                        result[alias] = [existing, entry]
                else:
                    result[alias] = entry

    return result
