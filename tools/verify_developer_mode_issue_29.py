"""Settings, restart, and shared-header contracts for Lexeditor issue 29."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from desktop_host import HostApi  # noqa: E402
from plugin_api import GamePlugin  # noqa: E402
from settings_manager import SettingsStore  # noqa: E402


framework = (ROOT / "ui" / "framework.js").read_text(encoding="utf-8")
css = (ROOT / "ui" / "framework.css").read_text(encoding="utf-8")
desktop = (ROOT / "desktop_host.py").read_text(encoding="utf-8")
chooser = (ROOT / "ui" / "chooser.html").read_text(encoding="utf-8")

for required in (
    'key:"developerMode"', 'id:"lex-lexer-mode"', 'id: "plugin-github"', 'id: "plugin-restart"',
    'class: "lex-developer-actions"', '"lexeditor-settings-changed"',
    'discardLabel: "Restart Without Saving"', 'saveLabel: "Save and Restart"',
    'class:"lex-settings-columns"', 'save_lexer_setting_defaults',
    'copy.addEventListener("dblclick"', 'bindSettingDependencies',
):
    assert required in framework, required
assert "developerActions, windowControls.root" in framework
assert ".lex-developer-actions" in css and ".lex-developer-button" in css
assert 'class:"lex-settings-columns"' in framework and ".lex-settings-lane-lexer" in css
assert "lex-setting-dependency-arrows" in css
assert "def restart_plugin" in desktop
assert "def save_lexer_setting_defaults" in desktop
assert "lexerMode" in desktop and "lexerAuthorized" in desktop
assert 'id="chooser-restart"' in chooser and "restart_lexeditor()" in chooser
assert "restartButton.hidden=!settings?.developerMode" in chooser
assert "const restartIcon = () =>" in framework and "M16.59 5.45" in framework
assert "M16.59 5.45" in chooser and "M20 11a8" not in chooser
assert 'plugin.plugin_id == "blank" and not lexer_mode' in desktop


class FakeSession:
    created: list["FakeSession"] = []

    def __init__(self, _environment=None):
        self.index = len(self.created) + 1
        self.url = f"http://127.0.0.1:{9000 + self.index}/"
        self.started = False
        self.stopped = False
        self.created.append(self)

    def start(self) -> dict:
        self.started = True
        return {"pluginId": "test", "hosted": True, "instance": self.index}

    def stop(self) -> None:
        self.stopped = True


with tempfile.TemporaryDirectory(prefix="lexeditor-developer-mode-", ignore_cleanup_errors=True) as temp_name:
    root = Path(temp_name)
    path = root / "settings.json"
    defaults_path = root / "default_settings.json"
    defaults_path.write_text(json.dumps({"tableRowsPerPage": 18}), encoding="utf-8")
    path.write_text(json.dumps({"version": 1, "updateCheckFrequency": "weekly"}), encoding="utf-8")
    settings = SettingsStore(path, defaults_path)
    assert settings.snapshot()["developerMode"] is False
    assert settings.snapshot()["tableRowsPerPage"] == 18
    settings.save("weekly", True)
    assert SettingsStore(path, defaults_path).snapshot()["developerMode"] is True
    settings.save("daily")
    assert SettingsStore(path, defaults_path).snapshot()["developerMode"] is True
    settings.save_lexer_defaults({"tableRowsPerPage": 22, "developerMode": True})
    packaged = SettingsStore(root / "new-user.json", defaults_path).snapshot()
    assert packaged["tableRowsPerPage"] == 22 and packaged["developerMode"] is True

    class FakeGithub:
        def __init__(self, authorized=True):
            self.authorized = authorized

        def visible_repository(self, _repository, refresh=False):
            return {"repository": "Lexer-Lux/Lexeditor", "login": "Lexer-Lux"} if self.authorized else None

    plugin = GamePlugin("test", "Test", "TEST", "Test", "#fff", lambda: [], lambda: None,
                        session_factory=FakeSession)
    host = HostApi({"test": plugin}, enforce_installations=False, auto_scan=False,
                   settings=settings, github=FakeGithub())
    saved = host.save_lexeditor_settings("daily", True, True, False, 650, 15, 1)
    assert saved["lexerMode"] and saved["lexerAuthorized"]
    saved = host.save_lexeditor_settings({
        **saved,
        "soundVolumePercent": 37,
        "lexerMode": True,
    })
    assert saved["soundVolumePercent"] == 37 and saved["lexerMode"]
    saved = host.save_lexer_setting_defaults({"soundVolumePercent": 37})
    assert saved["soundVolumePercent"] == 37
    assert saved["defaultValues"]["soundVolumePercent"] == 37
    saved = host.save_lexer_setting_defaults({"tableRowsPerPage": 24})
    assert saved["defaultValues"]["tableRowsPerPage"] == 24
    first = host.open_plugin("test")
    first_session = FakeSession.created[-1]
    restarted = host.restart_plugin("test")
    second_session = FakeSession.created[-1]
    assert first["url"] != restarted["url"]
    assert first_session.started and first_session.stopped
    assert second_session.started and not second_session.stopped
    try:
        host.restart_plugin("other")
    except ValueError:
        pass
    else:
        raise AssertionError("A non-active plugin restart was accepted")
    class FakeWindow:
        def __init__(self):
            self.destroyed = False
        def destroy(self):
            self.destroyed = True
    fake_window = FakeWindow()
    host.bind_window(fake_window)
    assert host.restart_lexeditor()["restarting"]
    assert host._restart_requested and fake_window.destroyed
    host.stop()
    assert second_session.stopped

print("Developer Mode, top-bar controls, and child restart contracts passed")
