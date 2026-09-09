"""Global Developer Mode / Restart regressions for issue #29.

These tests cover contracts that do not require a physical desktop session. The
remaining native GUI acceptance stays explicit in the issue rather than being
pretended by source tests.
"""
from __future__ import annotations

from pathlib import Path
import threading
import unittest
from unittest.mock import Mock, call, patch

from desktop_host import HostApi, LEXEDITOR_REPOSITORY
from games.blank.plugin import PLUGIN as BLANK_PLUGIN


ROOT = Path(__file__).resolve().parents[1]


class DeveloperModeHostTests(unittest.TestCase):
    @staticmethod
    def host(identity=None) -> HostApi:
        host = object.__new__(HostApi)
        host._settings = Mock()
        host._settings.snapshot.return_value = {
            "developerMode": True,
            "developerAuthorized": True,
            "developerLogin": "stale-saved-value",
            "soundEnabled": True,
        }
        host._github = Mock()
        host._github.visible_repository.return_value = identity
        return host

    def test_developer_mode_is_identity_fact_not_saved_preference(self):
        host = self.host(None)
        settings = host.lexeditor_settings()
        self.assertFalse(settings["developerMode"])
        self.assertFalse(settings["developerAuthorized"])
        self.assertEqual(settings["developerLogin"], "")
        self.assertTrue(settings["soundEnabled"])
        host._github.visible_repository.assert_called_once_with(LEXEDITOR_REPOSITORY)

        host = self.host({"repository": "Lexer-Lux/Lexeditor", "login": "Lexer-Lux"})
        settings = host.lexeditor_settings()
        self.assertTrue(settings["developerMode"])
        self.assertTrue(settings["developerAuthorized"])
        self.assertEqual(settings["developerLogin"], "Lexer-Lux")

    def test_developer_mode_rechecks_identity_instead_of_latching_owner_state(self):
        identity = {"repository": "Lexer-Lux/Lexeditor", "login": "Lexer-Lux"}
        host = self.host()
        host._github.visible_repository.side_effect = [identity, None]

        first = host.lexeditor_settings()
        second = host.lexeditor_settings()

        self.assertTrue(first["developerMode"])
        self.assertEqual(first["developerLogin"], "Lexer-Lux")
        self.assertFalse(second["developerMode"])
        self.assertFalse(second["developerAuthorized"])
        self.assertEqual(second["developerLogin"], "")
        self.assertEqual(
            host._github.visible_repository.call_args_list,
            [call(LEXEDITOR_REPOSITORY), call(LEXEDITOR_REPOSITORY)],
        )

    def test_packaged_default_write_requires_fresh_owner_authentication(self):
        values = {"soundVolumePercent": 35}
        denied = self.host(None)
        denied._settings.save_packaged_defaults = Mock()
        with self.assertRaisesRegex(PermissionError, "active GitHub account"):
            denied.save_developer_setting_defaults(values)
        denied._github.visible_repository.assert_called_once_with(
            LEXEDITOR_REPOSITORY, refresh=True)
        denied._settings.save_packaged_defaults.assert_not_called()

        identity = {"repository": "Lexer-Lux/Lexeditor", "login": "Lexer-Lux"}
        allowed = self.host(identity)
        allowed._settings.save_packaged_defaults = Mock()
        result = allowed.save_developer_setting_defaults(values)
        allowed._settings.save_packaged_defaults.assert_called_once_with(values)
        self.assertEqual(
            allowed._github.visible_repository.call_args_list,
            [call(LEXEDITOR_REPOSITORY, refresh=True), call(LEXEDITOR_REPOSITORY)],
        )
        self.assertTrue(result["developerMode"])
        self.assertEqual(result["developerLogin"], "Lexer-Lux")

    def test_blank_game_is_owner_only_but_does_not_require_installation(self):
        installation = {
            "root": None,
            "problems": [],
            "status": "ready",
            "statusText": "Ready",
            "canOpen": True,
        }

        def configured(identity):
            host = self.host(identity)
            host._installations = Mock()
            host._installations.rows.return_value = [
                {"plugin": BLANK_PLUGIN, "installation": installation}
            ]
            host._enforce_installations = True
            host._projects = Mock()
            host._plugin_id = None
            host._session = None
            host._dirty_count = 0
            host._font_errors = {}
            host._cover_art = Mock()
            host._cover_art.snapshot.return_value = {"state": "ready", "uri": ""}
            return host

        with patch("desktop_host.game_version", return_value=""), \
             patch("desktop_host.font_status", return_value={}):
            self.assertEqual(configured(None).plugins(), [])
            rows = configured({"repository": "Lexer-Lux/Lexeditor", "login": "Lexer-Lux"}).plugins()

        self.assertEqual([row["id"] for row in rows], ["blank"])
        self.assertTrue(rows[0]["canOpen"])


class RestartHostTests(unittest.TestCase):
    @staticmethod
    def host() -> HostApi:
        host = object.__new__(HostApi)
        host._lock = threading.RLock()
        host._window = Mock()
        host._restart_requested = False
        host._close_authorized = False
        host._plugin_id = "ff8"
        return host

    def test_restart_lexeditor_authorizes_close_and_requests_replacement(self):
        host = self.host()
        self.assertEqual(host.restart_lexeditor(), {"restarting": True})
        self.assertTrue(host._restart_requested)
        self.assertTrue(host._close_authorized)
        host._window.destroy.assert_called_once_with()

    def test_plugin_restart_is_restricted_to_active_plugin(self):
        host = self.host()
        host.open_plugin = Mock(return_value={"id": "ff8", "restarted": True})
        with self.assertRaisesRegex(ValueError, "active plugin"):
            host.restart_plugin("rdr2")
        host.open_plugin.assert_not_called()
        self.assertEqual(host.restart_plugin("ff8"), {"id": "ff8", "restarted": True})
        host.open_plugin.assert_called_once_with("ff8")


class DeveloperModeUiContractTests(unittest.TestCase):
    def test_home_restart_is_hidden_without_developer_identity_and_guards_dirty_resident(self):
        source = (ROOT / "ui" / "chooser.html").read_text(encoding="utf-8")
        self.assertIn("restartButton.hidden=!settings?.developerMode", source)
        self.assertIn("restartButton.hidden=!chooser.settings?.developerMode", source)
        self.assertIn("if(resident&&Number(resident.dirtyCount)>0)", source)
        self.assertIn("await window.pywebview.api.restart_lexeditor()", source)

    def test_plugin_restart_and_shortcut_are_developer_only(self):
        source = (ROOT / "ui" / "framework.js").read_text(encoding="utf-8")
        self.assertIn("restart.hidden = !developerMode", source)
        self.assertIn('letter === "r" && event.shiftKey', source)
        self.assertIn('developerMode ? "restart" : ""', source)
        self.assertIn("setDeveloperMode(value?.developerMode)", source)


if __name__ == "__main__":
    unittest.main()
