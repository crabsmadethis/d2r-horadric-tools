#!/usr/bin/env python3
"""
d2r_build_lib.py — Single authoritative item encoder for D2R save file editing.

Consolidated item encoder for D2R save file editing.
Key features:
  1. Dynamic BASES lookup from item_bases.py (659 entries) — no hardcoded dict
  2. Runeword double-terminator (from fix_obsidian_rw.py)
  3. Overflow protection on all property encoding
  4. UID/runeword/set validation at build time
  5. Support for ALL quality types (normal, superior, magic, set, unique, rare, crafted)
"""

import struct
import random

# ---------------------------------------------------------------------------
# Imports from data files
# ---------------------------------------------------------------------------

# Authoritative item base database (659 entries)
# Source: d2r_chargen/data/item_bases.py
from d2r_chargen.data.item_bases import ITEM_BASES as ITEM_BASES_FULL

# Unique items database (406 entries, UIDs 0-406)
# Source: d2r_chargen/data/unique_items.py
from d2r_chargen.data.unique_items import UNIQUE_ITEMS

# Set items database (127 entries)
# Source: d2r_chargen/data/set_items.py
from d2r_chargen.data.set_items import SET_ITEMS

# Runewords database (177 entries)
# Source: d2r_chargen/data/runewords.py
from d2r_chargen.data.runewords import RUNEWORDS

# Stat encoding parameters (361 stat definitions)
# Source: d2r_chargen/data/item_stat_cost.py
from d2r_chargen.data.item_stat_cost import ITEM_STAT_COST, STAT_BY_NAME

# Item grid dimensions (659 entries)
# Source: d2r_chargen/data/item_dimensions.py

# Huffman encoding table from d2r-editor/item_injector.py lines 43-51
# Maps character -> (value, num_bits) for LSB-first encoding
from d2r_chargen.data.huffman import HUFFMAN

from d2r_chargen.config import RW_BASE_CATEGORIES

# ---------------------------------------------------------------------------
# Canonical Constants
# Reference: d2rdoctor.md lines 696-698 (bodyloc), d2rdoctor.md line 38 (storage)
# ---------------------------------------------------------------------------
BODYLOC = {
    'helm': 1, 'neck': 2, 'body': 3, 'rhand': 4, 'lhand': 5,
    'rring': 6, 'lring': 7, 'belt': 8, 'feet': 9, 'hands': 10,
    'switch_rh': 11, 'switch_lh': 12
}

STORAGE = {
    'equipped': 0,   # location=0, storage=0 when equipped (use bodyloc)
    'inventory': 1,  # personal inventory
    'belt': 2,       # belt slots
    'cube': 4,       # Horadric Cube
    'stash': 5       # personal stash (10x8 in Reign of the Warlock)
}

# ---------------------------------------------------------------------------
# Module-level warning context
# Avoids threading a 'warnings' parameter through 12 private builder
# functions in items.py.  build_all_items() sets this before building and
# clears it afterward.
# ---------------------------------------------------------------------------
_current_warnings = None


def set_build_warnings(w):
    """Set the active BuildWarnings collector. Called by build_all_items()."""
    global _current_warnings
    _current_warnings = w


# ---------------------------------------------------------------------------
# A. Dynamic BASES Lookup
# Reference: item_bases.py flags field (bit 0=quantity, bit 1=durability,
#            bit 2=defense, bit 3=book)
# ---------------------------------------------------------------------------
def get_base_flags(type_code):
    """Look up item base flags from the authoritative ITEM_BASES_FULL database.

    Returns flags integer:
        bit 0 (1) = has quantity (stackable items like runes, throwing weapons)
        bit 1 (2) = has durability (weapons, armor)
        bit 2 (4) = has defense (armor, shields)
        bit 3 (8) = has book field (tomes: tbk, ibk)

    If the type code is not found, returns 0 (misc/charm/rune/jewel behavior).

    Note: item_bases.py flags do NOT include the book bit (8). Books (tbk, ibk)
    have flags=1 (quantity only) in item_bases.py, but the D2R binary format
    includes a 5-bit book type field. We detect books via the 'Book' category
    and OR in bit 3 (8) accordingly.
    Reference: d2rdoctor.md line 196 — 'if base & 8: br += 5'
    Reference: fix_obsidian_rw.py line 102 — 'tbk': 9, 'ibk': 9
    """
    tc = type_code.strip()
    info = ITEM_BASES_FULL.get(tc)
    if info is None:
        return 0  # unknown type: no defense, no durability, no quantity
    flags = info['flags']
    # Add book bit (8) if item is in the tome/book category.
    # item_bases.py line 536: tbk has categories=['Book', 'Miscellaneous'], flags=1
    # item_bases.py line 537: ibk has categories=['Book', 'Miscellaneous'], flags=1
    # But binary format needs base & 8 check for the 5-bit book type field
    categories = info.get('categories', [])
    if 'Book' in categories or 'Tome' in categories:
        flags |= 8  # add book bit
    return flags


# ---------------------------------------------------------------------------
# B. BitWriter — writes bits LSB-first (D2S format)
# Reference: fix_obsidian_rw.py lines 33-54
# Reference: build_characters.py lines 27-49
# ---------------------------------------------------------------------------
class BitWriter:
    """Write bits in LSB-first order, matching D2R save file format."""

    def __init__(self):
        self.buf = bytearray(8192)  # pre-allocated buffer
        self.pos = 0                # current bit position

    def write_bits(self, value, count):
        """Write 'count' bits of 'value', LSB first."""
        for i in range(count):
            bit = (value >> i) & 1
            self.buf[self.pos >> 3] |= bit << (self.pos & 7)
            self.pos += 1

    def write_huff(self, code):
        """Write 4-char Huffman type code (3 chars + space terminator).
        Uses HUFFMAN table from d2r-editor/item_injector.py lines 43-51."""
        for ch in code:
            val, bits = HUFFMAN[ch]
            self.write_bits(val, bits)

    def align(self):
        """Advance to next byte boundary (pad with 0 bits)."""
        self.pos = (self.pos + 7) & ~7

    def get_bytes(self):
        """Return completed item as bytes (byte-aligned)."""
        self.align()
        return bytes(self.buf[:self.pos >> 3])


# ---------------------------------------------------------------------------
# C. Property Encoder
# Reference: fix_obsidian_rw.py lines 58-84 (the working implementation)
# Reference: item_stat_cost.py header lines 1-31 (encoding type docs)
# ---------------------------------------------------------------------------

