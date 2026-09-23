import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from desktop_host import HostApi
from game_installation import GameInstallationManager
from plugins.palworld.plugin import PLUGIN


class AbsentGameTests(unittest.TestCase):
    def test_missing_saved_palworld_does_not_check_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            missing = root / "Palworld"
            config = root / "installations.json"
            config.write_text(json.dumps({"games": {"palworld": {"root": str(missing)}}}))
            manager = GameInstallationManager({"palworld": PLUGIN}, config, root / "data", auto_scan=False)
            with patch.object(manager, "_discover", return_value=[missing]):
                manager._scan_worker("palworld", 0, str(missing), None)
            self.assertEqual(manager.snapshot("palworld")["status"], "not-added")
            host = HostApi.__new__(HostApi)
            host._installations = manager
            host._enforce_installations = True
            host._projects = Mock()
            host._github = Mock()
            host._plugin_id = None
            host._font_errors = {}
            host._cover_art = Mock()
            with patch("desktop_host.game_version", return_value=""), patch("desktop_host.font_status", return_value={}):
                row = host.plugins()[0]
            self.assertEqual(row["status"], "not-added")
            self.assertFalse(row["canOpen"])
            host._projects.snapshot.assert_not_called()

    def test_existing_incomplete_game_still_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            game = root / "Palworld"
            game.mkdir()
            manager = GameInstallationManager({"palworld": PLUGIN}, root / "config.json", root / "data", auto_scan=False)
            with patch.object(manager, "_discover", return_value=[]):
                manager._scan_worker("palworld", 0, str(game), None)
            self.assertEqual(manager.snapshot("palworld")["status"], "warning")


if __name__ == "__main__":
    unittest.main()
