"""Parse the Iron Golem tail block of a D2R save.

Live probes on 2026-05-08 showed that an active Necromancer Iron Golem is
stored between the trailing `kf` and `lf` markers as one JM-less item bitstream:

    kf <u8:has_golem> [item bytes] 01 00 lf <u16:follower_count> [followers]

The item bytes are variable-length normal item encoding. There is no `JM`
section wrapper and no fixed-size golem record.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


TAIL_BRIDGE = b"\x01\x00"


@dataclass
class IronGolemBlock:
    has_golem_byte: int
    item_payload: bytes = b""
    bridge: bytes = b""
    kf_offset: int = -1
    lf_offset: int = -1

    @property
    def has_markers(self) -> bool:
        return self.kf_offset >= 0 and self.lf_offset >= 0

    @property
    def has_golem(self) -> bool:
        return self.has_golem_byte == 1

    @property
    def payload_len(self) -> int:
        return len(self.item_payload)

    @property
    def bridge_ok(self) -> bool:
        return self.bridge == TAIL_BRIDGE


@dataclass
class IronGolemItemHeader:
    type_code: str
    ilvl: int
    quality: int
    uid: Optional[int]
    storage: int
    col: int
    row: int
    bodyloc: int
    location: int
    ext: tuple[int, int, int]


def decode_iron_golem_block(data: bytes) -> IronGolemBlock:
    """Return the Iron Golem block before the trailing follower block.

    Missing or malformed markers return an empty block instead of raising; this
    mirrors `decode_follower_block` and keeps aggregate corpus scans tolerant.
    """
    lf = data.rfind(b"lf")
    if lf < 0:
        return IronGolemBlock(0)
    kf = data.rfind(b"kf", 0, lf)
    if kf < 0 or kf + 3 > len(data):
        return IronGolemBlock(0, kf_offset=kf, lf_offset=lf)

    has_golem_byte = data[kf + 2]
    bridge = data[lf - 2:lf] if lf >= 2 else b""
    item_payload = b""
    if has_golem_byte == 1 and bridge == TAIL_BRIDGE and lf >= kf + 5:
        item_payload = bytes(data[kf + 3:lf - 2])

    return IronGolemBlock(
        has_golem_byte=has_golem_byte,
        item_payload=item_payload,
        bridge=bytes(bridge),
        kf_offset=kf,
        lf_offset=lf,
    )


def decode_iron_golem_item_header(payload: bytes) -> IronGolemItemHeader | None:
    """Best-effort decode of the JM-less item payload header.

    Returns None if scanner support or enough bytes are unavailable.
    """
    if not payload:
        return None
    try:
        from d2r_chargen.scanner import decode_item_header

        hdr = decode_item_header(payload, 0)
    except Exception:
        return None

    type_code, ilvl, quality, uid, storage, col, row, bodyloc, location, ext = hdr
    if type_code == "???":
        return None
    return IronGolemItemHeader(
        type_code=type_code,
        ilvl=ilvl,
        quality=quality,
        uid=uid,
        storage=storage,
        col=col,
        row=row,
        bodyloc=bodyloc,
        location=location,
        ext=ext,
    )
