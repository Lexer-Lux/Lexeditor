"""Focused source contract for Lexeditor issue 34."""

from __future__ import annotations

from pathlib import Path
import sys
import threading
import time


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from windows_host import (  # noqa: E402
    APPCOMMAND_BROWSER_BACKWARD, APPCOMMAND_BROWSER_FORWARD, WM_APPCOMMAND,
    WM_XBUTTONDBLCLK, WM_XBUTTONDOWN, WM_XBUTTONUP, XBUTTON1, XBUTTON2,
    appcommand_navigation_event, xbutton_navigation_direction, xbutton_navigation_event,
)
from desktop_host import CHOOSER, HostApi  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    framework = (ROOT / "ui" / "framework.js").read_text(encoding="utf-8")
    host = (ROOT / "desktop_host.py").read_text(encoding="utf-8")
    native = (ROOT / "windows_host.py").read_text(encoding="utf-8")
    worklog = (ROOT / "worklog" / "issues" / "github-34.md").read_text(encoding="utf-8")

    for heading in (
        "Prior failure classes that can recur", "Primary evidence",
        "Sanctioned path", "Execution proof", "Player-visible acceptance boundary",
    ):
        require(heading in worklog, f"issue 34 recurrence audit is missing {heading}")

    require("class NavigationHistory" in framework,
            "the shared framework must own browse history separately from EditHistory")
    require("this.entries.splice(this.index + 1)" in framework,
            "a new destination must discard the stale Forward branch")
    require("async go(direction)" in framework and "this.index + step" in framework,
            "Back and Forward must traverse adjacent history entries")
    require('initial: `tab:${options.activeTab()}`' in framework,
            "history must start at the live plugin destination")
    require('githubWorkspace?.state.open ? "github" : `tab:${options.activeTab()}`' in framework,
            "tabs and the shared GitHub screen must use the same destination history")
    require("window.__lexeditorNavigateHistory = direction => navigationHistory.go(direction)" in framework,
            "the native host must call one shared Back/Forward entry point")
    require("installBrowserHistoryGuard" in framework
            and 'window.addEventListener("popstate", onPopState)' in framework
            and "navigationHistory.go(-1)" in framework,
            "an unconsumed WebView Back must stay in the document and use shared history")
    require("history.pushState(guard" in framework,
            "the WebView history guard must stand before the chooser URL entry")
    require("installExtendedMouseHistory" in framework
            and "event.button !== 3 && event.button !== 4" in framework
            and "navigationHistory.go(event.button === 3 ? -1 : 1)" in framework,
            "unconsumed physical Back and Forward buttons must share the in-page history")
    require("history.back(" not in framework and "history.forward(" not in framework
            and "history.go(" not in framework,
            "plugin history must never use WebView2 URL history")
    require("const historyIcon = direction =>" in framework
            and 'historyIcon("undo")' in framework
            and 'historyIcon("redo")' in framework,
            "Undo and Redo must use the shared SVG icon set")
    require('}, "↶")' not in framework and '}, "↷")' not in framework,
            "history commands must not depend on font arrow glyphs")

    require("return returnToMainMenu(options, leaveForMainMenu)" in framework,
            "the wordmark must remain the guarded Home control")
    require('callWindow("return_to_main_menu")' in framework,
            "guarded Home must still call the host lifecycle owner")
    require("window.__lexeditorNavigating = true" in framework
            and "window.__lexeditorNavigating = false" in framework,
            "an approved Home transition must suppress unload only while navigation is active")
    require("returned.hostNavigates" in framework,
            "Home must trust native navigation instead of a blocked HTTP-to-file redirect")
    require('chooser_url = f"{CHOOSER.as_uri()}#lexTransition=home"' in host
            and '"hostNavigates": True' in host,
            "the host must report that it owns main-menu navigation")
    require("returnToMainMenu = (options, leave) => confirmUnsavedExit" in framework,
            "Home must preserve Save, discard, and cancel protection")

    require("Application.AddMessageFilter" in native and "WM_XBUTTONDOWN" in native,
            "Windows must consume mouse X buttons before WebView2 URL history")
    require('window.run_js(f"window.__lexeditorNavigateHistory?.({direction});")' in native,
            "the native filter must forward only the mapped direction")
    require("IsChild(root_handle, target)" in native,
            "the process-wide message filter must be scoped to the Lexeditor form")
    require("install_mouse_navigation(window)" in host and "api.dispose()" in host,
            "the desktop host must own native-filter installation and cleanup")

    require(xbutton_navigation_direction(WM_XBUTTONDOWN, XBUTTON1 << 16) == -1,
            "XBUTTON1 must map to Back")
    require(xbutton_navigation_direction(WM_XBUTTONDOWN, XBUTTON2 << 16) == 1,
            "XBUTTON2 must map to Forward")
    require(xbutton_navigation_direction(WM_XBUTTONDOWN, 3 << 16) == 0,
            "unknown X buttons must pass through")
    require(xbutton_navigation_direction(0x020C, XBUTTON1 << 16) == 0,
            "only X-button-down may trigger navigation")
    require(xbutton_navigation_event(WM_XBUTTONDOWN, XBUTTON1 << 16) == (True, -1),
            "XBUTTON1 down must be consumed and issue one Back")
    require(xbutton_navigation_event(WM_XBUTTONUP, XBUTTON1 << 16) == (True, 0),
            "XBUTTON1 up must be consumed without a second Back")
    require(xbutton_navigation_event(WM_XBUTTONDBLCLK, XBUTTON2 << 16) == (True, 0),
            "XBUTTON2 double-click must be consumed without a second Forward")
    require(xbutton_navigation_event(WM_XBUTTONUP, 3 << 16) == (False, 0),
            "unrelated extended-button messages must pass through")
    require(appcommand_navigation_event(
        WM_APPCOMMAND, APPCOMMAND_BROWSER_BACKWARD << 16) == (True, -1),
        "browser Back app-command must use Lexeditor history")
    require(appcommand_navigation_event(
        WM_APPCOMMAND, APPCOMMAND_BROWSER_FORWARD << 16) == (True, 1),
        "browser Forward app-command must use Lexeditor history")
    require(appcommand_navigation_event(WM_APPCOMMAND, 3 << 16) == (False, 0),
            "unrelated app-commands must pass through")

    require("exercise_navigation_history" in host
            and 'window.evaluate_js("window.__lexeditorNavigateHistory(-1); true")' in host
            and 'window.evaluate_js("window.__lexeditorNavigateHistory(1); true")' in host,
            "the hidden host must execute both shared history directions")
    require("The wordmark bypassed the guarded Home dialog" in host,
            "the hidden host must prove dirty Home opens the guard")
    require("main-menu-requested-by-wordmark" in host
            and 'wait_for_javascript("document.querySelector(\'#global-save\').disabled")' in host,
            "the hidden host must complete an actual clean wordmark navigation")

    events: list[str] = []
    loaded = threading.Event()

    class Window:
        def load_url(self, url: str) -> None:
            require(url == f"{CHOOSER.as_uri()}#lexTransition=home", "Home loaded the wrong native URL")
            events.append("load")
            loaded.set()

    class Session:
        def stop(self) -> None:
            events.append("stop")

    api = object.__new__(HostApi)
    api._lock = threading.RLock()
    api._window = Window()
    api._session = Session()
    api._plugin_id = "ff8"
    api._dirty_count = 0
    returned = api.return_to_main_menu()
    require(returned.get("hostNavigates") is True, "Home did not claim native navigation")
    require(loaded.wait(2), "a clean Home click never navigated the native window")
    time.sleep(0.1)
    require(events == ["load"], f"Home must keep the resident plugin alive: {events}")

    print("Shared NavigationHistory, native X-button routing, guarded Home, and hidden-host contracts passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
