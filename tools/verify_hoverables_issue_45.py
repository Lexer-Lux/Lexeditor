"""Shared source and local-settings contract for global hoverables."""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from settings_manager import SettingsStore  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    framework = (ROOT / "ui" / "framework.js").read_text(encoding="utf-8")
    css = (ROOT / "ui" / "framework.css").read_text(encoding="utf-8")
    desktop = (ROOT / "desktop_host.py").read_text(encoding="utf-8")
    settings_source = (ROOT / "settings_manager.py").read_text(encoding="utf-8")
    ff8 = (ROOT / "games" / "ff8" / "editor.html").read_text(encoding="utf-8")
    require("const hoverable = options =>" in framework and "hoverable," in framework,
            "the shared framework must own and export hoverables")
    require('class: ["lex-hoverable"' in framework,
            "every plugin relationship must receive one semantic class")
    require("hoverableAltClickEnabled()" in framework and "event.altKey" in framework,
            "the shared activation path must apply the Alt+Click policy")
    require('event.detail === 0' in framework,
            "keyboard activation must remain available in Alt+Click mode")
    require('"data-hover-target-type"' in framework and '"data-hover-target-id"' in framework,
            "hoverables must expose typed stable target identity")
    require(".lex-hoverable:hover" in css and ".lex-hoverable:focus-visible" in css,
            "hover and keyboard focus must show the same visible link feedback")
    require("box-shadow: inset 0 0 0 1px var(--lex-highlight)" not in css,
            "a hoverable must have one highlight border, not a doubled inner outline")
    require("hoverableAltClick" in settings_source and "hoverableAltClick" in desktop,
            "the native settings bridge must carry the global modifier policy")
    require("Alt + Click hoverable linking" in framework,
            "the global settings dialog must expose the requested setting")
    require('targetType:"gf"' in ff8 and 'targetType:"item"' in ff8,
            "FF8 must use typed GF and Item relationships")
    require("state.selected.gfs=gf.id" in ff8 and "state.selected.items=item.id" in ff8,
            "FF8 relationships must select exact stable records before navigation")

    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "settings.json"
        store = SettingsStore(path)
        require(store.snapshot()["hoverableAltClick"] is False,
                "Alt+Click hoverable linking must be disabled by default")
        store.save("daily", hoverable_alt_click=True)
        require(SettingsStore(path).snapshot()["hoverableAltClick"] is True,
                "the per-user setting must survive a new settings store")
        store.save("weekly", True)
        reread = SettingsStore(path).snapshot()
        require(reread["hoverableAltClick"] is True,
                "older save callers must preserve the hoverable policy")
        require(reread["developerMode"] is True and reread["updateCheckFrequency"] == "weekly",
                "the new policy must not corrupt other global settings")
    print("Global hoverable source and settings contract passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