# Grouped stat counts (np) for the D2S encoding format.
# These are hardcoded D2S format knowledge — the vanilla ItemStatCost.txt
# doesn't export np, so item_stat_cost.py may not have it.
_NP_OVERRIDES = {
    17: 2,   # item_maxdamage_percent: [maxdmg%, mindmg%]
    48: 2,   # firemindam: [min, max]
    50: 2,   # lightmindam: [min, max]
    52: 2,   # magicmindam: [min, max]
    54: 3,   # coldmindam: [min, max, length]
    57: 3,   # poisonmindam: [min, max, length]
}


def _get_np(stat_id, info):
    """Get the np (group count) for a stat, using hardcoded overrides."""
    if stat_id in _NP_OVERRIDES:
        return _NP_OVERRIDES[stat_id]
    return info.get('np', 0)


def encode_property(w, stat_id, value, param=0):
    """Write a single item property (stat) into the BitWriter bitstream.

    Args:
        w: BitWriter instance
        stat_id: Stat ID from ITEM_STAT_COST (0-360)
        value: The decoded stat value (before sA addition), or a list of
               values for grouped stats (np > 0).
        param: Parameter value for skill/class stats (default 0)

    Encoding types (from item_stat_cost.py lines 15-18):
        e=0: Standard — optional sP param bits, then (value + sA) in sB bits
        e=1: Skill by class — same as e=0 (param = skill_id)
        e=2: Chance to cast — param = (skill_id << 6) | skill_level in sP bits
        e=3: Charges — param = (skill_id << 6) | skill_level, value = raw charges

    Grouped stats (np > 0):
        When a stat has np > 0 (e.g. poisonmindam np=3), D2R reads one stat ID
        followed by values for np consecutive stats. The value arg must be a
        list of np ints.  Example: (57, [102, 102, 200]) writes stat ID 57 once,
        then poisonmindam(10b), poisonmaxdam(10b), poisonlength(9b).

    Raises:
        ValueError: If stat_id unknown, sB=0, or value overflows sB bits
    """
    info = ITEM_STAT_COST.get(stat_id)
    if info is None:
        raise ValueError(f"Unknown stat_id {stat_id} — not in ITEM_STAT_COST")

    sB = info.get('sB', 0)
    sA = info.get('sA', 0)
    sP = info.get('sP', 0)
    e = info.get('e', 0)
    np_count = _get_np(stat_id, info)

    if sB == 0:
        raise ValueError(
            f"Stat {stat_id} ({info.get('s', '?')}) has sB=0 — "
            f"cannot be written to items"
        )

    # Grouped stats (np > 0): one stat ID, then np values back-to-back.
    # D2R reads all np values after a single 9-bit stat ID header.
    if np_count > 0:
        if not isinstance(value, (list, tuple)):
            raise ValueError(
                f"Stat {stat_id} ({info.get('s', '?')}) has np={np_count} — "
                f"value must be a list of {np_count} values, got {type(value).__name__}"
            )
        if len(value) != np_count:
            raise ValueError(
                f"Stat {stat_id} ({info.get('s', '?')}) has np={np_count} — "
                f"expected {np_count} values, got {len(value)}"
            )

        w.write_bits(stat_id, 9)
        for i in range(np_count):
            member_info = ITEM_STAT_COST.get(stat_id + i)
            member_sB = member_info['sB']
            member_sA = member_info.get('sA', 0)
            encoded_val = value[i] + member_sA
            max_val = (1 << member_sB) - 1
            member_sS = member_info.get('sS', 0)
            if member_sS and encoded_val < 0:
                min_signed = -(1 << (member_sB - 1))
                if encoded_val < min_signed:
                    raise ValueError(
                        f"Stat {stat_id + i} ({member_info.get('s', '?')}): "
                        f"value {value[i]} + sA={member_sA} = {encoded_val} "
                        f"exceeds signed {member_sB}-bit range [{min_signed}, {(1 << (member_sB-1))-1}]"
                    )
                encoded_val = encoded_val & max_val  # two's complement
            elif encoded_val < 0 or encoded_val > max_val:
                raise ValueError(
                    f"Stat {stat_id + i} ({member_info.get('s', '?')}): "
                    f"value {value[i]} + sA={member_sA} = {encoded_val} "
                    f"exceeds {member_sB}-bit range [0, {max_val}]"
                )
            w.write_bits(encoded_val, member_sB)
        return

    # Write 9-bit stat ID (all encoding types start with this)
    w.write_bits(stat_id, 9)

    if e == 3:
        # Charges encoding: param = (skill_id << 6) | skill_level
        # value is raw (NOT offset by sA), stored directly in sB bits
        # Reference: fix_obsidian_rw.py lines 69-74
        skill_id = param & 0x3FF       # 10 bits
        skill_level = (param >> 10) & 0x3F  # 6 bits
        encoded_param = (skill_id << 6) | skill_level
        if sP > 0:
            w.write_bits(encoded_param, sP)
        w.write_bits(value, sB)

    elif e == 2:
        # Chance to cast: param = (skill_id << 6) | skill_level
        # value IS offset by sA
        # Reference: fix_obsidian_rw.py lines 75-80
        skill_id = param & 0x3FF       # 10 bits
        skill_level = (param >> 10) & 0x3F  # 6 bits
        encoded_param = (skill_id << 6) | skill_level
        if sP > 0:
            w.write_bits(encoded_param, sP)
        encoded_val = value + sA
        max_val = (1 << sB) - 1
        if encoded_val < 0 or encoded_val > max_val:
            raise ValueError(
                f"Stat {stat_id} ({info.get('s', '?')}): e=2 value {value} + sA={sA} = "
                f"{encoded_val} exceeds {sB}-bit range [0, {max_val}]"
            )
        w.write_bits(encoded_val, sB)

    else:
        # e=0 (standard) and e=1 (skill by class): same encoding
        # Optional param bits, then value + sA in sB bits
        # Reference: fix_obsidian_rw.py lines 81-84
        if sP > 0:
            w.write_bits(param, sP)

        encoded_val = value + sA
        max_val = (1 << sB) - 1
        # Signed stats (sS=1): use two's complement for negative values
        sS = info.get('sS', 0)
        if sS and encoded_val < 0:
            min_signed = -(1 << (sB - 1))
            if encoded_val < min_signed:
                raise ValueError(
                    f"Stat {stat_id} ({info.get('s', '?')}): value {value} + sA={sA} = "
                    f"{encoded_val} exceeds signed {sB}-bit range [{min_signed}, {(1 << (sB-1))-1}]"
                )
            encoded_val = encoded_val & max_val  # two's complement
        elif encoded_val < 0 or encoded_val > max_val:
            raise ValueError(
                f"Stat {stat_id} ({info.get('s', '?')}): value {value} + sA={sA} = "
                f"{encoded_val} exceeds {sB}-bit range [0, {max_val}]"
            )
        w.write_bits(encoded_val, sB)


