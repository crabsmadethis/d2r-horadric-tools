#!/usr/bin/env python3
"""Compare bound-demon payloads from raw 116-byte blobs or `.d2s` saves."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from d2r_chargen.follower_block import (
    DEMON_PAYLOAD_LEN,
    decode_follower_block,
    demon_payload_unknown_slices,
    parse_demon_payload,
)


def hex_bytes(data: bytes) -> str:
    return data.hex(" ")


def load_payload(path: Path) -> bytes:
    data = path.read_bytes()
    if len(data) == DEMON_PAYLOAD_LEN:
        return data
    block = decode_follower_block(data)
    if block.payload_len == DEMON_PAYLOAD_LEN:
        return block.payload
    raise ValueError(
        f"{path}: expected a {DEMON_PAYLOAD_LEN}-byte payload or a .d2s "
        "with exactly one bound-demon payload"
    )


def diff_offsets(payloads: list[bytes]) -> list[tuple[int, list[int]]]:
    rows: list[tuple[int, list[int]]] = []
    for offset in range(DEMON_PAYLOAD_LEN):
        values = [payload[offset] for payload in payloads]
        if len(set(values)) > 1:
            rows.append((offset, values))
    return rows


def print_summary(paths: list[Path], payloads: list[bytes]) -> None:
    print("payloads:")
    for path, payload in zip(paths, payloads):
        fields = parse_demon_payload(payload)
        print(
            f"  {path.name}: monster_hcidx={fields.monster_hcidx} "
            f"monster_seed=0x{fields.monster_seed:08X} "
            f"bind_demon_level={fields.bind_demon_level} "
            f"affix_indices={hex_bytes(fields.affix_indices)}"
        )

    print("\nunknown slices:")
    for path, payload in zip(paths, payloads):
        print(f"  {path.name}:")
        for name, raw in demon_payload_unknown_slices(payload).items():
            print(f"    {name}={hex_bytes(raw)}")

    print("\nbyte diffs:")
    rows = diff_offsets(payloads)
    if not rows:
        print("  none")
        return
    names = [path.name for path in paths]
    print("  offset  " + "  ".join(names))
    for offset, values in rows:
        print("  " + f"+{offset:03d}   " + "  ".join(f"{value:02x}" for value in values))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "payloads",
        nargs="+",
        type=Path,
        help="Raw 116-byte demon payloads or .d2s saves with one follower payload.",
    )
    args = parser.parse_args()

    payloads = [load_payload(path) for path in args.payloads]
    print_summary(args.payloads, payloads)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
