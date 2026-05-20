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
SOCKET_FILLER_LEN = 11


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


@dataclass(frozen=True)
class IronGolemPayloadRecord:
    role: str
    offset: int
    length: int
    type_code: str | None = None
    quality: int | None = None
    uid: Optional[int] = None
    storage: int | None = None
    col: int | None = None
    row: int | None = None
    bodyloc: int | None = None
    location: int | None = None
    ext: tuple[int, int, int] | None = None
    flags: int = 0

    @property
    def end(self) -> int:
        return self.offset + self.length

    @property
    def is_runeword(self) -> bool:
        return bool(self.flags & (1 << 26))

    @property
    def is_socketed(self) -> bool:
        return bool(self.flags & (1 << 11))

    @property
    def is_simple(self) -> bool:
        return bool(self.flags & (1 << 21))

    def to_dict(self) -> dict[str, object]:
        flags = []
        if self.is_runeword:
            flags.append("runeword")
        if self.is_socketed:
            flags.append("socketed")
        if self.is_simple:
            flags.append("simple")
        return {
            "role": self.role,
            "offset": self.offset,
            "length": self.length,
            "type_code": self.type_code,
            "quality": self.quality,
            "uid": self.uid,
            "storage": self.storage,
            "col": self.col,
            "row": self.row,
            "bodyloc": self.bodyloc,
            "location": self.location,
            "ext": None if self.ext is None else list(self.ext),
            "flags": flags,
        }


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


def split_iron_golem_payload_records(payload: bytes) -> list[IronGolemPayloadRecord]:
    """Split a JM-less golem payload into parent and socket-filler records.

    The golem block has no `JM` count, so record lengths are inferred
    conservatively. Single-parent payloads remain one record. Runeword payloads
    are split only when the trailing bytes partition cleanly into known
    11-byte socket fillers with sequential socket indexes.
    """
    if not payload:
        return []

    split_at = _find_socket_filler_split(payload)
    if split_at is None:
        return [_build_payload_record(payload, 0, len(payload), "parent")]

    records = [_build_payload_record(payload, 0, split_at, "parent")]
    for idx, offset in enumerate(range(split_at, len(payload), SOCKET_FILLER_LEN)):
        records.append(
            _build_payload_record(
                payload,
                offset,
                SOCKET_FILLER_LEN,
                f"socket_filler_{idx}",
                minimal=True,
            )
        )
    return records


def compare_iron_golem_payloads(
    before: bytes,
    after: bytes,
) -> dict[str, object]:
    """Return public-safe byte-diff groups for two golem payloads."""
    records = split_iron_golem_payload_records(before)
    compared_len = min(len(before), len(after))
    diff_offsets = [
        offset for offset in range(compared_len) if before[offset] != after[offset]
    ]
    record_groups = []
    covered = set()

    for record in records:
        offsets = [
            offset
            for offset in diff_offsets
            if record.offset <= offset < record.end
        ]
        covered.update(offsets)
        if not offsets:
            continue
        record_groups.append({
            "role": record.role,
            "offset": record.offset,
            "length": record.length,
            "diff_count": len(offsets),
            "diff_offsets": offsets,
            "relative_offsets": [offset - record.offset for offset in offsets],
        })

    ungrouped = [offset for offset in diff_offsets if offset not in covered]
    return {
        "before_len": len(before),
        "after_len": len(after),
        "same_length": len(before) == len(after),
        "diff_count": len(diff_offsets) + abs(len(before) - len(after)),
        "diff_offsets": diff_offsets,
        "record_groups": record_groups,
        "ungrouped_offsets": ungrouped,
        "before_records": [record.to_dict() for record in records],
    }


def _find_socket_filler_split(payload: bytes) -> int | None:
    if len(payload) <= SOCKET_FILLER_LEN:
        return None

    parent_flags = _flags_at(payload, 0)
    if not (parent_flags & (1 << 26)):
        return None

    for offset in range(1, len(payload) - SOCKET_FILLER_LEN + 1):
        trailing_len = len(payload) - offset
        if trailing_len <= 0 or trailing_len % SOCKET_FILLER_LEN != 0:
            continue
        filler_count = trailing_len // SOCKET_FILLER_LEN
        if all(
            _is_socket_filler(payload, offset + idx * SOCKET_FILLER_LEN, idx)
            for idx in range(filler_count)
        ):
            return offset
    return None


def _is_socket_filler(payload: bytes, offset: int, socket_idx: int) -> bool:
    if offset < 0 or offset + SOCKET_FILLER_LEN > len(payload):
        return False
    flags = _flags_at(payload, offset)
    if not (flags & (1 << 21)):
        return False
    header = _decode_minimal_header(payload, offset)
    if header is None:
        return False
    type_code, storage, col, _row, bodyloc, location, ext = header
    return (
        type_code.startswith("r")
        and storage == 0
        and col == socket_idx
        and bodyloc == 0
        and location == 6
        and ext == (1, 0, 1)
    )


def _build_payload_record(
    payload: bytes,
    offset: int,
    length: int,
    role: str,
    *,
    minimal: bool = False,
) -> IronGolemPayloadRecord:
    flags = _flags_at(payload, offset)
    if minimal:
        header = _decode_minimal_header(payload, offset)
        if header is not None:
            type_code, storage, col, row, bodyloc, location, ext = header
            return IronGolemPayloadRecord(
                role=role,
                offset=offset,
                length=length,
                type_code=type_code,
                storage=storage,
                col=col,
                row=row,
                bodyloc=bodyloc,
                location=location,
                ext=ext,
                flags=flags,
            )

    full = _decode_full_header(payload, offset)
    if full is not None:
        type_code, _ilvl, quality, uid, storage, col, row, bodyloc, location, ext = full
        return IronGolemPayloadRecord(
            role=role,
            offset=offset,
            length=length,
            type_code=type_code,
            quality=quality,
            uid=uid,
            storage=storage,
            col=col,
            row=row,
            bodyloc=bodyloc,
            location=location,
            ext=ext,
            flags=flags,
        )

    return IronGolemPayloadRecord(
        role=role,
        offset=offset,
        length=length,
        flags=flags,
    )


def _decode_full_header(payload: bytes, offset: int):
    try:
        from d2r_chargen.scanner import decode_item_header

        header = decode_item_header(payload, offset)
    except Exception:
        return None
    if header[0] == "???":
        return None
    return header


def _decode_minimal_header(payload: bytes, offset: int):
    try:
        from d2r_chargen.scanner import bits_at, decode_huff4

        bit = offset * 8
        type_code, _type_end = decode_huff4(payload, bit + 53)
        return (
            type_code,
            bits_at(payload, bit + 50, 3),
            bits_at(payload, bit + 42, 4),
            bits_at(payload, bit + 46, 3),
            bits_at(payload, bit + 38, 4),
            bits_at(payload, bit + 35, 3),
            _ext_at(payload, offset),
        )
    except Exception:
        return None


def _flags_at(payload: bytes, offset: int) -> int:
    if offset < 0 or offset + 4 > len(payload):
        return 0
    return int.from_bytes(payload[offset:offset + 4], "little")


def _ext_at(payload: bytes, offset: int) -> tuple[int, int, int] | None:
    if offset < 0 or offset + 4 >= len(payload):
        return None
    b4 = payload[offset + 4]
    return (b4 & 1, (b4 >> 1) & 1, (b4 >> 2) & 1)
