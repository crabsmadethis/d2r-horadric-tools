#!/usr/bin/env python3
"""
d2r_scanner.py -- D2R save file diagnostic scanner.

Can be:
  1. Run standalone: python3 d2r_scanner.py [character_name|all]
  2. Imported: from d2r_chargen.scanner import run_scanner, scan_character_data
"""

import struct, sys, os, time, json

from d2r_chargen.data.huffman import HUFFMAN_TREE, RUNE_NAMES
try:
    from d2r_chargen.data.item_stat_cost import ITEM_STAT_COST
    from d2r_chargen.data.item_dimensions import ITEM_DIMENSIONS
    from d2r_chargen.data.unique_items import UNIQUE_ITEMS
    from d2r_chargen.data.set_items import SET_ITEMS
    from d2r_chargen.data.item_bases import ITEM_BASES as ITEM_BASES_FULL
    from d2r_chargen.data.runewords import RUNEWORDS
    _SCANNER_DATA_AVAILABLE = True
except ImportError:
    ITEM_STAT_COST = ITEM_DIMENSIONS = UNIQUE_ITEMS = SET_ITEMS = None
    ITEM_BASES_FULL = RUNEWORDS = None
    _SCANNER_DATA_AVAILABLE = False

# ============================================================
# Constants
# ============================================================
from d2r_chargen.config import SAVES, RW_BASE_CATEGORIES

STAT_DEFS = {
    0:('Strength',10),1:('Energy',10),2:('Dexterity',10),3:('Vitality',10),
    4:('StatPoints',10),5:('SkillPoints',8),6:('HP',21),7:('MaxHP',21),
    8:('Mana',21),9:('MaxMana',21),10:('Stamina',21),11:('MaxStamina',21),
    12:('Level',7),13:('Experience',32),14:('Gold',25),15:('StashedGold',25),
}
CLASSES = ["Amazon","Sorceress","Necromancer","Paladin","Barbarian","Druid","Assassin","Warlock"]
STOR = {0:'equip',1:'inv',2:'belt',3:'?',4:'cube',5:'stash'}


# ============================================================
# Utility Functions
# ============================================================
def bits_at(data, sb, c):
    val=0
    for i in range(c):
        p=sb+i; val|=((data[p>>3]>>(p&7))&1)<<i
    return val

def decode_huff1(data, pos):
    node=HUFFMAN_TREE
    while isinstance(node,list):
        bit=(data[pos>>3]>>(pos&7))&1; pos+=1; node=node[bit]
    return node,pos

def decode_huff4(data, sb):
    result=''; pos=sb
    for _ in range(4):
        ch,pos=decode_huff1(data,pos)
        if ch==' ': break
        result+=ch
    return result,pos

def decode_item_header(data, pos):
    """Return (itype, ilvl, quality, unique_id_or_None, storage, col, row, bodyloc, location, ext)."""
    b4=data[pos+4] if pos+4<len(data) else 0
    ext=((b4&1),(b4>>1)&1,(b4>>2)&1)
    location=bits_at(data,pos*8+35,3)
    bodyloc=bits_at(data,pos*8+38,4)
    col=bits_at(data,pos*8+42,4)
    row=bits_at(data,pos*8+46,3)
    storage=bits_at(data,pos*8+50,3)
    try: itype,type_end=decode_huff4(data,pos*8+53)
    except: return '???',0,0,None,storage,col,row,bodyloc,location,ext
    br=type_end
    br+=3  # nr_in_sockets
    br+=32 # item_id
    ilvl=bits_at(data,br,7); br+=7
    quality=bits_at(data,br,4); br+=4
    # multi_pic: 1-bit flag, if set then 3-bit graphic index
    multi_pic=bits_at(data,br,1); br+=1
    if multi_pic: br+=3
    # class_specific: 1-bit flag, if set then 11-bit class data
    class_spec=bits_at(data,br,1); br+=1
    if class_spec: br+=11
    uid=None
    if quality in (5,7): uid=bits_at(data,br,12)
    return itype,ilvl,quality,uid,storage,col,row,bodyloc,location,ext

def decode_stats(data):
    gf=data.find(b'gf')
    if gf<0: return {},[],'missing_gf'
    br=(gf+2)*8; stats={}; order=[]; term='exhausted'
    for _ in range(25):
        sid=bits_at(data,br,9); br+=9
        if sid==0x1ff: term='clean'; break
        if sid not in STAT_DEFS: term=f'dirty_sid_{sid}'; break
        n,bits=STAT_DEFS[sid]; val=bits_at(data,br,bits); br+=bits
        stats[sid]=val; order.append(sid)
    return stats,order,term

def calc_checksum(data):
    cs=0
    for i,b in enumerate(data):
        if 0x0c<=i<=0x0f: b=0
        cs=(((cs<<1)|(cs>>31))+b)&0xFFFFFFFF
    return cs


# ============================================================
# Core Validation
# ============================================================
def navigate_item_structure(data, pos, quality, is_runeword, is_socketed, flags32):
    """Walk item bit structure to find property start position.

    Navigates the same fields as validate_item_properties (lines 124-228)
    but without validation — pure bit advancement.

    Args:
        data: Full save file bytes.
        pos: BYTE position of item start.
        quality: Item quality (0-8).
        is_runeword: True if runeword flag (bit 26) is set.
        is_socketed: True if socketed flag (bit 11) is set.
        flags32: First 32 bits of item as integer.

    Returns:
        (prop_start_bit, runeword_id) where:
          prop_start_bit: Bit position where property list begins.
          runeword_id: Integer runeword ID if is_runeword, else None.
        Returns (None, None) for simple/ear items with no properties.
    """
    # Simple items and ear items have no properties
    if flags32 & (1 << 16):  # ear
        return None, None
    if flags32 & (1 << 21):  # simple
        return None, None

    base = 0
    br = pos * 8
    br += 32  # flags
    br += 3   # D2R ext
    br += 3   # location
    br += 4   # bodyloc
    br += 4   # col
    br += 3   # row
    br += 1   # unknown
    br += 3   # storage

    # Huffman type code (variable length)
    try:
        tc, br = decode_huff4(data, br)
        tc_stripped = tc.strip()
        base_info = ITEM_BASES_FULL.get(tc_stripped)
        base = base_info['flags'] if base_info else 0
    except Exception:
        return None, None

    br += 3   # nr_in_sockets
    br += 32  # item_id
    br += 7   # ilvl
    br += 4   # quality

    # multi_pic/class_spec conditional widths
    multi_pic = bits_at(data, br, 1); br += 1
    if multi_pic: br += 3
    class_spec = bits_at(data, br, 1); br += 1
    if class_spec: br += 11

    # Quality-specific fields
    if quality == 1:   br += 3     # inferior type
    elif quality == 3: br += 3     # superior type
    elif quality == 4: br += 22    # magic prefix(11) + suffix(11)
    elif quality == 5: br += 12    # set_id
    elif quality == 7: br += 12    # unique_id
    elif quality in (6, 8):        # rare / crafted
        br += 8  # first_name_id
        br += 8  # last_name_id
        for _ in range(6):         # 6 affix slots
            has_affix = bits_at(data, br, 1); br += 1
            if has_affix: br += 11

    # Runeword ID (16 bits if runeword flag set)
    rw_id = None
    if is_runeword:
        rw_id = bits_at(data, br, 16)
        br += 16

    # Personalized item name (7-bit null-terminated)
    if flags32 & (1 << 24):
        for _ in range(20):
            ch = bits_at(data, br, 7); br += 7
            if ch == 0: break

    # Book field
    if base & 8: br += 5

    # Extended body flag (1 bit, +96 if set)
    ext_body = bits_at(data, br, 1); br += 1
    if ext_body: br += 96

    # Defense (armor: base & 4)
    if base & 4: br += 11

    # Durability (weapons/armor: base & 6 nonzero)
    if base & 6:
        max_dur = bits_at(data, br, 8); br += 8
        if max_dur > 0: br += 9

    # Quantity (1-bit flag, +9 if set)
    has_qty = bits_at(data, br, 1); br += 1
    if has_qty: br += 9

    # Sockets (4 bits if socketed flag)
    if is_socketed: br += 4

    # Set item setflags (5 bits)
    if quality == 5: br += 5

    return br, rw_id