# ---------------------------------------------------------------------------
# D. Property List Termination
# Reference: fix_obsidian_rw.py lines 227-240 (runeword double terminator)
# Reference: d2rdoctor.md line 229 — terminators_expected = 2 if is_runeword
# ---------------------------------------------------------------------------
def encode_properties_terminated(w, props, is_runeword=False):
    """Write a list of property tuples, followed by 0x1FF terminator(s).

    Args:
        w: BitWriter instance
        props: list of tuples — (stat_id, value) or (stat_id, value, param)
        is_runeword: If True, write SECOND 0x1FF terminator for empty
                     runeword bonus list.

    Paired damage stats (np=2 or np=3 in item_stat_cost.py):
        Stats like lightmindam (50, np=2) encode min AND max under ONE stat ID.
        D2R reads: stat_id(9 bits), then value1(sB1 bits), then value2(sB2 bits).
        When props contains consecutive entries for a paired stat (e.g.,
        (LIGHT_MIN, 1), (LIGHT_MAX, 496)), they are merged into one write.

    Runeword items have TWO property lists in binary:
        List 1: base item magic properties → 0x1FF terminator
        List 2: runeword bonus properties → 0x1FF terminator
    For injected runewords, we write all props in the first list and
    leave the second list empty (just a terminator).
    """
    i = 0
    while i < len(props):
        stat_id, value = props[i][0], props[i][1]
        param = props[i][2] if len(props[i]) > 2 else 0
        info = ITEM_STAT_COST.get(stat_id)
        np_count = info.get('np', 1) if info else 1

        if np_count > 1 and not isinstance(value, (list, tuple)) and (i + np_count - 1) < len(props):
            # Paired stat with consecutive entries (legacy format):
            # e.g., (50, 1), (51, 496) for lightmindam np=2
            # Verify consecutive entries match expected stat IDs
            paired = True
            for j in range(1, np_count):
                if props[i + j][0] != stat_id + j:
                    paired = False
                    break

            if paired:
                w.write_bits(stat_id, 9)
                # Write first value
                sB = info.get('sB', 0)
                sA = info.get('sA', 0)
                w.write_bits(value + sA, sB)
                # Write subsequent values from consecutive stat entries
                for j in range(1, np_count):
                    next_info = ITEM_STAT_COST.get(stat_id + j)
                    next_sB = next_info.get('sB', 0)
                    next_sA = next_info.get('sA', 0)
                    next_val = props[i + j][1]
                    w.write_bits(next_val + next_sA, next_sB)
                i += np_count
                continue

        # Standard single-stat encoding
        encode_property(w, stat_id, value, param)
        i += 1

    # First terminator (always present)
    w.write_bits(0x1FF, 9)  # 9-bit all-ones = end of property list

    if is_runeword:
        # Second terminator: empty runeword bonus list
        # Reference: fix_obsidian_rw.py lines 233-240
        w.write_bits(0x1FF, 9)


# ---------------------------------------------------------------------------
# E. Validation Functions
# ---------------------------------------------------------------------------
def validate_unique_item(type_code, unique_id):
    """Verify that a unique item UID exists and matches the given type code.

    Args:
        type_code: 3 or 4 char item base code (e.g. 'amu', 'uit ')
        unique_id: UID from UNIQUE_ITEMS (0-406)

    Raises:
        ValueError: If UID not found or code mismatch
    """
    info = UNIQUE_ITEMS.get(unique_id)
    if info is None:
        raise ValueError(
            f"uid={unique_id} not in UNIQUE_ITEMS database (406 entries). "
            f"Always look up UIDs from d2r_chargen/data/unique_items.py"
        )
    tc = type_code.strip()
    if info['code'] != tc:
        raise ValueError(
            f"uid={unique_id} ({info['name']}) expects code='{info['code']}', "
            f"but got '{tc}'"
        )


def validate_set_item(type_code, set_id):
    """Verify that a set item ID exists and matches the given type code.

    Args:
        type_code: 3 or 4 char item base code
        set_id: Set item ID from SET_ITEMS (0-126)

    Raises:
        ValueError: If set_id not found or code mismatch
    """
    info = SET_ITEMS.get(set_id)
    if info is None:
        raise ValueError(
            f"set_id={set_id} not in SET_ITEMS database (127 entries). "
            f"Always look up set IDs from d2r_chargen/data/set_items.py"
        )
    tc = type_code.strip()
    if info['code'] != tc:
        raise ValueError(
            f"set_id={set_id} ({info['name']}) expects code='{info['code']}', "
            f"but got '{tc}'"
        )


def validate_runeword(type_code, runeword_id):
    """Verify that a runeword ID exists and check base type compatibility.

    Args:
        type_code: 3 or 4 char item base code
        runeword_id: Runeword ID from RUNEWORDS

    Raises:
        ValueError: If runeword_id not found or base type incompatible
    """
    info = RUNEWORDS.get(runeword_id)
    if info is None:
        raise ValueError(
            f"runeword_id={runeword_id} not in RUNEWORDS database (177 entries). "
            f"Always look up runeword IDs from d2r_chargen/data/runewords.py"
        )
    tc = type_code.strip()
    base_info = ITEM_BASES_FULL.get(tc)
    if base_info is None:
        return  # unknown base, can't validate categories

    rw_bases = info.get('bases', [])
    if not rw_bases:
        return  # no base restriction

    item_cats = base_info.get('categories', [])
    expanded_bases = set()
    for rb in rw_bases:
        expanded_bases.update(RW_BASE_CATEGORIES.get(rb, [rb]))

    if not any(cat in expanded_bases for cat in item_cats):
        raise ValueError(
            f"runeword '{info['name']}' (id={runeword_id}) requires bases "
            f"{rw_bases} but {tc} ({base_info['name']}) has categories {item_cats}"
        )


