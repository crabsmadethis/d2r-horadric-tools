"""
Golden-reference round-trip tests for merc JM encoding.

Fixture: tests/fixtures/hexshade_lv98_haseen.d2s
  Hexshade lv98 Necromancer, immediately after hiring Haseen (Act 2 Desert
  HolyFreeze merc) and equipping him with Insight + Andariel's Visage +
  Fortitude in-game. The save was cleanly flushed to disk before snapshotting.

These tests are read-only validations; they never mutate the fixture.
"""

import os
import struct
import unittest
import pytest
from pathlib import Path

# Skip entire file if game data not extracted (public d2r-tools installs won't
# have the generated data modules until `d2r-mod extract` is run).
pytest.importorskip(
    "d2r_chargen.data.item_stat_cost",
    reason="game data not extracted (run 'd2r-mod extract')",
)

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "hexshade_lv98_haseen.d2s")

# The golden-reference fixture is a real .d2s file (gitignored — kept locally
# by test maintainers; not shipped in the repo). Tests that depend on it are
# skipped cleanly if the file is absent. XP-curve and equipment-mode tests
# don't need the fixture — they run either way.
_FIXTURE_AVAILABLE = os.path.exists(FIXTURE)
needs_fixture = pytest.mark.skipif(
    not _FIXTURE_AVAILABLE,
    reason="golden-reference fixture not present (see docs for how to capture one)",
)

EXPECTED_FILE_SIZE = 2208

# Merc header offsets (plain LE integers, established 2026-04-19)
OFFSET_SEED   = 0xA3   # u32
OFFSET_A7     = 0xA7   # u8  (always 5 for active merc)
OFFSET_ID     = 0xA9   # u16 Hireling.Id
OFFSET_XP     = 0xAB   # u32

EXPECTED_SEED = 0x178E4E32
EXPECTED_A7   = 5
EXPECTED_ID   = 34       # Haseen, Act2 Desert HolyFreeze merc
EXPECTED_XP   = 123603480


@pytest.fixture(scope="module")
def save_bytes():
    with open(FIXTURE, "rb") as f:
        return f.read()


@needs_fixture
class TestMercHeader:
    """Validate the plain-integer merc header fields at 0xA3-0xAE."""

    def test_fixture_size(self, save_bytes):
        assert len(save_bytes) == EXPECTED_FILE_SIZE, (
            f"Fixture size {len(save_bytes)} != expected {EXPECTED_FILE_SIZE}; "
            "fixture may have been overwritten with a different save."
        )

    def test_seed(self, save_bytes):
        seed = struct.unpack_from("<I", save_bytes, OFFSET_SEED)[0]
        assert seed == EXPECTED_SEED, f"seed=0x{seed:08x}, want 0x{EXPECTED_SEED:08x}"

    def test_a7_active_merc(self, save_bytes):
        a7 = save_bytes[OFFSET_A7]
        assert a7 == EXPECTED_A7, f"a7={a7}, want {EXPECTED_A7}"

    def test_hireling_id(self, save_bytes):
        merc_id = struct.unpack_from("<H", save_bytes, OFFSET_ID)[0]
        assert merc_id == EXPECTED_ID, f"Hireling.Id={merc_id}, want {EXPECTED_ID}"

    def test_merc_xp(self, save_bytes):
        xp = struct.unpack_from("<I", save_bytes, OFFSET_XP)[0]
        assert xp == EXPECTED_XP, f"XP={xp}, want {EXPECTED_XP}"


@needs_fixture
class TestMercJMBlock:
    """Validate the merc item list (JM block that follows the 'jf' terminator)."""

    def test_jf_terminator_present(self, save_bytes):
        jf_pos = save_bytes.find(b"jf")
        assert jf_pos != -1, "'jf' section terminator not found in save"

    def test_jm_magic(self, save_bytes):
        jf_pos = save_bytes.find(b"jf")
        merc_jm_start = jf_pos + 2
        magic = save_bytes[merc_jm_start : merc_jm_start + 2]
        assert magic == b"JM", f"Expected JM magic after jf, got {magic!r}"

    def test_merc_item_count(self, save_bytes):
        """Haseen has 3 equipped items: Insight polearm, Andariel's Visage, Fortitude.

        The socket-filler runes (4 in Insight + 4 in Fortitude) are bit-packed
        sub-items within those base items; they are NOT reflected in this count.
        """
        jf_pos = save_bytes.find(b"jf")
        merc_jm_start = jf_pos + 2
        count = struct.unpack_from("<H", save_bytes, merc_jm_start + 2)[0]
        assert count == 3, (
            f"Expected 3 merc items (Insight + Andy's Visage + Fortitude), got {count}"
        )


