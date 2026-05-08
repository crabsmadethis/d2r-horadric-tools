"""Parse the follower-block section of a D2R save.

Discovered 2026-04-25: post-merc-items, all D2R saves carry an `lf` marker
followed by a u16 we call `follower_count`. When count >= 1, a per-follower
payload follows. For Reign of the Warlock the only known follower type is
the bound demon (Bind Demon skill, Skills.txt row 384), with a fixed 116-byte
payload. (scanner.py historically mislabeled this u16 as "merc hired" / lf_count;
renamed to follower_count in Task 2.2.)

Note on the embedded `gf` byte sequence: at offset +92 of the 116-byte demon
payload the bytes `0x67 0x66` ('gf') appear in both Fixture A and Fixture B
at the same position. This is data, not a section marker — the structural
golem section that sometimes follows the follower block (when count > 0) is
omitted entirely from current Marrowbind saves. The decoder therefore uses a
fixed 116-byte length for follower_count == 1, not a `gf`-terminated slice.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Optional

DEMON_PAYLOAD_LEN = 116
EXPECTED_TAIL_BRIDGE = b'\x01\x00'  # bytes immediately before trailing `lf`

# High-confidence field offsets within the 116-byte demon payload.
# Source: tests/fixtures/demon_block_decoded.md (Phase 0 decode notes).
# Low/medium-confidence fields (+24, +28, +44, +48, +64..+79) deliberately
# omitted — silently-wrong parsers are worse than missing parsers.
_OFF_MONSTER_HCIDX = 4   # u16 LE — MonStats.txt row index
_OFF_MONSTER_SEED = 6    # u32 LE — random instance seed
_OFF_BIND_DEMON_LEVEL = 52  # u32 LE — Bind Demon skill level at bind time
_OFF_AFFIX_INDICES = 80  # 5 raw bytes — MonUMod.txt indices (NOT a u32)
_AFFIX_LEN = 5

# Raw slices that are useful for live research but not yet safe to interpret as
# writer inputs. Names are intentionally cautious: these bytes are evidence, not
# schema.
DEMON_UNKNOWN_SLICE_RANGES = (
    ("runtime_stats_24_31", 24, 32),
    ("percent_or_caps_44_51", 44, 52),
    ("bitfields_64_79", 64, 80),
    ("hash_or_runtime_byte_88", 88, 89),
    ("volatile_runtime_89_91", 89, 92),
    ("post_gf_opcode_94", 94, 95),
    ("post_gf_tail_95_115", 95, 116),
)


@dataclass
class DemonPayloadFields:
    """High-confidence fields parsed from a 116-byte bound-demon payload."""
    monster_hcidx: int
    monster_seed: int
    bind_demon_level: int
    affix_indices: bytes


def parse_demon_payload(payload: bytes) -> DemonPayloadFields:
    """Parse high-confidence fields from a 116-byte demon payload.

    Raises ValueError if the payload is shorter than DEMON_PAYLOAD_LEN.
    """
    if len(payload) < DEMON_PAYLOAD_LEN:
        raise ValueError(
            f'demon payload too short: got {len(payload)} bytes, '
            f'need {DEMON_PAYLOAD_LEN}'
        )
    return DemonPayloadFields(
        monster_hcidx=struct.unpack_from('<H', payload, _OFF_MONSTER_HCIDX)[0],
        monster_seed=struct.unpack_from('<I', payload, _OFF_MONSTER_SEED)[0],
        bind_demon_level=struct.unpack_from('<I', payload, _OFF_BIND_DEMON_LEVEL)[0],
        affix_indices=bytes(payload[_OFF_AFFIX_INDICES:_OFF_AFFIX_INDICES + _AFFIX_LEN]),
    )


def demon_payload_unknown_slices(payload: bytes) -> dict[str, bytes]:
    """Return raw research slices from a 116-byte bound-demon payload.

    These slices deliberately do not assign semantic field names. They are for
    corpus comparison and live-test diffing while demon synthesis remains
    template-only.
    """
    if len(payload) < DEMON_PAYLOAD_LEN:
        raise ValueError(
            f'demon payload too short: got {len(payload)} bytes, '
            f'need {DEMON_PAYLOAD_LEN}'
        )
    return {
        name: bytes(payload[start:end])
        for name, start, end in DEMON_UNKNOWN_SLICE_RANGES
    }


@dataclass
class FollowerBlock:
    follower_count: int
    payload: bytes = b''

    @property
    def has_follower(self) -> bool:
        return self.follower_count > 0

    @property
    def payload_len(self) -> int:
        return len(self.payload)

    # ----- High-confidence demon-payload accessors (Option A: lazy props) -----
    # Numeric fields return None when there is no follower. affix_indices
    # returns b'' (parallel to `payload` defaulting to b''). Callers should
    # gate reads on `has_follower` for clarity.

    @property
    def monster_hcidx(self) -> Optional[int]:
        if len(self.payload) < DEMON_PAYLOAD_LEN:
            return None
        return struct.unpack_from('<H', self.payload, _OFF_MONSTER_HCIDX)[0]

    @property
    def monster_seed(self) -> Optional[int]:
        if len(self.payload) < DEMON_PAYLOAD_LEN:
            return None
        return struct.unpack_from('<I', self.payload, _OFF_MONSTER_SEED)[0]

    @property
    def bind_demon_level(self) -> Optional[int]:
        if len(self.payload) < DEMON_PAYLOAD_LEN:
            return None
        return struct.unpack_from('<I', self.payload, _OFF_BIND_DEMON_LEVEL)[0]

    @property
    def affix_indices(self) -> bytes:
        if len(self.payload) < DEMON_PAYLOAD_LEN:
            return b''
        return bytes(self.payload[_OFF_AFFIX_INDICES:_OFF_AFFIX_INDICES + _AFFIX_LEN])

    @property
    def unknown_slices(self) -> dict[str, bytes]:
        if len(self.payload) < DEMON_PAYLOAD_LEN:
            return {}
        return demon_payload_unknown_slices(self.payload)


def decode_follower_block(data: bytes) -> FollowerBlock:
    lf = data.rfind(b'lf')
    if lf < 0 or lf + 4 > len(data):
        return FollowerBlock(0)

    # The follower block starts after the final `lf`. The bytes immediately
    # before it are the fixed tail bridge (`01 00`) for both no-golem and
    # active-golem saves. Do not require `lf - kf == 5`; active Iron Golems
    # place a variable-length item payload between `kf 01` and this bridge.
    kf = data.rfind(b'kf', 0, lf)
    if kf < 0 or lf < 2 or data[lf - 2:lf] != EXPECTED_TAIL_BRIDGE:
        return FollowerBlock(0)

    count = struct.unpack_from('<H', data, lf + 2)[0]
    if count == 0:
        return FollowerBlock(0)
    payload_start = lf + 4
    return FollowerBlock(count, data[payload_start:payload_start + DEMON_PAYLOAD_LEN])
