import unittest
import pytest

# resolve.py imports generated data modules
pytest.importorskip("d2r_chargen.data.item_stat_cost",
                     reason="game data not extracted (run 'd2r-mod extract')")

from d2r_chargen.resolve import resolve_progression


class TestResolveProgression(unittest.TestCase):
    """Test YAML progression field resolution."""

    def test_hell_complete_string(self):
        result = resolve_progression('hell_complete')
        self.assertEqual(result['difficulty'], 'hell')
        self.assertTrue(result['waypoints']['normal'])
        self.assertTrue(result['waypoints']['nightmare'])
        self.assertTrue(result['waypoints']['hell'])
        self.assertTrue(result['quests']['normal'])
        self.assertTrue(result['quests']['nightmare'])
        self.assertTrue(result['quests']['hell'])

    def test_hell_start_string(self):
        result = resolve_progression('hell_start')
        self.assertEqual(result['difficulty'], 'hell')
        self.assertTrue(result['waypoints']['normal'])
        self.assertTrue(result['waypoints']['nightmare'])
        self.assertFalse(result['waypoints']['hell'])
        self.assertFalse(result['quests']['hell'])

    def test_nightmare_complete_string(self):
        result = resolve_progression('nightmare_complete')
        self.assertEqual(result['difficulty'], 'nightmare')
        self.assertTrue(result['waypoints']['normal'])
        self.assertTrue(result['waypoints']['nightmare'])
        self.assertFalse(result['waypoints']['hell'])
        self.assertFalse(result['quests']['hell'])

    def test_normal_start_string(self):
        result = resolve_progression('normal_start')
        self.assertEqual(result['difficulty'], 'normal')
        self.assertFalse(result['waypoints']['normal'])
        self.assertFalse(result['quests']['normal'])

    def test_normal_complete_string(self):
        result = resolve_progression('normal_complete')
        self.assertEqual(result['difficulty'], 'normal')
        self.assertTrue(result['waypoints']['normal'])
        self.assertTrue(result['quests']['normal'])
        self.assertFalse(result['waypoints']['nightmare'])

    def test_dict_with_preset(self):
        result = resolve_progression({
            'preset': 'hell_complete',
            'waypoints': {'hell': {'act5': False}},
        })
        self.assertEqual(result['difficulty'], 'hell')
        self.assertTrue(result['waypoints']['normal'])
        self.assertTrue(result['waypoints']['nightmare'])
        hell_wp = result['waypoints']['hell']
        self.assertIsInstance(hell_wp, dict)
        self.assertTrue(hell_wp['act1'])
        self.assertFalse(hell_wp['act5'])

    def test_dict_with_quest_override(self):
        result = resolve_progression({
            'preset': 'hell_complete',
            'quests': {'hell': {'act3': False}},
        })
        hell_q = result['quests']['hell']
        self.assertIsInstance(hell_q, dict)
        self.assertTrue(hell_q['act1'])
        self.assertFalse(hell_q['act3'])

    def test_invalid_preset_raises(self):
        with self.assertRaises(ValueError):
            resolve_progression('invalid_preset')

    def test_default_is_hell_start(self):
        result = resolve_progression('hell_start')
        self.assertEqual(result['difficulty'], 'hell')
        self.assertTrue(result['waypoints']['normal'])
        self.assertTrue(result['waypoints']['nightmare'])
        self.assertFalse(result['waypoints']['hell'])
        self.assertFalse(result['quests']['hell'])


import struct
from d2r_chargen.save import (
    set_waypoints_granular, set_quests_granular,
    find_section, set_all_waypoints, set_all_quests,
)
from d2r_chargen.build_lib import calc_checksum


def _make_d2s_stub():
    """Create a minimal d2s-like bytearray with WS and Woo! sections.

    Synthetic offsets (0x100, 0x200) — not real d2s layout, but find_section()
    uses data.find() so any offset works.
    """
    data = bytearray(900)
    struct.pack_into('<I', data, 0, 0xAA55AA55)
    data[0x15] = 0x0F
    data[0x18] = 6

    ws_off = 0x100
    data[ws_off:ws_off+2] = b'WS'
    data[ws_off+2:ws_off+8] = b'\x01\x00\x00\x00\x77\x00'

    woo_off = 0x200
    data[woo_off:woo_off+4] = b'Woo!'
    data[woo_off+4:woo_off+10] = b'\x06\x00\x00\x00\x2a\x00'

    return data