def validate_item_properties(data, pos, itype, quality, is_runeword, is_socketed, flags32):
    """Validate property bit stream. Returns (ok, error_msg, end_bit_pos).
    QA-corrected field order -- incorporates fixes C1-C5, H1-H2, M5-M7."""
    # M5: skip ear items (completely different encoding)
    if flags32 & (1 << 16): return True, None, 0
    # M6: skip simple items (no extended data)
    if flags32 & (1 << 21): return True, None, 0

    tc = itype.strip()
    base_info = ITEM_BASES_FULL.get(tc)
    base = base_info['flags'] if base_info else 0
    if base_info is None and quality >= 3:
        return True, None, 0  # M4: unknown base (not in item_bases.py 659 entries), skip

    # Navigate to property start position
    br, rw_id = navigate_item_structure(data, pos, quality, is_runeword, is_socketed, flags32)
    if br is None:
        return True, None, 0

    # Runeword validation (navigate_item_structure found rw_id, now validate it)
    if is_runeword:
        rw_info = RUNEWORDS.get(rw_id)
        if rw_info is None:
            return False, f"runeword_id={rw_id} not in RUNEWORDS database (177 entries)", br
        # Base type compatibility check
        rw_bases = rw_info.get('bases', [])
        if rw_bases and tc in ITEM_BASES_FULL:
            item_cats = ITEM_BASES_FULL[tc].get('categories', [])
            expanded_bases = set()
            for rb in rw_bases:
                expanded_bases.update(RW_BASE_CATEGORIES.get(rb, [rb]))
            if not any(cat in expanded_bases for cat in item_cats):
                return False, (f"runeword '{rw_info['name']}' (id={rw_id}) requires bases "
                    f"{rw_bases} but {tc} has categories {item_cats}"), br

    # --- Property list validation ---
    terminators_expected = 2 if is_runeword else 1
    terminators_found = 0
    seen_stats = set()
    prop_warnings = []

    # Per-stat reasonable maximum values for overflow detection (decoded = raw - sA)
    STAT_MAX_REASONABLE = {
        0: 500, 1: 500, 2: 500, 3: 500,     # attributes (sA=32)
        7: 512, 9: 512, 11: 512,             # life/mana/stam (sA=32)
        16: 511,                               # ED% (sA=0, 9 bits)
        31: 2000,                              # flat def (sA=10)
        39: 311, 41: 311, 43: 311, 45: 311,  # resists (sA=200, 9 bits)
        79: 411, 80: 155,                     # GF/MF (sA=100)
        127: 7,                                # +all skills (3 bits)
        188: 7,                                # skill tab value (3 bits)
    }

    for _ in range(200):  # safety limit
        stat_id = bits_at(data, br, 9); br += 9
        if stat_id == 0x1FF:
            terminators_found += 1
            if terminators_found >= terminators_expected:
                break
            seen_stats.clear()  # reset for runeword bonus property list
            continue

        info = ITEM_STAT_COST.get(stat_id)
        if info is None:
            return False, f"unknown stat_id={stat_id} at bit {br-9}", br

        sB = info.get('sB', 0)
        sP = info.get('sP', 0)
        sA = info.get('sA', 0)
        np_count = info.get('np', 1) or 1

        if sB == 0:
            return False, f"stat_id={stat_id} has sB=0 (unreadable)", br

        # Read param (if any)
        param_val = 0
        if sP > 0:
            param_val = bits_at(data, br, sP)
            br += sP

        # Read value
        raw_val = bits_at(data, br, sB)
        br += sB

        # (a) SKILL_TAB param validation (stat 188, RC-6)
        if stat_id == 188 and sP > 0:
            cls_enc = (param_val >> 3) & 0x1F
            tab_enc = param_val & 0x7
            if cls_enc > 7:
                return False, f"stat 188 (skill_tab): param class={cls_enc} > 7 (invalid)", br
            if tab_enc > 2:
                return False, f"stat 188 (skill_tab): param tab={tab_enc} > 2 (invalid)", br

        # (a2) NON_CLASS_SKILL param validation (stat 97) — skill ID must be valid
        if stat_id == 97 and sP > 0:
            if param_val > 450:
                return False, f"stat 97 (item_nonclassskill): skill_id={param_val} > 450 (invalid)", br
            decoded_level = raw_val - sA
            if decoded_level < 1 or decoded_level > 60:
                prop_warnings.append(f"stat 97 (item_nonclassskill): skill {param_val} level={decoded_level} outside 1-60")

        # (a3) ITEM_AURA param validation (stat 151) — aura skill ID must be valid
        if stat_id == 151 and sP > 0:
            if param_val > 450:
                return False, f"stat 151 (item_aura): aura_id={param_val} > 450 (invalid)", br
            decoded_level = raw_val - sA
            if decoded_level < 1 or decoded_level > 45:
                prop_warnings.append(f"stat 151 (item_aura): aura {param_val} level={decoded_level} outside 1-45")

        # (b) Property value overflow detection (RC-7, WARNING only)
        decoded_val = raw_val - sA
        max_reasonable = STAT_MAX_REASONABLE.get(stat_id)
        if max_reasonable is not None and decoded_val > max_reasonable:
            stat_name = info.get('s', f'stat_{stat_id}')
            prop_warnings.append(f"stat {stat_id} ({stat_name}): value {decoded_val} exceeds max {max_reasonable}")
        if decoded_val < -500 and sA > 0:
            stat_name = info.get('s', f'stat_{stat_id}')
            return False, f"stat {stat_id} ({stat_name}): value {decoded_val} implausibly negative (raw={raw_val}, sA={sA})", br

        # (c) Duplicate stat detection (RC-10, WARNING only)
        if stat_id in seen_stats:
            stat_name = info.get('s', f'stat_{stat_id}')
            prop_warnings.append(f"duplicate stat_id={stat_id} ({stat_name})")
        seen_stats.add(stat_id)

        # P1-5: np-grouped stat handling
        if np_count > 1:
            peek = bits_at(data, br, 9) if br + 9 <= len(data) * 8 else 0
            if peek != stat_id + 1:
                for k in range(1, np_count):
                    sibling = ITEM_STAT_COST.get(stat_id + k)
                    br += sibling.get('sB', sB) if sibling else sB
    else:
        return False, f"exceeded 200 stats without {terminators_expected} terminators", br

    if terminators_found < terminators_expected:
        return False, f"found {terminators_found}/{terminators_expected} terminators", br

    # Return end bit position as third element for zero-padding check by caller
    if prop_warnings:
        return True, "WARNINGS: " + "; ".join(prop_warnings), br

    return True, None, br


# ============================================================
# Grid Visualization
# ============================================================
def grid_view(occupied, cols, rows, label):
    """ASCII grid: occupied cells show item type, free cells show '.'"""
    grid=[['.' for _ in range(cols)] for _ in range(rows)]
    for (c,r),val in occupied.items():
        itype = val[0] if isinstance(val, tuple) else val
        if 0<=r<rows and 0<=c<cols:
            grid[r][c]=itype[:1].upper()
    print(f"  {label} ({cols}\u00d7{rows}):")
    hdr='    '+''.join(str(c%10) for c in range(cols))
    print(hdr)
    for r,row_data in enumerate(grid):
        print(f"  {r:2d}|{''.join(row_data)}|")
    print()


