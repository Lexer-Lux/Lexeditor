"""Contract for the shared settings-only save control (GitHub #68)."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def require(text: str, token: str, source: Path) -> None:
    if token not in text:
        raise AssertionError(f"{source.relative_to(ROOT)} is missing {token!r}")


def main() -> int:
    framework_path = ROOT / "ui" / "framework.js"
    framework = framework_path.read_text(encoding="utf-8")
    for token in (
        "const settingsSaveControl = (options = {}) =>",
        "class: \"save lex-save-icon lex-settings-save-control\"",
        "dirtyCount: settingsDirtyCount",
        "confirmDiscardChanges({",
        "if (event.target === backdrop && !settingsDirtyCount()) close();",
        'callWindow("save_lexeditor_settings", {...values, })',
        "const supportsDefault = definition =>",
        "supportedDefaultDefinitions.map(definition =>",
        "Restart LEXEDITOR to enable newly added settings.",
        "dialog.classList.toggle(\"lex-settings-must-scroll\"",
        "settingsSaveControl,",
    ):
        require(framework, token, framework_path)
    if "Managed helpers" in framework or "lex-helper-status" in framework:
        raise AssertionError("Game-managed helpers do not belong in global Settings")

    host_path = ROOT / "desktop_host.py"
    host = host_path.read_text(encoding="utf-8")
    if 'payload["helpers"]' in host:
        raise AssertionError("The global settings payload must not collect game helper status")

    ff8_path = ROOT / "games" / "ff8" / "editor.html"
    ff8 = ff8_path.read_text(encoding="utf-8")
    for token in ('lex-information-panel ff8-information', "runtime.version"):
        require(ff8, token, ff8_path)

    adopters = {
        "games/warband/editor.html": ("Object.keys(state.settingEdits).length", "save:saveSettings", "discard:discardSettings"),
        "games/rdr/editor.html": ("Object.keys(state.settingEdits).length", "save:saveSettings", "discard:discardSettings"),
        "games/rdr2/editor.html": ("Object.keys(state.settingEdits).length", "save:saveSettings", "discard:discardSettings"),
    }
    for relative, tokens in adopters.items():
        path = ROOT / relative
        source = path.read_text(encoding="utf-8")
        require(source, "LexeditorUI.settingsSaveControl({", path)
        for token in tokens:
            require(source, token, path)

    if "settingsSaveControl" in ff8:
        raise AssertionError(
            "FF8 Tweaks must use the plugin-wide Save control, not a separate settings save control"
        )

    chooser_path = ROOT / "ui" / "chooser.html"
    chooser = chooser_path.read_text(encoding="utf-8")
    for token in (
        "--lex-resident-handle-width",
        "stroke-width:6.5",
        "residentHandleWidthPercent",
    ):
        require(chooser, token, chooser_path)

    manager_path = ROOT / "settings_manager.py"
    manager = manager_path.read_text(encoding="utf-8")
    require(manager, '"residentHandleWidthPercent": 5.0', manager_path)
    require(manager, "max(2.5, min(12.0, resident_handle_width_percent))", manager_path)
    require(manager, '"mainMenuHeightPercent": 9.0', manager_path)
    require(manager, "max(3.0, min(20.0, main_menu_height_percent))", manager_path)
    require(manager, '"soundEnabled": True', manager_path)
    require(manager, '"soundVolumePercent": 50.0', manager_path)
    require(manager, '"soundVolumePercent", defaults["soundVolumePercent"],', manager_path)
    require(manager, '"globalMessageRarity": 3.0', manager_path)
    require(manager, '"loadingTransitionMinimumSeconds": 1.5', manager_path)

    print("Shared settings save control and responsive resident handle contract passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
