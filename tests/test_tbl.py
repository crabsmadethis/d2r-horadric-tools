"""
Tests for d2r_mod.assets.tbl — parser, builder, and patcher.
"""

import os
import struct
import tempfile
import unittest

from d2r_mod.assets.tbl import (
    parse_tbl, build_tbl, patch_tbl, _next_prime,
    _HEADER_SIZE, _HASH_ENTRY_SIZE, _HAS_INDEX_TABLE, _hash_table_start, _elf_hash,
)

HAS_VANILLA = os.path.isdir(os.path.join(os.path.dirname(__file__), "..", "vanilla"))
VANILLA_DIR = os.path.join(os.path.dirname(__file__), "..", "vanilla", "data", "local", "lng", "eng")
VANILLA_PATCH_TBL = os.path.join(VANILLA_DIR, "patchstring.tbl")
VANILLA_STRING_TBL = os.path.join(VANILLA_DIR, "string.tbl")
VANILLA_EXPANSION_TBL = os.path.join(VANILLA_DIR, "expansionstring.tbl")


@unittest.skipUnless(HAS_VANILLA, "vanilla data required")
class TestParseTbl(unittest.TestCase):
    def test_parse_returns_dict(self):
        with open(VANILLA_PATCH_TBL, "rb") as f:
            data = f.read()
        result = parse_tbl(data)
        self.assertIsInstance(result, dict)
        self.assertGreater(len(result), 100)

    def test_parse_count_matches_header(self):
        # patchstring.tbl contains duplicate keys (e.g. 'x' is used 114 times as
        # a placeholder).  parse_tbl returns a plain dict so duplicates collapse to
        # the last-seen value.  The dict length therefore equals the number of
        # *unique* keys, which is <= NumElements.
        with open(VANILLA_PATCH_TBL, "rb") as f:
            data = f.read()
        num_elements = struct.unpack_from("<H", data, 2)[0]
        result = parse_tbl(data)
        self.assertLessEqual(len(result), num_elements)
        self.assertGreater(len(result), 0)

    def test_all_entries_are_strings(self):
        with open(VANILLA_PATCH_TBL, "rb") as f:
            data = f.read()
        result = parse_tbl(data)
        for key, value in result.items():
            self.assertIsInstance(key, str, f"Key {key!r} is not a str")
            self.assertIsInstance(value, str, f"Value for {key!r} is not a str")

    def test_all_three_vanilla_files_parse(self):
        # Each file must parse without error and return a non-empty dict.
        # Duplicate placeholder keys ('x', 'X') exist in all three files, so
        # len(result) <= num_elements; we verify len >= num_elements - 300 as a
        # sanity bound (actual loss is 117/292/30 for patch/string/expansion).
        for path in (VANILLA_STRING_TBL, VANILLA_EXPANSION_TBL, VANILLA_PATCH_TBL):
            with open(path, "rb") as f:
                data = f.read()
            num_elements = struct.unpack_from("<H", data, 2)[0]
            result = parse_tbl(data)
            self.assertIsInstance(result, dict, f"{os.path.basename(path)}: not a dict")
            self.assertGreater(
                len(result),
                num_elements - 300,
                f"{os.path.basename(path)}: got {len(result)}, expected near {num_elements}",
            )
            self.assertLessEqual(
                len(result),
                num_elements,
                f"{os.path.basename(path)}: got {len(result)} > num_elements {num_elements}",
            )


@unittest.skipUnless(HAS_VANILLA, "vanilla data required")
class TestParseTblKnownValues(unittest.TestCase):
    def test_known_key_value_string_tbl(self):
        """string.tbl key '8ls' must map to 'Quarterstaff'."""
        with open(VANILLA_STRING_TBL, "rb") as f:
            data = f.read()
        result = parse_tbl(data)
        self.assertIn("8ls", result)
        self.assertEqual(result["8ls"], "Quarterstaff")

    def test_known_key_value_gothic_bow(self):
        """string.tbl key '8lw' must map to 'Gothic Bow'."""
        with open(VANILLA_STRING_TBL, "rb") as f:
            data = f.read()
        result = parse_tbl(data)
        self.assertIn("8lw", result)
        self.assertEqual(result["8lw"], "Gothic Bow")