# ============================================================
# Pre-flight Checks
# ============================================================
def preflight_check():
    """Run pre-flight checks on the save directory.
    Returns (all_files, ghost_chars, save_total, bak_total, bak_files, preflight_issues).
    Prints preflight report to stdout.
    """
    all_files = os.listdir(SAVES)
    preflight_issues = 0

    # 1. Ghost characters (.ctl without .d2s)
    ctl_chars = {f[:-4] for f in all_files if f.endswith('.ctl')}
    d2s_chars = {f[:-4] for f in all_files if f.endswith('.d2s') and '.' not in f[:-4]}
    ghost_chars = sorted(ctl_chars - d2s_chars)
    if ghost_chars:
        print("=" * 60)
        print("  \u26a0 GHOST CHARACTERS (will crash game at launch!)")
        print("=" * 60)
        for gc in ghost_chars:
            bak = [f for f in all_files if f.startswith(gc + '.d2s.') and f.endswith('_bak')]
            bak.sort(key=lambda f: os.path.getmtime(os.path.join(SAVES, f)), reverse=True)
            print(f"  \u2717 {gc}: has .ctl but NO .d2s file")
            if bak:
                newest = bak[0]
                mt = time.strftime('%m-%d %H:%M', time.localtime(os.path.getmtime(os.path.join(SAVES, newest))))
                print(f"    \u2192 restore from: {newest} ({os.path.getsize(os.path.join(SAVES, newest))}B [{mt}])")
            else:
                print(f"    \u2192 no backup found \u2014 remove {gc}.ctl/.key/.ma*/.map to unblock launch")
            preflight_issues += 1
        print()

    # 2. Truncated / zero-byte .d2s files
    MIN_D2S_SIZE = 335
    for f in sorted(all_files):
        if f.endswith('.d2s') and '.' not in f[:-4]:
            fpath = os.path.join(SAVES, f)
            sz = os.path.getsize(fpath)
            if sz < MIN_D2S_SIZE:
                if preflight_issues == 0:
                    print("=" * 60)
                    print("  \u26a0 CORRUPT SAVE FILES")
                    print("=" * 60)
                print(f"  \u2717 {f}: only {sz}B (minimum valid ~{MIN_D2S_SIZE}B)")
                bak = [b for b in all_files if b.startswith(f + '.') and b.endswith('_bak')]
                bak.sort(key=lambda b: os.path.getmtime(os.path.join(SAVES, b)), reverse=True)
                if bak:
                    print(f"    \u2192 restore from: {bak[0]}")
                preflight_issues += 1

    # 3. Shared stash integrity
    d2i_files = [f for f in all_files if f.endswith('.d2i')]
    for d2i in d2i_files:
        d2i_path = os.path.join(SAVES, d2i)
        sz = os.path.getsize(d2i_path)
        if sz < 16:
            if preflight_issues == 0:
                print("=" * 60)
                print("  \u26a0 SHARED STASH ISSUES")
                print("=" * 60)
            print(f"  \u2717 {d2i}: only {sz}B \u2014 likely corrupt")
            preflight_issues += 1
        else:
            with open(d2i_path, 'rb') as fh:
                d2i_data = bytearray(fh.read())
            d2i_sig = struct.unpack_from('<I', d2i_data, 0)[0] if len(d2i_data) >= 4 else 0
            if d2i_sig not in (0xAA55AA55, 0x00000061, 0x61):
                pass  # stash format varies; skip sig check but verify size
            d2i_stored_size = struct.unpack_from('<I', d2i_data, 4)[0] if len(d2i_data) >= 8 else 0
            print(f"  Shared stash: {d2i} ({sz}B)")

    # 4. Orphan support files
    support_exts = {'.key', '.ma0', '.ma1', '.ma2', '.ma3', '.map'}
    support_chars = set()
    for f in all_files:
        base, ext = os.path.splitext(f)
        if ext in support_exts and '.' not in base:
            support_chars.add(base)
    orphans = sorted(support_chars - ctl_chars - d2s_chars)
    if orphans:
        print(f"  ! Orphan files (no .ctl/.d2s): {', '.join(orphans)}")
        preflight_issues += 1

    # 5. Quarantine folder
    qdir = os.path.join(SAVES, 'quarantine')
    if os.path.isdir(qdir):
        qfiles = os.listdir(qdir)
        if qfiles:
            q_size = sum(os.path.getsize(os.path.join(qdir, f)) for f in qfiles)
            print(f"  Quarantine: {len(qfiles)} files ({q_size}B)")
            for qf in sorted(qfiles):
                mt = time.strftime('%m-%d %H:%M', time.localtime(os.path.getmtime(os.path.join(qdir, qf))))
                print(f"    {qf} ({os.path.getsize(os.path.join(qdir, qf))}B [{mt}])")

    # 6. Backup bloat + disk usage
    bak_files = [f for f in all_files if '_bak' in f or f.endswith('.bak')]
    bak_total = sum(os.path.getsize(os.path.join(SAVES, f)) for f in bak_files)
    save_total = sum(os.path.getsize(os.path.join(SAVES, f)) for f in all_files if os.path.isfile(os.path.join(SAVES, f)))
    oldest_bak = None
    if bak_files:
        oldest_bak = min(bak_files, key=lambda f: os.path.getmtime(os.path.join(SAVES, f)))
        oldest_mt = time.strftime('%m-%d %H:%M', time.localtime(os.path.getmtime(os.path.join(SAVES, oldest_bak))))
    print(f"  Disk: {save_total//1024}KB total, {bak_total//1024}KB in {len(bak_files)} backups", end='')
    if oldest_bak:
        print(f" (oldest: {oldest_mt})")
    else:
        print()

    if preflight_issues == 0:
        print("  Pre-flight: all clear")
    print()

    return all_files, ghost_chars, save_total, bak_total, bak_files, preflight_issues


