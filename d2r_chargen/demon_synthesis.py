"""Experimental bound-demon payload initializer.

This module builds only explicit, field-based 116-byte demon payloads. It is
not a general monster/name/aura synthesis API; callers must provide every
currently unknown context slice they intend to claim.
"""

from __future__ import annotations

import struct
from collections.abc import Sequence
from dataclasses import dataclass, field

from d2r_chargen.follower_block import DEMON_PAYLOAD_LEN


PREFIX_0_3 = bytes.fromhex("18 00 01 00")
STRUCT_10_23 = bytes.fromhex("10 00 02 03 00 00 00 00 00 00 03 00 00 00")
STRUCT_56_63 = bytes.fromhex("02 00 00 00 01 00 00 00")
GF_OPCODE_92_94 = bytes.fromhex("67 66 06")
ROW20_NO_AFFIX_TAIL_95_115 = bytes.fromhex(
    "00 74 0c 00 0e 00 e8 18 00 30 18 02 00 00 68 00 3e 04 00 f0 1f"
)


@dataclass(frozen=True)
class BoundDemonSynthesisFields:
    """Explicit inputs for the current experimental demon payload builder."""

    monster_hcidx: int
    monster_seed: int
    bind_metadata: int = 7
    affixes: bytes | Sequence[int] = field(default_factory=lambda: bytes(7))
    runtime_stats_24_31: bytes | Sequence[int] = field(default_factory=lambda: bytes(8))
    percent_or_caps_44_51: bytes | Sequence[int] = field(default_factory=lambda: bytes(8))
    bitfields_64_79: bytes | Sequence[int] = field(default_factory=lambda: bytes(16))
    post_gf_tail_95_115: bytes | Sequence[int] = ROW20_NO_AFFIX_TAIL_95_115


def build_bound_demon_payload(fields: BoundDemonSynthesisFields) -> bytes:
    """Build a 116-byte bound-demon payload from explicit initializer fields."""

    monster_hcidx = _validate_int("monster_hcidx", fields.monster_hcidx, 0xFFFF)
    monster_seed = _validate_int("monster_seed", fields.monster_seed, 0xFFFFFFFF)
    bind_metadata = _validate_int("bind_metadata", fields.bind_metadata, 0xFFFFFFFF)
    affixes = _validate_bytes("affixes", fields.affixes, 7)
    runtime_stats = _validate_bytes("runtime_stats_24_31", fields.runtime_stats_24_31, 8)
    percent_or_caps = _validate_bytes("percent_or_caps_44_51", fields.percent_or_caps_44_51, 8)
    bitfields = _validate_bytes("bitfields_64_79", fields.bitfields_64_79, 16)
    post_gf_tail = _validate_bytes("post_gf_tail_95_115", fields.post_gf_tail_95_115, 21)

    payload = bytearray(DEMON_PAYLOAD_LEN)
    payload[0:4] = PREFIX_0_3
    struct.pack_into("<H", payload, 4, monster_hcidx)
    struct.pack_into("<I", payload, 6, monster_seed)
    payload[10:24] = STRUCT_10_23
    payload[24:32] = runtime_stats
    payload[44:52] = percent_or_caps
    struct.pack_into("<I", payload, 52, bind_metadata)
    payload[56:64] = STRUCT_56_63
    payload[64:80] = bitfields
    payload[80:87] = affixes
    payload[87] = 0
    payload[88] = 0
    payload[89:92] = b"\0\0\0"
    payload[92:95] = GF_OPCODE_92_94
    payload[95:116] = post_gf_tail
    return bytes(payload)


def _validate_int(name: str, value: int, maximum: int) -> int:
    if not isinstance(value, int):
        raise TypeError(f"{name} must be an int")
    if not 0 <= value <= maximum:
        raise ValueError(f"{name} out of range 0..0x{maximum:x}: {value}")
    return value


def _validate_bytes(name: str, value: bytes | Sequence[int], expected_len: int) -> bytes:
    raw = bytes(value)
    if len(raw) != expected_len:
        raise ValueError(f"{name} must be {expected_len} bytes, got {len(raw)}")
    return raw