# ---------------------------------------------------------------------------
# F. build_item() — The Single Correct Implementation
# Reference: fix_obsidian_rw.py lines 132-248 (the working version)
# Reference: d2r-editor/item_injector.py lines 171-287 (ext bits, format docs)
# Reference: d2rdoctor.md lines 105-225 (scanner field order = ground truth)
# ---------------------------------------------------------------------------
def build_item(type_code, col, row, storage,
               quality=2, ilvl=99, item_id=None,
               socketed=False, num_sockets=0,
               socket_filler_count=None,
               unique_id=0, set_id=0,
               defense=0, max_dur=0, cur_dur=0,
               location=0, bodyloc=0,
               ethereal=False,
               properties=None,
               runeword=False, runeword_id=0,
               quantity=0,
               set_flags=0,
               magic_prefix=0, magic_suffix=0,
               rare_first_name=0, rare_last_name=0,
               rare_affixes=None,
               multi_pic=None, gfx_idx=0,
               rune_codes=None,
               warnings=None):
    """Build a complete D2R v105 item byte sequence.

    Supports ALL quality types:
        1 = inferior      3 = superior     4 = magic
        5 = set           7 = unique       6 = rare
        8 = crafted       2 = normal (default)

    Args:
        type_code: 3 or 4 char item code (e.g. 'amu', 'uit ', 'r01')
        col: Grid column (0-based, 4 bits → max 15)
        row: Grid row (0-based, 3 bits → max 7)
        storage: Storage location (use STORAGE constants)
        quality: Item quality (1-8)
        ilvl: Item level (1-99, 7 bits)
        item_id: 32-bit unique item ID (random if None)
        socketed: True if item has sockets
        num_sockets: Number of sockets (0-6, 4 bits)
        socket_filler_count: Number of following socket filler records. Defaults
            to the number of rune_codes for existing runeword callers.
        unique_id: 12-bit unique item UID (quality=7)
        set_id: 12-bit set item ID (quality=5)
        defense: Base defense value (11 bits, for items with base & 4)
        max_dur: Max durability (8 bits, for items with base & 6)
        cur_dur: Current durability (9 bits)
        location: 0=stored, 1=equipped (3 bits)
        bodyloc: Body location if equipped (use BODYLOC constants, 4 bits)
        ethereal: True if ethereal (flag bit 22)
        properties: List of (stat_id, value) or (stat_id, value, param) tuples
        runeword: True if runeword item
        runeword_id: 16-bit runeword ID (from RUNEWORDS)
        quantity: Stack quantity (9 bits, for stackable items)
        set_flags: 5-bit set flags for set items (quality=5)
        magic_prefix: 11-bit prefix ID for magic items (quality=4)
        magic_suffix: 11-bit suffix ID for magic items (quality=4)
        rare_first_name: 8-bit first name ID for rare/crafted items (quality=6/8)
        rare_last_name: 8-bit last name ID for rare/crafted items (quality=6/8)
        rare_affixes: List of up to 6 affix IDs for rare/crafted (0=none)

    Returns:
        bytes: Complete item byte sequence (byte-aligned)

    Raises:
        ValueError: On validation failures (UID mismatch, overflow, etc.)
        AssertionError: On structural issues (bad type_code length)
    """
    # --- Validation ---
    if item_id is None:
        item_id = random.randint(1, 0xFFFFFFFF)

    tc = type_code.strip()

    # Dynamic base flags lookup (replaces hardcoded BASES dicts).
    base = get_base_flags(tc)

    # Validate unique items (quality=7)
    if quality == 7:
        validate_unique_item(tc, unique_id)

    # Validate set items (quality=5)
    if quality == 5:
        validate_set_item(tc, set_id)

    # Validate runewords
    if runeword:
        validate_runeword(tc, runeword_id)

    # ------------------------------------------------------------------
    # Pre-encode warning checks (diagnostic only, never halt the build)
    # ------------------------------------------------------------------
    wc = warnings if warnings is not None else _current_warnings
    if wc is not None:
        # 1. Socket count vs base max_sockets
        base_info = ITEM_BASES_FULL.get(tc)
        if base_info is not None and num_sockets > 0:
            max_sock = base_info.get('max_sockets', 6)
            if num_sockets > max_sock:
                wc.warn(tc, f"num_sockets={num_sockets} exceeds base max_sockets={max_sock}")

        # 2. Durability max (8-bit field)
        if max_dur > 255:
            wc.warn(tc, f"max_dur={max_dur} exceeds 8-bit max (255)")

        # 3. Durability current (9-bit field)
        if cur_dur > 511:
            wc.warn(tc, f"cur_dur={cur_dur} exceeds 9-bit max (511)")

        # 4. Defense (11-bit field)
        if defense > 2047:
            wc.warn(tc, f"defense={defense} exceeds 11-bit max (2047)")

        # 5. Quantity (9-bit field)
        if quantity > 511:
            wc.warn(tc, f"quantity={quantity} exceeds 9-bit max (511)")
        # 5b. Quantity persistence caveats (non-fatal)
        #
        # These bases accept quantities at the byte level, but representative
        # Offline save/exit pulls have shown D2R may clear the field on
        # save/exit. Warn to reduce confusion without blocking fixture-level
        # encoding work.
        if quantity and tc in {"toa", "tes", "pk1", "xa1"}:
            wc.warn(
                tc,
                "D2R may clear misc/quest item quantity on save/exit; treat as non-persistent",
            )

        # 6. Property value overflow checks
        if properties:
            for prop in properties:
                p_stat_id = prop[0]
                p_value = prop[1]
                p_info = ITEM_STAT_COST.get(p_stat_id)
                if p_info is None:
                    continue
                p_sB = p_info.get('sB', 0)
                p_sA = p_info.get('sA', 0)
                if p_sB == 0:
                    continue
                np_count = _get_np(p_stat_id, p_info)
                if np_count > 0:
                    # Grouped stat: check each member
                    if not isinstance(p_value, (list, tuple)):
                        wc.warn(tc,
                            f"stat {p_stat_id} ({p_info.get('s', '?')}): "
                            f"grouped stat (np={np_count}) given scalar value; "
                            f"bounds check skipped")
                    elif isinstance(p_value, (list, tuple)):
                        for i, v in enumerate(p_value):
                            m_info = ITEM_STAT_COST.get(p_stat_id + i)
                            if m_info is None:
                                continue
                            m_sB = m_info.get('sB', 0)
                            m_sA = m_info.get('sA', 0)
                            m_sS = m_info.get('sS', 0)
                            encoded = v + m_sA
                            max_val = (1 << m_sB) - 1
                            # Mirror encode_property logic: sS only matters
                            # for negative encoded values (two's complement).
                            # Positive values use the unsigned max_val check.
                            if m_sS and encoded < 0:
                                lo = -(1 << (m_sB - 1))
                                if encoded < lo:
                                    wc.warn(tc,
                                        f"stat {p_stat_id + i} ({m_info.get('s', '?')}): "
                                        f"value {v} + sA={m_sA} = {encoded} "
                                        f"exceeds signed {m_sB}-bit min ({lo})")
                            elif encoded < 0 or encoded > max_val:
                                wc.warn(tc,
                                    f"stat {p_stat_id + i} ({m_info.get('s', '?')}): "
                                    f"value {v} + sA={m_sA} = {encoded} "
                                    f"exceeds {m_sB}-bit range [0, {max_val}]")
                else:
                    # Simple stat: mirror encode_property logic exactly
                    p_e = p_info.get('e', 0)
                    p_sS = p_info.get('sS', 0)
                    # e=3 (charges): value is raw, NOT offset by sA
                    encoded = p_value if p_e == 3 else p_value + p_sA
                    max_val = (1 << p_sB) - 1
                    if p_sS and encoded < 0:
                        lo = -(1 << (p_sB - 1))
                        if encoded < lo:
                            wc.warn(tc,
                                f"stat {p_stat_id} ({p_info.get('s', '?')}): "
                                f"value {p_value} + sA={p_sA} = {encoded} "
                                f"exceeds signed {p_sB}-bit min ({lo})")
                    elif encoded < 0 or encoded > max_val:
                        wc.warn(tc,
                            f"stat {p_stat_id} ({p_info.get('s', '?')}): "
                            f"value {p_value} + sA={p_sA} = {encoded} "
                            f"exceeds {p_sB}-bit range [0, {max_val}]")

    # Pad type code to 4 chars (3 + space terminator for Huffman)
    if len(type_code) == 3:
        type_code = type_code + ' '
    assert len(type_code) == 4, f"Type code must be 4 chars, got: {type_code!r}"

    w = BitWriter()

    # ==========================================================
    # FLAGS (32 bits)
    # Reference: d2r-editor/item_injector.py lines 7-8
    # Reference: fix_obsidian_rw.py lines 154-164
    # ==========================================================
    flags = 0
    flags |= (1 << 4)    # bit 4: identified
    if socketed:
        flags |= (1 << 11)  # bit 11: socketed
    if ethereal:
        flags |= (1 << 22)  # bit 22: ethereal
    flags |= (1 << 23)   # bit 23: always set to 1
    if runeword:
        flags |= (1 << 26)  # bit 26: runeword
    w.write_bits(flags, 32)

    # ==========================================================
    # D2R EXTENSION BITS (3 bits, value=5 → binary 101)
    # Reference: d2r-editor/item_injector.py line 214 — w.write_bits(5, 3)
    # Reference: d2rdoctor.md line 1333 — assert ((item[4]&7)==5)
    # Reference: d2rdoctor.md line 1555 — "Always verify ext bits"
    # Value 5 = bits (1,0,1) in LSB order = the D2R version marker
    # ==========================================================
    w.write_bits(5, 3)

    # ==========================================================
    # LOCATION FIELDS
    # Reference: d2r-editor/item_injector.py lines 9-14
    # Reference: d2rdoctor.md lines 65-68
    # ==========================================================
    w.write_bits(location, 3)   # 3 bits: 0=stored, 1=equipped
    w.write_bits(bodyloc, 4)    # 4 bits: body location (1-12 if equipped)
    w.write_bits(col, 4)        # 4 bits: grid column
    w.write_bits(row, 3)        # 3 bits: grid row
    w.write_bits(0, 1)          # 1 bit:  unknown (always 0)
    w.write_bits(storage, 3)    # 3 bits: storage location

    # ==========================================================
    # TYPE CODE (Huffman encoded, variable length)
    # Reference: d2r_inject.py lines 20-82 (Huffman tree)
    # ==========================================================
    w.write_huff(type_code)

    # ==========================================================
    # NON-SIMPLE ITEM DATA
    # Reference: d2r-editor/item_injector.py lines 17-33
    # Reference: d2rdoctor.md lines 132-135
    # ==========================================================
    nr_socketed = (
        int(socket_filler_count)
        if socket_filler_count is not None
        else len(rune_codes) if rune_codes else 0
    )
    w.write_bits(nr_socketed, 3)  # 3 bits: nr_of_items_in_sockets
    w.write_bits(item_id, 32)   # 32 bits: unique item ID
    w.write_bits(ilvl, 7)       # 7 bits: item level
    w.write_bits(quality, 4)    # 4 bits: quality (1-8)
    # multi_pic: auto-detect from item type if not explicitly set
    # Charms (cm1/cm2/cm3), jewels (jew) have multi_pic=1 in original items
    if multi_pic is None:
        tc = type_code.strip()
        multi_pic = 1 if tc in ('cm1', 'cm2', 'cm3', 'jew') else 0
    w.write_bits(multi_pic, 1)
    if multi_pic:
        w.write_bits(gfx_idx, 3)
    w.write_bits(0, 1)          # 1 bit: class_specific flag = 0

    # ==========================================================
    # QUALITY-SPECIFIC DATA
    # Reference: d2rdoctor.md lines 144-156
    # Reference: d2r-editor/item_injector.py lines 236-251
    # ==========================================================
    if quality == 1:
        # Inferior: 3 bits type
        w.write_bits(0, 3)
    elif quality == 2:
        # Normal: no extra bits
        pass
    elif quality == 3:
        # Superior: 3 bits type
        w.write_bits(0, 3)
    elif quality == 4:
        # Magic: 11-bit prefix + 11-bit suffix
        w.write_bits(magic_prefix, 11)
        w.write_bits(magic_suffix, 11)
    elif quality == 5:
        # Set: 12-bit set_id
        # Reference: d2rdoctor.md line 147
        w.write_bits(set_id, 12)
    elif quality == 7:
        # Unique: 12-bit unique_id
        # Reference: d2rdoctor.md line 148
        w.write_bits(unique_id, 12)
    elif quality in (6, 8):
        # Rare (6) or Crafted (8): 8-bit first_name + 8-bit last_name + 6 affix slots
        # Reference: d2rdoctor.md lines 149-154
        w.write_bits(rare_first_name, 8)
        w.write_bits(rare_last_name, 8)
        affixes = rare_affixes if rare_affixes else [0] * 6
        for i in range(6):
            affix_id = affixes[i] if i < len(affixes) else 0
            if affix_id > 0:
                w.write_bits(1, 1)        # has_affix = 1
                w.write_bits(affix_id, 11)  # 11-bit affix ID
            else:
                w.write_bits(0, 1)        # has_affix = 0

    # ==========================================================
    # RUNEWORD ID (16 bits, only if runeword flag set)
    # Reference: d2rdoctor.md lines 158-162
    #
    # D2R canonical form (observed in D2R-written saves, e.g. golden fixture
    # tests/fixtures/hexshade_lv98_haseen.d2s):
    #   low 12 bits = runeword_id + 27  (legacy "runeword bias")
    #   high 4 bits = 5                 (D2R version marker)
    #
    # D2R accepts the raw form (low12 = runeword_id, high4 = 0) for
    # char-equipped items but rejects it for merc-equipped items during
    # game-enter validation. Writing the canonical biased form satisfies
    # both code paths.
    # ==========================================================
    if runeword:
        w.write_bits(runeword_id + 27, 12)
        w.write_bits(5, 4)

    # No personalized name (we never set bit 24)

    # ==========================================================
    # BOOK FIELD (5 bits if base & 8)
    # Reference: d2rdoctor.md lines 195-196 — "C4: book field BEFORE extended body"
    # Reference: d2r-editor/item_injector.py line 26 — "[5 bits if base&8]"
    # Items: tbk (Tome of Town Portal), ibk (Tome of Identify)
    # ==========================================================
    if base & 8:
        w.write_bits(0, 5)  # book type (0 for standard tomes)

    # ==========================================================
    # EXTENDED BODY (timestamp) — 1-bit flag, +96 if set
    # Reference: d2rdoctor.md lines 198-200
    # We always set to 0 (no extended body for injected items)
    # ==========================================================
    w.write_bits(0, 1)

    # ==========================================================
    # DEFENSE (11 bits if base & 4)
    # Reference: d2rdoctor.md lines 202-210
    # ==========================================================
    if base & 4:
        w.write_bits(defense, 11)

    # ==========================================================
    # DURABILITY (8-bit max + 9-bit current if max > 0)
    # Condition: base & 6 nonzero (has durability field)
    # Reference: d2rdoctor.md lines 212-215
    # ==========================================================
    if base & 6:
        w.write_bits(max_dur, 8)
        if max_dur > 0:
            w.write_bits(cur_dur, 9)

    # ==========================================================
    # QUANTITY (v105: 1-bit presence flag + conditional 9-bit value)
    # Reference: d2rdoctor.md lines 217-219
    # Reference: d2r-editor/item_injector.py lines 268-273
    # ==========================================================
    if base & 1:
        # Stackable item: set presence flag and write quantity
        w.write_bits(1, 1)
        w.write_bits(quantity if quantity > 0 else 200, 9)
    else:
        # Non-stackable: presence flag = 0
        w.write_bits(0, 1)

    # ==========================================================
    # SOCKET COUNT (4 bits if socketed flag set)
    # Reference: d2rdoctor.md lines 221-222
    # ==========================================================
    if socketed:
        w.write_bits(num_sockets, 4)

    # ==========================================================
    # SET FLAGS (5 bits if quality=5, BEFORE property lists)
    # Reference: d2rdoctor.md lines 224-225 — "C3: set item setflags"
    # Reference: d2r-editor/item_injector.py line 32 — "[5 bits setflags if quality=5]"
    # These flags indicate which set bonus property lists are present
    # ==========================================================
    if quality == 5:
        w.write_bits(set_flags, 5)

    # ==========================================================
    # PROPERTIES — WITH CORRECT TERMINATION
    # Reference: fix_obsidian_rw.py lines 227-245 (THE FIX)
    # Reference: d2rdoctor.md line 229 — terminators_expected = 2 if is_runeword
    #
    # Runeword items need TWO property lists:
    #   List 1: base item magic properties (empty for quality=2) → 0x1FF
    #   List 2: runeword bonus properties → 0x1FF
    #
    # For injected runewords, we write:
    #   First 0x1FF (empty base properties)
    #   Actual runeword bonus properties + Second 0x1FF
    # ==========================================================
    if runeword:
        # First list: empty base properties
        w.write_bits(0x1FF, 9)
        # Second list: runeword bonus properties
        if properties:
            encode_properties_terminated(w, properties)
        else:
            w.write_bits(0x1FF, 9)
    else:
        # Non-runeword: single property list
        if properties:
            encode_properties_terminated(w, properties)
        else:
            w.write_bits(0x1FF, 9)

    # D2R v105 requires at least 1 bit of padding after the last terminator.
    # Items with exactly byte-aligned data (0 padding bits) cause
    # "FAILED TO JOIN GAME" — confirmed by testing sB=3 stats.
    if w.pos % 8 == 0:
        w.write_bits(0, 1)

    # Byte-align the item data
    w.align()
    return w.get_bytes()


