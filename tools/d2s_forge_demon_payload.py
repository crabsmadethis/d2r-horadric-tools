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
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from d2r_chargen.data.monumod_affixes import AFFIXES
from d2r_chargen.follower_block import (
    DEMON_PAYLOAD_LEN,
    DEMON_UNKNOWN_SLICE_RANGES,
    decode_follower_block,
    mutate_demon_payload,
)
from d2r_chargen.save import calc_checksum

_OFF_MONSTER_HCIDX = 4
_OFF_MONSTER_SEED = 6
_OFF_BIND_DEMON_LEVEL = 52
_OFF_AFFIX_INDICES = 80
_AFFIX_LEN = 7
_OFF_VOLATILE_RUNTIME = 89

_SLICE_RANGES = {
    name: (start, end)
    for name, start, end in DEMON_UNKNOWN_SLICE_RANGES
}

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
    "lightning": 17,
    "cold enchanted": 18,
    "cold": 18,
    "stone skin": 28,
    "stone": 28,
    "teleportation": 26,
    "teleport": 26,
    "multiple shots": 29,
    "multishot": 29,
    "resist": 8,
    "fanaticism": 37,
    "fanat": 37,
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
    """Parse up to seven comma-separated MonUMod affix bytes."""
    values = [parse_affix_token(part) for part in spec.split(",")]
    if len(values) > _AFFIX_LEN:
        raise ValueError(f"expected at most {_AFFIX_LEN} affixes, got {len(values)}")
    values.extend([0] * (_AFFIX_LEN - len(values)))
    return bytes(values)


@dataclass(frozen=True)
class SliceMutation:
    """One named unknown-slice mutation for a demon payload."""

    kind: str
    name: str
    value: bytes | None = None
    source: Path | None = None


@dataclass(frozen=True)
class OffsetCopyMutation:
    """Copy exact byte offsets from another demon payload."""

    offsets: tuple[int, ...]
    source: Path


def known_slice_names() -> tuple[str, ...]:
    return tuple(_SLICE_RANGES)


def _slice_range(name: str) -> tuple[int, int]:
    try:
        return _SLICE_RANGES[name]
    except KeyError:
        names = ", ".join(known_slice_names())
        raise ValueError(f"unknown slice {name!r}; known slices: {names}") from None


def _parse_slice_spec(spec: str, *, option: str) -> tuple[str, str]:
    if ":" not in spec:
        raise ValueError(f"{option} expects NAME:VALUE, got {spec!r}")
    name, value = spec.split(":", 1)
    name = name.strip()
    if not name:
        raise ValueError(f"{option} has empty slice name")
    _slice_range(name)
    return name, value.strip()


def _parse_hex_bytes(raw: str) -> bytes:
    if raw.startswith("0x"):
        raw = raw[2:]
    try:
        return bytes.fromhex(raw)
    except ValueError as exc:
        raise ValueError(f"invalid hex bytes {raw!r}") from exc


def parse_offset_token(token: str) -> int:
    """Parse one payload byte offset token such as '+024', '24', or '0x18'."""

    raw = token.strip()
    if raw.startswith("+"):
        raw = raw[1:]
    if not raw:
        raise ValueError("empty offset token")
    try:
        offset = int(raw, 16) if raw.lower().startswith("0x") else int(raw, 10)
    except ValueError as exc:
        raise ValueError(f"invalid offset token: {token!r}") from exc
    if offset < 0 or offset >= DEMON_PAYLOAD_LEN:
        raise ValueError(
            f"offset out of payload range: {offset}; expected 0..{DEMON_PAYLOAD_LEN - 1}"
        )
    return offset


def parse_offset_list(spec: str) -> tuple[int, ...]:
    """Parse a comma-separated list of exact payload byte offsets."""

    offsets = tuple(parse_offset_token(part) for part in spec.split(","))
    if not offsets:
        raise ValueError("empty offset list")
    if len(set(offsets)) != len(offsets):
        raise ValueError("offset list contains duplicates")
    return offsets


