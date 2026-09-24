"""The FF8 New Game tab stays hidden unless its plugin setting is on."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from plugins.ff8 import editor_settings


class EditorSettingsTests(unittest.TestCase):
    def test_new_game_defaults_to_hidden(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "ff8-editor.json"
            with patch.dict(os.environ, {editor_settings.ENV_VAR: str(target)}):
                self.assertEqual(editor_settings.load(), {"showNewGame": False})
                self.assertFalse(target.exists())

    def test_save_roundtrip_persists_the_toggle(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "ff8-editor.json"
            with patch.dict(os.environ, {editor_settings.ENV_VAR: str(target)}):
                self.assertEqual(editor_settings.save({"showNewGame": True}),
                                 {"showNewGame": True})
                self.assertEqual(editor_settings.load(), {"showNewGame": True})
                self.assertEqual(json.loads(target.read_text(encoding="utf-8")),
                                 {"showNewGame": True})

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
                self.assertEqual(editor_settings.load(), {"showNewGame": False})


if __name__ == "__main__":
    unittest.main()
