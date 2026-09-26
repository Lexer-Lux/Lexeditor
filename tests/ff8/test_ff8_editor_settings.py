"""FF8 editor settings are off unless their plugin setting is turned on."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from plugins.ff8 import editor_settings

OFF = {"showNewGame": False, "delingFieldLayout": False}


class EditorSettingsTests(unittest.TestCase):
    def test_new_game_defaults_to_hidden(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "ff8-editor.json"
            with patch.dict(os.environ, {editor_settings.ENV_VAR: str(target)}):
                self.assertEqual(editor_settings.load(), OFF)
                self.assertFalse(target.exists())

    def test_save_roundtrip_persists_the_toggle(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "ff8-editor.json"
            with patch.dict(os.environ, {editor_settings.ENV_VAR: str(target)}):
                self.assertEqual(editor_settings.save({"showNewGame": True}),
                                 {**OFF, "showNewGame": True})
                self.assertEqual(editor_settings.load(), {**OFF, "showNewGame": True})
                self.assertEqual(json.loads(target.read_text(encoding="utf-8")),
                                 {**OFF, "showNewGame": True})

    def test_deling_field_layout_defaults_off_and_persists(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "ff8-editor.json"
            with patch.dict(os.environ, {editor_settings.ENV_VAR: str(target)}):
                self.assertFalse(editor_settings.load()["delingFieldLayout"])
                editor_settings.save({"delingFieldLayout": True})
                self.assertTrue(editor_settings.load()["delingFieldLayout"])

    def test_unknown_keys_and_non_booleans_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "ff8-editor.json"
            with patch.dict(os.environ, {editor_settings.ENV_VAR: str(target)}):
                with self.assertRaisesRegex(ValueError, "Unknown FF8 editor setting"):
                    editor_settings.save({"showEverything": True})
                with self.assertRaisesRegex(ValueError, "must be true or false"):
                    editor_settings.save({"showNewGame": "yes"})
                with self.assertRaisesRegex(ValueError, "must be an object"):
                    editor_settings.save(["showNewGame"])
                self.assertFalse(target.exists())

    def test_corrupt_file_falls_back_to_hidden(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "ff8-editor.json"
            target.write_text("{not json", encoding="utf-8")
            with patch.dict(os.environ, {editor_settings.ENV_VAR: str(target)}):
                self.assertEqual(editor_settings.load(), OFF)


if __name__ == "__main__":
    unittest.main()