def build_slice_mutations(
    *,
    zero_slices: list[str] | None = None,
    set_slice_hex_specs: list[str] | None = None,
    copy_slice_from_specs: list[str] | None = None,
) -> list[SliceMutation]:
    """Parse and validate CLI slice-mutation specs."""

    mutations: list[SliceMutation] = []
    for raw_name in zero_slices or []:
        name = raw_name.strip()
        _slice_range(name)
        mutations.append(SliceMutation("zero", name))

    for spec in set_slice_hex_specs or []:
        name, raw_hex = _parse_slice_spec(spec, option="--set-slice-hex")
        value = _parse_hex_bytes(raw_hex)
        start, end = _slice_range(name)
        if len(value) != end - start:
            raise ValueError(
                f"slice {name!r} requires {end - start} bytes, got {len(value)}"
            )
        mutations.append(SliceMutation("set", name, value=value))

    for spec in copy_slice_from_specs or []:
        name, raw_path = _parse_slice_spec(spec, option="--copy-slice-from")
        if not raw_path:
            raise ValueError("--copy-slice-from has empty source path")
        mutations.append(SliceMutation("copy", name, source=Path(raw_path)))

    return mutations


def build_offset_copy_mutations(
    copy_offsets_from_specs: list[str] | None = None,
) -> list[OffsetCopyMutation]:
    """Parse exact-offset donor copy specs."""

    mutations: list[OffsetCopyMutation] = []
    for spec in copy_offsets_from_specs or []:
        if ":" not in spec:
            raise ValueError(f"--copy-offsets-from expects OFFSETS:PATH, got {spec!r}")
        raw_offsets, raw_path = spec.split(":", 1)
        offsets = parse_offset_list(raw_offsets)
        if not raw_path.strip():
            raise ValueError("--copy-offsets-from has empty source path")
        mutations.append(OffsetCopyMutation(offsets, Path(raw_path.strip())))
    return mutations


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
    slice_mutations: list[SliceMutation] | None = None,
    offset_copy_mutations: list[OffsetCopyMutation] | None = None,
) -> bytes:
    """Return a mutated copy of a 116-byte demon payload."""
    mutated = mutate_demon_payload(
        payload,
        monster_hcidx=monster_hcidx,
        monster_seed=monster_seed,
        bind_level=bind_level,
        affix_indices=affixes,
        zero_volatile=zero_volatile,
    )
    if slice_mutations:
        mutated = apply_slice_mutations(mutated, slice_mutations)
    if offset_copy_mutations:
        mutated = apply_offset_copy_mutations(mutated, offset_copy_mutations)
    return mutated


def apply_slice_mutations(payload: bytes, mutations: list[SliceMutation]) -> bytes:
    """Return a copy of `payload` with named unknown slices changed."""

    if len(payload) != DEMON_PAYLOAD_LEN:
        raise ValueError(
            f"payload must be {DEMON_PAYLOAD_LEN} bytes, got {len(payload)}"
        )

    out = bytearray(payload)
    for mutation in mutations:
        start, end = _slice_range(mutation.name)
        length = end - start
        if mutation.kind == "zero":
            value = b"\0" * length
        elif mutation.kind == "set":
            value = mutation.value or b""
        elif mutation.kind == "copy":
            if mutation.source is None:
                raise ValueError(f"copy mutation for {mutation.name!r} has no source")
            source_payload = load_payload(mutation.source)
            value = source_payload[start:end]
        else:
            raise ValueError(f"unknown slice mutation kind: {mutation.kind!r}")

        if len(value) != length:
            raise ValueError(
                f"slice {mutation.name!r} requires {length} bytes, got {len(value)}"
            )
        out[start:end] = value
    return bytes(out)


def apply_offset_copy_mutations(
    payload: bytes,
    mutations: list[OffsetCopyMutation],
) -> bytes:
    """Return a copy of `payload` with exact byte offsets copied from donors."""

    if len(payload) != DEMON_PAYLOAD_LEN:
        raise ValueError(
            f"payload must be {DEMON_PAYLOAD_LEN} bytes, got {len(payload)}"
        )

    out = bytearray(payload)
    for mutation in mutations:
        source_payload = load_payload(mutation.source)
        for offset in mutation.offsets:
            out[offset] = source_payload[offset]
    return bytes(out)