class TestParseTblConstants(unittest.TestCase):
    def test_header_size_constant(self):
        self.assertEqual(_HEADER_SIZE, 21)

    def test_hash_entry_size_constant(self):
        self.assertEqual(_HASH_ENTRY_SIZE, 17)

    def test_has_index_table_constant(self):
        self.assertTrue(_HAS_INDEX_TABLE)

    def test_hash_table_start_helper(self):
        # hash_table_start = HEADER_SIZE + num_elements * 2
        self.assertEqual(_hash_table_start(0), 21)
        self.assertEqual(_hash_table_start(10), 21 + 20)
        self.assertEqual(_hash_table_start(1216), 21 + 1216 * 2)


class TestElfHashUnit(unittest.TestCase):
    """Unit tests for _elf_hash() with known values."""

    def test_empty_string(self):
        self.assertEqual(_elf_hash(""), 0)

    def test_single_char(self):
        # 'A' = 65; h = (0 << 4) + 65 = 65; high=0; result = 65
        self.assertEqual(_elf_hash("A"), 65)

    def test_case_sensitive(self):
        # ELF hash is case-sensitive; 'a' != 'A'
        self.assertNotEqual(_elf_hash("a"), _elf_hash("A"))

    def test_known_key_quarterstaff(self):
        # string.tbl: key '8ls', HashTableSize=5393, stored hash_value=0
        # _elf_hash('8ls') == 16179; 16179 % 5393 == 0
        self.assertEqual(_elf_hash("8ls"), 16179)
        self.assertEqual(_elf_hash("8ls") % 5393, 0)

    def test_known_key_gothic_bow(self):
        # string.tbl: key '8lw', HashTableSize=5393, stored hash_value=4
        # _elf_hash('8lw') == 16183; 16183 % 5393 == 4
        self.assertEqual(_elf_hash("8lw"), 16183)
        self.assertEqual(_elf_hash("8lw") % 5393, 4)

    def test_returns_uint32(self):
        # Result must fit in a uint32 (never negative, never > 0xFFFFFFFF)
        for key in ["", "A", "test", "x" * 200, "Quarterstaff", "Diablo"]:
            h = _elf_hash(key)
            self.assertGreaterEqual(h, 0)
            self.assertLessEqual(h, 0xFFFFFFFF)


@unittest.skipUnless(HAS_VANILLA, "vanilla data required")
class TestElfHash(unittest.TestCase):
    def test_hash_matches_all_vanilla_entries(self):
        """ELF hash must match 100% of stored hash values across all .tbl files.

        Stored hash_value == _elf_hash(key) % hash_table_size (the bucket).
        """
        for name in ["string.tbl", "expansionstring.tbl", "patchstring.tbl"]:
            path = os.path.join(VANILLA_DIR, name)
            with open(path, "rb") as f:
                data = f.read()

            num_elements = struct.unpack_from("<H", data, 2)[0]
            hash_table_size = struct.unpack_from("<I", data, 4)[0]
            ht_start = _hash_table_start(num_elements)

            total = 0
            mismatches = []
            for i in range(hash_table_size):
                offset = ht_start + i * _HASH_ENTRY_SIZE
                if not data[offset]:
                    continue
                total += 1

                stored_hash = struct.unpack_from("<I", data, offset + 3)[0]
                key_off = struct.unpack_from("<I", data, offset + 7)[0]
                key_end = data.index(0, key_off)
                key = data[key_off:key_end].decode("latin-1")

                computed = _elf_hash(key)
                bucket = computed % hash_table_size
                if bucket != stored_hash:
                    mismatches.append((key, stored_hash, computed, bucket))

            self.assertGreater(total, 0, f"{name}: no entries found")
            self.assertEqual(
                len(mismatches), 0,
                f"{name}: {len(mismatches)}/{total} hash mismatches. "
                f"First 5: {mismatches[:5]}"
            )


