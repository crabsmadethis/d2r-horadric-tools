from pathlib import Path

import pytest

from d2r_chargen.follower_block import decode_follower_block, parse_demon_payload
from d2r_chargen.save import calc_checksum
from tools.d2s_forge_demon_payload import (
    OffsetCopyMutation,
    SliceMutation,
    apply_offset_copy_mutations,
    apply_slice_mutations,
    build_offset_copy_mutations,
    build_slice_mutations,
    mutate_payload,
    parse_affix_list,
    parse_affix_token,
    parse_offset_list,
    validate_slice_mutation_plan,
    write_payload_to_save,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


def _minimal_save_with_follower(payload: bytes) -> bytes:
    data = bytearray(b"\0" * 0x150)
    data.extend(b"JM\x00\x00JM\x00\x00kf\x00\x01\x00lf")
    data.extend((1).to_bytes(2, "little"))
    data.extend(payload)
    data[0x08:0x0C] = len(data).to_bytes(4, "little")
    data[0x0C:0x10] = b"\0\0\0\0"
    data[0x0C:0x10] = calc_checksum(data).to_bytes(4, "little")
    return bytes(data)


def test_parse_affix_tokens_by_id_name_and_alias():
    assert parse_affix_token("0x19") == 25
    assert parse_affix_token("Mana Burn") == 25
    assert parse_affix_token("manahit") == 25
    assert parse_affix_token("aura") == 30


def test_parse_affix_list_accepts_up_to_seven_and_pads():
    assert parse_affix_list("extra strong,fire enchanted,cursed,mana burn,extra fast") == bytes(
        [5, 9, 7, 25, 6, 0, 0]
    )
    assert parse_affix_list("cursed,aura enchanted,teleportation,extra strong,extra fast,spectral") == bytes(
        [7, 30, 26, 5, 6, 27, 0]
    )
    with pytest.raises(ValueError, match="at most 7"):
        parse_affix_list("1,2,3,4,5,6,7,8")


def test_mutate_payload_updates_high_confidence_fields():
    payload = (FIXTURES / "demon_block_b.bin").read_bytes()

    mutated = mutate_payload(
        payload,
        monster_hcidx=347,
        monster_seed=0x0018AB90,
        bind_level=20,
        affixes=bytes([5, 9, 7, 25, 6, 27, 30]),
        zero_volatile=True,
    )

    fields = parse_demon_payload(mutated)
    assert fields.monster_hcidx == 347
    assert fields.monster_seed == 0x0018AB90
    assert fields.bind_demon_level == 20
    assert fields.affix_indices == bytes([5, 9, 7, 25, 6, 27, 30])
    assert mutated[89:92] == b"\0\0\0"


def test_zero_slice_mutation_only_zeroes_named_slice():
    payload = bytearray((FIXTURES / "demon_block_b.bin").read_bytes())
    payload[64:80] = bytes(range(16))
    original = bytes(payload)

    mutated = apply_slice_mutations(
        original,
        [SliceMutation("zero", "bitfields_64_79")],
    )

    assert mutated[64:80] == b"\0" * 16
    assert mutated[:64] == original[:64]
    assert mutated[80:] == original[80:]


def test_set_slice_hex_requires_exact_slice_length():
    mutation = build_slice_mutations(
        set_slice_hex_specs=["runtime_stats_24_31:0001020304050607"]
    )
    assert mutation == [
        SliceMutation(
            "set",
            "runtime_stats_24_31",
            value=bytes.fromhex("0001020304050607"),
        )
    ]

    with pytest.raises(ValueError, match="requires 8 bytes"):
        build_slice_mutations(set_slice_hex_specs=["runtime_stats_24_31:000102"])


def test_copy_slice_from_uses_same_named_range(tmp_path):
    target = bytearray((FIXTURES / "demon_block_b.bin").read_bytes())
    donor = bytearray((FIXTURES / "demon_block_b.bin").read_bytes())
    target[95:116] = b"A" * 21
    donor[95:116] = b"B" * 21
    donor_path = tmp_path / "donor.bin"
    donor_path.write_bytes(donor)

    mutated = apply_slice_mutations(
        bytes(target),
        [SliceMutation("copy", "post_gf_tail_95_115", source=donor_path)],
    )

    assert mutated[95:116] == b"B" * 21
    assert mutated[:95] == bytes(target[:95])


def test_copy_offsets_from_uses_exact_payload_offsets(tmp_path):
    target = bytearray((FIXTURES / "demon_block_b.bin").read_bytes())
    donor = bytearray((FIXTURES / "demon_block_b.bin").read_bytes())
    target[24] = 0xAA
    target[85] = 0xAA
    target[95] = 0xAA
    donor[24] = 0xBB
    donor[85] = 0xCC
    donor[95] = 0xDD
    donor[96] = 0xEE
    donor_path = tmp_path / "donor.bin"
    donor_path.write_bytes(donor)

    mutation = build_offset_copy_mutations([f"+024,85,0x5f:{donor_path}"])
    mutated = apply_offset_copy_mutations(bytes(target), mutation)

    assert parse_offset_list("+024,85,0x5f") == (24, 85, 95)
    assert mutation == [OffsetCopyMutation((24, 85, 95), donor_path)]
    assert mutated[24] == 0xBB
    assert mutated[85] == 0xCC
    assert mutated[95] == 0xDD
    assert mutated[96] == target[96]
    assert mutated[23] == target[23]


def test_copy_offsets_rejects_duplicates_and_out_of_range():
    with pytest.raises(ValueError, match="duplicates"):
        parse_offset_list("+024,24")
    with pytest.raises(ValueError, match="payload range"):
        parse_offset_list("116")


def test_slice_probe_plan_refuses_multiple_slices_without_force():
    mutations = [
        SliceMutation("zero", "runtime_stats_24_31"),
        SliceMutation("zero", "bitfields_64_79"),
    ]

    with pytest.raises(ValueError, match="exactly one slice"):
        validate_slice_mutation_plan(slice_mutations=mutations)

    validate_slice_mutation_plan(
        slice_mutations=mutations,
        force_multiple_slices=True,
    )


def test_slice_probe_plan_refuses_combined_field_edits_without_force():
    mutations = [SliceMutation("zero", "runtime_stats_24_31")]

    with pytest.raises(ValueError, match="preserve high-confidence"):
        validate_slice_mutation_plan(
            slice_mutations=mutations,
            monster_hcidx=21,
        )

    validate_slice_mutation_plan(
        slice_mutations=mutations,
        monster_hcidx=21,
        force_combined_mutations=True,
    )


def test_offset_copy_probe_plan_refuses_combined_field_edits_without_force(tmp_path):
    donor = tmp_path / "donor.bin"
    donor.write_bytes((FIXTURES / "demon_block_b.bin").read_bytes())
    mutations = [OffsetCopyMutation((24,), donor)]

    with pytest.raises(ValueError, match="preserve high-confidence"):
        validate_slice_mutation_plan(
            slice_mutations=[],
            offset_copy_mutations=mutations,
            monster_hcidx=347,
        )

    validate_slice_mutation_plan(
        slice_mutations=[],
        offset_copy_mutations=mutations,
        monster_hcidx=347,
        force_combined_mutations=True,
    )


def test_write_payload_to_save_preserves_bridge_name_and_checksum(tmp_path):
    original_payload = (FIXTURES / "demon_block_b.bin").read_bytes()
    source = tmp_path / "source.d2s"
    output = tmp_path / "output.d2s"
    source.write_bytes(_minimal_save_with_follower(original_payload))

    mutated = mutate_payload(original_payload, affixes=bytes([5, 9, 7, 27, 30]))
    write_payload_to_save(source, output, mutated, character_name="modelprobe")

    out = output.read_bytes()
    assert int.from_bytes(out[0x08:0x0C], "little") == len(out)
    assert int.from_bytes(out[0x0C:0x10], "little") == calc_checksum(out)
    assert out[0x12B:0x13B].split(b"\0")[0] == b"modelprobe"
    block = decode_follower_block(out)
    assert block.follower_count == 1
    assert block.payload == mutated


def test_write_payload_to_save_rejects_non_letter_character_name(tmp_path):
    payload = (FIXTURES / "demon_block_b.bin").read_bytes()
    source = tmp_path / "source.d2s"
    output = tmp_path / "output.d2s"
    source.write_bytes(_minimal_save_with_follower(payload))

    with pytest.raises(ValueError, match="ASCII letters"):
        write_payload_to_save(source, output, payload, character_name="probe1")