def validate_slice_mutation_plan(
    *,
    slice_mutations: list[SliceMutation],
    offset_copy_mutations: list[OffsetCopyMutation] | None = None,
    force_multiple_slices: bool = False,
    force_combined_mutations: bool = False,
    monster_hcidx: int | None = None,
    monster_seed: int | None = None,
    bind_level: int | None = None,
    affixes: bytes | None = None,
    zero_volatile: bool = False,
) -> None:
    """Enforce one-slice probe guardrails before writing a staged save."""

    offset_copy_mutations = offset_copy_mutations or []
    if not slice_mutations and not offset_copy_mutations:
        return

    if len(slice_mutations) > 1 and not force_multiple_slices:
        raise ValueError(
            "slice probes must mutate exactly one slice; pass "
            "--force-multiple-slices to override"
        )

    combined = any(
        value is not None
        for value in (monster_hcidx, monster_seed, bind_level, affixes)
    ) or zero_volatile
    if combined and not force_combined_mutations:
        raise ValueError(
            "payload probes should preserve high-confidence fields; pass "
            "--force-combined-mutations to override"
        )


def _update_size_and_checksum(data: bytearray) -> None:
    struct.pack_into("<I", data, 0x08, len(data))
    data[0x0C:0x10] = b"\x00\x00\x00\x00"
    struct.pack_into("<I", data, 0x0C, calc_checksum(data))


def _write_character_name(data: bytearray, character_name: str) -> None:
    if not character_name.isascii() or not character_name.isalpha():
        raise ValueError("character name must be ASCII letters only")
    encoded = character_name.encode("ascii")
    if not 1 <= len(encoded) <= 15:
        raise ValueError("character name must be 1..15 bytes")
    data[0x12B:0x13B] = encoded + b"\0" * (16 - len(encoded))


def write_payload_to_save(
    source: Path,
    output: Path,
    payload: bytes,
    *,
    character_name: str | None = None,
) -> None:
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
    if character_name is not None:
        _write_character_name(new_data, character_name)
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
        "--character-name",
        help="Set the internal character name to ASCII letters only, 1..15 bytes.",
    )
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
        help="Set up to seven comma-separated MonUMod ids/names at +80..+86.",
    )
    parser.add_argument(
        "--zero-volatile",
        action="store_true",
        help="Set volatile payload bytes +89..+91 to 00 00 00.",
    )
    parser.add_argument(
        "--zero-slice",
        action="append",
        default=[],
        metavar="NAME",
        help="Set one named DEMON_UNKNOWN_SLICE_RANGES slice to zero bytes.",
    )
    parser.add_argument(
        "--set-slice-hex",
        action="append",
        default=[],
        metavar="NAME:HEX",
        help="Set one named slice to exact hex bytes of the same length.",
    )
    parser.add_argument(
        "--copy-slice-from",
        action="append",
        default=[],
        metavar="NAME:PATH",
        help="Copy one named slice from another raw payload or one-follower .d2s.",
    )
    parser.add_argument(
        "--copy-offsets-from",
        action="append",
        default=[],
        metavar="OFFSETS:PATH",
        help=(
            "Copy exact payload byte offsets from another raw payload or one-follower "
            ".d2s, for low-level model-companion probes."
        ),
    )
    parser.add_argument(
        "--force-multiple-slices",
        action="store_true",
        help="Allow more than one named slice mutation in one staged output.",
    )
    parser.add_argument(
        "--force-combined-mutations",
        action="store_true",
        help="Allow slice mutations to be combined with high-confidence field edits.",
    )
    args = parser.parse_args()

    payload_source = args.payload_from or args.source
    payload = load_payload(payload_source)
    try:
        slice_mutations = build_slice_mutations(
            zero_slices=args.zero_slice,
            set_slice_hex_specs=args.set_slice_hex,
            copy_slice_from_specs=args.copy_slice_from,
        )
        offset_copy_mutations = build_offset_copy_mutations(args.copy_offsets_from)
        validate_slice_mutation_plan(
            slice_mutations=slice_mutations,
            offset_copy_mutations=offset_copy_mutations,
            force_multiple_slices=args.force_multiple_slices,
            force_combined_mutations=args.force_combined_mutations,
            monster_hcidx=args.monster_hcidx,
            monster_seed=args.monster_seed,
            bind_level=args.bind_level,
            affixes=args.affixes,
            zero_volatile=args.zero_volatile,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from None

    mutated = mutate_payload(
        payload,
        monster_hcidx=args.monster_hcidx,
        monster_seed=args.monster_seed,
        bind_level=args.bind_level,
        affixes=args.affixes,
        zero_volatile=args.zero_volatile,
        slice_mutations=slice_mutations,
        offset_copy_mutations=offset_copy_mutations,
    )
    try:
        write_payload_to_save(
            args.source,
            args.output,
            mutated,
            character_name=args.character_name,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    print(f"wrote {args.output} follower_count=1 payload_bytes={len(mutated)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
