"""One WebView2 window and lifecycle owner for every Lexeditor plugin."""

from __future__ import annotations

import json
import os
import random
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

from cover_art import CoverArtCache
from font_manager import font_status, install_missing_fonts
from game_installation import GameInstallationManager
from game_version import game_version
from github_integration import GitHubIntegration
from plugin_api import GamePlugin, GitHubRepository, PluginSession
from project_manager import ProjectManager
import process_probe
from settings_manager import SettingsStore
from windows_host import (
    begin_window_resize, configure_process_identity, configure_window_icon, maximize_to_work_area,
    install_mouse_navigation, native_window_metrics, resize_window_by, restore_from_work_area,
    square_window_edges,
)


ROOT = Path(__file__).resolve().parent
CHOOSER = ROOT / "ui" / "chooser.html"
ICON = ROOT / "assets" / "lexeditor.ico"
STORAGE = ROOT / "out" / "webview2"
WINDOW_STATE_PATH = Path(os.environ.get("LOCALAPPDATA", ROOT / "out")) / "Lexeditor" / "window-state.json"
DEFAULT_WINDOW_BOUNDS = [80, 80, 1440, 900]
LOADING_QUOTES = ROOT / "ui" / "loading_quotes.json"
DEFAULT_VIEWS = ROOT / "ui" / "default_views.json"
LEXEDITOR_REPOSITORY = GitHubRepository(
    full_name="Lexer-Lux/Lexeditor",
    authorized_logins=("Lexer-Lux",),
)
HOME_LINKS = {
    "github": "https://github.com/Lexer-Lux/Lexeditor",
    "twitter": "https://twitter.com/LexerLux",
}


def load_window_geometry(path: Path = WINDOW_STATE_PATH) -> dict:
    """Read one safe restored rectangle and its maximized state."""
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        bounds = [int(value) for value in payload.get("bounds", [])]
        if len(bounds) != 4 or bounds[2] < 900 or bounds[3] < 620:
            raise ValueError("invalid saved window bounds")
        return {"bounds": bounds, "maximized": bool(payload.get("maximized", False))}
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return {"bounds": list(DEFAULT_WINDOW_BOUNDS), "maximized": False}