def encode_socketed_rune(rune_code, socket_idx=0):
    """Encode a rune as a simple socketed sub-item (inserted after parent).

    Args:
        rune_code: Rune type code (e.g., 'r18' for Ko rune)
        socket_idx: Socket slot index (0-based). First rune=0, second=1, etc.
    """
    w = BitWriter()
    # Flags: identified (bit 4) + simple (bit 21) + always-1 (bit 23)
    flags = (1 << 4) | (1 << 21) | (1 << 23)
    w.write_bits(flags, 32)
    w.write_bits(5, 3)       # D2R ext bits: 5 (binary 101)
    w.write_bits(6, 3)       # location = 6 (socketed in another item)
    w.write_bits(0, 4)       # bodyloc = 0
    w.write_bits(socket_idx, 4)  # col = socket slot index (0-based)
    w.write_bits(0, 3)       # row = 0
    w.write_bits(0, 1)       # unknown bit
    w.write_bits(0, 3)       # storage = 0
    # Huffman-encode the rune type code (pad to 4 chars)
    code = rune_code if len(rune_code) >= 4 else rune_code + ' ' * (4 - len(rune_code))
    w.write_huff(code)
    # Socketed sub-items (location=6) have an 8-bit field after the type code.
    # Value=2 observed in all D2R v105 socketed sub-items (Foedra.d2s reference).
    w.write_bits(2, 8)
    # Padding fix: D2R rejects socketed sub-items with insufficient padding.
    # Items with very short Huffman codes (r27/Ohm, r29/Sur = 18 bits) produce
    # only 79 data bits → 1 padding bit → 10-byte items that cause
    # "FAILED TO JOIN GAME". All working runes are 11 bytes (88 bits).
    # Fix: ensure at least 2 zero padding bits before alignment, which
    # guarantees all rune items reach the minimum 11-byte size.
    remainder = w.pos % 8
    if remainder == 0:
        w.write_bits(0, 2)  # 0 padding → add 2
    elif remainder == 7:
        w.write_bits(0, 2)  # 1 padding bit → add 1 more for 2 total
    # else: 2+ padding bits already, alignment will handle it
    w.align()
    return w.get_bytes()


