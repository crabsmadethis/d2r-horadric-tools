"""Compare two .d2s save files and report differences.

Uses byte-scanning for item discovery (same as importer.py and scanner.py).
"""
import struct

from d2r_chargen.config import CLASS_DEFS
from d2r_chargen.scanner import (
    bits_at, decode_item_header, navigate_item_structure,
)
from d2r_chargen.data.item_stat_cost import ITEM_STAT_COST
from d2r_chargen.data.unique_items import UNIQUE_ITEMS
from d2r_chargen.data.set_items import SET_ITEMS
from d2r_chargen.data.runewords import RUNEWORDS

_CLASS_BY_ID = {v['id']: name for name, v in CLASS_DEFS.items()}
_PROG_MAP = {0x00: 'Normal', 0x05: 'Nightmare', 0x0F: 'Hell'}
_SLOT_MAP = {
    1: 'helm', 2: 'neck', 3: 'body', 4: 'rarm', 5: 'larm',
    6: 'rring', 7: 'lring', 8: 'belt', 9: 'boots', 10: 'gloves',
    11: 'rarm2', 12: 'larm2',
}
_STOR_MAP = {0: 'equip', 1: 'inv', 4: 'cube', 5: 'stash'}


def diff_saves(path_a, path_b):
    """Compare two .d2s files.

    Returns dict with keys:
        header_changes: [{field, old, new}]
        stat_changes: [{stat, old, new}]
        items_added: [item_desc]
        items_removed: [item_desc]
        items_moved: [{item, old_loc, new_loc}]
    """
    data_a = bytearray(open(path_a, 'rb').read())
    data_b = bytearray(open(path_b, 'rb').read())

    return {
        'header_changes': _diff_headers(data_a, data_b),
        'stat_changes': _diff_stats(data_a, data_b),
        **_diff_items(data_a, data_b),
    }


def format_diff(result):
    """Format diff result as human-readable string."""
    lines = []

    if result['header_changes']:
        lines.append('Header:')
        for c in result['header_changes']:
            lines.append(f"  {c['field']:20s} {c['old']} -> {c['new']}")

    if result['stat_changes']:
        lines.append('Stats:')
        for c in result['stat_changes']:
            diff = ''
            if isinstance(c['old'], (int, float)) and isinstance(c['new'], (int, float)):
                d = c['new'] - c['old']
                diff = f'  ({d:+d})'
            lines.append(f"  {c['stat']:20s} {c['old']} -> {c['new']}{diff}")

    if result['items_added']:
        lines.append('Items added:')
        for item in result['items_added']:
            lines.append(f"  + {item}")

    if result['items_removed']:
        lines.append('Items removed:')
        for item in result['items_removed']:
            lines.append(f"  - {item}")

    if result.get('items_moved'):
        lines.append('Items moved:')
        for m in result['items_moved']:
            lines.append(f"  ~ {m['item']}: {m['old_loc']} -> {m['new_loc']}")

    if not lines:
        lines.append('No differences found.')

    return '\n'.join(lines)


def _diff_headers(a, b):
    changes = []

    if a[0x1B] != b[0x1B]:
        changes.append({'field': 'level', 'old': a[0x1B], 'new': b[0x1B]})
    if a[0x18] != b[0x18]:
        changes.append({
            'field': 'class',
            'old': _CLASS_BY_ID.get(a[0x18], f'class_{a[0x18]}'),
            'new': _CLASS_BY_ID.get(b[0x18], f'class_{b[0x18]}'),
        })
    if a[0x14] != b[0x14]:
        changes.append({
            'field': 'status_byte',
            'old': f'0x{a[0x14]:02X}',
            'new': f'0x{b[0x14]:02X}',
        })
    if a[0x15] != b[0x15]:
        changes.append({
            'field': 'progression',
            'old': _PROG_MAP.get(a[0x15], f'0x{a[0x15]:02X}'),
            'new': _PROG_MAP.get(b[0x15], f'0x{b[0x15]:02X}'),
        })

    name_a = a[0x12B:0x12B + 16].split(b'\x00')[0].decode('ascii', errors='replace')
    name_b = b[0x12B:0x12B + 16].split(b'\x00')[0].decode('ascii', errors='replace')
    if name_a != name_b:
        changes.append({'field': 'name', 'old': name_a, 'new': name_b})

    return changes


