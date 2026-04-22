"""build.py must pass json_served_names to register_custom_uniques."""
import json
import os

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.mark.slow
@pytest.mark.integration
def test_expansionstring_registry_empty_after_build():
    """After build, string_registry.json has no expansionstring entries
    (all 45 names are served by JSON and get skipped)."""
    from d2r_mod.build import build_mod
    build_mod(
        vanilla_dir=os.path.join(REPO, "vanilla"),
        overlays_dir=os.path.join(REPO, "overlays"),
        scripts_dir=os.path.join(REPO, "scripts"),
        build_dir=os.path.join(REPO, "build"),
    )
    with open(os.path.join(REPO, "build", "string_registry.json")) as f:
        registry = json.load(f)
    expansionstring = registry.get("expansionstring", {})
    assert expansionstring == {}, (
        f"expected empty expansionstring registry, got {len(expansionstring)} "
        f"entries (first: {list(expansionstring)[:3]})"
    )
