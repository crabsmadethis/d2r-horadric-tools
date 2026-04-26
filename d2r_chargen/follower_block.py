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
EXPECTED_KF_TO_LF_GAP = 5  # `kf` + `00 01 00` + `lf` — verified across 19 saves

# High-confidence field offsets within the 116-byte demon payload.
# Source: tests/fixtures/demon_block_decoded.md (Phase 0 decode notes).
# Low/medium-confidence fields (+24, +28, +44, +48, +64..+79) deliberately
# omitted — silently-wrong parsers are worse than missing parsers.
_OFF_MONSTER_HCIDX = 4   # u16 LE — MonStats.txt row index
_OFF_MONSTER_SEED = 6    # u32 LE — random instance seed
_OFF_BIND_DEMON_LEVEL = 52  # u32 LE — Bind Demon skill level at bind time
_OFF_AFFIX_INDICES = 80  # 5 raw bytes — MonUMod.txt indices (NOT a u32)
_AFFIX_LEN = 5


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


def decode_follower_block(data: bytes) -> FollowerBlock:
    kf = data.rfind(b'kf')
    if kf < 0:
        return FollowerBlock(0)
    lf = data.find(b'lf', kf + 2)
    if lf < 0 or lf - kf != EXPECTED_KF_TO_LF_GAP:
        return FollowerBlock(0)
    count = struct.unpack_from('<H', data, lf + 2)[0]
    if count == 0:
        return FollowerBlock(0)
    payload_start = lf + 4
    return FollowerBlock(count, data[payload_start:payload_start + DEMON_PAYLOAD_LEN])
