from pathlib import Path

import pytest

from d2r_chargen.follower_block import decode_follower_block, parse_demon_payload
from d2r_chargen.save import calc_checksum
from tools.d2s_forge_demon_payload import (
    mutate_payload,
    parse_affix_list,
    parse_affix_token,
    write_payload_to_save,
)


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


def test_parse_affix_tokens_by_id_name_and_alias():
    assert parse_affix_token("0x19") == 25
    assert parse_affix_token("Mana Burn") == 25
    assert parse_affix_token("manahit") == 25
    assert parse_affix_token("aura") == 30


def test_parse_affix_list_requires_exactly_five():
    assert parse_affix_list("extra strong,fire enchanted,cursed,mana burn,extra fast") == bytes(
        [5, 9, 7, 25, 6]
    )
    with pytest.raises(ValueError, match="exactly 5"):
        parse_affix_list("5,6,7")


def test_mutate_payload_updates_high_confidence_fields():
    payload = (FIXTURES / "demon_block_b.bin").read_bytes()

    mutated = mutate_payload(
        payload,
        monster_hcidx=347,
        monster_seed=0x0018AB90,
        bind_level=20,
        affixes=bytes([5, 9, 7, 25, 6]),
        zero_volatile=True,
    )

    fields = parse_demon_payload(mutated)
    assert fields.monster_hcidx == 347
    assert fields.monster_seed == 0x0018AB90
    assert fields.bind_demon_level == 20
    assert fields.affix_indices == bytes([5, 9, 7, 25, 6])
    assert mutated[89:92] == b"\0\0\0"


def test_write_payload_to_save_preserves_bridge_and_checksum(tmp_path):
    original_payload = (FIXTURES / "demon_block_b.bin").read_bytes()
    source = tmp_path / "source.d2s"
    output = tmp_path / "output.d2s"
    source.write_bytes(_minimal_save_with_follower(original_payload))

    mutated = mutate_payload(original_payload, affixes=bytes([5, 9, 7, 27, 30]))
    write_payload_to_save(source, output, mutated)

    out = output.read_bytes()
    assert int.from_bytes(out[0x08:0x0C], "little") == len(out)
    assert int.from_bytes(out[0x0C:0x10], "little") == calc_checksum(out)
    block = decode_follower_block(out)
    assert block.follower_count == 1
    assert block.payload == mutated