class TestSetWaypointsGranular(unittest.TestCase):

    def test_all_true_sets_all_waypoints(self):
        data = _make_d2s_stub()
        wp = {'normal': True, 'nightmare': True, 'hell': True}
        data = set_waypoints_granular(data, wp)
        ws = find_section(data, b'WS')
        for diff in range(3):
            base = ws + 8 + diff * 24
            self.assertEqual(data[base], 0x02)
            self.assertEqual(data[base+1], 0x01)
            for i in range(5):
                self.assertEqual(data[base+2+i], 0xFF)

    def test_all_false_clears_waypoints(self):
        data = _make_d2s_stub()
        data = set_waypoints_granular(data, {'normal': True, 'nightmare': True, 'hell': True})
        data = set_waypoints_granular(data, {'normal': False, 'nightmare': False, 'hell': False})
        ws = find_section(data, b'WS')
        for diff in range(3):
            base = ws + 8 + diff * 24
            for i in range(5):
                self.assertEqual(data[base+2+i], 0x00)

    def test_per_act_override(self):
        data = _make_d2s_stub()
        wp = {
            'normal': True,
            'nightmare': True,
            'hell': {'act1': True, 'act2': True, 'act3': True, 'act4': True, 'act5': False},
        }
        data = set_waypoints_granular(data, wp)
        ws = find_section(data, b'WS')
        hell_base = ws + 8 + 2 * 24
        hell_bytes = data[hell_base+2:hell_base+7]
        val = int.from_bytes(hell_bytes, 'little')
        for bit in range(30):
            self.assertEqual((val >> bit) & 1, 1, f"bit {bit} should be set")
        for bit in range(30, 39):
            self.assertEqual((val >> bit) & 1, 0, f"bit {bit} should be clear")

    def test_matches_set_all_waypoints(self):
        data1 = _make_d2s_stub()
        data2 = _make_d2s_stub()
        data1 = set_all_waypoints(data1)
        data2 = set_waypoints_granular(data2, {'normal': True, 'nightmare': True, 'hell': True})
        ws = find_section(data1, b'WS')
        for diff in range(3):
            base = ws + 8 + diff * 24
            self.assertEqual(data1[base:base+7], data2[base:base+7],
                             f"Mismatch in difficulty {diff}")


class TestSetQuestsGranular(unittest.TestCase):

    def test_all_true_sets_all_quests(self):
        data = _make_d2s_stub()
        q = {'normal': True, 'nightmare': True, 'hell': True}
        data = set_quests_granular(data, q)
        woo = find_section(data, b'Woo!')
        for diff in range(3):
            base = woo + 10 + diff * 96
            for quest in range(48):
                off = base + quest * 2
                self.assertEqual(data[off], 0x01, f"diff={diff} quest={quest} not complete")
                self.assertEqual(data[off+1], 0x10, f"diff={diff} quest={quest} no reward")

    def test_all_false_leaves_quests_empty(self):
        data = _make_d2s_stub()
        q = {'normal': False, 'nightmare': False, 'hell': False}
        data = set_quests_granular(data, q)
        woo = find_section(data, b'Woo!')
        for diff in range(3):
            base = woo + 10 + diff * 96
            for quest in range(48):
                off = base + quest * 2
                self.assertEqual(data[off], 0x00)
                self.assertEqual(data[off+1], 0x00)

    def test_per_act_override(self):
        data = _make_d2s_stub()
        q = {
            'normal': True,
            'nightmare': True,
            'hell': {'act1': True, 'act2': False, 'act3': False, 'act4': False, 'act5': False, 'act6': False},
        }
        data = set_quests_granular(data, q)
        woo = find_section(data, b'Woo!')
        hell_base = woo + 10 + 2 * 96
        for quest in range(8):
            off = hell_base + quest * 2
            self.assertEqual(data[off], 0x01)
        for quest in range(8, 16):
            off = hell_base + quest * 2
            self.assertEqual(data[off], 0x00)

    def test_matches_set_all_quests(self):
        data1 = _make_d2s_stub()
        data2 = _make_d2s_stub()
        data1 = set_all_quests(data1)
        data2 = set_quests_granular(data2, {'normal': True, 'nightmare': True, 'hell': True})
        woo = find_section(data1, b'Woo!')
        for diff in range(3):
            base = woo + 10 + diff * 96
            self.assertEqual(data1[base:base+96], data2[base:base+96],
                             f"Mismatch in difficulty {diff}")


