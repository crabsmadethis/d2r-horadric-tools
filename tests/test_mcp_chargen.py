"""Tests for d2r_mcp.chargen tool implementations."""
import os
import shutil
import pytest


@pytest.fixture
def chars_dir(tmp_path, monkeypatch):
    """Isolate CHARS_DIR so tests don't see real user characters.

    d2r_chargen.character does `from d2r_chargen.config import CHARS_DIR`
    at import time, creating a local binding. We patch both modules'
    copies so character.CHARS_DIR (read by _resolve_merc_template and
    load_character_yaml) points at the tmp dir. On teardown we restore
    the defaults explicitly rather than relying on monkeypatch order,
    so test_merc_encoding.py tests that run after these don't inherit
    a stale tmp path.
    """
    import d2r_chargen.config
    import d2r_chargen.character
    original_config = d2r_chargen.config.CHARS_DIR
    original_character = d2r_chargen.character.CHARS_DIR

    cdir = tmp_path / "chars"
    cdir.mkdir()
    monkeypatch.setenv("D2R_CHARS", str(cdir))
    d2r_chargen.config.CHARS_DIR = str(cdir)
    d2r_chargen.character.CHARS_DIR = str(cdir)
    try:
        yield cdir
    finally:
        # Restore explicitly — don't trust monkeypatch ordering around
        # module attribute changes we did by direct assignment.
        d2r_chargen.config.CHARS_DIR = original_config
        d2r_chargen.character.CHARS_DIR = original_character


class TestListChars:
    def test_list_empty(self, chars_dir):
        from d2r_mcp.chargen import list_chars
        result = list_chars()
        assert result["status"] == "ok"
        assert result["characters"] == []

    def test_list_skips_merc_templates(self, chars_dir):
        (chars_dir / "Tempest.yaml").write_text("name: Tempest\n")
        (chars_dir / "merc_templates.yaml").write_text("")
        from d2r_mcp.chargen import list_chars
        result = list_chars()
        assert result["characters"] == ["Tempest"]


class TestValidate:
    def test_validate_missing_yaml(self, chars_dir):
        from d2r_mcp.chargen import validate
        r = validate("NoSuchCharacter")
        assert r["status"] == "error"
        assert r["error"]["type"] == "not_found"

    def test_validate_yaml_only_bad_schema(self, chars_dir):
        (chars_dir / "Bad.yaml").write_text("name: Bad\nbogus_top_level: true\n")
        from d2r_mcp.chargen import validate
        r = validate("Bad", yaml_only=True)
        assert r["status"] == "error"
        assert r["error"]["type"] == "yaml_validation_failed"

    @pytest.mark.integration
    def test_validate_good_yaml_passes(self, chars_dir):
        fixture = os.path.join(
            os.path.dirname(__file__), "fixtures", "warlock_fixture.yaml"
        )
        shutil.copy2(fixture, chars_dir / "WarlockFixture.yaml")
        from d2r_mcp.chargen import validate
        r = validate("WarlockFixture", yaml_only=True)
        assert r["status"] == "ok"
        assert r["character"] == "WarlockFixture"


class TestBuild:
    def test_build_missing_yaml(self, chars_dir):
        from d2r_mcp.chargen import build
        r = build("Ghost")
        assert r["status"] == "error"
        assert r["error"]["type"] == "not_found"

    def test_build_bad_yaml(self, chars_dir):
        (chars_dir / "Bad.yaml").write_text("not: valid\n")
        from d2r_mcp.chargen import build
        r = build("Bad")
        assert r["status"] == "error"
        # Either yaml_validation_failed (schema) or build_exception
        # (load_character_yaml raises) is acceptable here — both mean
        # the live save was never touched.
        assert r["error"]["type"] in (
            "yaml_validation_failed", "build_exception", "build_failed"
        )
        assert r.get("rolled_back") is True


class TestImport:
    def test_import_missing_d2s(self, chars_dir, tmp_path, monkeypatch):
        saves = tmp_path / "saves"
        saves.mkdir()
        monkeypatch.setenv("D2R_SAVES", str(saves))
        monkeypatch.setattr("d2r_chargen.config.SAVES", str(saves))
        # Force config module to re-detect SAVES.
        import importlib
        import d2r_chargen.config
        importlib.reload(d2r_chargen.config)
        # Re-patch after reload since reload resets the module attribute
        monkeypatch.setattr("d2r_chargen.config.SAVES", str(saves))

        from d2r_mcp.chargen import import_save
        r = import_save("Ghost")
        assert r["status"] == "error"
        assert r["error"]["type"] == "not_found"

    def test_import_refuses_overwrite_without_force(self, chars_dir, tmp_path, monkeypatch):
        # Set up a fake saves dir with a real .d2s fixture
        saves = tmp_path / "saves"
        saves.mkdir()
        shutil.copy2(
            os.path.join(os.path.dirname(__file__), "fixtures",
                         "hexshade_lv98_haseen.d2s"),
            saves / "Hexshade.d2s",
        )
        monkeypatch.setenv("D2R_SAVES", str(saves))
        monkeypatch.setattr("d2r_chargen.config.SAVES", str(saves))
        import importlib
        import d2r_chargen.config
        importlib.reload(d2r_chargen.config)
        monkeypatch.setattr("d2r_chargen.config.SAVES", str(saves))

        (chars_dir / "Hexshade.yaml").write_text("name: Hexshade\n")

        from d2r_mcp.chargen import import_save
        r = import_save("Hexshade")
        assert r["status"] == "error"
        assert r["error"]["type"] == "would_overwrite"