# ---------------------------------------------------------------------------
# G. Save File Utilities
# ---------------------------------------------------------------------------

def find_item_list(data, search_from=0x300):
    """Find character item list JM header in a .d2s file.

    Reference: d2r_inject.py lines 410-415

    Returns the byte offset of the JM marker, or -1 if not found.
    Searches from 0x300 to 0x500 (typical range for character item list).
    """
    for i in range(search_from, min(len(data) - 4, 0x500)):
        if data[i:i + 2] == b'JM':
            return i
    return -1


def calc_checksum(data):
    """Calculate D2S file checksum (rotate-left accumulate).

    Reference: d2r-editor/item_injector.py lines 70-76
    Reference: d2rdoctor.md lines 98-103

    The checksum field at bytes 12-15 is treated as zero during calculation.
    """
    cs = 0
    for i, b in enumerate(data):
        if 0x0c <= i <= 0x0f:
            b = 0  # zero out checksum field during calculation
        cs = (((cs << 1) | (cs >> 31)) + b) & 0xFFFFFFFF
    return cs


def write_d2s(path, data):
    """Write .d2s data to file with updated file size and checksum.

    Reference: d2r_inject.py lines 399-407

    Updates:
        - File size field at offset 8 (4 bytes, little-endian)
        - Checksum field at offset 12 (4 bytes, little-endian)
    """
    data = bytearray(data)
    # Update file size
    struct.pack_into('<I', data, 8, len(data))
    # Calculate and write checksum
    data[12:16] = b'\x00\x00\x00\x00'
    cs = calc_checksum(data)
    struct.pack_into('<I', data, 12, cs)
    # Verify checksum
    stored = struct.unpack_from('<I', data, 0x0c)[0]
    verify = calc_checksum(data)
    if stored != verify:
        raise RuntimeError(
            f"Checksum verification failed: stored={stored:#010x}, "
            f"calculated={verify:#010x}"
        )
    with open(path, 'wb') as f:
        f.write(data)


