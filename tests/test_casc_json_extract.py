"""Verify extract_vanilla includes JSON string files."""
import os
import pytest

VANILLA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "vanilla")

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(
        not os.path.isdir(VANILLA_DIR),
        reason="vanilla/ not extracted (run 'd2r-mod extract')",
    ),
]


class TestJsonStringExtraction:
    def test_item_names_json_extracted(self):
        path = os.path.join(VANILLA_DIR, "data", "local", "lng", "strings", "item-names.json")
        assert os.path.exists(path), "item-names.json not extracted from CASC"

    def test_mercenaries_json_extracted(self):
        path = os.path.join(VANILLA_DIR, "data", "local", "lng", "strings", "mercenaries.json")
        assert os.path.exists(path), "mercenaries.json not extracted from CASC"

    def test_ui_json_extracted(self):
        path = os.path.join(VANILLA_DIR, "data", "local", "lng", "strings", "ui.json")
        assert os.path.exists(path), "ui.json not extracted from CASC"

    def test_next_string_id_extracted(self):
        path = os.path.join(VANILLA_DIR, "data", "local", "lng", "next_string_id.txt")
        assert os.path.exists(path), "next_string_id.txt not extracted from CASC"

    def test_item_names_valid_json(self):
        import json
        path = os.path.join(VANILLA_DIR, "data", "local", "lng", "strings", "item-names.json")
        with open(path, encoding="utf-8-sig") as f:
            entries = json.load(f)
        assert isinstance(entries, list)
        assert len(entries) > 1000
        assert all("id" in e and "Key" in e and "enUS" in e for e in entries[:10])