# ============================================================
# Per-Character Scan + Report
# ============================================================
def scan_characters(target, all_files, ghost_chars):
    """Scan characters and print report. Returns list of (fname, data) for delta tracking."""
    files = [f for f in all_files if f.endswith('.d2s') and '.' not in f[:-4]]
    files = sorted(files)
    if target != 'all':
        files = [f for f in files if target in f.lower()]

    for fname in files:
        path=os.path.join(SAVES,fname)
        with open(path,'rb') as f: data=bytearray(f.read())

        sig=struct.unpack_from('<I',data,0)[0]
        version=struct.unpack_from('<I',data,4)[0]
        stored_size=struct.unpack_from('<I',data,8)[0]
        stored_cs=struct.unpack_from('<I',data,0x0c)[0]
        calc_cs=calc_checksum(data)
        cls_id=data[0x18]; lvl_byte=data[0x1b]
        name_end=data.find(b'\x00',0x12b)
        char_name=data[0x12b:name_end].decode('ascii','replace') if name_end>0 else '?'

        jm=-1
        for i in range(0x300,min(len(data)-4,0x500)):
            if data[i:i+2]==b'JM': jm=i; break
        item_count=struct.unpack_from('<H',data,jm+2)[0] if jm>=0 else -1
        jf_marker=data.find(b'jf',jm+4) if jm>=0 else -1
        merc_jm=data.find(b'JM',jf_marker+2) if jf_marker>=0 else -1
        dead_body_jm=data.find(b'JM',jm+4) if jm>=0 else -1
        merc_count=struct.unpack_from('<H',data,merc_jm+2)[0] if merc_jm>=0 else -1

        # Section ordering validation
        if jm >= 0 and dead_body_jm > 0 and jf_marker > 0 and merc_jm > 0:
            if not (jm < dead_body_jm < jf_marker < merc_jm):
                print(f"  !! SECTION ORDER ERROR: JM[char]@{jm} JM[dead]@{dead_body_jm} jf@{jf_marker} JM[merc]@{merc_jm}")
                print(f"     Expected: JM[char] < JM[dead_body] < jf < JM[merc]")
        elif jm >= 0 and jf_marker < 0:
            print(f"  !! MISSING jf MARKER: cannot locate corpse/merc sections")
        elif jm >= 0 and merc_jm < 0:
            print(f"  !! MISSING JM[merc]: cannot locate merc item section")

        ws=data.find(b'WS')
        nm_wp=data[ws+34:ws+40].hex() if ws>=0 else 'N/A'
        hell_wp=data[ws+58:ws+64].hex() if ws>=0 else 'N/A'

        stats,_,stats_term=decode_stats(data)
        if stats_term=='missing_gf':
            print(f"  !! STATS BLOCK MISSING: no 'gf' marker \u2014 file may be truncated")
        elif stats_term=='exhausted':
            print(f"  !! STATS BLOCK: 25-stat limit reached without 0x1FF terminator \u2014 corrupt encoding")
        elif stats_term.startswith('dirty_sid_'):
            bad_sid=stats_term.split('_')[-1]
            print(f"  !! STATS BLOCK DIRTY TERMINATION: unknown stat_id={bad_sid} before 0x1FF terminator")
            print(f"     Decoded {len(stats)} stats before failure \u2014 block may be corrupt or misaligned")
        ifm=data.find(b'if')
        skills=list(data[ifm+2:ifm+32]) if ifm>=0 else []
        skills_spent=sum(skills)
        skills_unspent=stats.get(5,0)

        print(f"{'='*60}")
        print(f"  {fname}  [{CLASSES[cls_id] if cls_id<len(CLASSES) else f'cls{cls_id}'}  lv{lvl_byte}]")
        print(f"{'='*60}")
        if sig != 0xAA55AA55:
            print(f"  \u26a0 BAD SIGNATURE: expected 0xAA55AA55, got 0x{sig:08X}")
        if version != 105:
            print(f"  \u2139 VERSION: expected 105, got {version}")
        status_byte = data[0x14]
        is_hc = bool(status_byte & 0x04)
        is_died = bool(status_byte & 0x08)
        if is_hc and is_died:
            print(f"  !! DEAD HARDCORE: status=0x{status_byte:02X} — bit 2 (HC) + bit 3 (died) both set → cannot join game")
            print(f"     Fix: data[0x14] = 0x04  (clear died flag, keep HC)")
        print(f"  Checksum:  {'OK' if stored_cs==calc_cs else f'MISMATCH! calc={calc_cs:#010x}'} ({stored_cs:#010x})")
        size_match = '\u2713' if len(data) == stored_size else '\u2717 MISMATCH'
        print(f"  Size:      {len(data)}B (stored:{stored_size}) {size_match}")
        if len(data) != stored_size:
            print(f"  \u26a0 FILE SIZE MISMATCH: actual={len(data)} stored={stored_size} \u2014 file may be truncated or corrupted")
        print(f"  Items:     {item_count} char + {merc_count} merc")
        wp_ok = '\u2713' if hell_wp=='ffffffff7f00' else '?'
        print(f"  WP NM:     {nm_wp}  Hell: {hell_wp} {wp_ok}")
        prog_errors, prog_warnings = check_progression_consistency(data)
        if prog_errors:
            for pe in prog_errors:
                print(f"  !! PROGRESSION: {pe}")
        if prog_warnings:
            for pw in prog_warnings:
                print(f"  \u26a0 PROGRESSION: {pw}")
        CLASS_BASE_STATS={
            0:(20,15,25,20),1:(10,35,25,10),2:(15,25,25,15),3:(25,15,20,25),
            4:(30,10,20,25),5:(15,20,20,25),6:(20,25,20,20),7:(8,20,20,8),
        }
        if stats:
            hp=stats.get(7,0)/256; mana=stats.get(9,0)/256
            print(f"  Stats:     Str={stats.get(0,'?')} Dex={stats.get(2,'?')} Vit={stats.get(3,'?')} En={stats.get(1,'?')}")
            print(f"             HP={hp:.0f} Mana={mana:.0f} XP={stats.get(13,'?')}")
            base=CLASS_BASE_STATS.get(cls_id)
            if base:
                for sid,idx,name in [(0,0,'Str'),(1,1,'En'),(2,2,'Dex'),(3,3,'Vit')]:
                    val=stats.get(sid,0)
                    if val<base[idx]:
                        print(f"  \u26a0 {name}={val} BELOW BASE ({base[idx]}) \u2014 server will reject (Error:7)")
            lvl = stats.get(12, 0)
            xp = stats.get(13, 0)
            if lvl == 99 and xp != 3520485254:
                print(f"  \u26a0 XP MISMATCH: level 99 requires XP=3520485254, got {xp}")
            missing_stats=[(sid,STAT_DEFS[sid][0]) for sid in range(16) if sid not in stats]
            if missing_stats:
                print(f"  !! MISSING STATS ({len(missing_stats)}):")
                for msid,mname in missing_stats:
                    print(f"     stat {msid} ({mname}) \u2014 NOT in stats block (Battle.net will reject)")
            if base and 12 in stats:
                invested=sum(stats.get(sid,0)-base[idx] for sid,idx in [(0,0),(1,1),(2,2),(3,3)])
                unspent=stats.get(4,0); budget=5*(stats.get(12,1)-1); max_budget=budget+15
                total_used=invested+unspent
                if total_used>max_budget:
                    print(f"  !! STAT BUDGET OVERFLOW: invested={invested}+unspent={unspent}={total_used}, max={max_budget}")
                elif total_used<budget:
                    print(f"  !! STAT BUDGET DEFICIT: invested={invested}+unspent={unspent}={total_used}, expected {budget}-{max_budget}")
            for cur_id,max_id,label in [(6,7,'HP'),(8,9,'Mana'),(10,11,'Stamina')]:
                cur_val=stats.get(cur_id); max_val=stats.get(max_id)
                if cur_val is not None and max_val is not None and cur_val>max_val:
                    print(f"  !! {label} OVERFLOW: current={cur_val/256:.0f} > max={max_val/256:.0f}")
        print(f"  Skills:    {skills_spent} spent / {skills_unspent} unspent")
        nonzero_skills=[(i,v) for i,v in enumerate(skills) if v]
        if nonzero_skills:
            print(f"             non-zero: {nonzero_skills}")

        # Per-character sanity checks
        expected_name = fname[:-4]
        if char_name != expected_name:
            print(f"  \u26a0 NAME MISMATCH: file={expected_name} but internal name={char_name}")

        if len(data) > 0xA9:
            diff_act = data[0xA9]
            if diff_act > 14:
                print(f"  \u26a0 DIFFICULTY BYTE: 0xA9={diff_act} out of range (valid 0-14)")
            else:
                prog_byte = data[0x15] if len(data) > 0x15 else 0
                diff_tier = diff_act // 5
                prog_tier = {0:0, 5:1, 0x0F:2}.get(prog_byte, -1)
                if prog_tier >= 0 and diff_tier > prog_tier:
                    diff_names = ['Normal','NM','Hell']
                    print(f"  \u26a0 DIFFICULTY/PROGRESSION: active={diff_names[diff_tier]} (0xA9={diff_act}) but progression only unlocks up to {diff_names[prog_tier]} (0x15=0x{prog_byte:02x})")

        prog = data[0x15] if len(data) > 0x15 else 0
        prog_label = {0:'Normal',5:'NM unlocked',0x0F:'Hell unlocked'}.get(prog, f'prog=0x{prog:02x}')
        if prog >= 0x0F and lvl_byte < 2:
            print(f"  \u26a0 PROGRESSION/LEVEL: Hell unlocked but lv{lvl_byte} \u2014 likely needs rebuild")
        elif prog == 0 and lvl_byte >= 40:
            print(f"  \u26a0 PROGRESSION/LEVEL: lv{lvl_byte} but still Normal-only (prog=0x{prog:02x})")
        print()

        # Scan items + build grid
        inv_occ={}; stash_occ={}; cube_occ={}
        wrong_ext=[]; all_items=[]; runeword_flags={}; collisions=[]; prop_errors=[]
        uid_errors=[]; set_errors=[]; socket_errors=[]; storage_errors=[]
        zero_pad_candidates={}
        notable_types={'fla','uit','7pa','6ws','cjwl','cm3','cm2','cm1','ci1','ci2','ci3'}

        char_item_end = dead_body_jm if dead_body_jm > 0 else (jf_marker if jf_marker > 0 else len(data)-4)
        for pos in range(jm+4 if jm>=0 else 0, char_item_end):
            b0,b2=data[pos],data[pos+2]
            if b0==0x10 and b2 in (0x80, 0xa0, 0xc0, 0xe0):  # bit23 + optional eth(0x40)/compact(0x20)
                try:
                    itype,ilvl,quality,uid,storage,col,row,bodyloc,location,ext=decode_item_header(data,pos)
                except: continue
                all_items.append((pos,itype,ilvl,quality,uid,storage,col,row,bodyloc,location,ext))
                flags32=struct.unpack_from('<I',data,pos)[0]
                if flags32 & (1<<26): runeword_flags[pos]=True
                if ext!=(1,0,1): wrong_ext.append((pos,itype,storage,col,row,ext))
                if storage not in (0, 1, 2, 4, 5):
                    storage_errors.append((pos, itype, storage, col, row,
                        f"invalid storage={storage} (valid: 0=equip,1=inv,2=belt,4=cube,5=stash)"))
                tc=itype.strip()
                w,h=ITEM_DIMENSIONS.get(tc,(1,1))
                cells=[(col+dc,row+dr) for dc in range(w) for dr in range(h)]
                target_occ={1:inv_occ,5:stash_occ,4:cube_occ}.get(storage)
                if target_occ is not None:
                    for cell in cells:
                        if cell in target_occ and target_occ[cell]!=(itype,pos):
                            collisions.append((pos,itype,storage,col,row,cell,target_occ[cell]))
                        target_occ[cell]=(itype,pos)
                if quality == 7 and uid is not None:
                    uinfo = UNIQUE_ITEMS.get(uid)
                    if uinfo is None:
                        uid_errors.append((pos, itype, storage, col, row, f"uid={uid} not in UNIQUE_ITEMS"))
                    elif uinfo['code'] != tc and tc != '???':
                        uid_errors.append((pos, itype, storage, col, row,
                            f"uid={uid} ({uinfo['name']}) expects code='{uinfo['code']}' but item has '{tc}'"))
                if quality == 5 and uid is not None:
                    sinfo = SET_ITEMS.get(uid)
                    if sinfo is None:
                        set_errors.append((pos, itype, storage, col, row, f"set_id={uid} not in SET_ITEMS"))
                    elif sinfo['code'] != tc and tc != '???':
                        set_errors.append((pos, itype, storage, col, row,
                            f"set_id={uid} ({sinfo['name']}) expects code='{sinfo['code']}' but item has '{tc}'"))
                if flags32 & (1<<11) and tc in ITEM_BASES_FULL:
                    base_info = ITEM_BASES_FULL[tc]
                    max_sock = base_info.get('max_sockets', 6)
                    if max_sock == 0:
                        socket_errors.append((pos, itype, storage, col, row,
                            f"socketed flag set but {tc} ({base_info.get('name','?')}) has max_sockets=0"))
                if quality >= 1:
                    try:
                        prop_ok, prop_err, prop_end_br = validate_item_properties(
                            data, pos, itype, quality,
                            pos in runeword_flags,
                            bool(flags32 & (1<<11)),
                            flags32
                        )
                        if not prop_ok:
                            prop_errors.append((pos, itype, storage, col, row, prop_err))
                        elif prop_err:
                            prop_errors.append((pos, itype, storage, col, row, prop_err))
                        # Store end bit for zero-padding check after scan completes
                        if prop_ok and prop_end_br > 0 and prop_end_br % 8 == 0:
                            zero_pad_candidates[pos] = (itype, storage, col, row, prop_end_br)
                    except Exception as ex:
                        prop_errors.append((pos, itype, storage, col, row, f"parse exception: {ex}"))

        # Item count mismatch
        # JM count only includes parent/standalone items, NOT socket fillers (location=6)
        parent_count = sum(1 for _,_,_,_,_,_,_,_,_,loc,_ in all_items if loc != 6)
        filler_count = len(all_items) - parent_count
        scanned_count = parent_count
        if scanned_count != item_count:
            print(f"  \u26a0 ITEM COUNT MISMATCH: JM[char] header={item_count} but scanner found {scanned_count} parents (+{filler_count} socket fillers)")
            print(f"    Likely cause: items added/removed without updating JM count header")
        elif filler_count > 0:
            print(f"  Items: {item_count} parents + {filler_count} socket fillers = {len(all_items)} total")

        # Zero-padding check: verify items whose property stream ends byte-aligned
        # actually have padding in the file (item size > expected unpadded size)
        if zero_pad_candidates:
            for idx in range(len(all_items)):
                item_pos = all_items[idx][0]
                if item_pos in zero_pad_candidates:
                    itype_zp, stor_zp, col_zp, row_zp, end_br = zero_pad_candidates[item_pos]
                    next_pos = all_items[idx+1][0] if idx+1 < len(all_items) else char_item_end
                    actual_size = next_pos - item_pos
                    unpadded_size = (end_br - item_pos * 8) // 8
                    if actual_size <= unpadded_size:
                        prop_errors.append((item_pos, itype_zp, stor_zp, col_zp, row_zp,
                            f"ZERO-PADDING: {actual_size}B with 0 padding bits — D2R v105 will reject"))

        # Notable items
        def qname(q): return {2:'nrm',3:'sup',4:'mag',5:'set',6:'rare',7:'uniq',8:'crft'}.get(q,f'q{q}')

        print("  NOTABLE ITEMS:")
        for pos,itype,ilvl,quality,uid,storage,col,row,bodyloc,location,ext in all_items:
            rn=RUNE_NAMES.get(itype,'')
            is_notable=(itype.strip() in notable_types or rn or quality==7 or itype.startswith('ci'))
            if is_notable:
                ext_ok='\u2713' if ext==(1,0,1) else f'\u2717ext={ext}'
                uid_s=f' uid={uid}' if uid is not None else ''
                stor_s=STOR.get(storage,str(storage))
                label=rn if rn else itype
                rw_tag=' [RW]' if pos in runeword_flags else ''
                print(f"    {ext_ok} {label:8s} {qname(quality):5s} ilvl={ilvl:3d}{uid_s:10s} {stor_s}({col},{row}){rw_tag}")
        print()

        # Merc items
        merc_slots={}; merc_item_count=0; merc_filler_count=0
        merc_count_val = 0
        if merc_jm>=0:
            kf_pos=data.find(b'kf',merc_jm+4)
            merc_end=kf_pos if kf_pos>0 else merc_jm+200
            for pos in range(merc_jm+4,merc_end-4):
                b0=data[pos]
                b2=data[pos+2] if pos+2<len(data) else 0
                if b0==0x10 and b2 in (0x80, 0xa0, 0xc0, 0xe0):  # bit23 + optional eth(0x40)/compact(0x20)
                    try:
                        itype,ilvl,quality,uid,storage,col,row,bodyloc,location,ext=decode_item_header(data,pos)
                        merc_item_count+=1
                        if location == 6:
                            merc_filler_count+=1
                        else:
                            rn=RUNE_NAMES.get(itype,''); label=rn if rn else itype
                            merc_slots[bodyloc]=(label,quality,uid)
                        if quality >= 1:
                            try:
                                flags32_m=struct.unpack_from('<I',data,pos)[0]
                                is_rw_m = bool(flags32_m & (1<<26))
                                is_sock_m = bool(flags32_m & (1<<11))
                                mp_ok, mp_err, _ = validate_item_properties(
                                    data, pos, itype, quality, is_rw_m, is_sock_m, flags32_m)
                                if not mp_ok:
                                    prop_errors.append((pos, itype, 0, col, row, f"[MERC] {mp_err}"))
                                elif mp_err:
                                    prop_errors.append((pos, itype, 0, col, row, f"[MERC] {mp_err}"))
                            except Exception as mex:
                                prop_errors.append((pos, itype, 0, col, row, f"[MERC] parse exception: {mex}"))
                    except: pass
            merc_count_val=struct.unpack_from('<H',data,merc_jm+2)[0]
            merc_parent_count = merc_item_count - merc_filler_count
            if merc_parent_count!=merc_count_val:
                print(f"  \u26a0 MERC COUNT MISMATCH: JM[merc] header={merc_count_val} but found {merc_parent_count} parents (+{merc_filler_count} socket fillers)")
            elif merc_filler_count > 0:
                print(f"  Merc items: {merc_count_val} parents + {merc_filler_count} socket fillers = {merc_item_count} total")
            merc_list=[f"{v[0]}({qname(v[1])})" for v in merc_slots.values()]
            print(f"  MERC: {', '.join(merc_list) if merc_list else '(none)'}")
            if merc_item_count > 0:
                print(f"  ! REMINDER: Pre-injected merc items can cause Error:8 even with correct lf_count.")
                print(f"    Rule 6: Place merc gear in stash (storage=5) and equip in-game.")

        # Item property size check
        print()
        if len(all_items)>=1:
            item_sizes=[]
            for i,(pos,itype,ilvl,quality,uid,storage,col,row,bodyloc,location,ext) in enumerate(all_items):
                next_pos=all_items[i+1][0] if i+1<len(all_items) else char_item_end if char_item_end>0 else len(data)
                item_sizes.append((next_pos-pos,itype,quality,uid,storage,location))

            # P0-RUNE: Rune items (location=6, type r01-r33) must be >= 11 bytes
            rune_undersized = []
            for sz,t,q,u,st,loc in item_sizes:
                tc = t.strip()
                if loc == 6 and tc.startswith('r') and tc[1:].isdigit():
                    rn = RUNE_NAMES.get(t, tc)
                    if sz < 11:
                        rune_undersized.append((tc, rn, sz))
            if rune_undersized:
                print(f"  !! RUNE SIZE ERRORS ({len(rune_undersized)} runes):")
                for tc, rn, sz in rune_undersized:
                    print(f"    {rn} ({tc}): {sz}B < 11B minimum — D2R will reject (FAILED TO JOIN GAME)")
                    print(f"    Fix: encode_socketed_rune() must ensure >=2 padding bits (r27/r29 need special handling)")

            uniq_sizes=[s for s,t,q,u,st,loc in item_sizes if q==7]
            rw_sizes=[s for s,t,q,u,st,loc in item_sizes if q==2 and st==0 and s>15]
            if uniq_sizes:
                avg=sum(uniq_sizes)/len(uniq_sizes)
                status='\u2713' if avg>=28 else '\u26a0 STATLESS?' if avg<25 else '?'
                print(f"  ITEM SIZES: uniq avg={avg:.0f}B (n={len(uniq_sizes)})  {status}")
                if avg<25:
                    print(f"  \u26a0 Unique items avg {avg:.0f}B \u2014 likely missing stat properties (expect 30-45B)")
                    print(f"    Items built with build_item(unique_id=X) without properties?")
                    print(f"    Use build_lib.encode_property() for full stat encoding.")
            if rw_sizes:
                avg_rw=sum(rw_sizes)/len(rw_sizes)
                if avg_rw<25:
                    print(f"  \u26a0 Runeword bases avg {avg_rw:.0f}B \u2014 likely missing runeword properties")

        # Duplicate unique check
        equipped_uids={}
        for _,itype,ilvl,quality,uid,storage,col,row,bodyloc,location,ext in all_items:
            if storage==0 and quality==7 and uid is not None:
                if uid in equipped_uids:
                    prev_str=', '.join(str(s) for s in equipped_uids[uid])
                    print(f"  \u2139 DUPLICATE UNIQUE: uid={uid} in slots {prev_str} and {bodyloc} (allowed if different slots)")
                equipped_uids.setdefault(uid,[]).append(bodyloc)

        # lf consistency
        kf_pos=data.find(b'kf')
        lf_pos=data.find(b'lf',kf_pos) if kf_pos>=0 else -1
        lf_count=0
        if lf_pos>=0:
            lf_count=struct.unpack_from('<H',data,lf_pos+2)[0]
            merc_count_val2=struct.unpack_from('<H',data,merc_jm+2)[0] if merc_jm>=0 else 0
            consistent=(merc_count_val2==0 and lf_count==0) or (lf_count>=1)
            status='\u2713 consistent' if consistent else f'\u2717 INCONSISTENT \u2014 "failed to join game"'
            print(f"  LF:   lf_count={lf_count}  merc_items={merc_count_val2}  {status}")

        # kf/lf structural validation
        if kf_pos >= 0:
            golem_flag = data[kf_pos + 2] if kf_pos + 2 < len(data) else 255
            if golem_flag not in (0, 1):
                print(f"  !! IRON GOLEM FLAG: kf+2 = {golem_flag} (expected 0 or 1) -- corrupt tail section")
            if lf_pos >= 0 and lf_pos - kf_pos > 200:
                print(f"  !! kf-lf GAP: {lf_pos - kf_pos} bytes between kf and lf (expected ~5-10)")

        # Encoding issues
        if wrong_ext:
            print(f"  ENCODING ISSUES (will be silently deleted on load):")
            for pos,itype,stor,col,row,ext in wrong_ext:
                print(f"    @{pos} {itype} {STOR.get(stor,stor)}({col},{row}) ext={ext}")

        if uid_errors:
            print(f"  \u26a0 UNIQUE UID ERRORS ({len(uid_errors)} items):")
            for pos,itype,stor,col,row,err in uid_errors:
                stor_s=STOR.get(stor,str(stor))
                print(f"    @{pos} {itype} {stor_s}({col},{row}): {err}")

        if set_errors:
            print(f"  \u26a0 SET ITEM ERRORS ({len(set_errors)} items):")
            for pos,itype,stor,col,row,err in set_errors:
                stor_s=STOR.get(stor,str(stor))
                print(f"    @{pos} {itype} {stor_s}({col},{row}): {err}")

        if socket_errors:
            print(f"  \u26a0 SOCKET ERRORS ({len(socket_errors)} items):")
            for pos,itype,stor,col,row,err in socket_errors:
                stor_s=STOR.get(stor,str(stor))
                print(f"    @{pos} {itype} {stor_s}({col},{row}): {err}")

        if storage_errors:
            print(f"  !! STORAGE ID ERRORS ({len(storage_errors)} items):")
            for pos,itype,stor,col,row,err in storage_errors:
                print(f"    @{pos} {itype} stor={stor}({col},{row}): {err}")

        if prop_errors:
            print(f"  \u26a0 PROPERTY ERRORS ({len(prop_errors)} items):")
            for pos,itype,stor,col,row,err in prop_errors:
                rn=RUNE_NAMES.get(itype,'')
                label=rn if rn else itype
                stor_s=STOR.get(stor,str(stor))
                rw_tag=' [RW]' if pos in runeword_flags else ''
                print(f"    @{pos} {label} {stor_s}({col},{row}){rw_tag}: {err}")

        # Completeness check
        print()
        CSLOT={1:'helm',2:'neck',3:'body',4:'RH-weapon',5:'LH/shield',
               6:'R-ring',7:'L-ring',8:'belt',9:'feet',10:'hands',
               11:'switch-RH',12:'switch-LH'}
        MSLOT={1:'helm',3:'body',4:'weapon'}

        char_slots={}
        for _,itype,ilvl,quality,uid,storage,col,row,bodyloc,_,_ in all_items:
            if storage==0 and bodyloc>=1:
                if bodyloc not in char_slots or quality>char_slots[bodyloc][1]:
                    char_slots[bodyloc]=(itype,quality,uid)

        any_issue=False
        print("  CHAR SLOTS:")
        for sid,sname in CSLOT.items():
            if sid not in char_slots:
                print(f"    \u2717 EMPTY      : {sname}"); any_issue=True
            else:
                itype,quality,uid=char_slots[sid]
                rn=RUNE_NAMES.get(itype,''); label=rn if rn else itype
                uid_s=f' uid={uid}' if uid else ''
                ACCEPTABLE_NRM={'aqv','cqv','ibk','tbk'}
                is_runeword = False
                for p2,it2,_,_,_,st2,_,_,bl2,_,_ in all_items:
                    if st2==0 and bl2==sid and it2==itype:
                        is_runeword = p2 in runeword_flags
                        break
                flag=('' if itype.strip() in ACCEPTABLE_NRM or is_runeword else
                      '  \u2190 PLACEHOLDER' if quality<=2 else
                      ('  \u2190 WEAK (magic)' if quality==4 else ''))
                mark='!' if flag else '\u2713'
                print(f"    {mark} {sname:12s}: {label}{uid_s} ({qname(quality)}){flag}")
                if flag: any_issue=True

        # Bodyloc compatibility check
        BODYLOC_CATEGORIES = {
            1: ['Helm', 'Circlet', 'Pelt', 'Primal Helm'],
            2: ['Amulet'],
            3: ['Armor', 'Body Armor'],
            4: ['Weapon', 'Melee Weapon', 'Missile Weapon', 'Mace', 'Sword', 'Axe', 'Bow',
                'Crossbow', 'Dagger', 'Javelin', 'Polearm', 'Scepter', 'Spear', 'Staff',
                'Wand', 'Club', 'Hammer', 'Knife', 'Throwing Axe', 'Throwing Knife',
                'Amazon Weapon', 'Assassin Claw', 'Sorceress Orb'],
            5: ['Shield', 'Any Shield', 'Auric Shields', 'Voodoo Heads', 'Second Hand',
                'Weapon', 'Melee Weapon', 'Missile Weapon'],
            6: ['Ring'], 7: ['Ring'],
            8: ['Belt'],
            9: ['Boots'],
            10: ['Gloves'],
            11: ['Weapon', 'Melee Weapon', 'Missile Weapon', 'Mace', 'Sword', 'Axe',
                 'Bow', 'Crossbow', 'Dagger', 'Javelin', 'Polearm', 'Scepter', 'Spear',
                 'Staff', 'Wand', 'Club', 'Hammer', 'Amazon Weapon', 'Assassin Claw',
                 'Sorceress Orb'],
            12: ['Shield', 'Any Shield', 'Auric Shields', 'Weapon', 'Melee Weapon'],
        }
        for _,it2,_,_,_,st2,_,_,bl2,_,_ in all_items:
            if st2 == 0 and bl2 >= 1 and bl2 <= 12:
                tc2 = it2.strip()
                bi = ITEM_BASES_FULL.get(tc2)
                if bi and bl2 in BODYLOC_CATEGORIES:
                    item_cats = bi.get('categories', [])
                    expected_cats = BODYLOC_CATEGORIES[bl2]
                    if not any(cat in item_cats for cat in expected_cats):
                        print(f"    !! BODYLOC MISMATCH: {tc2} ({bi['name']}) in {CSLOT.get(bl2,'?')} "
                              f"(bodyloc={bl2}) -- categories {item_cats} don't match expected {expected_cats}")
                        any_issue = True

        # Bodyloc duplicate detection
        bodyloc_items = {}
        for _,it2,_,q2,u2,st2,_,_,bl2,_,_ in all_items:
            if st2 == 0 and bl2 >= 1:
                bodyloc_items.setdefault(bl2, []).append((it2, q2, u2))
        for bl, items_list in bodyloc_items.items():
            if len(items_list) > 1:
                print(f"    !! BODYLOC COLLISION: {len(items_list)} items in slot {bl} ({CSLOT.get(bl,'?')})")
                for it, q, u in items_list:
                    print(f"         {it} quality={q} uid={u}")
                any_issue = True

        print()
        print("  MERC SLOTS:")
        if lf_count==0:
            print("    \u2717 Merc not hired (lf_count=0) \u2014 hire in-game before injecting merc gear")
            any_issue=True
        else:
            exp_count=3
            if merc_count_val<exp_count:
                print(f"    \u2717 Merc has {merc_count_val}/{exp_count} items \u2014 missing gear"); any_issue=True
            else:
                print(f"    \u2713 Merc has {merc_count_val} items (helm+body+weapon)")
            for label,quality,uid in merc_slots.values():
                uid_s=f' uid={uid}' if uid else ''
                flag='  \u2190 PLACEHOLDER' if quality<=2 else ('  \u2190 WEAK (magic)' if quality==4 else '')
                mark='!' if flag else '\u2713'
                print(f"      {mark} {label}{uid_s} ({qname(quality)}){flag}")
                if flag: any_issue=True

        # Socketed bases in stash/inv
        SKIP={'aqv','tbk','ibk','box','cm1','cm2','cm3'}
        bases=[(itype,storage,col,row) for _,itype,ilvl,quality,uid,storage,col,row,bodyloc,_,_ in all_items
               if quality<=2 and storage in (1,5) and itype.strip() not in SKIP]
        if bases:
            print()
            print("  RUNEWORD BASES (nrm in stash/inv \u2014 awaiting socketing):")
            for itype,storage,col,row in bases:
                stor_s={1:'inv',5:'stash'}.get(storage,'?')
                print(f"    {itype:6s} at {stor_s}({col},{row})")

        # Charm check
        print()
        print("  CHARMS:")
        CHARM_STORAGE=(1,5)
        sunder=[uid for _,itype,ilvl,quality,uid,storage,col,row,bodyloc,_,_ in all_items
                if itype=='cm3' and quality==7 and uid in (2872,359) and storage in CHARM_STORAGE]
        gc_all =[(quality,uid) for _,itype,ilvl,quality,uid,storage,col,row,bodyloc,_,_ in all_items
                 if itype=='cm3' and storage in CHARM_STORAGE]
        lc_all =[(quality,uid) for _,itype,ilvl,quality,uid,storage,col,row,bodyloc,_,_ in all_items
                 if itype=='cm2' and storage in CHARM_STORAGE]
        sc_all =[(quality,uid) for _,itype,ilvl,quality,uid,storage,col,row,bodyloc,_,_ in all_items
                 if itype=='cm1' and storage in CHARM_STORAGE]
        anni=[(uid,storage) for _,itype,ilvl,quality,uid,storage,col,row,bodyloc,_,_ in all_items
              if itype=='cm1' and quality==7 and storage in CHARM_STORAGE]
        if not anni:
            print("    \u2717 MISSING : Annihilus (unique cm1) \u2014 every build needs one"); any_issue=True
        else:
            a_uid,a_stor=anni[0]; stor_s={1:'inv',5:'stash'}.get(a_stor,'?')
            print(f"    \u2713 Annihilus present (uid={a_uid} in {stor_s})")
        torch=[(uid,storage) for _,itype,ilvl,quality,uid,storage,col,row,bodyloc,_,_ in all_items
               if itype=='cm2' and quality==7 and storage in CHARM_STORAGE]
        if not torch:
            print("    \u2717 MISSING : Hellfire Torch (unique cm2) \u2014 every build needs one"); any_issue=True
        else:
            t_uid,t_stor=torch[0]; stor_s={1:'inv',5:'stash'}.get(t_stor,'?')
            print(f"    \u2713 Hellfire Torch present (uid={t_uid} in {stor_s})")
        if not sunder:
            print("    ! Gheeds Fortune (cm3 q=7) not found")
        else:
            print(f"    \u2713 Gheeds Fortune present (uid={sunder[0]})")
        gc_skillers=[uid for q,uid in gc_all if q==4]
        gc_uniq    =[(uid,qname(q)) for q,uid in gc_all if q==7 and uid not in (2872,359)]
        gc_other   =len([x for x in gc_all if x[0] not in (4,7)])
        if not gc_all:
            print("    \u2717 MISSING : No grand charms \u2014 add skillers"); any_issue=True
        else:
            skiller_s=f"{len(gc_skillers)} magic/skiller"
            other_s=f"{len(gc_uniq)} other-uniq" if gc_uniq else ""
            parts=[s for s in [skiller_s,other_s] if s]
            gc_mark = '\u2713' if gc_skillers else '!'
            print(f"    {gc_mark} Grand charms : {len(gc_all)} total  ({', '.join(parts)})")
            if not gc_skillers:
                print("        ! No magic grand charms \u2014 skiller GCs missing?"); any_issue=True
            for uid,qn in gc_uniq:
                print(f"        uid={uid} ({qn})")
        if lc_all:
            print(f"    \u2713 Large charms: {len(lc_all)}")
        if not sc_all:
            print("    ! Small charms: none \u2014 fill remaining inventory with small charms"); any_issue=True
        else:
            print(f"    \u2713 Small charms: {len(sc_all)}")

        if not any_issue:
            print()
            print("  \u2713 All slots filled with set/rare/unique/crafted gear")

        print()
        grid_view(inv_occ,10,4,'Inventory')
        grid_view(stash_occ,10,8,'Stash')
        grid_view(cube_occ,3,4,'Cube')

        if collisions:
            print(f"  \u26a0 GRID COLLISIONS ({len(collisions)} overlaps):")
            for pos,itype,stor,col,row,cell,existing in collisions:
                stor_s=STOR.get(stor,str(stor))
                ex_type=existing[0] if isinstance(existing,tuple) else existing
                print(f"    @{pos} {itype} at {stor_s}({col},{row}) overlaps cell {cell} (occupied by {ex_type})")
            print()

        # Backups
        print(f"  BACKUPS:")
        for f2 in sorted(os.listdir(SAVES)):
            if f2.startswith(fname+'.') and not f2.endswith('.d2s'):
                bp=os.path.join(SAVES,f2)
                mt=time.strftime('%m-%d %H:%M',time.localtime(os.path.getmtime(bp)))
                print(f"    {f2}: {os.path.getsize(bp)}B [{mt}]")
        print()

    return files


