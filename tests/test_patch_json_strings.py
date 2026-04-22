"""Tests for JSON string patching."""
import json
import os
import pytest
import yaml


class TestPatchJsonStrings:
    def _make_vanilla(self, tmp_path, filename, entries):
        """Create a vanilla JSON string file (UTF-8-BOM, matching D2R)."""
        strings_dir = tmp_path / "vanilla" / "data" / "local" / "lng" / "strings"
        strings_dir.mkdir(parents=True, exist_ok=True)
        path = strings_dir / filename
        with open(path, "w", encoding="utf-8-sig") as f:
            json.dump(entries, f, ensure_ascii=False)
        return str(tmp_path / "vanilla")

    def _make_next_id(self, tmp_path, next_id):
        """Create next_string_id.txt in vanilla dir."""
        lng_dir = tmp_path / "vanilla" / "data" / "local" / "lng"
        lng_dir.mkdir(parents=True, exist_ok=True)
        path = lng_dir / "next_string_id.txt"
        path.write_text(f"NEXT VALID ID\n\n{next_id}\n")
        return next_id

    def _make_patch(self, tmp_path, filename, target, entries):
        """Create a YAML patch spec."""
        patches_dir = tmp_path / "patches" / "json_strings"
        patches_dir.mkdir(parents=True)
        spec = {"target": target, "entries": entries}
        path = patches_dir / filename
        path.write_text(yaml.dump(spec))
        return str(patches_dir)

    def test_appends_new_entries(self, tmp_path):
        from d2r_mod.build_steps.patch_json_strings import run

        vanilla_entries = [
            {"id": 100, "Key": "existing", "enUS": "Existing Item"},
        ]
        vanilla_dir = self._make_vanilla(tmp_path, "item-names.json", vanilla_entries)
        self._make_next_id(tmp_path, 28105)
        build_dir = str(tmp_path / "build")
        os.makedirs(build_dir)
        patches_dir = self._make_patch(tmp_path, "test.yaml", "item-names.json", [
            {"key": "Manoomin", "value": "Manoomin"},
            {"key": "CustomSword", "value": "Blade of Testing"},
        ])

        result = run(patches_dir, vanilla_dir, build_dir)

        assert result["added"] == 2
        out_path = os.path.join(
            build_dir, "data", "local", "lng", "strings", "item-names.json"
        )
        assert os.path.exists(out_path)
        with open(out_path, encoding="utf-8-sig") as f:
            patched = json.load(f)
        assert len(patched) == 3
        new_entries = {e["Key"]: e for e in patched if e["Key"] != "existing"}
        assert "Manoomin" in new_entries
        assert new_entries["Manoomin"]["enUS"] == "Manoomin"
        assert new_entries["Manoomin"]["id"] == 28105
        assert new_entries["CustomSword"]["id"] == 28106

    def test_overrides_existing_key(self, tmp_path):
        from d2r_mod.build_steps.patch_json_strings import run

        vanilla_entries = [
            {"id": 100, "Key": "existing", "enUS": "Old Value", "zhTW": "keep"},
        ]
        vanilla_dir = self._make_vanilla(tmp_path, "item-names.json", vanilla_entries)
        self._make_next_id(tmp_path, 28105)
        build_dir = str(tmp_path / "build")
        os.makedirs(build_dir)
        patches_dir = self._make_patch(tmp_path, "test.yaml", "item-names.json", [
            {"key": "existing", "value": "New Value"},
        ])

        result = run(patches_dir, vanilla_dir, build_dir)

        assert result["added"] == 0
        assert result["overridden"] == 1
        out_path = os.path.join(
            build_dir, "data", "local", "lng", "strings", "item-names.json"
        )
        with open(out_path, encoding="utf-8-sig") as f:
            patched = json.load(f)
        # Same key, enUS replaced, id preserved, other locales untouched
        match = [e for e in patched if e["Key"] == "existing"]
        assert len(match) == 1
        assert match[0]["enUS"] == "New Value"
        assert match[0]["id"] == 100
        assert match[0]["zhTW"] == "keep"

    def test_unchanged_when_value_matches(self, tmp_path):
        from d2r_mod.build_steps.patch_json_strings import run

        vanilla_entries = [
            {"id": 100, "Key": "existing", "enUS": "Same Value"},
        ]
        vanilla_dir = self._make_vanilla(tmp_path, "item-names.json", vanilla_entries)
        self._make_next_id(tmp_path, 28105)
        build_dir = str(tmp_path / "build")
        os.makedirs(build_dir)
        patches_dir = self._make_patch(tmp_path, "test.yaml", "item-names.json", [
            {"key": "existing", "value": "Same Value"},
        ])

        result = run(patches_dir, vanilla_dir, build_dir)

        assert result["added"] == 0
        assert result["overridden"] == 0
        assert result["unchanged"] == 1

    def test_multiple_targets(self, tmp_path):
        from d2r_mod.build_steps.patch_json_strings import run

        self._make_vanilla(tmp_path, "item-names.json", [
            {"id": 100, "Key": "item1", "enUS": "Item 1"},
        ])
        self._make_vanilla(tmp_path, "mercenaries.json", [
            {"id": 200, "Key": "merc01", "enUS": "OldMerc"},
        ])
        vanilla_dir = str(tmp_path / "vanilla")
        self._make_next_id(tmp_path, 28105)
        build_dir = str(tmp_path / "build")
        os.makedirs(build_dir)

        patches_dir = tmp_path / "patches" / "json_strings"
        patches_dir.mkdir(parents=True)
        (patches_dir / "items.yaml").write_text(yaml.dump({
            "target": "item-names.json",
            "entries": [{"key": "NewItem", "value": "New Item"}],
        }))
        (patches_dir / "mercs.yaml").write_text(yaml.dump({
            "target": "mercenaries.json",
            "entries": [{"key": "merc_a4_01", "value": "Auriel"}],
        }))

        result = run(str(patches_dir), vanilla_dir, build_dir)

        assert result["added"] == 2
        items_out = os.path.join(
            build_dir, "data", "local", "lng", "strings", "item-names.json"
        )
        mercs_out = os.path.join(
            build_dir, "data", "local", "lng", "strings", "mercenaries.json"
        )
        assert os.path.exists(items_out)
        assert os.path.exists(mercs_out)

    def test_ids_globally_unique_across_targets(self, tmp_path):
        from d2r_mod.build_steps.patch_json_strings import run

        self._make_vanilla(tmp_path, "item-names.json", [
            {"id": 100, "Key": "item1", "enUS": "Item 1"},
        ])
        self._make_vanilla(tmp_path, "mercenaries.json", [
            {"id": 200, "Key": "merc01", "enUS": "OldMerc"},
        ])
        vanilla_dir = str(tmp_path / "vanilla")
        self._make_next_id(tmp_path, 28105)
        build_dir = str(tmp_path / "build")
        os.makedirs(build_dir)

        patches_dir = tmp_path / "patches" / "json_strings"
        patches_dir.mkdir(parents=True)
        (patches_dir / "a_items.yaml").write_text(yaml.dump({
            "target": "item-names.json",
            "entries": [{"key": "A", "value": "A"}, {"key": "B", "value": "B"}],
        }))
        (patches_dir / "b_mercs.yaml").write_text(yaml.dump({
            "target": "mercenaries.json",
            "entries": [{"key": "C", "value": "C"}],
        }))

        result = run(str(patches_dir), vanilla_dir, build_dir)

        all_ids = set()
        for fname in ["item-names.json", "mercenaries.json"]:
            path = os.path.join(
                build_dir, "data", "local", "lng", "strings", fname
            )
            with open(path, encoding="utf-8-sig") as f:
                for e in json.load(f):
                    assert e["id"] not in all_ids, f"Duplicate ID {e['id']}"
                    all_ids.add(e["id"])

    def test_dedupes_across_yaml_files(self, tmp_path):
        from d2r_mod.build_steps.patch_json_strings import run

        vanilla_entries = [
            {"id": 100, "Key": "existing", "enUS": "Existing"},
        ]
        vanilla_dir = self._make_vanilla(tmp_path, "item-names.json", vanilla_entries)
        self._make_next_id(tmp_path, 28105)
        build_dir = str(tmp_path / "build")
        os.makedirs(build_dir)

        patches_dir = tmp_path / "patches" / "json_strings"
        patches_dir.mkdir(parents=True)
        (patches_dir / "a_first.yaml").write_text(yaml.dump({
            "target": "item-names.json",
            "entries": [{"key": "DupeKey", "value": "First"}],
        }))
        (patches_dir / "b_second.yaml").write_text(yaml.dump({
            "target": "item-names.json",
            "entries": [{"key": "DupeKey", "value": "Second"}],
        }))

        result = run(str(patches_dir), vanilla_dir, build_dir)

        # Second YAML overrides first; 1 added (new key), 1 overridden
        assert result["added"] == 1
        assert result["overridden"] == 1
        out_path = os.path.join(
            build_dir, "data", "local", "lng", "strings", "item-names.json"
        )
        with open(out_path, encoding="utf-8-sig") as f:
            patched = json.load(f)
        dupe_entries = [e for e in patched if e["Key"] == "DupeKey"]
        assert len(dupe_entries) == 1
        assert dupe_entries[0]["enUS"] == "Second"

    def test_no_patches_dir_is_noop(self, tmp_path):
        from d2r_mod.build_steps.patch_json_strings import run

        result = run(str(tmp_path / "nonexistent"), str(tmp_path), str(tmp_path / "build"))
        assert result["added"] == 0
        assert result["skipped"] == 0

    def test_preserves_vanilla_entries(self, tmp_path):
        from d2r_mod.build_steps.patch_json_strings import run

        vanilla_entries = [
            {"id": 100, "Key": "qf1", "enUS": "Khalim's Flail", "zhTW": "foo"},
            {"id": 101, "Key": "qf2", "enUS": "Khalim's Will", "zhTW": "bar"},
        ]
        vanilla_dir = self._make_vanilla(tmp_path, "item-names.json", vanilla_entries)
        self._make_next_id(tmp_path, 28105)
        build_dir = str(tmp_path / "build")
        os.makedirs(build_dir)
        patches_dir = self._make_patch(tmp_path, "test.yaml", "item-names.json", [
            {"key": "NewKey", "value": "New Value"},
        ])

        run(patches_dir, vanilla_dir, build_dir)

        out_path = os.path.join(
            build_dir, "data", "local", "lng", "strings", "item-names.json"
        )
        with open(out_path, encoding="utf-8-sig") as f:
            patched = json.load(f)
        vanilla_by_key = {e["Key"]: e for e in patched if e["Key"] in ("qf1", "qf2")}
        assert vanilla_by_key["qf1"]["zhTW"] == "foo"
        assert vanilla_by_key["qf2"]["zhTW"] == "bar"

    def test_output_has_utf8_bom(self, tmp_path):
        from d2r_mod.build_steps.patch_json_strings import run

        vanilla_entries = [
            {"id": 100, "Key": "existing", "enUS": "Existing"},
        ]
        vanilla_dir = self._make_vanilla(tmp_path, "item-names.json", vanilla_entries)
        self._make_next_id(tmp_path, 28105)
        build_dir = str(tmp_path / "build")
        os.makedirs(build_dir)
        patches_dir = self._make_patch(tmp_path, "test.yaml", "item-names.json", [
            {"key": "NewKey", "value": "New Value"},
        ])

        run(patches_dir, vanilla_dir, build_dir)

        out_path = os.path.join(
            build_dir, "data", "local", "lng", "strings", "item-names.json"
        )
        with open(out_path, "rb") as f:
            raw = f.read(3)
        assert raw == b"\xef\xbb\xbf", f"Expected UTF-8 BOM, got {raw!r}"