# ── _next_prime ──────────────────────────────────────────────────────────────

class TestNextPrime(unittest.TestCase):
    def test_small_primes(self):
        self.assertEqual(_next_prime(2), 2)
        self.assertEqual(_next_prime(3), 3)
        self.assertEqual(_next_prime(4), 5)
        self.assertEqual(_next_prime(5), 5)

    def test_one_returns_two(self):
        # Smallest prime is 2
        self.assertEqual(_next_prime(1), 2)

    def test_composite_returns_next_prime(self):
        self.assertEqual(_next_prime(10), 11)
        self.assertEqual(_next_prime(14), 17)
        self.assertEqual(_next_prime(20), 23)

    def test_large_prime(self):
        self.assertEqual(_next_prime(100), 101)
        self.assertEqual(_next_prime(1000), 1009)


# ── build_tbl ────────────────────────────────────────────────────────────────

class TestBuildTbl(unittest.TestCase):
    def test_build_from_scratch(self):
        entries = {"Hello": "World", "Foo": "Bar"}
        data = build_tbl(entries)
        result = parse_tbl(data)
        self.assertEqual(result, entries)

    def test_single_entry(self):
        entries = {"OnlyKey": "OnlyValue"}
        data = build_tbl(entries)
        result = parse_tbl(data)
        self.assertEqual(result, entries)

    def test_empty_value(self):
        entries = {"Key": ""}
        data = build_tbl(entries)
        result = parse_tbl(data)
        self.assertEqual(result, entries)

    def test_many_entries(self):
        entries = {f"key_{i:03d}": f"value_{i:03d}" for i in range(100)}
        data = build_tbl(entries)
        result = parse_tbl(data)
        self.assertEqual(result, entries)

    def test_non_ascii_latin1(self):
        entries = {"H\xe9ro\xefque": "\xc9p\xe9e"}
        data = build_tbl(entries)
        result = parse_tbl(data)
        self.assertEqual(result, entries)

    def test_empty_dict(self):
        entries = {}
        data = build_tbl(entries)
        result = parse_tbl(data)
        self.assertEqual(result, entries)

    def test_structural_invariant(self):
        entries = {"Alpha": "One", "Beta": "Two", "Gamma": "Three"}
        data = build_tbl(entries)

        # Parse header
        num_elements = struct.unpack_from("<H", data, 0x02)[0]
        hash_table_size = struct.unpack_from("<I", data, 0x04)[0]
        str_data_start = struct.unpack_from("<I", data, 0x09)[0]
        file_size = struct.unpack_from("<I", data, 0x11)[0]

        # Verify NumElements
        self.assertEqual(num_elements, len(entries))

        # ht_start + ht_size * 17 == str_data_start
        ht_start = _hash_table_start(num_elements)
        self.assertEqual(ht_start + hash_table_size * _HASH_ENTRY_SIZE, str_data_start)

        # file_size == len(data)
        self.assertEqual(file_size, len(data))

    def test_version_is_one(self):
        data = build_tbl({"k": "v"})
        version = struct.unpack_from("<B", data, 0x08)[0]
        self.assertEqual(version, 1)

    def test_loop_count_is_max_probe_plus_one(self):
        entries = {"A": "1", "B": "2", "C": "3"}
        data = build_tbl(entries)
        loop_count = struct.unpack_from("<I", data, 0x0D)[0]
        self.assertGreaterEqual(loop_count, 1)
        hash_table_size = struct.unpack_from("<I", data, 0x04)[0]
        self.assertLessEqual(loop_count, hash_table_size)


