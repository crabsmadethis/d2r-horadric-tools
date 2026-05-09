from pathlib import Path

import pytest

from d2r_chargen.follower_block import decode_follower_block, parse_demon_payload
from d2r_chargen.resolve import resolve_bound_demon
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


@pytest.fixture
def demon_fixture_dir(tmp_path):
    payload = (FIXTURES / "demon_block_b.bin").read_bytes()
    (tmp_path / "template.d2s").write_bytes(_minimal_save_with_follower(payload))
    return tmp_path


def test_resolve_bound_demon_template_overrides_high_confidence_fields(demon_fixture_dir):
    payload = resolve_bound_demon(
        {
            "template": "template",
            "monster_hcidx": 20,
            "monster_seed": "0x0018AB90",
            "bind_level": 20,
            "affixes": ["Extra Strong", "Cold Enchanted", "none"],
        },
        demon_fixture_dir,
    )

    fields = parse_demon_payload(payload)
    assert fields.monster_hcidx == 20
    assert fields.monster_seed == 0x0018AB90
    assert fields.bind_demon_level == 20
    assert fields.affix_indices == bytes([5, 18, 0, 0, 0])
    assert payload[89:92] == b"\0\0\0"


def test_resolve_bound_demon_template_without_overrides_preserves_payload(demon_fixture_dir):
    source = decode_follower_block((demon_fixture_dir / "template.d2s").read_bytes()).payload
    payload = resolve_bound_demon({"template": "template"}, demon_fixture_dir)
    assert payload == source


def test_resolve_bound_demon_rejects_too_many_affixes(demon_fixture_dir):
    with pytest.raises(ValueError, match="at most 5"):
        resolve_bound_demon(
            {"template": "template", "affixes": [1, 2, 3, 4, 5, 6]},
            demon_fixture_dir,
        )
