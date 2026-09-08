"""Regression coverage for FF8 field-map asset pairing and optional SYM data."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from games.ff8 import field_data


class FieldAssetTests(unittest.TestCase):
    def test_jsm_without_sym_is_valid_but_orphan_sym_is_not(self):
        field_data._validate_asset_relationships("test/map", {"jsm"})
        with self.assertRaisesRegex(ValueError, r"test/map.*missing JSM"):
            field_data._validate_asset_relationships("test/map", {"sym"})

    def test_true_pairs_report_exact_missing_component(self):
        with self.assertRaisesRegex(ValueError, r"test/map.*missing MIM"):
            field_data._validate_asset_relationships("test/map", {"map"})
        with self.assertRaisesRegex(ValueError, r"test/map.*missing MRT"):
            field_data._validate_asset_relationships("test/map", {"rat"})

    def test_inner_asset_resolver_accepts_unique_alias_and_rejects_ambiguity(self):
        exact = {"name": r"nested\\mapa.jsm", "basename": "mapa.jsm"}
        alias = {"name": r"nested\\different.sym", "basename": "different.sym"}
        entries = [exact, alias]
        self.assertIs(field_data._memory_entry_for_map(entries, "mapa", "jsm", "grp/mapa"), exact)
        self.assertIs(field_data._memory_entry_for_map(entries, "mapa", "sym", "grp/mapa"), alias)
        entries.append({"name": r"other\\second.sym", "basename": "second.sym"})
        with self.assertRaisesRegex(ValueError, r"grp/mapa.*ambiguous SYM"):
            field_data._memory_entry_for_map(entries, "mapa", "sym", "grp/mapa")

    def test_map_rows_parses_jsm_with_empty_sym_metadata(self):
        key = "grp/mapa"
        row = {"id": 1, "key": key, "name": "mapa", "group": "grp",
               "mapId": None, "listed": False}
        scripts = {"header": {}, "groups": [], "methods": [],
                   "opcodeCount": len(field_data.field_scripts.OPCODE_NAMES)}
        with tempfile.TemporaryDirectory() as name:
            jsm = Path(name) / "mapa.jsm"
            jsm.write_bytes(b"JSM")
            with patch.object(field_data, "_map_row", return_value=row), \
                 patch.object(field_data, "_source_paths", return_value=(jsm, None)), \
                 patch.object(field_data, "_inf_source_path", return_value=None), \
                 patch.object(field_data, "_dialogue_source_path", return_value=None), \
                 patch.object(field_data, "_walkmesh_source_path", return_value=None), \
                 patch.object(field_data, "_background_source_paths", return_value=(None, None)), \
                 patch.object(field_data, "_encounter_source_paths", return_value=(None, None)), \
                 patch.object(field_data.field_scripts, "read", return_value=scripts) as read_scripts, \
                 patch.object(field_data, "_parse_card_players", return_value=[{"id": 0}]) as players:
                result = field_data.map_rows(key)
            read_scripts.assert_called_once_with(b"JSM", b"")
            players.assert_called_once_with(b"JSM", b"")
            self.assertEqual(result["players"], [{"id": 0}])
            self.assertEqual(result["scripts"], scripts)

    def test_script_rebuild_does_not_require_sym(self):
        key = "grp/mapa"
        row = {"id": 1, "key": key, "name": "mapa", "group": "grp",
               "mapId": None, "listed": False}
        documents = [{"id": 0, "source": "return"}]
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            jsm = root / "mapa.jsm"
            jsm.write_bytes(b"JSM")
            with patch.object(field_data, "_map_row", return_value=row), \
                 patch.object(field_data, "_source_paths", return_value=(jsm, None)), \
                 patch.object(field_data.paths, "DIRECT_ROOT", root / "direct"), \
                 patch.object(field_data.field_scripts, "rebuild", return_value=(b"rebuilt", 1)) as rebuild:
                destination, raw, changed = field_data._prepare_script_documents(key, documents)
            rebuild.assert_called_once_with(b"JSM", b"", documents)
            self.assertEqual(raw, b"rebuilt")
            self.assertEqual(changed, 1)
            self.assertEqual(destination.name, "mapa.jsm")


if __name__ == "__main__":
    unittest.main()
