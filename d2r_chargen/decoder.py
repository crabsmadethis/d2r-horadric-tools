"""Decode item property bitstreams back to property tuples.

This is the inverse of build_lib.encode_property(). The scanner's
validate_item_properties() has a similar bit-navigation structure but only
checks constraints — this function accumulates decoded values.

Encoding reference (build_lib.py:190-265):
  Grouped (np>0): stat_id(9) + np sequential values (each member_sB bits)
  e=0/1 (standard): stat_id(9) + param(sP) + (value+sA)(sB)
  e=2 (CTC): stat_id(9) + encoded_param(sP) + (value+sA)(sB)
      Bitstream param: (skill_id << 6) | skill_level
      Internal param:  skill_id | (skill_level << 10)
  e=3 (charges): stat_id(9) + encoded_param(sP) + value(sB)  [NO sA offset]
      Bitstream param: (skill_id << 6) | skill_level
      Internal param:  skill_id | (skill_level << 10)
"""
from d2r_chargen.data.item_stat_cost import ITEM_STAT_COST
from d2r_chargen.scanner import bits_at


def _sign_extend(raw, bits):
    """Sign-extend a two's-complement value stored in `bits` unsigned bits."""
    sign_bit = 1 << (bits - 1)
    if raw & sign_bit:
        return raw - (1 << bits)
    return raw


def decode_item_properties(data, bit_offset, num_terminators=1):
    """Decode property bitstream starting at bit_offset.

    Args:
        data: bytes or bytearray of the item data.
        bit_offset: Starting bit position.
        num_terminators: How many 0x1FF terminators to expect
            (2 for runeword items, 1 otherwise).

    Returns:
        (properties, end_bit) where properties is a list of tuples:
          (stat_id, value)         — simple scalar
          (stat_id, value, param)  — parameterized (skills, CTC, charges)
          (stat_id, [v0, v1, ...]) — grouped stat (np > 1)
    """
    br = bit_offset
    total_bits = len(data) * 8
    properties = []
    terminators_found = 0

    for _ in range(200):  # safety limit matching scanner
        if br + 9 > total_bits:
            break

        stat_id = bits_at(data, br, 9)
        br += 9

        if stat_id == 0x1FF:
            terminators_found += 1
            if terminators_found >= num_terminators:
                break
            continue

        info = ITEM_STAT_COST.get(stat_id)
        if info is None:
            raise ValueError(f"Unknown stat_id={stat_id} at bit {br - 9}")

        sB = info.get('sB', 0)
        sP = info.get('sP', 0)
        sA = info.get('sA', 0)
        sS = info.get('sS', 0)
        e = info.get('e', 0)
        np_count = info.get('np', 1) or 1

        if sB == 0:
            raise ValueError(f"stat_id={stat_id} has sB=0 (unreadable)")

        # Grouped stats: one stat ID, np sequential values
        # Mirrors scanner.py:320-326 peek-ahead logic
        if np_count > 1:
            values = []
            # First member uses this stat's sB/sA
            raw = bits_at(data, br, sB)
            br += sB
            decoded = _sign_extend(raw, sB) - sA if sS else raw - sA
            values.append(decoded)

            # Remaining members: peek to detect individual vs compact encoding
            for k in range(1, np_count):
                sibling = ITEM_STAT_COST.get(stat_id + k)
                sibling_sB = sibling.get('sB', sB) if sibling else sB
                sibling_sA = sibling.get('sA', 0) if sibling else 0
                sibling_sS = sibling.get('sS', 0) if sibling else 0

                # Peek: does next 9-bit value equal stat_id + k?
                if br + 9 <= total_bits:
                    peek = bits_at(data, br, 9)
                    if peek == stat_id + k:
                        # Individual variant: skip the redundant stat ID header
                        br += 9

                raw = bits_at(data, br, sibling_sB)
                br += sibling_sB
                decoded = _sign_extend(raw, sibling_sB) - sibling_sA if sibling_sS else raw - sibling_sA
                values.append(decoded)

            properties.append((stat_id, values))
            continue

        # Read param (if any)
        param_val = 0
        if sP > 0:
            param_val = bits_at(data, br, sP)
            br += sP

        # Read value
        raw_val = bits_at(data, br, sB)
        br += sB

        if e == 3:
            # Charges: param in bitstream is (skill_id << 6) | skill_level
            # Reconstruct internal format: skill_id | (skill_level << 10)
            # Value is raw (NOT offset by sA)
            skill_level = param_val & 0x3F
            skill_id = (param_val >> 6) & 0x3FF
            internal_param = skill_id | (skill_level << 10)
            properties.append((stat_id, raw_val, internal_param))

        elif e == 2:
            # CTC: param in bitstream is (skill_id << 6) | skill_level
            # Reconstruct internal format: skill_id | (skill_level << 10)
            # Value IS offset by sA (subtract to get actual)
            skill_level = param_val & 0x3F
            skill_id = (param_val >> 6) & 0x3FF
            internal_param = skill_id | (skill_level << 10)
            decoded_val = (_sign_extend(raw_val, sB) if sS else raw_val) - sA
            properties.append((stat_id, decoded_val, internal_param))

        elif sP > 0:
            # e=0 or e=1 with param (skills, auras, etc.)
            decoded_val = (_sign_extend(raw_val, sB) if sS else raw_val) - sA
            properties.append((stat_id, decoded_val, param_val))

        else:
            # e=0 simple scalar
            decoded_val = (_sign_extend(raw_val, sB) if sS else raw_val) - sA
            properties.append((stat_id, decoded_val))

    return properties, br