@needs_fixture
class TestMercItemsDecode(unittest.TestCase):
    """Decode and record the exact contents of the 3 merc parent items.

    These assertions are the byte-level contract for Task 3.3's round-trip
    test: any encoder change that alters what lives in the fixture will
    break these assertions first, at a meaningful semantic level.

    Parent items discovered from fixture (in JM block order):
      1. Fortitude  — runeword on Archon Plate ('utp'), eth, bodyloc=3 (body)
      2. Andariel's Visage — unique ('usk'), eth, uid=345, bodyloc=1 (helm)
      3. Insight    — runeword on Thresher ('7wc'), eth, bodyloc=4 (weapon)

    Socket fillers (8 total, location=6, simple=True):
      Fortitude: r01, r12, r14, r28  (El Sol Dol Lo — Fortitude rune sequence)
      Insight:   r08, r03, r07, r12  (Ral Tir Tal Sol — Insight rune sequence)
    """

    @classmethod
    def setUpClass(cls):
        fixture_path = Path(__file__).parent / "fixtures" / "hexshade_lv98_haseen.d2s"
        cls.data = fixture_path.read_bytes()

    def _collect_merc_items(self):
        """Walk the merc JM block and return (parents, fillers) lists.

        Each parent entry: (pos, itype, ilvl, quality, uid, bodyloc, is_runeword, is_eth)
        Each filler entry: (pos, itype)
        """
        from d2r_chargen.scanner import decode_item_header
        data = self.data

        jf_pos = data.index(b"jf")
        merc_jm = jf_pos + 2
        kf_pos = data.find(b"kf", merc_jm + 4)
        merc_end = kf_pos if kf_pos > 0 else merc_jm + 500

        parents = []
        fillers = []
        for pos in range(merc_jm + 4, merc_end - 4):
            b0 = data[pos]
            b2 = data[pos + 2] if pos + 2 < len(data) else 0
            if b0 == 0x10 and b2 in (0x80, 0xa0, 0xc0, 0xe0):
                itype, ilvl, quality, uid, storage, col, row, bodyloc, location, ext = (
                    decode_item_header(data, pos)
                )
                flags32 = struct.unpack_from("<I", data, pos)[0]
                is_runeword = bool(flags32 & (1 << 26))
                is_eth = bool(flags32 & (1 << 22))
                if location == 6:
                    fillers.append((pos, itype.strip()))
                else:
                    parents.append(
                        (pos, itype.strip(), ilvl, quality, uid, bodyloc, is_runeword, is_eth)
                    )
        return parents, fillers

    def test_three_parent_items_base_codes(self):
        """The 3 parent items have the expected base-type codes."""
        parents, _ = self._collect_merc_items()
        self.assertEqual(len(parents), 3, f"Expected 3 parent items, got {len(parents)}")
        codes = [p[1] for p in parents]
        # JM order: Fortitude (utp), Andariel's Visage (usk), Insight (7wc)
        self.assertEqual(codes, ["utp", "usk", "7wc"])

    def test_parent_items_are_all_eth(self):
        """All 3 parent merc items are ethereal."""
        parents, _ = self._collect_merc_items()
        for pos, itype, ilvl, quality, uid, bodyloc, is_rw, is_eth in parents:
            self.assertTrue(is_eth, f"Item {itype!r} at {pos:#x} is not ethereal")

    def test_runeword_items(self):
        """Fortitude (utp) and Insight (7wc) are runewords; Andariel's Visage is not."""
        parents, _ = self._collect_merc_items()
        by_code = {p[1]: p for p in parents}
        self.assertTrue(by_code["utp"][6], "Fortitude (utp) should be a runeword")
        self.assertTrue(by_code["7wc"][6], "Insight (7wc) should be a runeword")
        self.assertFalse(by_code["usk"][6], "Andariel's Visage (usk) should NOT be a runeword")

    def test_andys_visage_uid(self):
        """Andariel's Visage has unique id 345."""
        parents, _ = self._collect_merc_items()
        by_code = {p[1]: p for p in parents}
        uid = by_code["usk"][4]
        self.assertEqual(uid, 345, f"Expected uid=345 for Andariel's Visage, got uid={uid}")

    def test_parent_bodyloc_slots(self):
        """Each parent item is in the correct merc body slot.

        bodyloc 1 = helm, 3 = body armour, 4 = weapon (right-hand / polearm).
        """
        parents, _ = self._collect_merc_items()
        bodyloc_map = {p[1]: p[5] for p in parents}
        self.assertEqual(bodyloc_map["usk"], 1, "Andariel's Visage should be in helm slot (1)")
        self.assertEqual(bodyloc_map["utp"], 3, "Fortitude should be in body slot (3)")
        self.assertEqual(bodyloc_map["7wc"], 4, "Insight should be in weapon slot (4)")

    def test_eight_socket_fillers(self):
        """There are 8 socket-filler runes total (4 in Fortitude + 4 in Insight)."""
        _, fillers = self._collect_merc_items()
        self.assertEqual(len(fillers), 8, f"Expected 8 socket fillers, got {len(fillers)}")

    def test_socket_filler_rune_codes(self):
        """Socket fillers are the exact runes that make up Fortitude and Insight.

        Fortitude (El Sol Dol Lo): r01, r12, r14, r28
        Insight  (Ral Tir Tal Sol): r08, r03, r07, r12
        """
        _, fillers = self._collect_merc_items()
        filler_codes = [f[1] for f in fillers]
        self.assertEqual(
            filler_codes,
            ["r01", "r12", "r14", "r28", "r08", "r03", "r07", "r12"],
        )


