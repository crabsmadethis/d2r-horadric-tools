"""CLI validation coverage for bound-demon payload scanning."""

import argparse
from pathlib import Path

import pytest

pytest.importorskip(
    "d2r_chargen.data.item_stat_cost",
    reason="game data not extracted (run 'd2r-mod extract')",
)

from d2r_chargen.follower_block import decode_follower_block, parse_demon_payload
from d2r_chargen.save import calc_checksum


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


def _minimal_save_with_follower(payload: bytes) -> bytes:
    data = bytearray(b"\0" * 0x130)
    data.extend(b"JM\x00\x00JM\x00\x00kf\x00\x01\x00lf")
    data.extend((1).to_bytes(2, "little"))
    data.extend(payload)
    data[0x08:0x0C] = len(data).to_bytes(4, "little")
    data[0x0C:0x10] = b"\0\0\0\0"
    data[0x0C:0x10] = calc_checksum(data).to_bytes(4, "little")
    return bytes(data)


def test_validate_binary_scan_includes_bound_demon_payload(
    tmp_path,
    monkeypatch,
):
    chars_dir = tmp_path / "chars"
    saves_dir = tmp_path / "saves"
    chars_dir.mkdir()
    saves_dir.mkdir()

    payload = (FIXTURES / "demon_block_b.bin").read_bytes()
    template_path = tmp_path / "template.d2s"
    template_path.write_bytes(_minimal_save_with_follower(payload))

    (chars_dir / "Warnlock.yaml").write_text(
        f"""
schema_version: 1
name: Warnlock
class: warlock
level: 20
stats:
  strength: 10
  dexterity: 10
  vitality: 10
  energy: 10
skills:
  Bind Demon: 1
equipment: []
bound_demon:
  template_path: {template_path}
  monster_hcidx: 724
  source_affixes: [Cursed]
  skill_affixes: auto
""".lstrip()
    )

    monkeypatch.setattr("d2r_chargen.config.CHARS_DIR", str(chars_dir))
    monkeypatch.setattr("d2r_chargen.config.SAVES", str(saves_dir))

    observed = {}

    def fake_scan(path):
        block = decode_follower_block(Path(path).read_bytes())
        observed["has_follower"] = block.has_follower
        observed["payload"] = block.payload
        return {
            "errors": [],
            "warnings": [],
            "item_count": 0,
            "checksum_ok": True,
        }

    monkeypatch.setattr("d2r_chargen.scanner.scan_character_data", fake_scan)

    from d2r_chargen.cli import cmd_validate

    cmd_validate(argparse.Namespace(name="Warnlock", yaml_only=False))

    assert observed["has_follower"] is True
    assert len(observed["payload"]) == 116
    fields = parse_demon_payload(observed["payload"])
    assert fields.monster_hcidx == 724
    assert fields.affix_indices == bytes([7, 0, 0, 0, 0, 0, 0])
