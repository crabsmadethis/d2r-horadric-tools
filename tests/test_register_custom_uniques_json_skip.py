"""register_custom_uniques must skip names already served by JSON."""
import os
import tempfile

from d2r_mod.assets.tbl import build_tbl, parse_tbl
from d2r_mod.build_steps.register_custom_uniques import run


def _write_uniqueitems(path: str, names: list[str]) -> None:
    with open(path, "w", encoding="latin-1") as f:
        f.write("index\tother\n")
        for n in names:
            f.write(f"{n}\tx\n")


def test_skips_names_present_in_json():
    """A name in vanilla JSON's enUS set must not be added to TBL."""
    with tempfile.TemporaryDirectory() as tmp:
        uniques = os.path.join(tmp, "UniqueItems.txt")
        _write_uniqueitems(uniques, ["Cold Rupture", "Nightstone"])
        tbl_out = os.path.join(tmp, "expansionstring.tbl")
        with open(tbl_out, "wb") as f:
            f.write(build_tbl({}))
        vanilla_keys = set()
        json_served = {"Cold Rupture"}
        result = run(uniques, tbl_out, vanilla_keys,
                     json_served_names=json_served)
        assert result["added"] == 1
        assert result["skipped_json"] == 1

        with open(tbl_out, "rb") as f:
            parsed = parse_tbl(f.read())
        assert "Nightstone" in parsed
        assert "Cold Rupture" not in parsed


def test_backward_compat_when_no_json_set_passed():
    """Calling without json_served_names preserves old behavior (nothing skipped)."""
    with tempfile.TemporaryDirectory() as tmp:
        uniques = os.path.join(tmp, "UniqueItems.txt")
        _write_uniqueitems(uniques, ["Widget"])
        tbl_out = os.path.join(tmp, "expansionstring.tbl")
        with open(tbl_out, "wb") as f:
            f.write(build_tbl({}))
        result = run(uniques, tbl_out, set())
        assert result["added"] == 1
        assert "skipped_json" not in result or result["skipped_json"] == 0