# ── build_tbl vanilla round-trip ─────────────────────────────────────────────

@unittest.skipUnless(HAS_VANILLA, "vanilla data required")
class TestBuildTblVanilla(unittest.TestCase):
    def test_vanilla_round_trip(self):
        """Parse vanilla patchstring.tbl -> build -> parse -> compare entries."""
        with open(VANILLA_PATCH_TBL, "rb") as f:
            data = f.read()
        original = parse_tbl(data)
        rebuilt_data = build_tbl(original)
        rebuilt = parse_tbl(rebuilt_data)
        self.assertEqual(rebuilt, original)

    def test_rebuilt_structural_invariant(self):
        """Rebuild vanilla .tbl, verify header fields are consistent."""
        with open(VANILLA_PATCH_TBL, "rb") as f:
            data = f.read()
        original = parse_tbl(data)
        rebuilt_data = build_tbl(original)

        num_elements = struct.unpack_from("<H", rebuilt_data, 0x02)[0]
        hash_table_size = struct.unpack_from("<I", rebuilt_data, 0x04)[0]
        str_data_start = struct.unpack_from("<I", rebuilt_data, 0x09)[0]
        file_size = struct.unpack_from("<I", rebuilt_data, 0x11)[0]

        ht_start = _hash_table_start(num_elements)
        self.assertEqual(ht_start + hash_table_size * _HASH_ENTRY_SIZE, str_data_start)
        self.assertEqual(file_size, len(rebuilt_data))
        self.assertEqual(num_elements, len(original))


# ── patch_tbl ────────────────────────────────────────────────────────────────

@unittest.skipUnless(HAS_VANILLA, "vanilla data required")
class TestPatchTbl(unittest.TestCase):
    def test_patch_adds_new_key(self):
        with tempfile.NamedTemporaryFile(suffix=".tbl", delete=False) as tmp:
            out_path = tmp.name
        try:
            patch_tbl(VANILLA_PATCH_TBL, {"Manoomin": "Manoomin"}, out_path)
            with open(out_path, "rb") as f:
                data = f.read()
            result = parse_tbl(data)
            self.assertIn("Manoomin", result)
            self.assertEqual(result["Manoomin"], "Manoomin")
        finally:
            os.unlink(out_path)

    def test_patch_overrides_existing_key(self):
        # Find the first key in vanilla
        with open(VANILLA_PATCH_TBL, "rb") as f:
            data = f.read()
        original = parse_tbl(data)
        first_key = next(iter(original))

        with tempfile.NamedTemporaryFile(suffix=".tbl", delete=False) as tmp:
            out_path = tmp.name
        try:
            patch_tbl(VANILLA_PATCH_TBL, {first_key: "OVERRIDDEN_VALUE"}, out_path)
            with open(out_path, "rb") as f:
                patched_data = f.read()
            result = parse_tbl(patched_data)
            self.assertEqual(result[first_key], "OVERRIDDEN_VALUE")
        finally:
            os.unlink(out_path)

    def test_patch_preserves_unmodified(self):
        with open(VANILLA_PATCH_TBL, "rb") as f:
            data = f.read()
        original = parse_tbl(data)
        original_count = len(original)

        with tempfile.NamedTemporaryFile(suffix=".tbl", delete=False) as tmp:
            out_path = tmp.name
        try:
            patch_tbl(VANILLA_PATCH_TBL, {"Manoomin": "WildRice"}, out_path)
            with open(out_path, "rb") as f:
                patched_data = f.read()
            result = parse_tbl(patched_data)
            # Should have original count + 1 new key
            self.assertEqual(len(result), original_count + 1)
            # Spot-check a few original keys survive
            checked = 0
            for key, value in original.items():
                if checked >= 10:
                    break
                self.assertIn(key, result)
                self.assertEqual(result[key], value)
                checked += 1
        finally:
            os.unlink(out_path)