# ============================================================
# Delta Tracking + Summary
# ============================================================
def delta_and_summary(files, ghost_chars, save_total, bak_total, bak_files):
    """Delta tracking and save directory summary."""
    snapshot_path = os.path.join(SAVES, '.d2r_scanner_snapshot.json')
    current_snapshot = {}
    for fname_s in files:
        path_s = os.path.join(SAVES, fname_s)
        with open(path_s, 'rb') as f_s:
            d = bytearray(f_s.read())
        jm_s = -1
        for i_s in range(0x300, min(len(d)-4, 0x500)):
            if d[i_s:i_s+2] == b'JM':
                jm_s = i_s; break
        ic = struct.unpack_from('<H', d, jm_s+2)[0] if jm_s >= 0 else -1
        current_snapshot[fname_s[:-4]] = {
            'size': len(d),
            'items': ic,
            'checksum': struct.unpack_from('<I', d, 0x0c)[0],
            'timestamp': time.strftime('%Y-%m-%d %H:%M', time.localtime(os.path.getmtime(path_s)))
        }

    try:
        with open(snapshot_path, 'r') as sf:
            previous = json.load(sf)
        changes = []
        for name, cur in current_snapshot.items():
            prev = previous.get(name)
            if prev:
                for key in ('size', 'items'):
                    if cur[key] != prev[key]:
                        changes.append(f"    {name}: {key} {prev[key]}\u2192{cur[key]}")
        if changes:
            print(f"\n  DELTA since {previous.get('_scan_time', '?')}:")
            for c in changes:
                print(c)
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    current_snapshot['_scan_time'] = time.strftime('%Y-%m-%d %H:%M')
    with open(snapshot_path, 'w') as sf:
        json.dump(current_snapshot, sf, indent=2)

    print(f"{'='*60}")
    print(f"  SAVE DIRECTORY SUMMARY")
    print(f"{'='*60}")
    print(f"  Characters: {len(files)} scanned, {len(ghost_chars)} ghost")
    print(f"  Disk: {save_total//1024}KB total, {bak_total//1024}KB in {len(bak_files)} backups")
    if bak_total > 50*1024:
        print(f"  ! Consider pruning old backups to reclaim {bak_total//1024}KB")
    print(f"\nScan complete.")


