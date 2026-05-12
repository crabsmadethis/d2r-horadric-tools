from pathlib import Path

import pytest

pytest.importorskip(
    "d2r_chargen.data.item_stat_cost",
    reason="game data not extracted (run 'd2r-mod extract')",
)

from d2r_chargen.follower_block import decode_follower_block, parse_demon_payload
from d2r_chargen.character import _effective_bind_demon_level
from d2r_chargen.resolve import bind_demon_skill_affixes, resolve_bound_demon
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
    assert fields.affix_indices == bytes([5, 18, 0, 0, 0, 0, 0])
    assert payload[89:92] == b"\0\0\0"


def test_resolve_bound_demon_template_without_overrides_preserves_payload(demon_fixture_dir):
    source = decode_follower_block((demon_fixture_dir / "template.d2s").read_bytes()).payload
    payload = resolve_bound_demon({"template": "template"}, demon_fixture_dir)
    assert payload == source


def test_resolve_bound_demon_template_path_uses_local_save(
    demon_fixture_dir,
    tmp_path,
):
    local_template = tmp_path / "local-template.d2s"
    local_template.write_bytes((demon_fixture_dir / "template.d2s").read_bytes())

    payload = resolve_bound_demon(
        {
            "template_path": str(local_template),
            "monster_hcidx": 724,
            "source_affixes": ["fanat", "Cursed"],
            "skill_affixes": ["Aura Enchanted"],
        },
        demon_fixture_dir,
    )

    fields = parse_demon_payload(payload)
    assert fields.monster_hcidx == 724
    assert fields.affix_indices == bytes([37, 30, 7, 0, 0, 0, 0])


def test_resolve_bound_demon_rejects_template_and_template_path(
    demon_fixture_dir,
):
    with pytest.raises(ValueError, match="both 'template' and 'template_path'"):
        resolve_bound_demon(
            {
                "template": "template",
                "template_path": str(demon_fixture_dir / "template.d2s"),
            },
            demon_fixture_dir,
        )


def test_resolve_bound_demon_rejects_too_many_affixes(demon_fixture_dir):
    with pytest.raises(ValueError, match="at most 7"):
        resolve_bound_demon(
            {"template": "template", "affixes": [1, 2, 3, 4, 5, 6, 7, 8]},
            demon_fixture_dir,
        )


def test_bind_demon_skill_affix_thresholds():
    assert bind_demon_skill_affixes(1) == []
    assert bind_demon_skill_affixes(5) == [5]
    assert bind_demon_skill_affixes(10) == [5, 6]
    assert bind_demon_skill_affixes(15) == [5, 6, 27]
    assert bind_demon_skill_affixes(20) == [5, 6, 27, 30]


def test_resolve_bound_demon_composes_source_and_auto_skill_affixes(demon_fixture_dir):
    payload = resolve_bound_demon(
        {
            "template": "template",
            "source_affixes": ["Cursed", "Lightning", "Cold Enchanted"],
            "skill_affixes": "auto",
        },
        demon_fixture_dir,
        effective_bind_level=10,
    )

    fields = parse_demon_payload(payload)
    assert fields.affix_indices == bytes([7, 17, 18, 5, 6, 0, 0])


def test_resolve_bound_demon_keeps_fanaticism_source_separate_from_aura_skill(
    demon_fixture_dir,
):
    payload = resolve_bound_demon(
        {
            "template": "template",
            "source_affixes": ["fanat", "Cursed"],
            "skill_affixes": ["Aura Enchanted"],
        },
        demon_fixture_dir,
    )

    fields = parse_demon_payload(payload)
    assert fields.affix_indices == bytes([37, 30, 7, 0, 0, 0, 0])


def test_resolve_bound_demon_pairs_fanaticism_before_aura_for_visible_path(
    demon_fixture_dir,
):
    payload = resolve_bound_demon(
        {
            "template": "template",
            "source_affixes": ["Fanaticism", "Cursed", "Stone Skin"],
            "skill_affixes": ["Aura Enchanted", "Extra Strong"],
        },
        demon_fixture_dir,
    )

    fields = parse_demon_payload(payload)
    assert fields.affix_indices == bytes([37, 30, 7, 28, 5, 0, 0])


def test_resolve_bound_demon_auto_skill_affixes_without_source(demon_fixture_dir):
    payload = resolve_bound_demon(
        {
            "template": "template",
            "effective_bind_level": 20,
        },
        demon_fixture_dir,
    )

    fields = parse_demon_payload(payload)
    assert fields.affix_indices == bytes([5, 6, 27, 30, 0, 0, 0])


def test_resolve_bound_demon_composes_natural_overcap_affixes(demon_fixture_dir):
    payload = resolve_bound_demon(
        {
            "template": "template",
            "source_affixes": ["Cursed", "Aura Enchanted", "Teleportation"],
            "skill_affixes": "auto",
        },
        demon_fixture_dir,
        effective_bind_level=20,
    )

    fields = parse_demon_payload(payload)
    assert fields.affix_indices == bytes([7, 30, 26, 5, 6, 27, 0])


def test_player_yaml_composes_affixes_from_character_effective_level(demon_fixture_dir):
    char_def = {
        "class": "warlock",
        "skills": {"Bind Demon": 10},
        "equipment": [
            {
                "slot": "helm",
                "rare": True,
                "base": "ci3",
                "properties": {"all_skills": 10},
            }
        ],
        "bound_demon": {
            "template": "template",
            "source_affixes": [
                "Fanaticism",
                "Aura Enchanted",
                "Cursed",
                "Stone Skin",
            ],
            "skill_affixes": "auto",
        },
    }

    effective_level = _effective_bind_demon_level(char_def)
    payload = resolve_bound_demon(
        char_def["bound_demon"],
        demon_fixture_dir,
        effective_bind_level=effective_level,
    )

    fields = parse_demon_payload(payload)
    assert effective_level == 20
    assert fields.affix_indices == bytes([37, 30, 7, 28, 5, 6, 27])


def test_resolve_bound_demon_rejects_raw_and_composed_affixes(demon_fixture_dir):
    with pytest.raises(ValueError, match="raw seven-slot override"):
        resolve_bound_demon(
            {
                "template": "template",
                "affixes": ["Extra Strong"],
                "source_affixes": ["Cursed"],
            },
            demon_fixture_dir,
            effective_bind_level=20,
        )


def test_resolve_bound_demon_rejects_composed_affix_overflow(demon_fixture_dir):
    with pytest.raises(ValueError, match="at most 7"):
        resolve_bound_demon(
            {
                "template": "template",
                "source_affixes": [
                    "Fanaticism",
                    "Cursed",
                    "Lightning",
                    "Cold Enchanted",
                    "Stone Skin",
                ],
                "skill_affixes": "auto",
            },
            demon_fixture_dir,
            effective_bind_level=20,
        )
