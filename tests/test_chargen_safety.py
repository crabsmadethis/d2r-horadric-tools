"""Rule-enforcement tests for d2r_chargen deploy pipeline.

These tests pin the safety-critical invariants described in CLAUDE.md
rules #3, #4, #10, #17. If any of them start failing after a refactor,
the refactor broke a hard-won safety property and must be reverted.
"""
import os
import shutil
import time
import pytest

FIXTURE_YAML = os.path.join(
    os.path.dirname(__file__), "fixtures", "warlock_fixture.yaml"
)

# Use the existing hexshade fixture as a "good enough" .d2s template.
# We just need a valid file at the live save path — the exact content
# doesn't matter since the scanner is stubbed to always fail before any
# promote can happen.
FIXTURE_D2S = os.path.join(
    os.path.dirname(__file__), "fixtures", "hexshade_lv98_haseen.d2s"
)


@pytest.mark.integration
def test_live_save_mtime_unchanged_on_scanner_failure(tmp_path, monkeypatch):
    """Scanner error during build MUST NOT touch the live save file.

    Crafts a chargen run that produces a scanner-failing save (by
    stubbing scan_character_data to always return an error), then
    asserts the live save's mtime is unchanged.
    """
    # Point SAVES and CHARS_DIR at tmp dirs so we don't touch real saves.
    saves_dir = tmp_path / "saves"
    chars_dir = tmp_path / "chars"
    saves_dir.mkdir()
    chars_dir.mkdir()

    # Seed: copy the fixture YAML into chars_dir as "Warlock.yaml".
    shutil.copy2(FIXTURE_YAML, chars_dir / "Warlock.yaml")

    # The fixture YAML has name: TestWarlock, so deploy_character will
    # look for TestWarlock.d2s in SAVES.  Copy a known-good .d2s there
    # as the "existing live save."
    live_d2s = saves_dir / "TestWarlock.d2s"
    shutil.copy2(FIXTURE_D2S, live_d2s)

    pre_mtime = live_d2s.stat().st_mtime
    pre_size = live_d2s.stat().st_size

    # Monkeypatch the already-imported module-level names inside character.py.
    # character.py does `from d2r_chargen.config import SAVES, CHARS_DIR` at
    # import time, so patching the config module alone is not enough.
    monkeypatch.setattr("d2r_chargen.character.SAVES", str(saves_dir))
    monkeypatch.setattr("d2r_chargen.character.CHARS_DIR", str(chars_dir))

    # Stub scan_character_data in the scanner module.  deploy_character
    # imports it lazily via `from d2r_chargen.scanner import scan_character_data`
    # inside the function body, so this monkeypatch is effective.
    def _always_fail(_path):
        return {
            "name": "TestWarlock", "class_id": 7, "level": 85,
            "checksum_ok": True, "size_ok": True,
            "item_count": 0, "merc_count": 0,
            "errors": ["injected scanner failure for test"],
            "warnings": [],
        }
    monkeypatch.setattr(
        "d2r_chargen.scanner.scan_character_data", _always_fail
    )

    # Small fudge to ensure a real mtime delta would be detectable even
    # on low-resolution filesystems.
    time.sleep(0.05)

    from d2r_chargen.character import deploy_character
    result = deploy_character("Warlock", phase=1, force=True)
    assert result is False, "deploy must return False on scanner error"

    post_mtime = live_d2s.stat().st_mtime
    post_size = live_d2s.stat().st_size

    assert post_mtime == pre_mtime, (
        f"live save mtime CHANGED on scanner failure "
        f"(pre={pre_mtime} post={post_mtime}). Rule #17 violated — "
        f"deploy_character is not scan-before-promote."
    )
    assert post_size == pre_size


@pytest.mark.integration
def test_backup_failure_returns_false_without_touching_live_save(tmp_path, monkeypatch):
    """Rule #3: if the backup write fails (full disk, permission denied),
    deploy_character must refuse to proceed and leave the live save
    untouched. The MCP wrapper converts this into a clean build_failed
    envelope instead of a raw OSError crash.
    """
    saves_dir = tmp_path / "saves"
    chars_dir = tmp_path / "chars"
    saves_dir.mkdir()
    chars_dir.mkdir()

    shutil.copy2(FIXTURE_YAML, chars_dir / "Warlock.yaml")
    live_d2s = saves_dir / "Warlock.d2s"
    shutil.copy2(FIXTURE_D2S, live_d2s)

    pre_mtime = live_d2s.stat().st_mtime
    pre_size = live_d2s.stat().st_size

    monkeypatch.setattr("d2r_chargen.character.SAVES", str(saves_dir))
    monkeypatch.setattr("d2r_chargen.character.CHARS_DIR", str(chars_dir))

    # Stub shutil.copy2 only for the backup-target path (ending in
    # .pre_chargen_bak) so the test doesn't break the earlier template-copy
    # step inside deploy_character.
    import shutil as _shutil
    real_copy2 = _shutil.copy2

    def _fail_on_backup(src, dst, *a, **kw):
        if str(dst).endswith(".pre_chargen_bak"):
            raise OSError(28, "No space left on device (simulated)")
        return real_copy2(src, dst, *a, **kw)

    monkeypatch.setattr("d2r_chargen.character.shutil.copy2", _fail_on_backup)

    time.sleep(0.05)

    from d2r_chargen.character import deploy_character
    result = deploy_character("Warlock", phase=1, force=True)
    assert result is False, \
        "deploy must return False (not raise) on backup failure"

    assert live_d2s.stat().st_mtime == pre_mtime, \
        "live save was modified despite backup failure"
    assert live_d2s.stat().st_size == pre_size