def save_window_geometry(payload: dict, path: Path = WINDOW_STATE_PATH) -> None:
    """Atomically save the window rectangle outside the WebView cache."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)


EXHAUSTED_QUOTE = ("I'm officially all out of funny loading messages. "
                   "You must really like this program!")


def choose_loading_quote(payload: dict, plugin_id: str, global_rarity: float,
                         chooser=random.choices, used: set[str] | None = None):
    """Choose one game line with down-weighted shared lines.

    `used` collects the lines already shown this session so no message repeats
    until the pool runs dry.
    """
    def clean_lines(key: str) -> list[str]:
        source = payload.get(key, []) if isinstance(payload, dict) else []
        if not isinstance(source, list):
            return []
        return [str(line).strip() for line in source if str(line).strip()]

    # A plugin can borrow another plugin's section, so a game and its remaster
    # share one pool instead of duplicating every line: "shares" maps a plugin
    # id to the sections it draws from as well as its own. Borrowed lines are
    # GAME lines, not global ones - they carry full weight - and a line present
    # in both sections is only offered once.
    shares = payload.get("shares", {}) if isinstance(payload, dict) else {}
    borrowed = shares.get(plugin_id, []) if isinstance(shares, dict) else []
    game_lines = clean_lines(plugin_id)
    if isinstance(borrowed, list):
        seen = set(game_lines)
        for section in borrowed:
            for line in clean_lines(str(section)):
                if line not in seen:
                    seen.add(line)
                    game_lines.append(line)
    global_lines = clean_lines("global")
    try:
        rarity = max(1.0, float(global_rarity))
    except (TypeError, ValueError):
        rarity = 3.0
    if used is not None:
        game_lines = [line for line in game_lines if line not in used]
        global_lines = [line for line in global_lines if line not in used]
    lines = game_lines + global_lines
    if not lines:
        return EXHAUSTED_QUOTE if used is not None else "Loading editor…"
    weights = [1.0] * len(game_lines) + [1.0 / rarity] * len(global_lines)
    chosen = chooser(lines, weights=weights, k=1)[0]
    if used is not None:
        used.add(chosen)
    return chosen


class HostApi:
    """Small bridge exposed to the shared JavaScript framework."""

    def __init__(self, plugins: dict[str, GamePlugin],
                 installation_manager: GameInstallationManager | None = None,
                 enforce_installations: bool = True,
                 auto_scan: bool = True,
                 github: GitHubIntegration | None = None,
                 cover_art: CoverArtCache | None = None,
                 settings: SettingsStore | None = None,
                 projects: ProjectManager | None = None,
                 window_state_path: Path | None = WINDOW_STATE_PATH):
        self._plugins = plugins
        self._installations = installation_manager or GameInstallationManager(
            plugins, auto_scan=auto_scan,
        )
        self._enforce_installations = enforce_installations
        self._github = github or GitHubIntegration()
        self._cover_art = cover_art or CoverArtCache(plugins)
        self._settings = settings or SettingsStore()
        # Loading messages shown this run; a message repeats only once
        # every line has been used.
        self._shown_quotes: set[str] = set()
        self._projects = projects or ProjectManager(plugins)
        self._window_state_path = window_state_path
        self._session: PluginSession | None = None
        self._session_identity: dict | None = None
        self._plugin_id: str | None = None
        self._window = None
        self._maximized = False
        self._restore_bounds: list[int] | None = None
        self._dirty_count = 0
        self._close_authorized = False
        self._main_menu_navigation_error = ""
        self._transition_snapshot = ""
        self._restart_requested = False
        self._font_errors: dict[str, str] = {}
        self._game_processes: dict[str, subprocess.Popen] = {}
        self._mouse_navigation = None
        # Helper versions are read from GitHub only when Lexer opens the panel,
        # and the answer is kept for the rest of the run unless he refreshes.
        self._helper_versions: list[dict] | None = None
        self._lock = threading.RLock()

    def bind_window(self, window, maximized: bool = False) -> None:
        """Bind the one desktop window after pywebview creates it."""
        with self._lock:
            self._window = window
            self._maximized = maximized

    def apply_window_geometry(self, payload: dict) -> None:
        """Apply saved bounds after the native WinForms window exists."""
        bounds = [int(value) for value in payload.get("bounds", DEFAULT_WINDOW_BOUNDS)]
        restore_from_work_area(self._bound_window(), bounds)
        with self._lock:
            self._restore_bounds = list(bounds)
            self._maximized = False
        if payload.get("maximized"):
            geometry = maximize_to_work_area(self._bound_window())
            with self._lock:
                self._restore_bounds = geometry.get("restoreBounds", list(bounds))
                self._maximized = True

    def remember_window_geometry(self) -> None:
        """Save the normal rectangle and whether the custom frame is maximized."""
        with self._lock:
            path = self._window_state_path
            maximized = self._maximized
            restore_bounds = list(self._restore_bounds) if self._restore_bounds else None
        if path is None:
            return
        try:
            metrics = native_window_metrics(self._bound_window())
            bounds = restore_bounds if maximized and restore_bounds else metrics.get("bounds")
            if bounds and len(bounds) == 4:
                save_window_geometry({"bounds": [int(value) for value in bounds], "maximized": maximized}, path)
        except (OSError, RuntimeError, TypeError, ValueError):
            pass

    def constrain_native_maximize(self) -> None:
        """Convert a Windows maximize request to the same safe work-area state."""
        with self._lock:
            if self._maximized:
                return
        geometry = maximize_to_work_area(self._bound_window())
        with self._lock:
            self._restore_bounds = geometry.get("restoreBounds")
            self._maximized = True

    def _bound_window(self):
        with self._lock:
            if self._window is None:
                raise RuntimeError("Lexeditor's desktop window is not ready")
            return self._window

    def window_state(self) -> dict:
        with self._lock:
            return {"maximized": self._maximized, "frameless": True}

    def configure_native_window(self) -> dict:
        """Apply the packaged identity after WinForms creates the real window."""
        window = self._bound_window()
        result = configure_window_icon(window, ICON)
        # Windows 11 rounds and outlines every top-level window, which on a
        # frameless shell shows as a hairline of the desktop behind it.
        result["squareEdges"] = square_window_edges(window)
        with self._lock:
            if self._mouse_navigation is None:
                self._mouse_navigation = install_mouse_navigation(window)
        return result

    def dispose(self) -> None:
        """Release native hooks and stop the active plugin service."""
        with self._lock:
            mouse_navigation = self._mouse_navigation
            self._mouse_navigation = None
        if mouse_navigation is not None:
            mouse_navigation.close()
        self.stop()

    def window_minimize(self) -> dict:
        self._bound_window().minimize()
        return self.window_state()

    def window_toggle_maximize(self) -> dict:
        window = self._bound_window()
        with self._lock:
            was_maximized = self._maximized
            self._maximized = not was_maximized
        if was_maximized:
            restore_from_work_area(window, self._restore_bounds)
            with self._lock:
                self._restore_bounds = None
        else:
            geometry = maximize_to_work_area(window)
            with self._lock:
                self._restore_bounds = geometry.get("restoreBounds")
        return self.window_state()

    def set_dirty_count(self, count: int) -> dict:
        """Keep native close requests synchronized with the active editor."""
        normalized = max(0, int(count))
        with self._lock:
            self._dirty_count = normalized
        return {"dirty": normalized}

    def window_close(self) -> dict:
        with self._lock:
            self._close_authorized = True
        self._bound_window().destroy()
        return {"closing": True}

    def restart_lexeditor(self) -> dict:
        """Close the current window and replace this desktop-host process."""
        with self._lock:
            self._restart_requested = True
            self._close_authorized = True
        self._bound_window().destroy()
        return {"restarting": True}

    def window_closing(self) -> bool:
        """Cancel an unconfirmed native close while the editor is dirty."""
        with self._lock:
            if self._close_authorized or self._dirty_count == 0:
                allowed = True
            else:
                allowed = False
            window = self._window

        if allowed:
            self.remember_window_geometry()
            return True

        def request_prompt() -> None:
            if window is None:
                return
            try:
                window.run_js("window.__lexeditorRequestWindowClose?.();")
            except Exception:
                pass

        threading.Thread(target=request_prompt, daemon=True).start()
        return False

    def return_to_main_menu(self) -> dict:
        """Show the game menu while the current detached service stays resident."""
        # WebView2 can block an HTTP plugin page from assigning a file URL.
        # Let the bridge reply, then make the trusted native window navigate.
        with self._lock:
            window = self._window
            self._dirty_count = 0

        chooser_url = f"{CHOOSER.as_uri()}#lexTransition=home"

        def navigate_home() -> None:
            time.sleep(0.05)
            try:
                if window is not None:
                    window.load_url(chooser_url)
            except Exception as error:
                with self._lock:
                    self._main_menu_navigation_error = str(error)

        threading.Thread(target=navigate_home, daemon=True).start()
        return {"url": chooser_url, "hostNavigates": True, "resident": self._plugin_id}

    def resume_plugin(self, plugin_id: str) -> dict:
        """Return to the existing child service without running setup again."""
        with self._lock:
            if plugin_id != self._plugin_id or self._session is None:
                raise RuntimeError(f"{plugin_id} is not resident")
            if self._session.process is not None and self._session.process.poll() is not None:
                raise RuntimeError(f"The resident {plugin_id} service has stopped")
            self._dirty_count = 0
            return {
                "id": plugin_id,
                "url": f"{self._session.url}?lexTransition=resume",
                "identity": self._session_identity,
                "resident": True,
            }

    def loading_quote(self, plugin_id: str) -> dict:
        """Choose one editable game or down-weighted global line."""
        if plugin_id != "__home__" and plugin_id not in self._plugins:
            raise ValueError(f"Unknown Lexeditor plugin: {plugin_id}")
        try:
            payload = json.loads(LOADING_QUOTES.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            payload = {}
        rarity = self._settings.snapshot().get("globalMessageRarity", 3.0)
        return {
            "pluginId": plugin_id,
            "quote": choose_loading_quote(
                payload, plugin_id, rarity, used=self._shown_quotes),
        }

    def cover_art_data_uri(self, plugin_id: str) -> dict:
        """Embed private cached art so a cross-page snapshot cannot lose it."""
        if plugin_id not in self._plugins:
            raise ValueError(f"Unknown Lexeditor plugin: {plugin_id}")
        return {"pluginId": plugin_id, "uri": self._cover_art.data_uri(plugin_id)}

    def set_transition_snapshot(self, html: str) -> dict:
        """Keep one inert menu frame for the next cross-page pan."""
        snapshot = str(html or "")
        if len(snapshot) > 2_000_000:
            # A pan is cosmetic. Never let an oversized visual snapshot block
            # access to an editor. Thumbnail generation normally keeps this
            # below the limit; this is the final safe degradation.
            snapshot = ""
        with self._lock:
            self._transition_snapshot = snapshot
        return {
            "stored": bool(snapshot),
            "length": len(snapshot),
            "reason": "" if snapshot else "empty-or-too-large",
        }

    def transition_snapshot(self) -> dict:
        """Return the last inert menu frame without exposing mutable host state."""
        with self._lock:
            snapshot = self._transition_snapshot
        return {"html": snapshot}

    def _begin_nonclient_drag(self, hit_test: int) -> dict:
        """Give window move and resize to Windows after an HTML pointer press."""
        import ctypes

        window = self._bound_window()
        native = getattr(window, "native", None)
        if native is None:
            raise RuntimeError("Lexeditor's native window is not ready")
        handle = int(native.Handle.ToInt64())
        ctypes.windll.user32.ReleaseCapture()
        ctypes.windll.user32.SendMessageW(handle, 0x00A1, hit_test, 0)
        return {"started": True}

    def window_begin_move(self) -> dict:
        with self._lock:
            if self._maximized:
                return {"started": False, "reason": "maximized"}
        return self._begin_nonclient_drag(2)

    def window_begin_resize(self, edge: str) -> dict:
        with self._lock:
            if self._maximized:
                return {"started": False, "reason": "maximized"}
        return begin_window_resize(self._bound_window(), edge)

    def window_resize_by(self, edge: str, dx: int, dy: int) -> dict:
        """Deterministic resize path used by native acceptance checks."""
        with self._lock:
            if self._maximized:
                return {"started": False, "reason": "maximized"}
        bounds = resize_window_by(self._bound_window(), edge, dx, dy)
        return {"bounds": bounds, "edge": edge}

    def plugins(self) -> list[dict]:
        rows = []
        lexer_mode = bool(self._settings.snapshot().get("lexerMode"))
        for managed in self._installations.rows(bypass=not self._enforce_installations):
            plugin = managed["plugin"]
            if plugin.plugin_id == "blank" and not lexer_mode:
                continue
            installation = managed["installation"]
            problems = installation["problems"]
            if plugin.projects is not None:
                project = self._projects.snapshot(plugin.plugin_id)
                selected = next((row for row in project["projects"] if row["current"]), None)
                if selected and selected["problems"]:
                    problems = problems + selected["problems"]
                    installation = dict(installation)
                    installation["problems"] = problems
                    installation["status"] = "warning"
                    installation["statusText"] = problems[0]
                    installation["canOpen"] = False
            helper = installation.get("helper") or {}
            row_extra = {
                "helperName": plugin.helper_name or helper.get("runtime") or "",
                "helperInstalled": bool(helper.get("installed")),
                "helperInstallable": plugin.helper_install is not None,
            }
            if plugin.session_factory is None:
                problems = problems + ["Shared UI session is not implemented"]
                installation = dict(installation)
                installation["problems"] = problems
                installation["status"] = "warning"
                installation["statusText"] = problems[0]
                installation["canOpen"] = False
            rows.append({
                **row_extra,
                "id": plugin.plugin_id,
                "name": plugin.name,
                "subtitle": plugin.subtitle,
                "description": plugin.description,
                "accent": plugin.accent,
                "ready": installation["canOpen"] and not problems,
                "problem": (problems or [None])[0],
                **installation,
                "current": plugin.plugin_id == self._plugin_id,
                "resident": plugin.plugin_id == self._plugin_id and self._session is not None,
                "dirtyCount": self._dirty_count
                if plugin.plugin_id == self._plugin_id and self._session is not None else 0,
                "gameVersion": game_version(
                    installation.get("root"),
                    plugin.installation.required_paths if plugin.installation else (),
                ),
                "fonts": font_status(
                    plugin, self._font_errors.get(plugin.plugin_id, ""),
                ),
                "coverArt": self._cover_art.snapshot(plugin.plugin_id),
            })
        return rows

    def lexeditor_settings(self) -> dict:
        """Return shared settings and managed-helper state."""
        payload = self._settings.snapshot()
        identity = self._github.visible_repository(LEXEDITOR_REPOSITORY)
        payload["lexerAuthorized"] = bool(identity)
        payload["lexerLogin"] = (identity or {}).get("login", "")
        if not identity:
            payload["lexerMode"] = False
        return payload

    def save_lexeditor_settings(self, values: dict | str, *legacy_values) -> dict:
        """Save bounded global application settings."""
        if isinstance(values, dict):
            payload = values
        else:
            names = ("developerMode", "lexerMode", "hoverableAltClick", "selectionHoldMs",
                     "tableRowsPerPage", "panelGapPercent", "mainMenuHeightPercent",
                     "soundEnabled", "soundVolumePercent")
            payload = {"updateCheckFrequency": values, **dict(zip(names, legacy_values))}
        lexer_mode = bool(payload.get("lexerMode"))
        authorized = bool(self._github.visible_repository(LEXEDITOR_REPOSITORY, refresh=True))
        if lexer_mode and not authorized:
            raise PermissionError("Lexer Mode requires Lexer's active GitHub account")
        self._settings.save(
            str(payload.get("updateCheckFrequency", "daily")),
            None if "developerMode" not in payload else bool(payload["developerMode"]),
            bool(lexer_mode) if authorized else False,
            None if "hoverableAltClick" not in payload else bool(payload["hoverableAltClick"]),
            payload.get("selectionHoldMs"),
            payload.get("tableRowsPerPage"),
            payload.get("panelGapPercent"),
            payload.get("mainMenuHeightPercent"),
            None if "soundEnabled" not in payload else bool(payload["soundEnabled"]),
            payload.get("soundVolumePercent"),
        )
        return self.lexeditor_settings()

    def save_lexer_setting_defaults(self, values: dict) -> dict:
        """Save distributable setting defaults for the active repository owner."""
        if not self._settings.snapshot().get("lexerMode"):
            raise PermissionError("Lexer Mode is not enabled")
        if not self._github.visible_repository(LEXEDITOR_REPOSITORY, refresh=True):
            raise PermissionError("Lexer's active GitHub account is required")
        self._settings.save_lexer_defaults(values)
        return self.lexeditor_settings()

    def save_lexeditor_view_preference(self, key: str, value: int) -> dict:
        """Save one per-user UI preference outside every mod project."""
        self._settings.save_view_preference(str(key), int(value))
        return self.lexeditor_settings()

    def clear_lexeditor_view_preference(self, key: str) -> dict:
        """Clear one per-page override and use the global value again."""
        self._settings.clear_view_preference(str(key))
        return self.lexeditor_settings()

    def restart_plugin(self, plugin_id: str) -> dict:
        """Replace the active child service without creating another window."""
        with self._lock:
            if plugin_id != self._plugin_id:
                raise ValueError("Restart is available only for the active plugin")
        return self.open_plugin(plugin_id)

    def _github_repository(self, plugin_id: str):
        """Resolve one configured repository before the owner check."""
        plugin = self._plugins.get(plugin_id)
        if plugin is None:
            raise ValueError(f"Unknown Lexeditor plugin: {plugin_id}")
        if plugin.github is None:
            raise ValueError(f"{plugin.name} has no configured GitHub repository")
        return plugin.github

    def github_repository(self, plugin_id: str) -> dict | None:
        """Show safe repository metadata only to an allowed active owner."""
        plugin = self._plugins.get(plugin_id)
        if plugin is None:
            raise ValueError(f"Unknown Lexeditor plugin: {plugin_id}")
        if plugin.github is None:
            return None
        repository = self._github_repository(plugin_id)
        return self._github.visible_repository(repository)

    def default_views(self, plugin_id: str) -> dict:
        """Return packaged view defaults for one plugin."""
        try:
            payload = json.loads(DEFAULT_VIEWS.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            payload = {}
        views = payload.get(plugin_id, {}) if isinstance(payload, dict) else {}
        return {"plugin": plugin_id, "views": views if isinstance(views, dict) else {}}

    def save_default_view(self, plugin_id: str, tab_id: str,
                          preferences: dict) -> dict:
        """Save a distributable view default for the authorized developer."""
        plugin = self._plugins.get(plugin_id)
        if plugin is None:
            raise ValueError(f"Unknown Lexeditor plugin: {plugin_id}")
        if not self._settings.snapshot().get("lexerMode"):
            raise PermissionError("Lexer Mode is not enabled")
        if not self._github.visible_repository(LEXEDITOR_REPOSITORY, refresh=True):
            raise PermissionError("Lexer's active GitHub account is required")
        tab_id = str(tab_id).strip()
        token = f"{plugin_id}-{tab_id}"
        if not tab_id or not isinstance(preferences, dict):
            raise ValueError("The view default is incomplete")
        clean = {}
        for key, value in preferences.items():
            key = str(key)
            if token not in key or len(key) > 220 or not isinstance(value, str) or len(value) > 20_000:
                continue
            clean[key] = value
        if not clean:
            raise ValueError("This tab has no saved view settings")
        try:
            payload = json.loads(DEFAULT_VIEWS.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                payload = {}
        except (OSError, ValueError, TypeError):
            payload = {}
        payload.setdefault(plugin_id, {})[tab_id] = clean
        temporary = DEFAULT_VIEWS.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(DEFAULT_VIEWS)
        return {"saved": True, "plugin": plugin_id, "tab": tab_id, "preferences": len(clean)}

    def github_issues(self, plugin_id: str, state: str = "open") -> dict:
        """List issues for the active game's embedded owner workspace."""
        return self._github.list_issues(self._github_repository(plugin_id), state)

    def github_issue(self, plugin_id: str, number: int) -> dict:
        """Read one issue for the embedded detail pane."""
        return self._github.view_issue(self._github_repository(plugin_id), number)

    def github_labels(self, plugin_id: str) -> dict:
        """List repository labels for the embedded label editor."""
        return self._github.list_labels(self._github_repository(plugin_id))

    def github_edit_issue(self, plugin_id: str, number: int,
                          title: str, body: str) -> dict:
        """Save one issue's editable text after a fresh owner check."""
        return self._github.edit_issue(
            self._github_repository(plugin_id), number, title, body,
        )

    def github_set_issue_labels(self, plugin_id: str, number: int,
                                labels: list[str]) -> dict:
        """Replace one issue's selected labels after a fresh owner check."""
        return self._github.set_issue_labels(
            self._github_repository(plugin_id), number, labels,
        )

    def github_comment_issue(self, plugin_id: str, number: int,
                             body: str) -> dict:
        """Post one issue comment after a fresh owner check."""
        return self._github.comment_issue(
            self._github_repository(plugin_id), number, body,
        )

    def begin_game_scan(self, plugin_id: str) -> dict:
        """Start one background scan or report the scan already in progress."""
        return self._installations.begin_scan(plugin_id)

    def locate_game(self, plugin_id: str) -> dict:
        """Let the user override an active scan with a native folder choice."""
        import webview

        current = self._installations.snapshot(plugin_id)
        directory = current.get("root") or ""
        if directory and not Path(directory).is_dir():
            directory = str(Path(directory).parent)
        selection = self._bound_window().create_file_dialog(
            webview.FOLDER_DIALOG,
            directory=directory,
            allow_multiple=False,
        )
        if not selection:
            return {"cancelled": True, "installation": self._installations.snapshot(plugin_id)}
        selected = selection[0] if isinstance(selection, (list, tuple)) else selection
        return {
            "cancelled": False,
            "installation": self._installations.configure_directory(plugin_id, selected),
        }

    def open_game_data_location(self, plugin_id: str, filename: str) -> dict:
        from game_data_location import find_original_location
        if plugin_id not in self._plugins:
            raise ValueError(f"Unknown Lexeditor plugin: {plugin_id}")
        snapshot = self._installations.snapshot(plugin_id)
        configured = snapshot.get("path") or snapshot.get("root") or ""
        roots = []
        roots.append(Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Lexeditor" / "game-data" / plugin_id)
        target = find_original_location(filename, roots, Path(configured) if configured else None)
        subprocess.Popen(["explorer.exe", str(target)] if target.is_dir() else
                         ["explorer.exe", "/select,", str(target)])
        return {"path": str(target)}

    def open_game_folder(self, plugin_id: str) -> dict:
        """Open one configured game root without accepting a page-supplied path."""
        if plugin_id not in self._plugins:
            raise ValueError(f"Unknown Lexeditor plugin: {plugin_id}")
        snapshot = self._installations.snapshot(plugin_id)
        configured = str(snapshot.get("root", "")).strip()
        if not configured:
            raise RuntimeError(f"{plugin_id} has no configured game folder")
        root = Path(configured).resolve()
        if not root.is_dir():
            raise RuntimeError(f"The configured game folder is unavailable: {root}")
        os.startfile(str(root))
        return {"opened": True, "path": str(root)}

    def install_helper(self, plugin_id: str) -> dict:
        """Install this plugin's runtime helper, then re-check readiness.

        First-time setup: a plugin whose helper is missing reports `broken` and
        refuses to open, and this is the action that clears it.
        """
        plugin = self._plugins.get(plugin_id)
        if plugin is None:
            raise ValueError(f"Unknown Lexeditor plugin: {plugin_id}")
        if plugin.helper_install is None:
            raise RuntimeError(f"{plugin.name} has no installable helper")
        result = plugin.helper_install() or {}
        snapshot = self._installations.snapshot(plugin_id)
        return {
            "helper": result,
            "installed": bool((snapshot.get("helper") or {}).get("installed")),
            "status": snapshot.get("status"),
            "canOpen": snapshot.get("canOpen"),
            "problems": snapshot.get("problems", []),
        }

    def helper_versions(self, refresh: bool = False) -> dict:
        """Report every plugin helper whose upstream has a newer release.

        Lexeditor pins helpers and its forks never self-update, because a user
        updating one part on its own can break the whole program. This panel is
        therefore the only update path, and it only ever reports: nothing here
        installs anything.
        """
        if not self._settings.snapshot().get("lexerMode"):
            raise PermissionError("Lexer Mode is not enabled")
        with self._lock:
            cached = self._helper_versions
        if cached is not None and not refresh:
            return {"helpers": cached, "cached": True}
        rows = []
        for plugin_id, plugin in sorted(self._plugins.items()):
            if plugin.helper_upstream is None:
                continue
            row = {"pluginId": plugin_id, "plugin": plugin.name,
                   "helper": plugin.helper_name or "Helper"}
            try:
                row.update(plugin.helper_upstream() or {})
            except Exception as error:  # a helper check must never break Home
                row["error"] = str(error)
            row["behind"] = bool(row.get("behind"))
            rows.append(row)
        with self._lock:
            self._helper_versions = rows
        return {"helpers": rows, "cached": False}

    def open_mod_folder(self, plugin_id: str, path: str) -> dict:
        """Open one of this plugin's own mod folders.

        The path is matched against the project list rather than trusted from
        the page, so this cannot be used to open an arbitrary directory.
        """
        if plugin_id not in self._plugins:
            raise ValueError(f"Unknown Lexeditor plugin: {plugin_id}")
        wanted = Path(str(path)).resolve()
        known = {
            Path(str(row.get("path", ""))).resolve()
            for row in self._projects.snapshot(plugin_id).get("projects", [])
            if row.get("path")
        }
        if wanted not in known:
            raise ValueError("That folder is not one of this plugin's mods")
        if not wanted.is_dir():
            raise RuntimeError(f"The mod folder is unavailable: {wanted}")
        os.startfile(str(wanted))
        return {"opened": True, "path": str(wanted)}

    def open_home_link(self, target: str) -> dict:
        """Open one fixed Home destination in the user's default browser."""
        key = str(target).strip().lower()
        url = HOME_LINKS.get(key)
        if url is None:
            raise ValueError("Unknown Lexeditor Home link")
        return {"opened": bool(webbrowser.open(url, new=2, autoraise=True)), "url": url}

    def _game_executable(self, plugin_id: str) -> tuple[Path, Path]:
        plugin = self._plugins.get(plugin_id)
        if plugin is None:
            raise ValueError(f"Unknown Lexeditor plugin: {plugin_id}")
        if plugin.installation is None:
            raise RuntimeError(f"{plugin.name} has no game installation descriptor")
        snapshot = self._installations.snapshot(plugin_id)
        configured = str(snapshot.get("root", "")).strip()
        if not configured:
            raise RuntimeError(f"{plugin.name} has no configured game folder")
        root = Path(configured).resolve()
        relative = (Path(plugin.installation.launch_path)
                    if plugin.installation.launch_path
                    else next((Path(value) for value in plugin.installation.required_paths
                               if Path(value).suffix.casefold() == ".exe"), None))
        if relative is None:
            raise RuntimeError(f"{plugin.name} has no configured game executable")
        executable = (root / relative).resolve()
        if root not in executable.parents or not executable.is_file():
            raise RuntimeError(f"The configured game executable is unavailable: {executable}")
        return root, executable

    def _external_game_processes(self, plugin_id: str) -> list[dict]:
        """Find this game's live processes, whoever started them.

        Only processes that are genuinely running count. A terminated entry
        Windows still lists would otherwise show a Stop button that cannot
        stop anything.
        """
        plugin = self._plugins.get(plugin_id)
        if plugin is None or not plugin.process_names:
            return []
        return process_probe.live_processes(plugin.process_names)

    def _game_controller(self, plugin_id: str):
        """Use a plugin-owned launch policy only when explicitly registered."""
        plugin = self._plugins.get(plugin_id)
        factory = getattr(plugin, "game_process_factory", None)
        if factory is None:
            return None
        with self._lock:
            if not hasattr(self, "_game_controllers"):
                self._game_controllers = {}
            if plugin_id not in self._game_controllers:
                self._game_controllers[plugin_id] = factory()
            return self._game_controllers[plugin_id]

    def game_process_status(self, plugin_id: str) -> dict:
        """Report this game's process, whoever started it.

        Reporting only processes this host owns let a crashed or externally
        started game sit invisible behind a Play button while the helper
        manager refused to work because that same process existed.
        """
        controller = self._game_controller(plugin_id)
        if controller is not None:
            return controller.status()
        with self._lock:
            process = self._game_processes.get(plugin_id)
            running = process is not None and process.poll() is None
            if process is not None and not running:
                self._game_processes.pop(plugin_id, None)
            if running:
                return {"running": True, "pid": process.pid, "owned": True}
        external = self._external_game_processes(plugin_id)
        return {
            "running": bool(external),
            "pid": external[0]["pid"] if external else None,
            "owned": False,
            "processes": external,
        }

    def launch_game(self, plugin_id: str) -> dict:
        """Start the configured game without opening a command window."""
        controller = self._game_controller(plugin_id)
        if controller is not None:
            root, _executable = self._game_executable(plugin_id)
            project = Path(self._projects.snapshot(plugin_id)["current"])
            return controller.launch(root, project)
        with self._lock:
            current = self._game_processes.get(plugin_id)
            if current is not None and current.poll() is None:
                return {"running": True, "pid": current.pid, "alreadyRunning": True}
            root, executable = self._game_executable(plugin_id)
            flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            process = subprocess.Popen([str(executable)], cwd=str(root), creationflags=flags)
            self._game_processes[plugin_id] = process
            return {"running": True, "pid": process.pid, "alreadyRunning": False}

    def stop_game(self, plugin_id: str) -> dict:
        """Stop this game, including a copy this host did not start.

        The Stop button has to be able to clear whatever the status call
        reported, or the editor shows a running game it cannot act on.
        """
        controller = self._game_controller(plugin_id)
        if controller is not None:
            return controller.stop()
        with self._lock:
            process = self._game_processes.get(plugin_id)
            owned = process is not None and process.poll() is None
            if not owned:
                self._game_processes.pop(plugin_id, None)
        if not owned:
            external = self._external_game_processes(plugin_id)
            if not external:
                return {"running": False, "stopped": False}
            for row in external:
                subprocess.run(
                    ["taskkill", "/PID", str(row["pid"]), "/F"],
                    capture_output=True, text=True, check=False,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    timeout=15,
                )
            return {
                "running": bool(self._external_game_processes(plugin_id)),
                "stopped": True,
                "stoppedProcesses": [row["pid"] for row in external],
            }
        with self._lock:
            process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        with self._lock:
            self._game_processes.pop(plugin_id, None)
        return {"running": False, "stopped": True}

    def download_fonts(self, plugin_id: str) -> dict:
        with self._lock:
            plugin = self._plugins.get(plugin_id)
            if plugin is None:
                raise ValueError(f"Unknown Lexeditor plugin: {plugin_id}")
            result = install_missing_fonts(plugin)
            if result["errors"]:
                self._font_errors[plugin_id] = result["error"]
            else:
                self._font_errors.pop(plugin_id, None)
            return result

    def mod_projects(self, plugin_id: str) -> dict:
        """Return known editable projects for the shared header selector."""
        return self._projects.snapshot(plugin_id)

    def _choose_folder(self, directory: str = "") -> str:
        import webview

        selection = self._bound_window().create_file_dialog(
            webview.FOLDER_DIALOG,
            directory=directory if directory and Path(directory).is_dir() else "",
            allow_multiple=False,
        )
        if not selection:
            return ""
        selected = selection[0] if isinstance(selection, (list, tuple)) else selection
        return str(Path(selected).resolve())

    def _restart_for_project(self, plugin_id: str, project: dict) -> dict:
        opened = self.open_plugin(plugin_id)
        return {**project, "url": opened["url"], "identity": opened["identity"]}

    def select_mod_project(self, plugin_id: str, path: str) -> dict:
        """Persist one valid project and restart its child service."""
        project = self._projects.select(plugin_id, path)
        return self._restart_for_project(plugin_id, project)

    def browse_mod_project(self, plugin_id: str) -> dict:
        """Select an existing editable project with the native folder picker."""
        current = self._projects.snapshot(plugin_id)
        selected = self._choose_folder(current.get("current", ""))
        if not selected:
            return {**current, "cancelled": True}
        project = self._projects.select(plugin_id, selected)
        return self._restart_for_project(plugin_id, project)

    def create_mod_project(self, plugin_id: str, name: str) -> dict:
        """Clone the plugin's valid starter into a new selected folder."""
        current = Path(self._projects.snapshot(plugin_id)["current"])
        selected = self._choose_folder(str(current.parent))
        if not selected:
            return {**self._projects.snapshot(plugin_id), "cancelled": True}
        project = self._projects.create(plugin_id, selected, name)
        return self._restart_for_project(plugin_id, project)

    def rename_mod_project(self, plugin_id: str, path: str, name: str) -> dict:
        """Rename one editable project and restart it when it is active."""
        before = self._projects.snapshot(plugin_id)
        was_current = os.path.normcase(before.get("current", "")) == os.path.normcase(str(Path(path).resolve()))
        project = self._projects.rename(plugin_id, path, name)
        return self._restart_for_project(plugin_id, project) if was_current else project

    def open_plugin(self, plugin_id: str) -> dict:
        with self._lock:
            plugin = self._plugins.get(plugin_id)
            if plugin is None:
                raise ValueError(f"Unknown Lexeditor plugin: {plugin_id}")
            problems = plugin.check()
            if problems:
                raise RuntimeError("\n".join(problems))
            if plugin.session_factory is None:
                raise RuntimeError(f"{plugin.name} has not moved to the shared UI host")
            if self._enforce_installations and plugin.installation is not None:
                self._installations.prepare(plugin_id)
            environment = (
                self._installations.environment(plugin_id)
                if self._enforce_installations and plugin.installation is not None else {}
            )
            if plugin.projects is not None:
                project = self._projects.snapshot(plugin_id)
                current = next((row for row in project["projects"] if row["current"]), None)
                if current is None or not current["valid"]:
                    raise RuntimeError("\n".join((current or {}).get(
                        "problems", [f"{plugin.name} has no valid editable project"])))
                environment[plugin.projects.root_env] = project["current"]
            fonts = self.download_fonts(plugin_id)
            session = plugin.session_factory(environment) if environment else plugin.session_factory()
            try:
                identity = session.start()
            except Exception:
                session.stop()
                raise
            previous = self._session
            self._session = session
            self._session_identity = identity
            self._plugin_id = plugin_id
            self._dirty_count = 0
            if previous is not None:
                previous.stop()
            return {
                "id": plugin_id,
                "name": plugin.name,
                "url": f"{session.url}?lexTransition=load",
                "identity": identity,
                "fonts": fonts,
                "resident": False,
            }

    def stop(self) -> None:
        with self._lock:
            if self._session is not None:
                self._session.stop()
            self._session = None
            self._session_identity = None
            self._plugin_id = None


def run_host(plugins: dict[str, GamePlugin], initial_plugin: str | None = None,
             hidden: bool = False) -> int:
    """Run the shared desktop window until it closes."""
    configure_process_identity()
    try:
        import webview
    except ImportError as error:
        raise RuntimeError(
            "Lexeditor's embedded runtime is missing. Run install.ps1."
        ) from error

    geometry = load_window_geometry()
    api = HostApi(plugins)
    initial_url = CHOOSER.as_uri()
    if initial_plugin:
        try:
            initial_url = api.open_plugin(initial_plugin)["url"]
        except RuntimeError:
            initial_url = CHOOSER.as_uri()
    STORAGE.mkdir(parents=True, exist_ok=True)
    left, top, width, height = geometry["bounds"]
    window = webview.create_window(
        "Lexeditor",
        initial_url,
        js_api=api,
        width=width,
        height=height,
        x=left,
        y=top,
        min_size=(900, 620),
        hidden=hidden,
        maximized=False,
        frameless=True,
        easy_drag=False,
        background_color="#171a1f",
        text_select=True,
    )
    if window is None:
        api.dispose()
        raise RuntimeError("Lexeditor could not create its desktop window")
    api.bind_window(window, maximized=False)
    def constrain_maximize(*_args) -> None:
        api.constrain_native_maximize()

    window.events.maximized += constrain_maximize
    def configure_shown_window(*_args) -> None:
        api.configure_native_window()
        api.apply_window_geometry(geometry)

    window.events.shown += configure_shown_window
    window.events.closing += api.window_closing
    window.events.closed += lambda *_args: api.dispose()
    webview.start(
        gui="edgechromium",
        private_mode=False,
        storage_path=str(STORAGE),
        icon=str(ICON),
    )
    restart_requested = api._restart_requested
    api.dispose()
    if restart_requested:
        # os.execv is emulated on Windows: it starts a new process and kills
        # this one, which loses the window and leaves the plugin service
        # running, so the "restarted" editor kept serving the old host. Start a
        # detached replacement explicitly, after dispose() has stopped the
        # child service, then let this process exit normally.
        arguments = ([sys.executable, *sys.argv]
                     if not getattr(sys, "frozen", False)
                     else [sys.executable, *sys.argv[1:]])
        flags = 0
        if os.name == "nt":
            flags = (getattr(subprocess, "DETACHED_PROCESS", 0)
                     | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
        subprocess.Popen(
            arguments, cwd=str(ROOT), close_fds=True, creationflags=flags,
        )
    return 0


def smoke_host_switch(plugins: dict[str, GamePlugin], first: str, second: str) -> list[str]:
    """Confirm two plugins use one hidden WebView2 window and one live service."""
    configure_process_identity()
    try:
        import webview
    except ImportError as error:
        raise RuntimeError(
            "Lexeditor's embedded runtime is missing. Run install.ps1."
        ) from error

    api = HostApi(plugins, enforce_installations=False, auto_scan=False)
    first_opened = api.open_plugin(first)
    first_session = api._session
    STORAGE.mkdir(parents=True, exist_ok=True)
    window = webview.create_window(
        "Lexeditor host smoke",
        first_opened["url"],
        js_api=api,
        width=1100,
        height=720,
        hidden=True,
        frameless=True,
        easy_drag=False,
        background_color="#171a1f",
        text_select=True,
    )
    if window is None:
        api.dispose()
        raise RuntimeError("Lexeditor could not create its hidden test window")

    api.bind_window(window)
    def constrain_maximize(*_args) -> None:
        api.constrain_native_maximize()

    window.events.maximized += constrain_maximize
    def configure_shown_window(*_args) -> None:
        api.configure_native_window()

    window.events.shown += configure_shown_window
    window.events.closing += api.window_closing

    results: list[dict] = []
    main_menu_results: list[dict] = []
    errors: list[str] = []
    phase = 0
    busy = False
    pending_loaded = False
    navigation_trace: list[str] = []
    host_trace: list[str] = []
    lock = threading.Lock()

    def wait_for_plugin(plugin_id: str) -> dict:
        deadline = time.monotonic() + 30
        last = None
        project_required = plugins[plugin_id].projects is not None
        while time.monotonic() < deadline:
            try:
                last = window.evaluate_js("""
                  (() => ({
                    plugin: document.body?.dataset?.lexPlugin || '',
                    theme: document.body?.dataset?.lexTheme || '',
                    title: document.title,
                    ready: typeof state !== 'undefined' && !state.booting,
                    nav: document.querySelectorAll('nav button').length,
                    shell: !!document.querySelector('.lex-shell-header'),
                    help: !!document.querySelector('#plugin-data-map'),
                    info: !!document.querySelector('#plugin-info'),
                    restart: !!document.querySelector('#plugin-restart'),
                    project: !!document.querySelector('.lex-project-control:not([hidden])'),
                    projectActions: [...document.querySelectorAll('.lex-project-menu-actions > button')]
                      .map(button => button.textContent.trim()),
                    separateProjectActions: document.querySelectorAll('.lex-project-action').length,
                    projectStatusText: document.querySelector('#plugin-status')?.textContent || '',
                    projectGeometry: (() => {
                      const trigger = document.querySelector('.lex-project-select');
                      const name = trigger?.querySelector('.lex-project-name');
                      const path = trigger?.querySelector('.lex-project-path');
                      if (!trigger || !name || !path) return null;
                      const nameRect = name.getBoundingClientRect();
                      const pathRect = path.getBoundingClientRect();
                      return {
                        font: getComputedStyle(trigger).fontFamily,
                        display: getComputedStyle(trigger).display,
                        align: getComputedStyle(trigger).alignItems,
                        triggerRect: [trigger.getBoundingClientRect().top, trigger.getBoundingClientRect().bottom],
                        nameRect: [nameRect.top, nameRect.bottom],
                        pathRect: [pathRect.top, pathRect.bottom],
                        centerDelta: Math.abs((nameRect.top + nameRect.bottom - pathRect.top - pathRect.bottom) / 2),
                        marker: getComputedStyle(trigger, '::after').content,
                      };
                    })(),
                    undo: !!document.querySelector('#global-undo'),
                    redo: !!document.querySelector('#global-redo'),
                    save: !!document.querySelector('#global-save'),
                    minimize: !!document.querySelector('#window-minimize'),
                    maximize: !!document.querySelector('#window-maximize'),
                    close: !!document.querySelector('#window-close'),
                    dragRegions: document.querySelectorAll('.lex-window-drag-region').length,
                    supportedDragRegions: document.querySelectorAll('.pywebview-drag-region').length,
                    resizeHandles: document.querySelectorAll('.lex-window-resize-handle').length,
                    commandOrder: [...document.querySelectorAll('.lex-shell-command-row button')]
                      .filter(button => button.id !== 'plugin-github')
                      .map(button => button.id).filter(Boolean),
                    navScrollButtons: document.querySelectorAll('.lex-nav-scroll-button').length,
                    navOverflow: (() => {
                      const nav = document.querySelector('.lex-shell-header nav');
                      return !!nav && nav.scrollWidth > nav.clientWidth + 1;
                    })(),
                    navWrap: getComputedStyle(document.querySelector('.lex-shell-header nav')).flexWrap,
                    saveBeforeWindows: (() => {
                      const save = document.querySelector('#global-save')?.getBoundingClientRect();
                      const minimize = document.querySelector('#window-minimize')?.getBoundingClientRect();
                      return !!save && !!minimize && save.right <= minimize.left;
                    })()
                  }))()
                """)
                if (last and last.get("plugin") == plugin_id and last.get("ready")
                        and (not project_required or (
                            last.get("project") and
                            last.get("projectActions") == ["New Mod", "Find a Mod"]
                        ))):
                    return last
            except Exception:
                pass
            time.sleep(0.05)
        raise RuntimeError(f"{plugin_id} did not finish loading in WebView2: {last}")

    def wait_for_main_menu() -> dict:
        deadline = time.monotonic() + 30
        last = None
        while time.monotonic() < deadline:
            try:
                last = window.evaluate_js("""
                  (() => ({
                    title: document.title,
                    heading: document.querySelector('h1')?.innerText || '',
                    cards: document.querySelectorAll('#games .game').length,
                    covers: document.querySelectorAll('#games .game .game-cover').length,
                    statusIndicators: document.querySelectorAll('#games .game .state-indicator').length,
                    hoverPanels: document.querySelectorAll('#games .game .game-hover').length,
                    actionIcons: document.querySelectorAll('#games .game .game-action-icon').length,
                    residentHandles: document.querySelectorAll('#resident-handle:not([hidden])').length,
                    fontButtons: document.querySelectorAll('#games .game .font-install').length,
                    fonts: [...document.querySelectorAll('#games .game')].map(card => ({
                      plugin: card.dataset.plugin,
                      count: card.querySelector('.font-count')?.textContent || '',
                      tooltip: card.querySelector('.font-tooltip')?.textContent || '',
                      items: [...card.querySelectorAll('.font-row')].map(row => ({
                        name: row.querySelectorAll('span')[1]?.textContent || '',
                        installed: row.classList.contains('installed')
                      })),
                      buttonDisabled: !!card.querySelector('.font-install')?.disabled
                    })),
                    windowControls: ['window-minimize','window-maximize','window-close']
                      .every(id => !!document.getElementById(id)),
                    dragRegions: document.querySelectorAll('.lex-window-drag-region').length,
                    resizeHandles: document.querySelectorAll('.lex-window-resize-handle').length,
                    maximized: document.body?.dataset?.windowMaximized || '',
                    fontSetStatus: document.fonts?.status || '',
                    lexendCheck: document.fonts?.check('16px Lexend') || false,
                    lexendFaceLoaded: [...(document.fonts || [])].some(face =>
                      face.family.replace(/["']/g, '') === 'Lexend' && face.status === 'loaded'),
                    bodyFont: getComputedStyle(document.body).fontFamily,
                    headingFont: getComputedStyle(document.querySelector('h1')).fontFamily,
                    loading: document.body?.innerText.includes('Loading plugins') || false
                  }))()
                """)
                if (last and last.get("heading") == "LEXEDITOR" and
                        last.get("cards", 0) == len(plugins) and
                        last.get("statusIndicators", 0) == len(plugins) and
                        last.get("hoverPanels", 0) == len(plugins) and
                        last.get("actionIcons", 0) == len(plugins) and
                        last.get("fontButtons", 0) == 0 and
                        last.get("fontSetStatus") == "loaded" and
                        last.get("lexendCheck") and last.get("lexendFaceLoaded") and
                        not last.get("loading")):
                    return last
            except Exception:
                pass
            time.sleep(0.05)
        raise RuntimeError(f"The main menu did not finish loading in WebView2: {last}")

    def wait_for_javascript(expression: str, expected=True, timeout: float = 5) -> object:
        deadline = time.monotonic() + timeout
        last = None
        while time.monotonic() < deadline:
            try:
                last = window.evaluate_js(expression)
                if last == expected:
                    return last
            except Exception:
                pass
            time.sleep(0.05)
        raise RuntimeError(f"WebView2 navigation did not reach {expected!r}: {last!r}")

    def exercise_navigation_history() -> dict:
        navigation_trace.append("start")
        if api._mouse_navigation is None:
            raise RuntimeError("The native mouse navigation filter was not installed")
        navigation_trace.append("native-filter")
        initial_url = str(window.evaluate_js("location.href"))
        destinations = window.evaluate_js("""
          (() => {
            const tabs = [...document.querySelectorAll('nav button[data-tab]')];
            const current = tabs.find(button => button.classList.contains('active'))?.dataset.tab;
            const choices = tabs.filter(button => button.dataset.tab !== current).slice(0, 2);
            if (!current || choices.length < 2) return null;
            choices[0].click();
            choices[1].click();
            return {initial: current, back: choices[0].dataset.tab, forward: choices[1].dataset.tab};
          })()
        """)
        if not destinations:
            raise RuntimeError("The plugin did not expose enough destinations for navigation history")
        navigation_trace.append("tabs-clicked")
        wait_for_javascript(
            "document.querySelector('nav button.active')?.dataset.tab || ''",
            destinations["forward"],
        )
        window.evaluate_js("window.__lexeditorNavigateHistory(-1); true")
        wait_for_javascript(
            "document.querySelector('nav button.active')?.dataset.tab || ''",
            destinations["back"],
        )
        navigation_trace.append("back")
        window.evaluate_js("window.__lexeditorNavigateHistory(1); true")
        wait_for_javascript(
            "document.querySelector('nav button.active')?.dataset.tab || ''",
            destinations["forward"],
        )
        navigation_trace.append("forward")
        window.evaluate_js("document.querySelector('#plugin-data-map').click()")
        wait_for_javascript("document.querySelector('#plugin-data-map').classList.contains('active')")
        navigation_trace.append("datamap")
        window.evaluate_js("window.__lexeditorNavigateHistory(-1); true")
        wait_for_javascript(
            "document.querySelector('nav button.active')?.dataset.tab || ''",
            destinations["forward"],
        )
        navigation_trace.append("datamap-back")
        changed = window.evaluate_js("""
          (() => {
            document.querySelector('nav button[data-tab="items"]')?.click();
            const control = document.querySelector('#main input[type=number], #main select, #main input[type=checkbox]');
            if (!control) return false;
            if (control.type === 'checkbox') control.checked = !control.checked;
            else if (control.tagName === 'SELECT') control.selectedIndex = (control.selectedIndex + 1) % control.options.length;
            else control.value = String(Number(control.value || 0) + 1);
            control.dispatchEvent(new Event('input', {bubbles:true}));
            control.dispatchEvent(new Event('change', {bubbles:true}));
            return true;
          })()
        """)
        if not changed:
            raise RuntimeError("The hidden plugin had no editable control for the Home guard check")
        wait_for_javascript("!document.querySelector('#global-save').disabled")
        navigation_trace.append("dirty")
        window.evaluate_js("document.querySelector('.lex-brand-button').click()")
        wait_for_javascript("!!document.querySelector('.lex-exit-dialog')")
        navigation_trace.append("home-guard")
        actions = window.evaluate_js(
            "[...document.querySelectorAll('.lex-exit-dialog .lex-dialog-action')].map(button => button.textContent)"
        )
        if actions != ["Cancel", "Exit Without Saving", "Save and Exit"]:
            raise RuntimeError(f"The wordmark bypassed the guarded Home dialog: {actions}")
        window.evaluate_js("document.querySelector('.lex-exit-dialog .lex-dialog-action').click()")
        if str(window.evaluate_js("location.href")) != initial_url:
            raise RuntimeError("Back/Forward left the active plugin URL")
        navigation_trace.append("complete")
        return {**destinations, "special": "datamap", "homeGuard": actions}

    def inspect_loaded() -> None:
        nonlocal phase, busy, pending_loaded
        with lock:
            if busy:
                pending_loaded = True
                return
            busy = True
            pending_loaded = False
            current_phase = phase
            phase += 1
        try:
            if current_phase == 1:
                main_menu_results.append(wait_for_main_menu())
                if first_session is None or first_session.process is None:
                    raise RuntimeError("The first plugin service was not supervised")
                if first_session.process.poll() is not None:
                    raise RuntimeError("Returning home stopped the resident plugin service")
                if main_menu_results[-1].get("residentHandles") != 1:
                    raise RuntimeError("The main menu did not show one resident-plugin handle")
                results[0]["mainMenuReturn"] = True
                opened = api.resume_plugin(first)
                if opened.get("identity") != first_opened.get("identity"):
                    raise RuntimeError("The resident return changed the plugin identity")
                window.load_url(opened["url"])
                with lock:
                    pending_loaded = True
                return
            if current_phase == 2:
                resumed = wait_for_plugin(first)
                if (api._session is not first_session or first_session.process is None or
                        first_session.process.poll() is not None):
                    raise RuntimeError("The resident return started or lost the child service")
                results[0]["residentReturn"] = {
                    "plugin": resumed["plugin"],
                    "pid": first_session.process.pid,
                    "identity": api._session_identity,
                }
                opened = api.open_plugin(second)
                if first_session.process.poll() is None and not first_session.wait_closed():
                    raise RuntimeError("Opening another game did not stop the former resident service")
                window.load_url(opened["url"])
                with lock:
                    pending_loaded = True
                return
            if current_phase > 3:
                return
            expected = first if current_phase == 0 else second
            result = wait_for_plugin(expected)
            host_trace.append(f"plugin-{current_phase}-loaded")
            result["windowCount"] = len(webview.windows)
            result["renderer"] = webview.renderer
            result["frameless"] = window.frameless and not window.easy_drag
            if current_phase == 0:
                result["navigationHistory"] = exercise_navigation_history()
                restored_metrics = native_window_metrics(window)
                state = api.window_toggle_maximize()
                window.evaluate_js("window.__lexeditorApplyWindowState({maximized:true}); true")
                wait_for_javascript(
                    "document.querySelectorAll('.pywebview-drag-region').length",
                    0,
                )
                host_trace.append("maximize-called")
                deadline = time.monotonic() + 2
                metrics = native_window_metrics(window)
                while metrics["bounds"] != metrics["workArea"] and time.monotonic() < deadline:
                    time.sleep(0.05)
                    metrics = native_window_metrics(window)
                native_state = metrics["windowState"].casefold()
                if not state["maximized"] or "normal" not in native_state:
                    raise RuntimeError(f"The work-area maximize state is wrong: {metrics}")
                if metrics["bounds"] != metrics["workArea"]:
                    raise RuntimeError(f"Maximize covered reserved desktop space: {metrics}")
                if (metrics["appUserModelId"] != "Lexer.Lexeditor" or
                        not metrics["largeIcon"] or not metrics["smallIcon"]):
                    raise RuntimeError(f"The native taskbar identity is incomplete: {metrics}")
                result["nativeHostIdentity"] = metrics
                before_blocked_interaction = metrics["bounds"]
                blocked_move = api.window_begin_move()
                blocked_resize = api.window_begin_resize("right")
                blocked_resize_by = api.window_resize_by("right", 12, 0)
                after_blocked_interaction = native_window_metrics(window)["bounds"]
                if (blocked_move.get("started") or blocked_resize.get("started") or
                        blocked_resize_by.get("started") or
                        after_blocked_interaction != before_blocked_interaction):
                    raise RuntimeError(
                        "The maximized window still accepted move or resize input: "
                        f"{blocked_move}, {blocked_resize}, {blocked_resize_by}, "
                        f"{before_blocked_interaction} -> {after_blocked_interaction}"
                    )
                result["maximizedInteractionsBlocked"] = True
                host_trace.append("maximize-verified")
                api.window_minimize()
                native_state = str(window.native.WindowState).casefold()
                if "minimized" not in native_state:
                    raise RuntimeError(f"The maximized window did not minimize: {native_state}")
                window.restore()
                host_trace.append("maximized-restore-called")
                maximized_after_minimize = native_window_metrics(window)
                if (not api.window_state()["maximized"] or
                        maximized_after_minimize["bounds"] != metrics["workArea"]):
                    raise RuntimeError(
                        "Restore after minimize lost the work-area maximize state: "
                        f"{maximized_after_minimize}"
                    )
                state = api.window_toggle_maximize()
                window.evaluate_js("window.__lexeditorApplyWindowState({maximized:false}); true")
                wait_for_javascript(
                    "document.querySelectorAll('.pywebview-drag-region').length",
                    1,
                )
                host_trace.append("unmaximize-called")
                restored_after = native_window_metrics(window)
                if (state["maximized"] or
                        "normal" not in restored_after["windowState"].casefold() or
                        restored_after["bounds"] != restored_metrics["bounds"]):
                    raise RuntimeError(
                        f"The window did not restore its prior rectangle: {restored_after}"
                    )
                resize_edges = (
                    "top", "right", "bottom", "left",
                    "top-left", "top-right", "bottom-right", "bottom-left",
                )
                for edge in resize_edges:
                    before_resize = native_window_metrics(window)["bounds"]
                    api.window_resize_by(edge, 12, 12)
                    changed_resize = native_window_metrics(window)["bounds"]
                    if changed_resize == before_resize:
                        raise RuntimeError(f"The restored {edge} handle did not resize the window")
                    restore_from_work_area(window, before_resize)
                result["nativeResizeEdges"] = list(resize_edges)
                host_trace.append("restored-resize-verified")
                api.window_minimize()
                host_trace.append("normal-minimize-called")
                native_state = str(window.native.WindowState).casefold()
                if "minimized" not in native_state:
                    raise RuntimeError(f"The native window did not minimize: {native_state}")
                window.restore()
                host_trace.append("normal-restore-called")
                native_state = str(window.native.WindowState).casefold()
                if "normal" not in native_state:
                    raise RuntimeError(f"The native window did not restore after minimize: {native_state}")
                result["nativeWindowState"] = True
            results.append(result)
            if current_phase == 0:
                window.evaluate_js("document.querySelector('#global-undo').click()")
                wait_for_javascript("document.querySelector('#global-save').disabled")
                window.evaluate_js("document.querySelector('.lex-brand-button').click()")
                host_trace.append("main-menu-requested-by-wordmark")
                with lock:
                    pending_loaded = True
            elif current_phase == 3:
                result["nativeClose"] = True
                api.window_close()
        except Exception as error:
            errors.append(str(error))
            try:
                window.destroy()
            except Exception:
                pass
        finally:
            rerun = False
            with lock:
                busy = False
                if pending_loaded:
                    pending_loaded = False
                    rerun = True
            if rerun:
                threading.Thread(target=inspect_loaded, daemon=True).start()

    def on_loaded(*_args) -> None:
        host_trace.append("loaded-event")
        threading.Thread(target=inspect_loaded, daemon=True).start()

    def timeout() -> None:
        if len(results) < 2 and not errors:
            errors.append(
                "The hidden WebView2 switch check timed out; "
                f"navigation trace: {navigation_trace}; host trace: {host_trace}; "
                f"home error: {api._main_menu_navigation_error!r}"
            )
        try:
            window.destroy()
        except Exception:
            pass

    window.events.loaded += on_loaded
    timer = threading.Timer(50, timeout)
    timer.daemon = True
    timer.start()
    try:
        webview.start(
            gui="edgechromium",
            private_mode=True,
            storage_path=str(STORAGE / "smoke"),
            icon=str(ICON),
        )
    finally:
        timer.cancel()
        api.dispose()
    if errors:
        raise RuntimeError(errors[0])
    if len(results) != 2:
        raise RuntimeError(f"Expected two rendered plugins; got {len(results)}")
    if len(main_menu_results) != 1:
        raise RuntimeError(f"Expected one rendered main menu; got {len(main_menu_results)}")
    main_menu = main_menu_results[0]
    if (not main_menu["windowControls"] or main_menu["dragRegions"] < 1 or
            main_menu["resizeHandles"] != 8 or main_menu["maximized"] != "false"):
        raise RuntimeError(f"The main menu did not use the shared restored window frame: {main_menu}")
    if (not main_menu["bodyFont"].startswith("Lexend") or
            not main_menu["headingFont"].startswith("Lexend")):
        raise RuntimeError(f"The main menu rendered a fallback font: {main_menu}")
    font_rows = {row["plugin"]: row for row in main_menu["fonts"]}
    if set(font_rows) != set(plugins):
        raise RuntimeError(f"The main menu did not render every plugin card: {font_rows}")
    for plugin_id, plugin in plugins.items():
        row = font_rows[plugin_id]
        if row["count"] or row["tooltip"] or row["items"]:
            raise RuntimeError(f"The main menu exposed font details for {plugin_id}: {row}")
    for expected, result in zip((first, second), results):
        if result["plugin"] != expected or result["theme"] != expected:
            raise RuntimeError(f"The shared host loaded the wrong plugin theme: {result}")
        if result["renderer"] != "edgechromium" or result["windowCount"] != 1:
            raise RuntimeError(f"The plugin did not use one WebView2 window: {result}")
        if (not result["frameless"] or result["dragRegions"] != 1 or
                result["supportedDragRegions"] != 1 or result["resizeHandles"] != 8 or
                (expected == first and not result.get("maximizedInteractionsBlocked"))):
            raise RuntimeError(f"The plugin did not use the shared frameless window: {result}")
        if not all(result[key] for key in (
            "shell", "help", "info", "project", "restart", "undo", "redo", "save", "minimize", "maximize", "close"
        )):
            raise RuntimeError(f"The plugin did not use the shared shell controls: {result}")
        expected_order = [
            "global-save", "global-game-process", "global-undo", "global-redo", "plugin-data-map", "plugin-info", "plugin-restart",
            "window-minimize", "window-maximize", "window-close",
        ]
        expected_with_settings = expected_order.copy()
        expected_with_settings.insert(4, "lexeditor-settings")
        if result["commandOrder"] not in (expected_order, expected_with_settings):
            raise RuntimeError(f"The shared two-row command order is wrong: {result}")
        if (result["projectActions"] != ["New Mod", "Find a Mod"] or
                result["separateProjectActions"]):
            raise RuntimeError(f"The project selector actions are wrong: {result}")
        geometry = result.get("projectGeometry") or {}
        if (not geometry.get("font") or
                geometry.get("display") != "flex" or geometry.get("align") != "center" or
                (geometry.get("pathRect", [0, 0])[1] and geometry.get("centerDelta", 99) > 1) or
                geometry.get("marker") not in ('""', "none") or
                result.get("projectStatusText")):
            raise RuntimeError(f"The project selector is visually misaligned: {result}")
        if (result["navScrollButtons"] or result["navOverflow"] or
                result["navWrap"] != "wrap" or not result["saveBeforeWindows"]):
            raise RuntimeError(f"The shared tabs still scroll or the window controls are misplaced: {result}")
    if (not results[0].get("nativeWindowState") or
            len(results[0].get("nativeResizeEdges", [])) != 8 or
            not results[0].get("mainMenuReturn") or
            not results[0].get("residentReturn") or
            not results[1].get("nativeClose")):
        raise RuntimeError("The hidden native window-action check did not run")
    if not results[0].get("navigationHistory"):
        raise RuntimeError("The hidden Back/Forward and guarded Home check did not run")
    return [
        f"{first} rendered in one WebView2 window with its own theme",
        f"returning home kept {first} resident; its handle resumed the same service before the menu opened {second}",
        "both plugins used one frameless title bar with native window controls",
        "native minimize, maximize, restore, and close passed in the hidden host",
        "maximized move and resize input was rejected by the shared frame and native host",
        "frameless maximize matched the Windows work area and preserved the taskbar",
        "the running window exposed the Lexeditor AppUserModelID and both native icons",
        "both plugins used the shared Project, Data Map, Info, Save, Undo, and Redo controls",
        "the restored main menu used the shared window controls, drag region, and resize handles",
        "the main menu kept font details inside each plugin's information page",
        "shared Back/Forward traversed plugin destinations while the wordmark kept the unsaved Home guard",
    ]