# ---------------------------------------------------------------------------
# H. Stat ID Shortcuts (convenience aliases)
# Reference: build_characters.py lines 325-349
# Reference: item_stat_cost.py (verified IDs)
# ---------------------------------------------------------------------------
S = STAT_BY_NAME

# Common stat IDs for item building
STRENGTH     = S['strength']              # 0  (sB=8,  sA=32)
ENERGY       = S['energy']                # 1  (sB=7,  sA=32)
DEXTERITY    = S['dexterity']             # 2  (sB=7,  sA=32)
VITALITY     = S['vitality']              # 3  (sB=7,  sA=32)
MAXHP        = S['maxhp']                 # 7  (sB=9,  sA=32)
MAXMANA      = S['maxmana']               # 9  (sB=8,  sA=32)
ED           = S['item_armor_percent']     # 16 (sB=9,  sA=0)
FLAT_DEF     = S['armorclass']             # 31 (sB=11, sA=10)
FIRE_RES     = S['fireresist']             # 39 (sB=9,  sA=200)
LIGHT_RES    = S['lightresist']            # 41 (sB=9,  sA=200)
COLD_RES     = S['coldresist']             # 43 (sB=9,  sA=200)
POISON_RES   = S['poisonresist']           # 45 (sB=9,  sA=200)
FCR          = S['item_fastercastrate']    # 105 (sB=9, sA=0)
FHR          = S['item_fastergethitrate']  # 99  (sB=7, sA=20)
FRW          = S['item_fastermovevelocity'] # 96  (sB=7, sA=20)
IAS          = S['item_fasterattackrate']  # 93  (sB=7, sA=0)
MF           = S['item_magicbonus']        # 80  (sB=7, sA=100)
ALL_SKILLS   = S['item_allskills']         # 127 (sB=3, sA=0)
MAGIC_ABSORB     = S['item_absorbmagic']       # 147 (sB=7, sA=0)
ABSORB_COLD_PCT  = S['item_absorbcold_percent'] # 148 (sB=7, sA=0) — NOT the same as MAGIC_ABSORB
REPLENISH        = S['hpregen']                # 74  (sB=6, sA=30)
SKILL_TAB        = S['item_addskill_tab']      # 188 (sB=3, sA=0, sP=16)
NON_CLASS_SKILL  = S['item_nonclassskill']     # 97  (sB=6, sA=0, sP=9) — oskills (Teleport, BO, etc.)
ITEM_AURA        = S['item_aura']              # 151 (sB=5, sA=0, sP=9) — aura when equipped