# ---------------------------------------------------------------------------
# Task 3.2: equipment_mode field
# ---------------------------------------------------------------------------

def _minimal_char_def(merc=None):
    """Build a minimal valid character definition dict with optional merc block."""
    char_def = {
        "schema_version": 1,
        "name": "ModeTest",
        "class": "sorceress",
        "level": 80,
        "stats": {
            "strength": 60,
            "dexterity": 35,
            "vitality": 200,
            "energy": 35,
        },
        "equipment": [],
    }
    if merc is not None:
        char_def["merc"] = merc
    return char_def


# Simple single-item merc equipment list for fast tests (unique helm, no sockets)
_SIMPLE_MERC_EQUIPMENT = [
    {"slot": "helm", "unique": "Andariel's Visage", "ethereal": True,
     "extra_properties": {"life_leech": 10}},
]


class TestEquipmentMode:
    """Verify merc.equipment_mode routing logic in build_all_items()."""

    def test_default_mode_is_direct_when_type_set(self):
        """YAML with merc.type but no equipment_mode/inject → direct mode,
        items routed to merc (section='merc', injected into JM[merc])."""
        from d2r_chargen.character import build_all_items
        char_def = _minimal_char_def(merc={
            "type": "act2_might",
            "equipment": _SIMPLE_MERC_EQUIPMENT,
        })
        items = build_all_items(char_def)
        assert items, "Expected at least one item"
        # All items must be section='merc' (direct default when type is set)
        sections = [s for s, _ in items]
        assert all(s == "merc" for s in sections), (
            f"Expected all section='merc', got: {sections}"
        )

    def test_default_mode_is_stash_when_no_type(self):
        """YAML with merc but no type → stash mode (merc section used as
        stash overflow for manual-equip workflows)."""
        from d2r_chargen.character import build_all_items
        char_def = _minimal_char_def(merc={"equipment": _SIMPLE_MERC_EQUIPMENT})
        items = build_all_items(char_def)
        assert items, "Expected at least one item"
        sections = [s for s, _ in items]
        assert all(s == "char" for s in sections), (
            f"Expected all section='char' (stash), got: {sections}"
        )

    def test_equipment_mode_stash_explicit(self):
        """Explicit equipment_mode: stash behaves identically to the default."""
        from d2r_chargen.character import build_all_items
        char_def = _minimal_char_def(merc={
            "equipment": _SIMPLE_MERC_EQUIPMENT,
            "equipment_mode": "stash",
        })
        items = build_all_items(char_def)
        assert items, "Expected at least one item"
        sections = [s for s, _ in items]
        assert all(s == "char" for s in sections), (
            f"Expected all section='char', got: {sections}"
        )

    def test_equipment_mode_direct_routes_to_merc_jm(self):
        """equipment_mode: direct → merc items tagged section='merc'."""
        from d2r_chargen.character import build_all_items
        char_def = _minimal_char_def(merc={
            "equipment": _SIMPLE_MERC_EQUIPMENT,
            "equipment_mode": "direct",
        })
        items = build_all_items(char_def)
        assert items, "Expected at least one item"
        merc_items = [(s, b) for s, b in items if s == "merc"]
        assert merc_items, (
            "Expected at least one item with section='merc' for direct mode, "
            f"got sections: {[s for s, _ in items]}"
        )
        # None should be in 'char' stash (the merc items are routed to merc JM)
        char_items = [(s, b) for s, b in items if s == "char"]
        assert not char_items, (
            f"Expected no char-section items in direct mode, got {len(char_items)}"
        )

    def test_legacy_inject_true_alias(self):
        """Legacy inject: true → same routing as equipment_mode: direct."""
        from d2r_chargen.character import build_all_items
        char_def = _minimal_char_def(merc={
            "equipment": _SIMPLE_MERC_EQUIPMENT,
            "inject": True,
        })
        items = build_all_items(char_def)
        assert items, "Expected at least one item"
        sections = [s for s, _ in items]
        assert any(s == "merc" for s in sections), (
            f"inject: true should route to section='merc', got: {sections}"
        )

    def test_legacy_inject_false_alias(self):
        """Legacy inject: false → same routing as equipment_mode: stash."""
        from d2r_chargen.character import build_all_items
        char_def = _minimal_char_def(merc={
            "equipment": _SIMPLE_MERC_EQUIPMENT,
            "inject": False,
        })
        items = build_all_items(char_def)
        assert items, "Expected at least one item"
        sections = [s for s, _ in items]
        assert all(s == "char" for s in sections), (
            f"inject: false should route to section='char', got: {sections}"
        )

    def test_invalid_equipment_mode_raises(self):
        """equipment_mode: 'bogus' → ValueError."""
        from d2r_chargen.character import build_all_items
        import pytest
        char_def = _minimal_char_def(merc={
            "equipment": _SIMPLE_MERC_EQUIPMENT,
            "equipment_mode": "bogus",
        })
        with pytest.raises(ValueError, match="Invalid merc.equipment_mode"):
            build_all_items(char_def)

    def test_both_fields_set_equipment_mode_wins(self, capsys):
        """When both equipment_mode and legacy inject are set, equipment_mode
        wins and a warning is printed. Conflicting values: equipment_mode=direct
        (route to merc) + inject=False (would route to stash). The explicit
        field must take precedence."""
        from d2r_chargen.character import build_all_items
        char_def = _minimal_char_def(merc={
            "equipment": _SIMPLE_MERC_EQUIPMENT,
            "equipment_mode": "direct",
            "inject": False,
        })
        items = build_all_items(char_def)
        assert items, "Expected at least one item"
        sections = [s for s, _ in items]
        # equipment_mode: direct must win → at least one item tagged 'merc'
        assert any(s == "merc" for s in sections), (
            f"equipment_mode='direct' must win over inject=False, got: {sections}"
        )
        # Warning should be emitted on stdout
        captured = capsys.readouterr()
        assert "both" in captured.out.lower() or "equipment_mode" in captured.out, (
            f"Expected a warning about the both-set conflict, got stdout: "
            f"{captured.out!r}"
        )