from d2r_chargen.scanner import check_progression_consistency


class TestScannerProgressionChecks(unittest.TestCase):

    def _make_scan_stub(self, prog_byte=0x0F, is_hc=False, act_byte=10,
                        normal_wp=True, nm_wp=True, hell_wp=True,
                        normal_q=True, nm_q=True, hell_q=True):
        """Create a d2s stub with controllable progression state."""
        from d2r_chargen.save import (
            set_waypoints_granular, set_quests_granular, find_section,
        )
        data = _make_d2s_stub()
        data[0x15] = prog_byte
        data[0x14] = 0x04 if is_hc else 0x00
        if len(data) > 0xA9:
            data[0xA9] = act_byte

        wp = {'normal': normal_wp, 'nightmare': nm_wp, 'hell': hell_wp}
        data = set_waypoints_granular(data, wp)
        q = {'normal': normal_q, 'nightmare': nm_q, 'hell': hell_q}
        data = set_quests_granular(data, q)
        return data

    def test_hell_complete_passes(self):
        data = self._make_scan_stub(prog_byte=0x0F, normal_wp=True,
                                     nm_wp=True, hell_wp=True,
                                     normal_q=True, nm_q=True, hell_q=True)
        errors, warnings = check_progression_consistency(data)
        self.assertEqual(errors, [])

    def test_hell_unlocked_but_normal_wp_missing(self):
        data = self._make_scan_stub(prog_byte=0x0F, normal_wp=False)
        errors, warnings = check_progression_consistency(data)
        self.assertTrue(any('Normal' in e and 'waypoint' in e.lower() for e in errors),
                        f"Expected Normal WP error, got: {errors}")

    def test_hell_unlocked_but_normal_quests_missing(self):
        data = self._make_scan_stub(prog_byte=0x0F, normal_q=False)
        errors, warnings = check_progression_consistency(data)
        self.assertTrue(any('Normal' in e and 'quest' in e.lower() for e in errors),
                        f"Expected Normal quest error, got: {errors}")

    def test_nm_unlocked_but_normal_wp_missing(self):
        data = self._make_scan_stub(prog_byte=0x05, normal_wp=False,
                                     hell_wp=False, hell_q=False)
        errors, warnings = check_progression_consistency(data)
        self.assertTrue(any('Normal' in e for e in errors))

    def test_hc_with_act_byte_set_warns(self):
        data = self._make_scan_stub(prog_byte=0x0F, is_hc=True, act_byte=10)
        errors, warnings = check_progression_consistency(data)
        self.assertTrue(any('HC' in w or 'act byte' in w.lower() for w in warnings),
                        f"Expected HC act byte warning, got: {warnings}")

    def test_level_vs_progression_warning(self):
        data = self._make_scan_stub(prog_byte=0x00)
        data[0x1B] = 99  # level 99 but normal only
        errors, warnings = check_progression_consistency(data)
        self.assertTrue(any('level' in w.lower() or 'lv99' in w.lower() for w in warnings),
                        f"Expected level/progression warning, got: {warnings}")

    def test_yaml_vs_binary_mismatch(self):
        """YAML says hell_complete but Hell WPs are empty."""
        data = self._make_scan_stub(prog_byte=0x0F, hell_wp=False)
        errors, warnings = check_progression_consistency(data, yaml_progression='hell_complete')
        self.assertTrue(any('hell_complete' in w and 'empty' in w for w in warnings),
                        f"Expected YAML/binary mismatch warning, got: {warnings}")

    def test_yaml_vs_binary_match_no_warning(self):
        """YAML says hell_complete and Hell WPs are set — no warning."""
        data = self._make_scan_stub(prog_byte=0x0F, hell_wp=True)
        errors, warnings = check_progression_consistency(data, yaml_progression='hell_complete')
        yaml_warns = [w for w in warnings if 'hell_complete' in w]
        self.assertEqual(yaml_warns, [])


if __name__ == '__main__':
    unittest.main()