# ============================================================
# Progression Consistency Check
# ============================================================

def check_progression_consistency(data, yaml_progression=None):
    """Validate progression byte vs waypoint/quest state.

    Args:
        data: bytearray of .d2s file
        yaml_progression: Optional string preset name from YAML (e.g. 'hell_complete').
            When provided, also checks that binary state matches the YAML declaration.

    Returns:
        Tuple of (errors: list[str], warnings: list[str]).
        Errors are deployment blockers. Warnings are informational.
    """
    errors = []
    warnings = []

    prog_byte = data[0x15] if len(data) > 0x15 else 0
    prog_tier = {0x00: 0, 0x05: 1, 0x0F: 2}.get(prog_byte, -1)
    diff_names = ['Normal', 'Nightmare', 'Hell']
    is_hc = bool(data[0x14] & 0x04) if len(data) > 0x14 else False
    lvl_byte = data[0x1B] if len(data) > 0x1B else 1

    # HC act byte check
    if is_hc and len(data) > 0xA9 and data[0xA9] != 0:
        warnings.append(
            f"HC character has act byte 0xA9={data[0xA9]} set — "
            f"game validates act vs quest state for HC; should be 0"
        )

    # Check waypoints for lower difficulties
    ws = data.find(b'WS')
    if ws >= 0 and prog_tier > 0:
        for diff_idx in range(prog_tier):
            base = ws + 8 + diff_idx * 24
            wp_bytes = data[base+2:base+7]
            if all(b == 0 for b in wp_bytes):
                errors.append(
                    f"{diff_names[diff_idx]} waypoints are empty but "
                    f"{diff_names[prog_tier]} is unlocked (prog=0x{prog_byte:02X})"
                )

    # Check quests for lower difficulties
    woo = data.find(b'Woo!')
    if woo >= 0 and prog_tier > 0:
        for diff_idx in range(prog_tier):
            base = woo + 10 + diff_idx * 96
            quest_bytes = data[base:base+96]
            if all(b == 0 for b in quest_bytes):
                errors.append(
                    f"{diff_names[diff_idx]} quests are empty but "
                    f"{diff_names[prog_tier]} is unlocked (prog=0x{prog_byte:02X})"
                )

    # WP/quest inconsistency within a difficulty
    if ws >= 0 and woo >= 0:
        for diff_idx in range(3):
            wp_base = ws + 8 + diff_idx * 24
            wp_bytes = data[wp_base+2:wp_base+7]
            has_wp = any(b != 0 for b in wp_bytes)

            q_base = woo + 10 + diff_idx * 96
            q_bytes = data[q_base:q_base+96]
            has_quests = any(b != 0 for b in q_bytes)

            if has_quests and not has_wp:
                warnings.append(
                    f"{diff_names[diff_idx]}: quests completed but waypoints missing"
                )
            elif has_wp and not has_quests and diff_idx < prog_tier:
                warnings.append(
                    f"{diff_names[diff_idx]}: waypoints set but quests incomplete"
                )

    # Level vs progression
    if prog_byte == 0x00 and lvl_byte >= 40:
        warnings.append(
            f"lv{lvl_byte} but only Normal unlocked (prog=0x{prog_byte:02X})"
        )

    # YAML-vs-binary check (only when YAML context available)
    if yaml_progression and ws >= 0:
        _COMPLETE_PRESETS = {
            'hell_complete': 2, 'nightmare_complete': 1, 'normal_complete': 0,
        }
        if yaml_progression in _COMPLETE_PRESETS:
            expected_tier = _COMPLETE_PRESETS[yaml_progression]
            target_base = ws + 8 + expected_tier * 24
            target_wp = data[target_base+2:target_base+7]
            if all(b == 0 for b in target_wp):
                warnings.append(
                    f"YAML declares '{yaml_progression}' but "
                    f"{diff_names[expected_tier]} waypoints are empty"
                )

    return errors, warnings