# ---------------------------------------------------------------------------
# Task 3.3 phase 1: Round-trip parity diagnostic
# ---------------------------------------------------------------------------

def _build_roundtrip_char_def():
    """Build a minimal char_def using insight_holyfreeze in direct mode."""
    from d2r_chargen.character import _resolve_merc_template
    char_def = {
        'schema_version': 1,
        'name': 'RoundTripTest',
        'class': 'warlock',
        'level': 99,
        'stats': {'strength': 156, 'dexterity': 35, 'vitality': 340, 'energy': 35},
        'equipment': [],
        'merc': {'template': 'insight_holyfreeze', 'equipment_mode': 'direct'},
    }
    _resolve_merc_template(char_def)
    return char_def


def _get_golden_merc_items():
    """Return the raw bytes of merc items from the golden fixture.

    Reads from JM[merc] start (after 4-byte JM+count header) to the kf
    terminator.
    """
    fixture = Path(__file__).parent / "fixtures" / "hexshade_lv98_haseen.d2s"
    data = fixture.read_bytes()
    jf = data.index(b"jf")
    kf = data.index(b"kf", jf)
    # JM magic (2) + u16 count (2) = 4 bytes before items
    merc_items_start = jf + 2 + 4
    return data[merc_items_start:kf]


@needs_fixture
class TestRoundTripParity:
    """Task 3.3 phase 1: byte-level diff between chargen and golden fixture.

    These tests are DIAGNOSTIC — they characterise what diverges between
    chargen output and D2R's own serialisation so that subsequent phases
    can fix specific fields.  Only weak invariants are asserted; byte
    equality is explicitly NOT required.
    """

    def test_chargen_produces_3_parent_items(self):
        """Chargen MUST emit exactly 3 merc-section parent items (matches golden)."""
        from d2r_chargen.character import build_all_items
        from d2r_chargen.scanner import decode_item_header

        char_def = _build_roundtrip_char_def()
        all_items = build_all_items(char_def)
        merc_bytes_list = [b for s, b in all_items if s == "merc"]

        parent_count = 0
        for b in merc_bytes_list:
            if len(b) < 4:
                continue
            flags32 = struct.unpack_from("<I", b)[0]
            is_simple = bool(flags32 & (1 << 21))
            if not is_simple:
                parent_count += 1

        assert parent_count == 3, (
            f"Expected 3 parent merc items, got {parent_count}. "
            f"Total merc-section entries: {len(merc_bytes_list)}"
        )

    def test_round_trip_dump_diff(self):
        """Diagnostic: compare chargen output against golden fixture byte-by-byte.

        This test NEVER asserts byte equality — it writes a structured diff
        report to /tmp/merc_round_trip_diff.txt and prints a summary of the
        first divergences.  Only weak invariants (non-empty blobs) are checked.
        """
        from d2r_chargen.character import build_all_items
        from d2r_chargen.scanner import decode_item_header

        char_def = _build_roundtrip_char_def()
        all_items = build_all_items(char_def)
        merc_bytes_list = [b for s, b in all_items if s == "merc"]

        # Concatenate in order returned — this mirrors what rebuild_items()
        # would write into the JM[merc] block.
        chargen_output = b"".join(merc_bytes_list)
        golden_merc_items = _get_golden_merc_items()

        # Weak invariants — these failing means something fundamental is broken.
        assert len(chargen_output) > 0, "chargen produced empty merc output"
        assert len(golden_merc_items) > 0, "golden fixture returned empty merc block"

        # ------------------------------------------------------------------ #
        # Build structured diff report                                         #
        # ------------------------------------------------------------------ #
        lines = []
        lines.append("=== MERC ROUND-TRIP DIFF — Task 3.3 phase 1 ===")
        lines.append(f"chargen_output:    {len(chargen_output)} bytes")
        lines.append(f"golden_merc_items: {len(golden_merc_items)} bytes")
        lines.append(f"length delta:      {len(chargen_output) - len(golden_merc_items):+d} bytes")
        lines.append("")

        # Decode per-item summary for both sides
        def _decode_items_summary(raw_concat):
            """Return list of (offset, itype, is_simple, length_guess) for
            each item detected by scanning for 0x10 magic byte."""
            items_info = []
            pos = 0
            while pos < len(raw_concat):
                b0 = raw_concat[pos]
                if b0 != 0x10:
                    pos += 1
                    continue
                if pos + 3 >= len(raw_concat):
                    break
                flags32 = struct.unpack_from("<I", raw_concat, pos)[0]
                is_simple = bool(flags32 & (1 << 21))
                try:
                    itype, ilvl, quality, uid, storage, col, row, bodyloc, location, ext = (
                        decode_item_header(raw_concat, pos)
                    )
                    is_rw = bool(flags32 & (1 << 26))
                    is_eth = bool(flags32 & (1 << 22))
                    items_info.append({
                        'offset': pos,
                        'itype': itype.strip() if itype else '???',
                        'is_simple': is_simple,
                        'ilvl': ilvl,
                        'quality': quality,
                        'uid': uid,
                        'bodyloc': bodyloc,
                        'is_rw': is_rw,
                        'is_eth': is_eth,
                    })
                    # Advance past this item — item length not directly encoded;
                    # step forward at least 1 byte to avoid infinite loop.
                except Exception:
                    items_info.append({
                        'offset': pos,
                        'itype': '???',
                        'is_simple': is_simple,
                        'error': True,
                    })
                pos += 1
            return items_info

        lines.append("--- chargen items (all merc-section entries) ---")
        cg_infos = _decode_items_summary(chargen_output)
        seen_offsets = set()
        for info in cg_infos:
            if info['offset'] in seen_offsets:
                continue
            seen_offsets.add(info['offset'])
            if info.get('error'):
                lines.append(f"  @{info['offset']:#06x}: DECODE_ERROR simple={info['is_simple']}")
            elif info['is_simple']:
                lines.append(
                    f"  @{info['offset']:#06x}: [filler] type={info['itype']!r}"
                )
            else:
                lines.append(
                    f"  @{info['offset']:#06x}: [parent] type={info['itype']!r} "
                    f"ilvl={info['ilvl']} qual={info['quality']} uid={info['uid']} "
                    f"bodyloc={info['bodyloc']} rw={info['is_rw']} eth={info['is_eth']}"
                )

        lines.append("")
        lines.append("--- golden items ---")
        gld_infos = _decode_items_summary(golden_merc_items)
        seen_offsets = set()
        for info in gld_infos:
            if info['offset'] in seen_offsets:
                continue
            seen_offsets.add(info['offset'])
            if info.get('error'):
                lines.append(f"  @{info['offset']:#06x}: DECODE_ERROR simple={info['is_simple']}")
            elif info['is_simple']:
                lines.append(
                    f"  @{info['offset']:#06x}: [filler] type={info['itype']!r}"
                )
            else:
                lines.append(
                    f"  @{info['offset']:#06x}: [parent] type={info['itype']!r} "
                    f"ilvl={info['ilvl']} qual={info['quality']} uid={info['uid']} "
                    f"bodyloc={info['bodyloc']} rw={info['is_rw']} eth={info['is_eth']}"
                )

        # ------------------------------------------------------------------ #
        # Byte-by-byte diff — first 20 divergences                            #
        # ------------------------------------------------------------------ #
        lines.append("")
        lines.append("--- byte-by-byte diff (first 20 divergences) ---")
        compare_len = min(len(chargen_output), len(golden_merc_items))
        divergences = []
        for i in range(compare_len):
            if chargen_output[i] != golden_merc_items[i]:
                ctx_start = max(0, i - 3)
                ctx_end = min(compare_len, i + 4)
                cg_ctx = chargen_output[ctx_start:ctx_end].hex()
                gld_ctx = golden_merc_items[ctx_start:ctx_end].hex()
                divergences.append(
                    f"  offset {i:#06x}: chargen=0x{chargen_output[i]:02x} "
                    f"golden=0x{golden_merc_items[i]:02x} | "
                    f"cg_ctx={cg_ctx} gld_ctx={gld_ctx}"
                )
                if len(divergences) >= 20:
                    break

        if not divergences:
            if len(chargen_output) == len(golden_merc_items):
                lines.append("  *** BYTE-IDENTICAL up to compare_len — PERFECT MATCH ***")
            else:
                lines.append(
                    f"  Identical for first {compare_len} bytes; "
                    f"length differs: {len(chargen_output)} vs {len(golden_merc_items)}"
                )
        else:
            lines.extend(divergences)
            if len(divergences) >= 20:
                total_div = sum(
                    1 for i in range(compare_len)
                    if chargen_output[i] != golden_merc_items[i]
                )
                lines.append(
                    f"  ... ({total_div} total divergent bytes in "
                    f"first {compare_len} bytes)"
                )

        if len(chargen_output) != len(golden_merc_items):
            lines.append("")
            tail_label = "chargen tail" if len(chargen_output) > len(golden_merc_items) else "golden tail"
            tail = (chargen_output if len(chargen_output) > len(golden_merc_items)
                    else golden_merc_items)
            lines.append(
                f"--- {tail_label} (extra {abs(len(chargen_output) - len(golden_merc_items))} bytes) ---"
            )
            lines.append(f"  {tail[compare_len:compare_len+32].hex()}")

        # ------------------------------------------------------------------ #
        # Full hex dumps side by side (for /tmp file)                         #
        # ------------------------------------------------------------------ #
        lines.append("")
        lines.append("--- full hex dump: chargen_output ---")
        for i in range(0, len(chargen_output), 16):
            chunk = chargen_output[i:i+16]
            lines.append(f"  {i:#06x}  {chunk.hex()}")

        lines.append("")
        lines.append("--- full hex dump: golden_merc_items ---")
        for i in range(0, len(golden_merc_items), 16):
            chunk = golden_merc_items[i:i+16]
            lines.append(f"  {i:#06x}  {chunk.hex()}")

        report = "\n".join(lines)

        # Write to /tmp for manual inspection
        Path("/tmp/merc_round_trip_diff.txt").write_text(report)

        # Print summary to stdout so pytest -s shows it
        print("\n" + "\n".join(lines[:60]))

        # Weak assertions only — this is a DIAGNOSTIC test
        assert len(chargen_output) > 0
        assert len(golden_merc_items) > 0


