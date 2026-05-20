from d2r_chargen.bound_demon_registry import (
    bound_demon_registry_public_report,
    build_bound_demon_package_payload,
    get_bound_demon_package,
    list_bound_demon_package_ids,
)
from d2r_chargen.follower_block import demon_payload_unknown_slices, parse_demon_payload


def test_registry_lists_enabled_validated_packages():
    package_ids = list_bound_demon_package_ids()

    assert "row724-black-lancer-seedg-holy-shock-v1" in package_ids


def test_registry_package_records_supported_and_unsupported_dimensions():
    package = get_bound_demon_package("row724-black-lancer-seedg-holy-shock-v1")

    assert package is not None
    assert package.enabled
    assert package.monster_hcidx == 724
    assert package.monster_seed == 0x0008F2C8
    assert package.semantic_claims.generated_name == "Black Break the Tainted"
    assert "arbitrary aura flavor selection" in package.unsupported_dimensions


def test_registry_builds_package_payload():
    payload = build_bound_demon_package_payload(
        "row724-black-lancer-seedg-holy-shock-v1"
    )

    fields = parse_demon_payload(payload)
    slices = demon_payload_unknown_slices(payload)
    assert fields.monster_hcidx == 724
    assert fields.monster_seed == 0x0008F2C8
    assert fields.affix_indices == bytes.fromhex("25 1e 07 1c 05 06 1b")
    assert slices["runtime_stats_24_31"] == bytes.fromhex(
        "02 00 00 00 43 00 00 00"
    )


def test_registry_public_report_is_machine_readable():
    report = bound_demon_registry_public_report()

    assert report["schema"] == "bound-demon-validated-packages-v1"
    [package] = report["packages"]
    assert package["package_id"] == "row724-black-lancer-seedg-holy-shock-v1"
    assert package["supported_rows"] == [724]
    assert package["inputs"]["monster_seed"] == "0x0008f2c8"
    assert package["inputs"]["runtime_stats_24_31_hex"] == (
        "02 00 00 00 43 00 00 00"
    )
    assert package["semantic_claims"]["generated_name"] == (
        "Black Break the Tainted"
    )


def test_cli_lists_validated_bound_demon_packages(capsys):
    from d2r_chargen.cli import cmd_bound_demon_packages

    class Args:
        all = False
        json = False

    cmd_bound_demon_packages(Args())
    output = capsys.readouterr().out

    assert "row724-black-lancer-seedg-holy-shock-v1" in output
    assert "Black Break the Tainted" in output
    assert "unsupported:" in output


def test_cli_lists_validated_bound_demon_packages_as_json(capsys):
    import json

    from d2r_chargen.cli import cmd_bound_demon_packages

    class Args:
        all = False
        json = True

    cmd_bound_demon_packages(Args())
    output = json.loads(capsys.readouterr().out)

    assert output["schema"] == "bound-demon-validated-packages-v1"
    assert output["packages"][0]["package_id"] == (
        "row724-black-lancer-seedg-holy-shock-v1"
    )
