"""Identity-only Developer Mode, settings, restart, and shared-header contracts."""
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
settings_source = (ROOT / "settings_manager.py").read_text(encoding="utf-8")

for forbidden in (
    "lexerMode", "lex-lexer-mode", "I am Lexer", "I AM LEXER",
    "save_lexer_setting_defaults", "save_lexer_defaults",
):
    assert forbidden not in framework, forbidden
    assert forbidden not in desktop, forbidden
    assert forbidden not in settings_source, forbidden

for required in (
    'id: "plugin-github"', 'id: "plugin-restart"', 'class: "lex-developer-actions"',
    '"lexeditor-settings-changed"', 'discardLabel: "Restart Without Saving"',
    'saveLabel: "Save and Restart"', 'class:"lex-settings-columns"',
    'save_developer_setting_defaults', 'developerActive = !!settings.developerMode',
    'copy.addEventListener("dblclick"', 'bindSettingDependencies',
):
    assert required in framework, required
assert "developerActions, windowControls.root" in framework
assert ".lex-developer-actions" in css and ".lex-developer-button" in css
assert "lex-setting-dependency-arrows" in css
assert "def restart_plugin" in desktop
assert "def save_developer_setting_defaults" in desktop
assert 'payload["developerMode"] = authorized' in desktop
assert 'payload["developerLogin"]' in desktop
assert 'id="chooser-restart"' in chooser and "restart_lexeditor()" in chooser
assert "restartButton.hidden=!settings?.developerMode" in chooser
assert 'lexerButton.textContent="DEV"' in chooser
assert "const restartIcon = () =>" in framework and "M16.59 5.45" in framework
assert "M16.59 5.45" in chooser and "M20 11a8" not in chooser
assert 'plugin.plugin_id == "blank" and not developer_mode' in desktop


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


class FakeGithub:
    def __init__(self, authorized=True):
        self.authorized = authorized

    def visible_repository(self, repository, refresh=False):
        if not self.authorized:
            return None
        return {"repository": repository.full_name, "login": "Lexer-Lux"}


with tempfile.TemporaryDirectory(prefix="lexeditor-developer-mode-", ignore_cleanup_errors=True) as temp_name:
    root = Path(temp_name)
    path = root / "settings.json"
    defaults_path = root / "default_settings.json"
    defaults_path.write_text(json.dumps({"tableRowsPerPage": 18}), encoding="utf-8")
    # Old mode keys are tolerated only as ignored migration debris.
    path.write_text(json.dumps({
        "version": 7, "updateCheckFrequency": "weekly",
        "developerMode": False, "lexerMode": True,
    }), encoding="utf-8")
    settings = SettingsStore(path, defaults_path)
    snapshot = settings.snapshot()
    assert "developerMode" not in snapshot and "lexerMode" not in snapshot
    assert snapshot["tableRowsPerPage"] == 18
    settings.save("daily")
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert "developerMode" not in stored and "lexerMode" not in stored
    settings.save_packaged_defaults({"tableRowsPerPage": 22})
    packaged = SettingsStore(root / "new-user.json", defaults_path).snapshot()
    assert packaged["tableRowsPerPage"] == 22
    assert "developerMode" not in packaged

    plugin = GamePlugin(
        "test", "Test", "TEST", "Test", "#fff", lambda: [], lambda: None,
        session_factory=FakeSession,
    )
    host = HostApi(
        {"test": plugin}, enforce_installations=False, auto_scan=False,
        settings=settings, github=FakeGithub(),
    )
    identity = host.lexeditor_settings()
    assert identity["developerMode"] and identity["developerAuthorized"]
    assert identity["developerLogin"] == "Lexer-Lux"

    saved = host.save_lexeditor_settings({
        "updateCheckFrequency": "daily", "soundVolumePercent": 37,
    })
    assert saved["soundVolumePercent"] == 37 and saved["developerMode"]
    saved = host.save_developer_setting_defaults({"soundVolumePercent": 37})
    assert saved["defaultValues"]["soundVolumePercent"] == 37
    saved = host.save_developer_setting_defaults({"tableRowsPerPage": 24})
    assert saved["defaultValues"]["tableRowsPerPage"] == 24

    blocked = HostApi(
        {"test": plugin}, enforce_installations=False, auto_scan=False,
        settings=settings, github=FakeGithub(False),
    )
    assert not blocked.lexeditor_settings()["developerMode"]
    try:
        blocked.save_developer_setting_defaults({"tableRowsPerPage": 20})
    except PermissionError:
        pass
    else:
        raise AssertionError("Packaged defaults bypassed Developer Mode authorization")

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
        def __init__(self): self.destroyed = False
        def destroy(self): self.destroyed = True

    fake_window = FakeWindow()
    host.bind_window(fake_window)
    assert host.restart_lexeditor()["restarting"]
    assert host._restart_requested and fake_window.destroyed
    host.stop()
    assert second_session.stopped

print("Identity-only Developer Mode, packaged defaults, and restart contracts passed")