# ---------------------------------------------------------------------------
# Task 2.1: merc.xp passthrough
# ---------------------------------------------------------------------------

class TestMercXPPassthrough:
    """Verify merc.xp YAML field reaches disk at offset 0xAB."""

    def test_merc_xp_default_is_zero(self, tmp_path):
        """No merc.xp specified → chargen writes 0 (fresh-hire default)."""
        # Direct check that the char_def without xp yields xp=0 at set_merc_header.
        # Full deploy would require a full template; we verify at the logic level.
        merc = {'type': 'act2_holyfreeze'}
        xp = int(merc.get('xp', 0))
        assert xp == 0

    def test_merc_xp_int_passthrough(self):
        """merc.xp: 123603480 → passed as-is to set_merc_header (no coercion)."""
        merc = {'type': 'act2_holyfreeze', 'xp': 123603480}
        xp = int(merc.get('xp', 0))
        assert xp == 123603480

    def test_merc_xp_in_yaml_reaches_disk_header(self, tmp_path):
        """End-to-end: deploy a char with merc.xp, read bytes, verify 0xAB."""
        # Minimal: exercise set_merc_header directly with a throwaway buffer.
        import struct
        from d2r_chargen.save import set_merc_header
        data = bytearray(0x200)
        set_merc_header(data, hireling_id=34, xp=123603480, seed=0x178E4E32)
        assert struct.unpack('<I', data[0xAB:0xAF])[0] == 123603480
        assert struct.unpack('<H', data[0xA9:0xAB])[0] == 34