# ============================================================
# Programmatic Scan (returns structured data)
# ============================================================
def scan_character_data(filepath):
    """Scan a single .d2s file and return structured results.

    Performs header checks (signature, checksum, size) AND item-level
    property validation so the deploy loop catches the same issues as
    the interactive scanner (Rule 4 / Rule 17).

    Args:
        filepath: Path to .d2s file

    Returns:
        dict with keys: name, class_id, level, checksum_ok, size_ok,
        item_count, merc_count, errors, warnings
    """
    with open(filepath, 'rb') as f:
        data = bytearray(f.read())

    sig = struct.unpack_from('<I', data, 0)[0]
    version = struct.unpack_from('<I', data, 4)[0]
    stored_size = struct.unpack_from('<I', data, 8)[0]
    stored_cs = struct.unpack_from('<I', data, 0x0c)[0]
    calc_cs = calc_checksum(data)
    cls_id = data[0x18]
    lvl_byte = data[0x1b]
    name_end = data.find(b'\x00', 0x12b)
    char_name = data[0x12b:name_end].decode('ascii', 'replace') if name_end > 0 else '?'

    jm = -1
    for i in range(0x300, min(len(data)-4, 0x500)):
        if data[i:i+2] == b'JM':
            jm = i
            break
    item_count = struct.unpack_from('<H', data, jm+2)[0] if jm >= 0 else -1

    jf_marker = data.find(b'jf', jm+4) if jm >= 0 else -1
    merc_jm = data.find(b'JM', jf_marker+2) if jf_marker >= 0 else -1
    merc_count = struct.unpack_from('<H', data, merc_jm+2)[0] if merc_jm >= 0 else -1

    errors = []
    warnings = []

    if sig != 0xAA55AA55:
        errors.append(f"Bad signature: 0x{sig:08X}")
    if version != 105:
        warnings.append(f"Unexpected version: {version}")
    if stored_cs != calc_cs:
        errors.append(f"Checksum mismatch: stored=0x{stored_cs:08X} calc=0x{calc_cs:08X}")
    if len(data) != stored_size:
        errors.append(f"Size mismatch: actual={len(data)} stored={stored_size}")

    # Progression consistency
    prog_errs, prog_warns = check_progression_consistency(data)
    errors.extend(prog_errs)
    warnings.extend(prog_warns)

    # Item-level property validation (matches interactive scanner)
    if jm >= 0:
        char_item_end = jf_marker if jf_marker > 0 else len(data) - 4
        runeword_flags = {}
        for pos in range(jm + 4, char_item_end):
            b0, b2 = data[pos], data[pos + 2] if pos + 2 < len(data) else 0
            if b0 == 0x10 and b2 in (0x80, 0xa0, 0xc0, 0xe0):
                try:
                    itype, ilvl, quality, uid, storage, col, row, bodyloc, location, ext = \
                        decode_item_header(data, pos)
                except Exception:
                    continue
                flags32 = struct.unpack_from('<I', data, pos)[0]
                if flags32 & (1 << 26):
                    runeword_flags[pos] = True
                # UID validation
                tc = itype.strip()
                if quality == 7 and uid is not None:
                    uinfo = UNIQUE_ITEMS.get(uid)
                    if uinfo is None:
                        errors.append(f"item@{pos:#x}: uid={uid} not in UNIQUE_ITEMS")
                    elif uinfo['code'] != tc and tc != '???':
                        errors.append(f"item@{pos:#x}: uid={uid} ({uinfo['name']}) expects '{uinfo['code']}' got '{tc}'")
                if quality == 5 and uid is not None:
                    sinfo = SET_ITEMS.get(uid)
                    if sinfo is None:
                        errors.append(f"item@{pos:#x}: set_id={uid} not in SET_ITEMS")
                    elif sinfo['code'] != tc and tc != '???':
                        errors.append(f"item@{pos:#x}: set_id={uid} ({sinfo['name']}) expects '{sinfo['code']}' got '{tc}'")
                # Property stream validation
                if quality >= 1:
                    try:
                        prop_ok, prop_err, _ = validate_item_properties(
                            data, pos, itype, quality,
                            pos in runeword_flags,
                            bool(flags32 & (1 << 11)),
                            flags32
                        )
                        if not prop_ok:
                            errors.append(f"item@{pos:#x} ({tc}): {prop_err}")
                        elif prop_err:
                            warnings.append(f"item@{pos:#x} ({tc}): {prop_err}")
                    except Exception as ex:
                        warnings.append(f"item@{pos:#x} ({tc}): property parse exception: {ex}")

    return {
        'name': char_name,
        'class_id': cls_id,
        'level': lvl_byte,
        'checksum_ok': stored_cs == calc_cs,
        'size_ok': len(data) == stored_size,
        'item_count': item_count,
        'merc_count': merc_count,
        'errors': errors,
        'warnings': warnings,
    }


# ============================================================
# Main Entry Point
# ============================================================
def run_scanner(target='all'):
    """Run the full scanner.

    Args:
        target: Character name filter (lowercase), or 'all'
    """
    all_files, ghost_chars, save_total, bak_total, bak_files, _ = preflight_check()
    files = scan_characters(target, all_files, ghost_chars)
    delta_and_summary(files, ghost_chars, save_total, bak_total, bak_files)


if __name__ == '__main__':
    target = sys.argv[1].lower() if len(sys.argv) > 1 else 'all'
    run_scanner(target)
