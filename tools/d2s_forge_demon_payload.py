#!/usr/bin/env python3
"""Forge controlled bound-demon payload mutations into a staged `.d2s`.

This is a lab helper for Reign of the Warlock demon research. It never edits
the source save in place. Use it to answer whether D2R accepts, canonicalizes,
or rejects specific high-confidence demon payload fields before promoting any
of those knobs into normal chargen YAML.
"""
from __future__ import annotations

import argparse
import shutil
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from d2r_chargen.data.monumod_affixes import AFFIXES
from d2r_chargen.follower_block import (
    DEMON_PAYLOAD_LEN,
    decode_follower_block,
    mutate_demon_payload,
)
from d2r_chargen.save import calc_checksum

_OFF_MONSTER_HCIDX = 4
_OFF_MONSTER_SEED = 6
_OFF_BIND_DEMON_LEVEL = 52
_OFF_AFFIX_INDICES = 80
_AFFIX_LEN = 5
_OFF_VOLATILE_RUNTIME = 89

_AFFIX_ALIASES = {
    "mana burn": 25,
    "manaburn": 25,
    "manahit": 25,
    "aura": 30,
    "aura enchanted": 30,
    "spectral": 27,
    "spectral hit": 27,
    "extra strong": 5,
    "strong": 5,
    "extra fast": 6,
    "fast": 6,
    "fire enchanted": 9,
    "fire": 9,
    "cursed": 7,
    "lightning enchanted": 3,
    "resist": 8,
}


def parse_int_token(token: str) -> int:
    """Parse decimal or 0x-prefixed integer tokens."""
    return int(token.strip(), 0)


def parse_affix_token(token: str) -> int:
    """Parse one MonUMod token by id, display name, or common shorthand."""
    raw = token.strip()
    if not raw:
        raise ValueError("empty affix token")
    try:
        value = parse_int_token(raw)
    except ValueError:
        normalized = raw.lower().replace("_", " ").replace("-", " ")
        normalized = " ".join(normalized.split())
        if normalized in _AFFIX_ALIASES:
            return _AFFIX_ALIASES[normalized]
        for idx, name in AFFIXES.items():
            if normalized == name.lower():
                return idx
        raise ValueError(f"unknown affix token: {token!r}") from None
    if value < 0 or value > 255:
        raise ValueError(f"affix id out of byte range: {value}")
    return value


def parse_affix_list(spec: str) -> bytes:
    """Parse exactly five comma-separated MonUMod affix bytes."""
    values = [parse_affix_token(part) for part in spec.split(",")]
    if len(values) != _AFFIX_LEN:
        raise ValueError(f"expected exactly 5 affixes, got {len(values)}")
    return bytes(values)


def load_payload(path: Path) -> bytes:
    """Load a raw 116-byte payload or extract one from a `.d2s` save."""
    data = path.read_bytes()
    if len(data) == DEMON_PAYLOAD_LEN:
        return data
    block = decode_follower_block(data)
    if block.payload_len == DEMON_PAYLOAD_LEN:
        return block.payload
    raise ValueError(f"{path} does not contain one {DEMON_PAYLOAD_LEN}-byte demon payload")


def mutate_payload(
    payload: bytes,
    *,
    monster_hcidx: int | None = None,
    monster_seed: int | None = None,
    bind_level: int | None = None,
    affixes: bytes | None = None,
    zero_volatile: bool = False,
) -> bytes:
    """Return a mutated copy of a 116-byte demon payload."""
    return mutate_demon_payload(
        payload,
        monster_hcidx=monster_hcidx,
        monster_seed=monster_seed,
        bind_level=bind_level,
        affix_indices=affixes,
        zero_volatile=zero_volatile,
    )


def _update_size_and_checksum(data: bytearray) -> None:
    struct.pack_into("<I", data, 0x08, len(data))
    data[0x0C:0x10] = b"\x00\x00\x00\x00"
    struct.pack_into("<I", data, 0x0C, calc_checksum(data))


def write_payload_to_save(source: Path, output: Path, payload: bytes) -> None:
    """Write one follower payload into a staged copy of `source`."""
    if len(payload) != DEMON_PAYLOAD_LEN:
        raise ValueError(f"payload must be {DEMON_PAYLOAD_LEN} bytes, got {len(payload)}")
    data = bytearray(source.read_bytes())
    lf = data.rfind(b"lf")
    if lf < 0 or lf + 4 > len(data):
        raise ValueError(f"could not find trailing lf marker in {source}")
    kf = data.rfind(b"kf", 0, lf)
    if kf < 0 or lf < 2 or data[lf - 2:lf] != b"\x01\x00":
        raise ValueError(f"could not verify kf/lf follower bridge in {source}")

    new_data = bytearray(data[:lf + 2])
    new_data.extend(struct.pack("<H", 1))
    new_data.extend(payload)
    _update_size_and_checksum(new_data)

    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_suffix(output.suffix + ".tmp")
    tmp.write_bytes(new_data)
    shutil.move(str(tmp), output)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Source .d2s to copy and mutate.")
    parser.add_argument("output", type=Path, help="Output .d2s staging path.")
    parser.add_argument(
        "--payload-from",
        type=Path,
        help="Optional raw payload or .d2s to use instead of source's current payload.",
    )
    parser.add_argument("--monster-hcidx", type=parse_int_token, help="Set payload +4 u16.")
    parser.add_argument("--monster-seed", type=parse_int_token, help="Set payload +6 u32.")
    parser.add_argument("--bind-level", type=parse_int_token, help="Set payload +52 u32.")
    parser.add_argument(
        "--affixes",
        type=parse_affix_list,
        help="Set exactly five comma-separated MonUMod ids/names at +80..+84.",
    )
    parser.add_argument(
        "--zero-volatile",
        action="store_true",
        help="Set volatile payload bytes +89..+91 to 00 00 00.",
    )
    args = parser.parse_args()

    payload_source = args.payload_from or args.source
    payload = load_payload(payload_source)
    mutated = mutate_payload(
        payload,
        monster_hcidx=args.monster_hcidx,
        monster_seed=args.monster_seed,
        bind_level=args.bind_level,
        affixes=args.affixes,
        zero_volatile=args.zero_volatile,
    )
    write_payload_to_save(args.source, args.output, mutated)
    print(f"wrote {args.output} follower_count=1 payload_bytes={len(mutated)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