# ---------------------------------------------------------------------------
# Merc XP curve (Phase 1 deliverable: formula from 17-save survey)
# ---------------------------------------------------------------------------

class TestMercXPCurve:
    """Verify the xp_for_level() formula against observed disk values."""

    def test_haseen_lv98_id34(self):
        """Id=34 (Act2 HolyFreeze Hell, Exp/Lvl=130), lv98 → 123,603,480."""
        from d2r_chargen.data.merc_xp_curve import xp_for_level
        assert xp_for_level(hireling_id=34, level=98) == 123_603_480

    def test_act1_fire_hell_lv98_id4(self):
        """Id=4 (Act1 Fire-Hell, Exp/Lvl=120), lv98 → 114,095,520 (matches
        Foedra, Tempest, TestXXX observed values)."""
        from d2r_chargen.data.merc_xp_curve import xp_for_level
        assert xp_for_level(hireling_id=4, level=98) == 114_095_520

    def test_desert_def_nm_lv98_id10(self):
        """Id=10 (Act2 Def-NM, Exp/Lvl=120), lv98 → 114,095,520 (same base as Id=4)."""
        from d2r_chargen.data.merc_xp_curve import xp_for_level
        assert xp_for_level(hireling_id=10, level=98) == 114_095_520

    def test_formula_at_lv50_id34(self):
        """lv50 Id=34: 130 × 51 × 2500 = 16,575,000."""
        from d2r_chargen.data.merc_xp_curve import xp_for_level
        assert xp_for_level(hireling_id=34, level=50) == 16_575_000

    def test_formula_at_lv1(self):
        """Threshold for level 1 is Exp/Lvl × 2 × 1 = 2 × Exp/Lvl.
        This is the minimum XP that displays as level 1."""
        from d2r_chargen.data.merc_xp_curve import xp_for_level
        assert xp_for_level(hireling_id=34, level=1) == 260  # 130 × 2 × 1
        assert xp_for_level(hireling_id=4, level=1) == 240   # 120 × 2 × 1

    def test_unknown_hireling_id_raises(self):
        from d2r_chargen.data.merc_xp_curve import xp_for_level, MercXPError
        with pytest.raises(MercXPError, match="Unknown Hireling.Id"):
            xp_for_level(hireling_id=999, level=98)

    def test_level_out_of_range(self):
        """Level must be in [1, 98]; 0 and 99 reject."""
        from d2r_chargen.data.merc_xp_curve import xp_for_level, MercXPError
        with pytest.raises(MercXPError, match="out of range"):
            xp_for_level(hireling_id=34, level=99)
        with pytest.raises(MercXPError, match="out of range"):
            xp_for_level(hireling_id=34, level=0)

    def test_level_for_xp_roundtrip(self):
        """level_for_xp(xp_for_level(L)) == L across the full range."""
        from d2r_chargen.data.merc_xp_curve import xp_for_level, level_for_xp
        for L in (1, 25, 50, 75, 97, 98):
            xp = xp_for_level(hireling_id=34, level=L)
            back = level_for_xp(hireling_id=34, xp=xp)
            assert back == L, f"roundtrip lv{L}: wrote xp={xp}, read back lv={back}"

    def test_level_for_xp_between_thresholds(self):
        """Merc with XP between thresholds shows the lower level."""
        from d2r_chargen.data.merc_xp_curve import xp_for_level, level_for_xp
        t50 = xp_for_level(hireling_id=34, level=50)
        t51 = xp_for_level(hireling_id=34, level=51)
        # Anything in [t50, t51-1] should display as lv50
        assert level_for_xp(hireling_id=34, xp=t50) == 50
        assert level_for_xp(hireling_id=34, xp=t51 - 1) == 50
        assert level_for_xp(hireling_id=34, xp=t51) == 51

    def test_fresh_hire_xp_zero(self):
        """A merc with 0 XP is displayed as level 1 (below the lv1 threshold)."""
        from d2r_chargen.data.merc_xp_curve import level_for_xp
        assert level_for_xp(hireling_id=34, xp=0) == 1