def _diff_stats(a, b):
    stats_a = _read_stats(a)
    stats_b = _read_stats(b)
    changes = []
    all_keys = sorted(set(stats_a) | set(stats_b))
    for key in all_keys:
        va = stats_a.get(key)
        vb = stats_b.get(key)
        if va != vb:
            changes.append({'stat': key, 'old': va, 'new': vb})
    return changes


def _read_stats(data):
    """Read character stats from gf section."""
    gf_pos = data.find(b'gf')
    if gf_pos == -1:
        return {}
    br = (gf_pos + 2) * 8
    stats = {}
    stat_names = {
        0: 'Strength', 1: 'Energy', 2: 'Dexterity', 3: 'Vitality',
        4: 'Stat Points', 5: 'Skill Points', 6: 'HP', 7: 'Max HP',
        8: 'Mana', 9: 'Max Mana', 13: 'Experience', 14: 'Gold', 15: 'Stash Gold',
    }
    for _ in range(16):
        if br + 9 > len(data) * 8:
            break
        stat_id = bits_at(data, br, 9)
        br += 9
        if stat_id == 0x1FF:
            break
        info = ITEM_STAT_COST.get(stat_id)
        if not info:
            break
        cB = info.get('cB', 0)
        if cB == 0:
            break
        raw = bits_at(data, br, cB)
        br += cB
        vS = info.get('vS', 0)
        value = raw >> vS if vS else raw
        name = stat_names.get(stat_id, info.get('s', f'stat_{stat_id}'))
        stats[name] = value
    return stats


def _diff_items(a, b):
    """Diff items between two saves."""
    items_a = _collect_items(a)
    items_b = _collect_items(b)

    def item_key(item):
        return (item.get('quality', 0), item.get('type', ''), item.get('uid', 0))

    keys_a = {item_key(i): i for i in items_a}
    keys_b = {item_key(i): i for i in items_b}

    added = []
    removed = []
    moved = []

    for key, item in keys_b.items():
        if key not in keys_a:
            added.append(item['desc'])
        elif item['loc'] != keys_a[key]['loc']:
            moved.append({
                'item': item['desc'],
                'old_loc': keys_a[key]['loc'],
                'new_loc': item['loc'],
            })

    for key, item in keys_a.items():
        if key not in keys_b:
            removed.append(item['desc'])

    return {
        'items_added': added,
        'items_removed': removed,
        'items_moved': moved,
    }


def _collect_items(data):
    """Collect items with identity and location info using byte-scanning."""
    jm_pos = data.find(b'JM')
    if jm_pos == -1:
        return []

    jf_pos = data.find(b'jf', jm_pos + 4)
    if jf_pos == -1:
        jf_pos = len(data)

    items = []
    for pos in range(jm_pos + 4, min(jf_pos, len(data) - 2)):
        if data[pos] != 0x10 or data[pos + 2] not in (0x80, 0xa0, 0xc0, 0xe0):
            continue

        try:
            hdr = decode_item_header(data, pos)
        except Exception:
            continue

        itype, ilvl, quality, uid, storage, col, row, bodyloc, location, ext = hdr
        tc = itype.strip()
        flags32 = struct.unpack_from('<I', data, pos)[0]

        is_runeword = bool(flags32 & (1 << 26))
        rw_id = None
        if is_runeword:
            nav = navigate_item_structure(
                data, pos, quality, is_runeword,
                bool(flags32 & (1 << 11)), flags32
            )
            if nav[0] is not None:
                rw_id = nav[1]

        desc = tc
        if quality == 7:
            info = UNIQUE_ITEMS.get(uid)
            desc = info['name'] if info else f'unique_{uid}'
        elif quality == 5:
            info = SET_ITEMS.get(uid)
            desc = info['name'] if info else f'set_{uid}'
        elif is_runeword and rw_id is not None:
            info = RUNEWORDS.get(rw_id)
            desc = f"{info['name']} ({tc})" if info else f'rw_{rw_id}'

        loc = _STOR_MAP.get(storage, f'stor_{storage}')
        if storage == 0 and bodyloc > 0:
            loc = _SLOT_MAP.get(bodyloc, f'bodyloc_{bodyloc}')
        elif storage in (1, 4, 5):
            loc = f'{loc}[{col},{row}]'

        items.append({
            'quality': quality,
            'type': tc,
            'uid': uid if uid is not None else (rw_id or 0),
            'desc': desc,
            'loc': loc,
        })

    return items