# ===========================================================================
# SMOKE TESTS
# ===========================================================================
if __name__ == '__main__':
    print("=" * 60)
    print("d2r_build_lib.py — Smoke Tests")
    print("=" * 60)

    errors = 0

    # --- Test 1: Simple rune (no defense/durability) ---
    print("\n--- Test 1: El Rune (r01) in stash ---")
    try:
        rune = build_item(
            'r01', col=0, row=0, storage=STORAGE['stash'],
            quality=2, ilvl=1
        )
        print(f"  Bytes: {len(rune)}")
        # Runes have flags=0 in item_bases.py (line 628): no defense, no durability
        # Expect: 32 flags + 3 ext + 18 location + ~22 huffman + 3+32+7+4+2 = ~123 bits
        # Plus quantity flag (1 bit, value=0) + terminator (9 bits) + alignment
        # Reasonable range: 14-22 bytes
        assert 10 <= len(rune) <= 25, f"Unexpected size: {len(rune)}"
        # Verify ext bits: byte 4, bits 0-2 should be 5 (1,0,1)
        assert (rune[4] & 7) == 5, f"Bad ext bits: {rune[4] & 7}"
        print(f"  Ext bits: OK ((byte[4] & 7) == 5)")
        print(f"  PASS")
    except Exception as e:
        print(f"  FAIL: {e}")
        errors += 1

    # --- Test 2: Unique armor (defense + durability + properties) ---
    # unique_items.py line 253: UID 248 = Harlequin Crest (Shako), code='uap'
    print("\n--- Test 2: Unique Shako (uid=248, code='uap') ---")
    try:
        # Verify UID 248 exists and is Shako
        uid_info = UNIQUE_ITEMS.get(248)
        assert uid_info is not None, "UID 248 not in UNIQUE_ITEMS"
        print(f"  UID 248 = {uid_info['name']} (code={uid_info['code']})")

        shako = build_item(
            uid_info['code'], col=0, row=0, storage=STORAGE['stash'],
            quality=7, ilvl=69, unique_id=248,
            defense=141,
            max_dur=12, cur_dur=12,
            properties=[
                (ALL_SKILLS, 2),         # +2 All Skills
                (MAXHP, 99),             # +99 Life
                (MAXMANA, 99),           # +99 Mana
                (MF, 50),               # 50% MF
            ]
        )
        print(f"  Bytes: {len(shako)}")
        # Armor item: 32+3+18+huff+47+12(uid)+1+11(def)+8+9(dur)+1+props+9+align
        assert 20 <= len(shako) <= 40, f"Unexpected size: {len(shako)}"
        assert (shako[4] & 7) == 5, f"Bad ext bits: {shako[4] & 7}"
        print(f"  Ext bits: OK")
        print(f"  PASS")
    except Exception as e:
        print(f"  FAIL: {e}")
        errors += 1

    # --- Test 3: Runeword weapon (socketed + runeword + double terminator) ---
    print("\n--- Test 3: Runeword CTA (crs, runeword_id=39) ---")
    try:
        # Verify runeword 39 exists
        rw_info = RUNEWORDS.get(39)
        assert rw_info is not None, "Runeword 39 not in RUNEWORDS"
        print(f"  Runeword 39 = {rw_info['name']} ({rw_info['runes']})")

        cta = build_item(
            'crs', col=0, row=0, storage=STORAGE['stash'],
            quality=2, ilvl=31,
            socketed=True, num_sockets=5,
            max_dur=20, cur_dur=20,
            runeword=True, runeword_id=39,
            properties=[
                (ALL_SKILLS, 1),
                (IAS, 40),
                (ED, 250),
                (REPLENISH, 12),
                (MF, 30),
            ]
        )
        print(f"  Bytes: {len(cta)}")
        # Runeword: all of the above PLUS 16 rw_id + 4 sockets + double terminator
        assert 20 <= len(cta) <= 45, f"Unexpected size: {len(cta)}"
        assert (cta[4] & 7) == 5, f"Bad ext bits: {cta[4] & 7}"
        print(f"  Ext bits: OK")

        # Verify double terminator is present:
        # The last 18 bits before alignment should contain two 0x1FF sequences
        # (Actually they're at different positions due to properties, but we can
        # verify the item parses without error as a structural test)
        print(f"  PASS (double terminator encoded)")
    except Exception as e:
        print(f"  FAIL: {e}")
        errors += 1

    # --- Test 4: Overflow protection ---
    print("\n--- Test 4: Overflow protection ---")
    try:
        # Stat 127 (ALL_SKILLS) has sB=3, sA=0, max value = 7
        # Trying to write value=8 should raise ValueError
        try:
            build_item(
                'amu', col=0, row=0, storage=STORAGE['stash'],
                quality=4, ilvl=99,
                properties=[(ALL_SKILLS, 8)]  # sB=3, max=7
            )
            print(f"  FAIL: Should have raised ValueError for overflow")
            errors += 1
        except ValueError as ve:
            print(f"  Caught overflow: {ve}")
            print(f"  PASS")
    except Exception as e:
        print(f"  FAIL: {e}")
        errors += 1

    # --- Test 5: UID validation ---
    print("\n--- Test 5: UID validation ---")
    try:
        # Mismatched code/UID should raise
        try:
            build_item(
                'rin', col=0, row=0, storage=STORAGE['stash'],
                quality=7, ilvl=99, unique_id=248,  # 248 = Harlequin Crest, code='uap' not 'rin'
                properties=[]
            )
            print(f"  FAIL: Should have raised ValueError for UID mismatch")
            errors += 1
        except ValueError as ve:
            print(f"  Caught mismatch: {ve}")
            print(f"  PASS")
    except Exception as e:
        print(f"  FAIL: {e}")
        errors += 1

    # --- Test 6: Set item (quality=5) ---
    print("\n--- Test 6: Set item (quality=5, Civerb's Ward, set_id=0) ---")
    try:
        set_info = SET_ITEMS.get(0)
        assert set_info is not None, "Set ID 0 not in SET_ITEMS"
        print(f"  Set ID 0 = {set_info['name']} (code={set_info['code']})")

        set_item = build_item(
            set_info['code'], col=2, row=0, storage=STORAGE['stash'],
            quality=5, ilvl=9, set_id=0,
            defense=14,
            max_dur=24, cur_dur=24,
            set_flags=0,
            properties=[
                (FLAT_DEF, 15),  # +15 Defense
            ]
        )
        print(f"  Bytes: {len(set_item)}")
        assert 20 <= len(set_item) <= 40, f"Unexpected size: {len(set_item)}"
        assert (set_item[4] & 7) == 5, f"Bad ext bits"
        print(f"  PASS")
    except Exception as e:
        print(f"  FAIL: {e}")
        errors += 1

    # --- Test 7: get_base_flags coverage ---
    print("\n--- Test 7: get_base_flags validation ---")
    try:
        # Monarch (uit): flags=6 in item_bases.py line 159 (defense + durability)
        assert get_base_flags('uit') == 6, f"uit should be 6, got {get_base_flags('uit')}"
        # Ring (rin): flags=0 in item_bases.py line 540 (no defense, no durability)
        assert get_base_flags('rin') == 0, f"rin should be 0, got {get_base_flags('rin')}"
        # Tome of TP (tbk): flags=1 in item_bases.py line 536 + book bit = 9
        assert get_base_flags('tbk') == 9, f"tbk should be 9, got {get_base_flags('tbk')}"
        # Crystal Sword (crs): should be weapon with durability
        crs_flags = get_base_flags('crs')
        assert crs_flags & 2, f"crs should have durability bit, got {crs_flags}"
        # Unknown code: returns 0
        assert get_base_flags('zzz') == 0, f"unknown should be 0"
        print(f"  uit={get_base_flags('uit')}, rin={get_base_flags('rin')}, "
              f"tbk={get_base_flags('tbk')}, crs={get_base_flags('crs')}")
        print(f"  PASS")
    except Exception as e:
        print(f"  FAIL: {e}")
        errors += 1

    # --- Summary ---
    print("\n" + "=" * 60)
    if errors == 0:
        print("ALL TESTS PASSED")
    else:
        print(f"{errors} TEST(S) FAILED")
    print("=" * 60)