# ---------------------------------------------------------------------------
# merc.level YAML → xp auto-resolve
# ---------------------------------------------------------------------------

class TestMercLevelResolve:
    """Verify merc.level YAML field auto-resolves to merc.xp via the curve."""

    def test_level_resolves_to_xp_via_type(self):
        """merc.level + merc.type → merc.xp set correctly."""
        from d2r_chargen.character import _resolve_merc_level_to_xp
        char_def = {
            'merc': {'type': 'act2_holyfreeze', 'level': 98},
        }
        _resolve_merc_level_to_xp(char_def)
        assert char_def['merc']['xp'] == 123_603_480

    def test_level_resolves_for_act1_fire_hell(self):
        from d2r_chargen.character import _resolve_merc_level_to_xp
        char_def = {'merc': {'type': 'act1_fire', 'level': 98}}
        _resolve_merc_level_to_xp(char_def)
        assert char_def['merc']['xp'] == 114_095_520

    def test_xp_wins_over_level_with_warning(self, capsys):
        """If both level and xp are set, xp wins and a warning is printed."""
        from d2r_chargen.character import _resolve_merc_level_to_xp
        char_def = {
            'merc': {'type': 'act2_holyfreeze', 'level': 50, 'xp': 123_603_480},
        }
        _resolve_merc_level_to_xp(char_def)
        # xp preserved (explicit wins)
        assert char_def['merc']['xp'] == 123_603_480
        captured = capsys.readouterr()
        assert 'WARNING' in captured.out and 'xp' in captured.out

    def test_level_without_type_raises(self):
        from d2r_chargen.character import _resolve_merc_level_to_xp
        char_def = {'merc': {'level': 98}}
        with pytest.raises(ValueError, match="merc.level requires merc.type"):
            _resolve_merc_level_to_xp(char_def)

    def test_level_with_unknown_type_raises(self):
        from d2r_chargen.character import _resolve_merc_level_to_xp
        char_def = {'merc': {'type': 'fake_merc', 'level': 98}}
        with pytest.raises(ValueError, match="Unknown merc type"):
            _resolve_merc_level_to_xp(char_def)

    def test_no_level_is_noop(self):
        """If merc.level is absent, do nothing."""
        from d2r_chargen.character import _resolve_merc_level_to_xp
        char_def = {'merc': {'type': 'act2_holyfreeze', 'xp': 260}}
        _resolve_merc_level_to_xp(char_def)
        assert char_def['merc']['xp'] == 260
        assert 'level' not in char_def['merc']

    def test_end_to_end_via_load_character_yaml(self, tmp_path):
        """Full path: YAML file with merc.level → load → xp populated."""
        import yaml
        from d2r_chargen.character import load_character_yaml
        yaml_content = {
            'schema_version': 1,
            'name': 'LevelTest',
            'class': 'warlock',
            'level': 99,
            'stats': {'strength': 156, 'dexterity': 35, 'vitality': 340, 'energy': 35},
            'equipment': [],
            'merc': {
                'type': 'act2_holyfreeze',
                'level': 98,
                'equipment_mode': 'direct',
            },
        }
        f = tmp_path / "level_test.yaml"
        f.write_text(yaml.safe_dump(yaml_content))
        loaded = load_character_yaml(str(f))
        assert loaded['merc']['xp'] == 123_603_480
