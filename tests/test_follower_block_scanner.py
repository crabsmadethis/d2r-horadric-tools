"""Tests for scanner.py integration of follower_block decoder (Task 2.1).

Verifies that the scanner prints a `BOUND DEMON` section when an active
follower is present and stays silent for saves with no follower. Also
guards against regression of the bogus `IRON GOLEM FLAG` warning that the
old kf-validation block emitted.
"""
import shutil
from pathlib import Path

import pytest

# Skip entire file if game data not extracted
pytest.importorskip("d2r_chargen.data.item_stat_cost",
                     reason="game data not extracted (run 'd2r-mod extract')")

from d2r_chargen.scanner import run_scanner

FIX = Path(__file__).resolve().parent / 'fixtures'

if not (FIX / 'marrowbind_demon_b.d2s').exists() or not (FIX / 'tempest.d2s').exists():
    pytest.skip('.d2s fixtures not present (gitignored in public repo)',
                allow_module_level=True)


def _stage_fixture(tmp_path, fixture_name, install_name):
    """Copy a fixture .d2s into a temp saves dir under a chosen filename."""
    saves = tmp_path / 'saves'
    saves.mkdir()
    src = FIX / fixture_name
    dst = saves / install_name
    shutil.copy(src, dst)
    return saves


def _run_with_saves(monkeypatch, saves_dir, target):
    """Point the scanner at a fake SAVES directory and invoke run_scanner."""
    monkeypatch.setenv('D2R_SAVES', str(saves_dir))
    monkeypatch.setattr('d2r_chargen.scanner.SAVES', str(saves_dir))


def test_scanner_prints_demon_block(capsys, tmp_path, monkeypatch):
    """Marrowbind (warlock with active demon) should print BOUND DEMON section."""
    saves = _stage_fixture(tmp_path, 'marrowbind_demon_b.d2s', 'Marrowbind.d2s')
    _run_with_saves(monkeypatch, saves, 'marrowbind')
    run_scanner('marrowbind')
    out = capsys.readouterr().out

    assert 'BOUND DEMON:' in out, f'expected BOUND DEMON section in output:\n{out}'
    assert 'monster_hcidx = 20' in out, out
    assert 'bind_demon_lv = 7' in out, out
    assert 'monster_seed  = 0x' in out, out
    # Marrowbind fixture B has affix indices including 5 (Extra Strong)
    # and 6 (Extra Fast) per Bind Demon par2..par5.
    assert 'Extra Strong' in out or 'Extra Fast' in out, out


def test_scanner_silent_for_no_follower(capsys, tmp_path, monkeypatch):
    """Tempest (no follower) should NOT print BOUND DEMON section."""
    saves = _stage_fixture(tmp_path, 'tempest.d2s', 'Tempest.d2s')
    _run_with_saves(monkeypatch, saves, 'tempest')
    run_scanner('tempest')
    out = capsys.readouterr().out

    assert 'BOUND DEMON' not in out, f'should not print BOUND DEMON when no follower:\n{out}'


def test_scanner_no_bogus_iron_golem_warning(capsys, tmp_path, monkeypatch):
    """The old IRON GOLEM FLAG warning is gone (replaced with kf-lf gap check)."""
    saves = _stage_fixture(tmp_path, 'tempest.d2s', 'Tempest.d2s')
    _run_with_saves(monkeypatch, saves, 'tempest')
    run_scanner('tempest')
    out = capsys.readouterr().out

    assert 'IRON GOLEM FLAG' not in out, f'IRON GOLEM warning should be removed:\n{out}'


def test_scanner_kf_lf_gap_silent_for_normal_save(capsys, tmp_path, monkeypatch):
    """Normal saves (gap == 5) should not emit a kf-lf GAP warning."""
    saves = _stage_fixture(tmp_path, 'tempest.d2s', 'Tempest.d2s')
    _run_with_saves(monkeypatch, saves, 'tempest')
    run_scanner('tempest')
    out = capsys.readouterr().out

    assert 'kf-lf GAP' not in out, f'gap warning should not fire on a normal save:\n{out}'


# ---------------------------------------------------------------------------
# Task 2.3: semantic fix — follower_count is NOT the merc-hired signal
# ---------------------------------------------------------------------------

def test_marrowbind_no_false_merc_not_hired(capsys, tmp_path, monkeypatch):
    """Marrowbind has follower_count=1 AND a hired merc (3 items).

    Old behaviour: 'Merc not hired (follower_count=0)' printed only when
    follower_count==0. Marrowbind passed because its follower_count==1
    happened to coincide with having a merc — but that's coincidence.

    New behaviour: the check uses merc_count_val (JM[merc] item count).
    Marrowbind has 3 merc items, so 'Merc not hired' must NOT print.
    """
    saves = _stage_fixture(tmp_path, 'marrowbind_demon_b.d2s', 'Marrowbind.d2s')
    _run_with_saves(monkeypatch, saves, 'marrowbind')
    run_scanner('marrowbind')
    out = capsys.readouterr().out

    assert 'Merc not hired' not in out, (
        f'Marrowbind has 3 merc items — must not print Merc not hired:\n{out}'
    )


@pytest.mark.parametrize('fixture,install', [
    ('marrowbind_demon_b.d2s', 'Marrowbind.d2s'),
    ('tempest.d2s', 'Tempest.d2s'),
])
def test_lf_consistency_uses_payload_size(capsys, tmp_path, monkeypatch, fixture, install):
    """Phase 0.4 finding: count must match payload size, not match merc state.

    Marrowbind fixture has follower_count=1 + 116B payload — must read 'ok'.
    Tempest has follower_count=0 + 0B payload — must also read 'ok'.
    Neither must produce the old 'INCONSISTENT — failed to join game' string
    based on the (now-removed) merc/follower coupling.
    """
    saves = _stage_fixture(tmp_path, fixture, install)
    target = install.split('.')[0].lower()
    _run_with_saves(monkeypatch, saves, target)
    run_scanner(target)
    out = capsys.readouterr().out
    assert 'INCONSISTENT' not in out, f'{fixture} produced INCONSISTENT:\n{out}'
    assert '✓ ok' in out, f'{fixture} did not print ok status:\n{out}'
