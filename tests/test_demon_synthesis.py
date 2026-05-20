import pytest

from d2r_chargen.demon_synthesis import (
    GF_OPCODE_92_94,
    ROW20_NO_AFFIX_TAIL_95_115,
    BoundDemonSynthesisFields,
    build_bound_demon_payload,
)
from d2r_chargen.follower_block import (
    DEMON_PAYLOAD_LEN,
    demon_payload_unknown_slices,
    parse_demon_payload,
)


def test_build_row20_no_affix_initializer_payload():
    payload = build_bound_demon_payload(
        BoundDemonSynthesisFields(monster_hcidx=20, monster_seed=0x0000F74F)
    )

    fields = parse_demon_payload(payload)
    slices = demon_payload_unknown_slices(payload)
    assert len(payload) == DEMON_PAYLOAD_LEN
    assert payload[0:4] == bytes.fromhex("18 00 01 00")
    assert fields.monster_hcidx == 20
    assert fields.monster_seed == 0x0000F74F
    assert fields.bind_demon_level == 7
    assert fields.affix_indices == bytes(7)
    assert slices["runtime_stats_24_31"] == bytes(8)
    assert slices["bitfields_64_79"] == bytes(16)
    assert payload[92:95] == GF_OPCODE_92_94
    assert payload[95:116] == ROW20_NO_AFFIX_TAIL_95_115


def test_build_row724_no_affix_initializer_payload():
    payload = build_bound_demon_payload(
        BoundDemonSynthesisFields(monster_hcidx=724, monster_seed=0x0008F2C2)
    )

    fields = parse_demon_payload(payload)
    assert len(payload) == DEMON_PAYLOAD_LEN
    assert fields.monster_hcidx == 724
    assert fields.monster_seed == 0x0008F2C2
    assert fields.affix_indices == bytes(7)
    assert payload[4:10] == bytes.fromhex("d4 02 c2 f2 08 00")


def test_build_synthk_validated_package_shape():
    payload = build_bound_demon_payload(
        BoundDemonSynthesisFields(
            monster_hcidx=724,
            monster_seed=0x0008F2C8,
            affixes=bytes.fromhex("25 1e 07 1c 05 06 1b"),
            runtime_stats_24_31=bytes.fromhex("02 00 00 00 43 00 00 00"),
        )
    )

    fields = parse_demon_payload(payload)
    slices = demon_payload_unknown_slices(payload)
    assert fields.monster_hcidx == 724
    assert fields.monster_seed == 0x0008F2C8
    assert fields.affix_indices == bytes.fromhex("25 1e 07 1c 05 06 1b")
    assert slices["runtime_stats_24_31"] == bytes.fromhex("02 00 00 00 43 00 00 00")
    assert slices["percent_or_caps_44_51"] == bytes(8)
    assert slices["bitfields_64_79"] == bytes(16)
    assert payload[87:92] == bytes(5)
    assert payload[92:95] == GF_OPCODE_92_94
    assert payload[95:116] == ROW20_NO_AFFIX_TAIL_95_115


def test_builder_rejects_out_of_range_integer_fields():
    with pytest.raises(ValueError, match="monster_hcidx out of range"):
        build_bound_demon_payload(
            BoundDemonSynthesisFields(monster_hcidx=0x10000, monster_seed=0)
        )
    with pytest.raises(ValueError, match="monster_seed out of range"):
        build_bound_demon_payload(
            BoundDemonSynthesisFields(monster_hcidx=20, monster_seed=0x100000000)
        )


def test_builder_rejects_bad_slice_lengths():
    with pytest.raises(ValueError, match="affixes must be 7 bytes"):
        build_bound_demon_payload(
            BoundDemonSynthesisFields(
                monster_hcidx=20,
                monster_seed=0,
                affixes=bytes(6),
            )
        )
    with pytest.raises(ValueError, match="runtime_stats_24_31 must be 8 bytes"):
        build_bound_demon_payload(
            BoundDemonSynthesisFields(
                monster_hcidx=20,
                monster_seed=0,
                runtime_stats_24_31=bytes(7),
            )
        )
