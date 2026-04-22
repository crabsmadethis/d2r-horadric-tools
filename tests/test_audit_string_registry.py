"""Tests for the expansionstring audit tool."""
import json
import os

import pytest

from tools.audit_string_registry import categorize_entry, build_report

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_categorize_identity_in_vanilla_json():
    """An entry whose key/value matches a vanilla JSON enUS is 'vanilla_identity'."""
    vanilla_index = {"Cold Rupture": ("item-names.json", "Cold Rupture")}
    patches_keys = set()
    result = categorize_entry("Cold Rupture", "Cold Rupture",
                              vanilla_index, patches_keys)
    assert result["category"] == "vanilla_identity"
    assert result["json_file"] == "item-names.json"


def test_categorize_covered_by_patches():
    """An entry absent from vanilla JSON but present in patches is 'patch_covered'."""
    vanilla_index = {}
    patches_keys = {"Flamekeeper's Antlers"}
    result = categorize_entry("Flamekeeper's Antlers", "Flamekeeper's Antlers",
                              vanilla_index, patches_keys)
    assert result["category"] == "patch_covered"


def test_categorize_needs_override():
    """An entry whose value differs from vanilla enUS is 'needs_override'."""
    vanilla_index = {"Cold Rupture": ("item-names.json", "Cold Rupture")}
    patches_keys = set()
    result = categorize_entry("Cold Rupture", "FROSTMOURNE",
                              vanilla_index, patches_keys)
    assert result["category"] == "needs_override"


def test_categorize_orphan():
    """An entry absent from vanilla JSON and patches is 'orphan'."""
    vanilla_index = {}
    patches_keys = set()
    result = categorize_entry("Nonexistent", "Nonexistent",
                              vanilla_index, patches_keys)
    assert result["category"] == "orphan"


@pytest.mark.slow
@pytest.mark.integration
def test_report_post_audit_expansionstring_empty():
    """Post-audit (2026-04-22) the build pipeline skips JSON-served names, so
    the expansionstring table is either absent from the registry or empty.
    A non-empty expansionstring means a name leaked through that JSON doesn't
    serve — investigate via `python3 -m tools.audit_string_registry`.
    """
    report = build_report(
        registry_path=os.path.join(REPO, "build", "string_registry.json"),
        vanilla_strings_dir=os.path.join(REPO, "vanilla", "data", "local", "lng", "strings"),
        patches_dir=os.path.join(REPO, "patches", "json_strings"),
    )
    expansionstring = report["tables"].get("expansionstring", {})
    total = sum(len(v) for v in expansionstring.values()) if expansionstring else 0
    assert total == 0, (
        f"expected empty expansionstring, got {total} entries. "
        f"Run `python3 -m tools.audit_string_registry` to inspect."
    )


@pytest.mark.slow
@pytest.mark.integration
def test_categorization_on_synthetic_pre_audit_registry(tmp_path):
    """Categorize the historical (pre-2026-04-22) 45-entry registry shape
    against current vanilla JSON + patches: 23 vanilla_identity + 14 needs_override
    + 8 patch_covered. Locks in the audit tool's classification behavior.
    """
    import json
    historical = {
        "expansionstring": {n: n for n in [
            # 23 vanilla_identity
            "Expansion", "Cold Rupture", "Flame Rift", "Crack of the Heavens",
            "Rotting Fissure", "Bone Break", "Black Cleft", "Ars Tor'Baalos",
            "Ars Dul'Mephistos", "Measured Wrath", "Dreadfang", "Wraithstep",
            "Bloodpact Shard", "Sling", "Opalvein", "Entropy Locket",
            "Gheed's Wager", "Defender's Bile", "Guardian's Thunder",
            "Protector's Frost", "Defender's Fire", "Protector's Stone",
            "Guardian's Light",
            # 14 needs_override (TBL writes that disagree with vanilla JSON enUS)
            "Ars Al'Diablolos", "Unique Warlock Helm",
            "PreCrafted Cold Rupture", "Crafted Cold Rupture",
            "PreCrafted Flame Rift", "PreCrafted Crack of the Heavens",
            "PreCrafted Rotting Fissure", "PreCrafted Bone Break",
            "PreCrafted Black Cleft", "Crafted Flame Rift",
            "Crafted Crack of the Heavens", "Crafted Rotting Fissure",
            "Crafted Bone Break", "Crafted Black Cleft",
            # 8 patch_covered
            "Elite Uniques", "Warlock Class Pack", "Flamekeeper's Antlers",
            "Thunderhurler's Grip", "Hawkeye's Sight", "Deathgrip Scepter",
            "Crusader's Vengeance", "Manoomin",
        ]}
    }
    snapshot = tmp_path / "string_registry.json"
    snapshot.write_text(json.dumps(historical))
    report = build_report(
        registry_path=str(snapshot),
        vanilla_strings_dir=os.path.join(REPO, "vanilla", "data", "local", "lng", "strings"),
        patches_dir=os.path.join(REPO, "patches", "json_strings"),
    )
    expansionstring = report["tables"]["expansionstring"]
    by_cat = {c: len(expansionstring[c]) for c in expansionstring}
    assert by_cat.get("vanilla_identity", 0) == 23
    assert by_cat.get("needs_override", 0) == 14
    assert by_cat.get("patch_covered", 0) == 8
    assert by_cat.get("orphan", 0) == 0
