#!/usr/bin/env python3
"""Read-only aggregate scanner for D2R `.d2s` save-file corpora.

This tool is intentionally privacy-preserving: it reports aggregate counters
only by default. Use --examples if you need a tiny list of relative filenames
for follow-up, but do not paste full local paths into public issues.
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from d2r_chargen.iron_golem import (
    decode_iron_golem_block,
    decode_iron_golem_item_header,
)


MAGIC = b"\x55\xaa\x55\xaa"
DEMON_PAYLOAD_LEN = 116


def calc_checksum(data: bytes) -> int:
    """Calculate the D2S rotate-left checksum with bytes 0x0c..0x0f zeroed."""
    checksum = 0
    for i, byte in enumerate(data):
        if 0x0C <= i <= 0x0F:
            byte = 0
        checksum = (((checksum << 1) | (checksum >> 31)) + byte) & 0xFFFFFFFF
    return checksum


def _u8(data: bytes, offset: int) -> int | None:
    if len(data) < offset + 1:
        return None
    return data[offset]


def _u16(data: bytes, offset: int) -> int | None:
    if len(data) < offset + 2:
        return None
    return struct.unpack_from("<H", data, offset)[0]


def _u32(data: bytes, offset: int) -> int | None:
    if len(data) < offset + 4:
        return None
    return struct.unpack_from("<I", data, offset)[0]


def _counter_key(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    return str(value)


class CorpusSummary:
    def __init__(self, *, examples_limit: int = 0) -> None:
        self.examples_limit = examples_limit
        self.total_files_seen = 0
        self.valid_d2s = 0
        self.not_d2s = 0
        self.read_errors = 0
        self.counters: dict[str, Counter[Any]] = defaultdict(Counter)
        self.invalid_followers: list[str] = []
        self.bad_headers: list[str] = []
        self.marker_failures: list[str] = []

    def add_counter(self, name: str, value: Any) -> None:
        self.counters[name][value] += 1

    def add_example(self, bucket: list[str], rel_path: str) -> None:
        if self.examples_limit and len(bucket) < self.examples_limit:
            bucket.append(rel_path)

    def as_dict(self) -> dict[str, Any]:
        return {
            "total_files_seen": self.total_files_seen,
            "valid_d2s": self.valid_d2s,
            "not_d2s": self.not_d2s,
            "read_errors": self.read_errors,
            "counters": {
                name: {_counter_key(k): v for k, v in counter.most_common()}
                for name, counter in sorted(self.counters.items())
            },
            "examples": {
                "invalid_followers": self.invalid_followers,
                "bad_headers": self.bad_headers,
                "marker_failures": self.marker_failures,
            },
        }


def iter_d2s_candidates(roots: list[Path]) -> list[tuple[Path, Path]]:
    """Return `(root, path)` pairs for unique `.d2s` candidates."""
    seen: set[Path] = set()
    pairs: list[tuple[Path, Path]] = []
    for root in roots:
        root = root.expanduser()
        if root.is_file():
            candidates = [root]
            base = root.parent
        else:
            candidates = list(root.rglob("*.d2s")) if root.exists() else []
            base = root
        for path in candidates:
            try:
                resolved = path.resolve()
            except OSError:
                resolved = path.absolute()
            if resolved in seen:
                continue
            seen.add(resolved)
            pairs.append((base, path))
    return pairs


def summarize_file(summary: CorpusSummary, root: Path, path: Path) -> None:
    summary.total_files_seen += 1
    try:
        data = path.read_bytes()
    except OSError:
        summary.read_errors += 1
        return

    rel_path = path.name
    try:
        rel_path = str(path.relative_to(root))
    except ValueError:
        pass

    if len(data) < 16 or data[:4] != MAGIC:
        summary.not_d2s += 1
        return

    summary.valid_d2s += 1

    version = _u32(data, 0x04)
    stored_size = _u32(data, 0x08)
    stored_checksum = _u32(data, 0x0C)
    size_ok = stored_size == len(data)
    checksum_ok = stored_checksum == calc_checksum(data)
    summary.add_counter("version", version)
    summary.add_counter("size_ok", size_ok)
    summary.add_counter("checksum_ok", checksum_ok)
    if not size_ok or not checksum_ok:
        summary.add_example(summary.bad_headers, rel_path)

    for name, offset, reader in (
        ("status", 0x14, _u8),
        ("progression", 0x15, _u8),
        ("class_id", 0x18, _u8),
        ("header_level", 0x1B, _u8),
        ("difficulty_current", 0x98, _u8),
        ("merc_status_u16_0xA7", 0xA7, _u16),
        ("hireling_id", 0xA9, _u16),
        ("merc_xp", 0xAB, _u32),
    ):
        value = reader(data, offset)
        if value is not None:
            summary.add_counter(name, value)

    gf = data.find(b"gf", 0x250)
    if_marker = data.find(b"if", gf + 2) if gf >= 0 else -1
    # Use the first JM after the skills marker as the player item list.
    # Some older/quarantined saves do not keep the exact 32-byte distance
    # assumed by the v105 writer, but the relative section order still holds.
    char_jm = data.find(b"JM", if_marker + 2) if if_marker >= 0 else -1
    lf = data.rfind(b"lf")
    kf = data.rfind(b"kf", 0, lf) if lf >= 0 else -1
    merc_jm = data.rfind(b"JM", 0, kf) if kf >= 0 else -1
    jf = data.rfind(b"jf", 0, merc_jm) if merc_jm >= 0 else -1
    pre_item_markers_ok = gf >= 0 and if_marker > gf and char_jm > if_marker
    tail_markers_ok = merc_jm >= 0 and kf > merc_jm and lf > kf
    summary.add_counter("pre_item_markers_ok", pre_item_markers_ok)
    summary.add_counter("tail_markers_ok", tail_markers_ok)
    summary.add_counter("has_jf_before_merc_jm", jf >= 0)
    if not pre_item_markers_ok or not tail_markers_ok:
        summary.add_example(summary.marker_failures, rel_path)

    if gf >= 0:
        summary.add_counter("gf_offset_bucket_0x100", gf // 0x100 * 0x100)
    if if_marker >= 0 and gf >= 0:
        summary.add_counter("stats_block_bytes", if_marker - (gf + 2))
    if kf >= 0 and lf >= 0:
        summary.add_counter("kf_to_lf_gap", lf - kf)
        golem = decode_iron_golem_block(data)
        if golem.has_markers:
            summary.add_counter("has_golem_byte", golem.has_golem_byte)
            summary.add_counter("golem_bridge_ok", golem.bridge_ok)
            summary.add_counter("golem_item_payload_bytes", golem.payload_len)
            if golem.has_golem:
                header = decode_iron_golem_item_header(golem.item_payload)
                summary.add_counter("golem_item_header_ok", header is not None)
                if header is not None:
                    summary.add_counter("golem_item_type", header.type_code)
                    summary.add_counter("golem_item_quality", header.quality)
                    summary.add_counter("golem_item_storage", header.storage)
                    summary.add_counter("golem_item_location", header.location)
                    summary.add_counter("golem_item_bodyloc", header.bodyloc)
    if merc_jm >= 0 and merc_jm + 4 <= len(data):
        summary.add_counter("merc_item_count", struct.unpack_from("<H", data, merc_jm + 2)[0])
    if lf >= 0 and lf + 4 <= len(data):
        follower_count = struct.unpack_from("<H", data, lf + 2)[0]
        trailing_payload_bytes = len(data) - (lf + 4)
        expected_payload_bytes = follower_count * DEMON_PAYLOAD_LEN
        follower_payload_ok = trailing_payload_bytes == expected_payload_bytes
        summary.add_counter("follower_count", follower_count)
        summary.add_counter("trailing_payload_bytes", trailing_payload_bytes)
        summary.add_counter("follower_payload_ok", follower_payload_ok)
        if not follower_payload_ok:
            summary.add_example(summary.invalid_followers, rel_path)


def print_text(summary: CorpusSummary) -> None:
    data = summary.as_dict()
    print(f"files seen: {data['total_files_seen']}")
    print(f"valid .d2s: {data['valid_d2s']}")
    print(f"not .d2s: {data['not_d2s']}")
    print(f"read errors: {data['read_errors']}")
    for name, counter in data["counters"].items():
        print(f"\n{name}:")
        for value, count in counter.items():
            print(f"  {value}: {count}")
    examples = data["examples"]
    for name, values in examples.items():
        if values:
            print(f"\n{name} examples:")
            for value in values:
                print(f"  {value}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "roots",
        nargs="+",
        type=Path,
        help="Files or directories to scan recursively for .d2s saves.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text.")
    parser.add_argument(
        "--examples",
        type=int,
        default=0,
        help="Include up to N relative filenames for failed buckets.",
    )
    parser.add_argument(
        "--fail-on-invalid-follower",
        action="store_true",
        help="Exit non-zero if any save has follower_count/payload mismatch.",
    )
    args = parser.parse_args()

    summary = CorpusSummary(examples_limit=args.examples)
    for root, path in iter_d2s_candidates(args.roots):
        summarize_file(summary, root, path)

    if args.json:
        print(json.dumps(summary.as_dict(), indent=2, sort_keys=True))
    else:
        print_text(summary)

    if args.fail_on_invalid_follower:
        invalid_count = summary.counters["follower_payload_ok"].get(False, 0)
        if invalid_count:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
