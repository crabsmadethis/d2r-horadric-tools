#!/usr/bin/env python3
"""Forge follower-block variants into a staged `.d2s` output file.

This is a lab helper for D2S research. It never edits the source in place and
should be used with temp/staging paths first. Scanner-clean output can then be
manually copied into the live save directory when a test plan explicitly calls
for it.
"""
from __future__ import annotations

import argparse
import shutil
import struct
from pathlib import Path


DEMON_PAYLOAD_LEN = 116


def calc_checksum(data: bytes) -> int:
    checksum = 0
    for i, byte in enumerate(data):
        if 0x0C <= i <= 0x0F:
            byte = 0
        checksum = (((checksum << 1) | (checksum >> 31)) + byte) & 0xFFFFFFFF
    return checksum


def _decode_template_payload(data: bytes) -> bytes:
    lf = data.rfind(b"lf")
    if lf < 0 or lf + 4 > len(data):
        return b""
    kf = data.rfind(b"kf", 0, lf)
    if kf < 0 or lf - kf != 5:
        return b""
    count = struct.unpack_from("<H", data, lf + 2)[0]
    if count < 1:
        return b""
    return data[lf + 4:lf + 4 + DEMON_PAYLOAD_LEN]


def _read_payload(args: argparse.Namespace) -> tuple[int, bytes]:
    sources = [args.payload_bin, args.template_d2s, args.strip, args.invalid_count_without_payload]
    if sum(bool(source) for source in sources) != 1:
        raise SystemExit(
            "Choose exactly one of --payload-bin, --template-d2s, --strip, "
            "or --invalid-count-without-payload."
        )
    if args.strip:
        return 0, b""
    if args.invalid_count_without_payload:
        return 1, b""
    if args.payload_bin:
        payload = Path(args.payload_bin).read_bytes()
    else:
        template = Path(args.template_d2s).read_bytes()
        payload = _decode_template_payload(template)
        if not payload:
            raise SystemExit(f"template has no follower payload: {args.template_d2s}")
    if len(payload) != DEMON_PAYLOAD_LEN:
        raise SystemExit(
            f"payload must be {DEMON_PAYLOAD_LEN} bytes, got {len(payload)}"
        )
    return 1, payload


def _update_size_and_checksum(data: bytearray) -> None:
    struct.pack_into("<I", data, 0x08, len(data))
    data[0x0C:0x10] = b"\x00\x00\x00\x00"
    struct.pack_into("<I", data, 0x0C, calc_checksum(data))


def forge_follower(source: Path, output: Path, follower_count: int, payload: bytes) -> None:
    data = bytearray(source.read_bytes())
    lf = data.rfind(b"lf")
    if lf < 0 or lf + 4 > len(data):
        raise SystemExit(f"could not find trailing lf marker in {source}")

    kf = data.rfind(b"kf", 0, lf)
    if kf < 0:
        raise SystemExit(f"could not find kf marker before lf in {source}")
    if lf - kf != 5:
        raise SystemExit(f"unexpected kf-to-lf gap {lf - kf}; refusing to forge")

    new_data = bytearray(data[:lf + 2])
    new_data.extend(struct.pack("<H", follower_count))
    new_data.extend(payload)
    _update_size_and_checksum(new_data)

    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_suffix(output.suffix + ".tmp")
    tmp.write_bytes(new_data)
    shutil.move(str(tmp), output)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Source .d2s to copy and modify.")
    parser.add_argument("output", type=Path, help="Output .d2s staging path.")
    parser.add_argument("--payload-bin", type=Path, help="Raw 116-byte demon payload.")
    parser.add_argument("--template-d2s", type=Path, help=".d2s containing a follower payload to copy.")
    parser.add_argument("--strip", action="store_true", help="Write follower_count=0 and no payload.")
    parser.add_argument(
        "--invalid-count-without-payload",
        action="store_true",
        help="Write follower_count=1 with no payload. For negative live tests only.",
    )
    args = parser.parse_args()

    count, payload = _read_payload(args)
    forge_follower(args.source, args.output, count, payload)
    print(
        f"wrote {args.output} follower_count={count} "
        f"payload_bytes={len(payload)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
