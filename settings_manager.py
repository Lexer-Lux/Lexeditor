"""Persistent settings shared by the Lexeditor shell and managed helpers."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import threading


ROOT = Path(os.environ.get("LOCALAPPDATA", Path(__file__).resolve().parent / "out")) / "Lexeditor"
DEFAULT_PATH = ROOT / "settings.json"
PACKAGED_DEFAULTS_PATH = Path(__file__).resolve().parent / "ui" / "default_settings.json"
UPDATE_FREQUENCIES = {
    "every-launch": ("Every launch", 0),
    "daily": ("Daily", 24 * 60 * 60),
    "weekly": ("Weekly", 7 * 24 * 60 * 60),
    "monthly": ("Monthly", 30 * 24 * 60 * 60),
    "never": ("Never", None),
}
DEFAULTS = {
    "updateCheckFrequency": "daily",
    "hoverableAltClick": False,
    "selectionHoldMs": 650,
    "tableRowsPerPage": 15,
    "panelGapPercent": 1.0,
    "residentHandleWidthPercent": 5.0,
    "mainMenuHeightPercent": 9.0,
    "soundEnabled": True,
    "soundVolumePercent": 50.0,
    "absentGameDesaturationPercent": 75.0,
    "globalMessageRarity": 3.0,
    "loadingTransitionMinimumSeconds": 1.5,
    "viewPreferences": {},
}
PACKAGED_DEFAULT_KEYS = tuple(key for key in DEFAULTS if key != "viewPreferences")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_time(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


class SettingsStore:
    def __init__(self, path: Path | None = None,
                 defaults_path: Path | None = None) -> None:
        self.path = Path(path or DEFAULT_PATH)
        self.defaults_path = Path(defaults_path or PACKAGED_DEFAULTS_PATH)
        self._lock = threading.RLock()

    def _packaged_defaults(self) -> dict:
        try:
            payload = json.loads(self.defaults_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            payload = {}
        return {**DEFAULTS, **{
            key: payload[key] for key in PACKAGED_DEFAULT_KEYS if key in payload
        }}

    def _read(self) -> dict:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            payload = {}
        defaults = self._packaged_defaults()
        frequency = payload.get("updateCheckFrequency", defaults["updateCheckFrequency"])
        if frequency not in UPDATE_FREQUENCIES:
            frequency = defaults["updateCheckFrequency"]
        raw_preferences = payload.get("viewPreferences", {})
        try:
            selection_hold_ms = int(payload.get("selectionHoldMs", defaults["selectionHoldMs"]))
        except (TypeError, ValueError):
            selection_hold_ms = defaults["selectionHoldMs"]
        try:
            table_rows_per_page = int(payload.get(
                "tableRowsPerPage", defaults["tableRowsPerPage"],
            ))
        except (TypeError, ValueError):
            table_rows_per_page = defaults["tableRowsPerPage"]
        try:
            panel_gap_percent = float(payload.get("panelGapPercent", defaults["panelGapPercent"]))
        except (TypeError, ValueError):
            panel_gap_percent = defaults["panelGapPercent"]
        try:
            resident_handle_width_percent = float(payload.get(
                "residentHandleWidthPercent", defaults["residentHandleWidthPercent"],
            ))
        except (TypeError, ValueError):
            resident_handle_width_percent = DEFAULTS["residentHandleWidthPercent"]
        try:
            main_menu_height_percent = float(payload.get(
                "mainMenuHeightPercent", defaults["mainMenuHeightPercent"],
            ))
        except (TypeError, ValueError):
            main_menu_height_percent = defaults["mainMenuHeightPercent"]
        try:
            absent_game_desaturation_percent = float(payload.get(
                "absentGameDesaturationPercent", defaults["absentGameDesaturationPercent"]
            ))
        except (TypeError, ValueError):
            absent_game_desaturation_percent = DEFAULTS["absentGameDesaturationPercent"]
        try:
            sound_volume_percent = float(payload.get(
                "soundVolumePercent", defaults["soundVolumePercent"]
            ))
        except (TypeError, ValueError):
            sound_volume_percent = DEFAULTS["soundVolumePercent"]
        try:
            global_message_rarity = float(payload.get(
                "globalMessageRarity", defaults["globalMessageRarity"]
            ))
        except (TypeError, ValueError):
            global_message_rarity = DEFAULTS["globalMessageRarity"]
        try:
            loading_transition_minimum_seconds = float(payload.get(
                "loadingTransitionMinimumSeconds", defaults["loadingTransitionMinimumSeconds"]
            ))
        except (TypeError, ValueError):
            loading_transition_minimum_seconds = DEFAULTS["loadingTransitionMinimumSeconds"]
        view_preferences = {
            str(key): int(value)
            for key, value in raw_preferences.items()
            if isinstance(key, str) and isinstance(value, int) and (
                (key.startswith("rows:") and 5 <= value <= 80) or
                (not key.startswith("rows:") and 1 <= value <= 6)
            )
        } if isinstance(raw_preferences, dict) else {}
        return {
            "updateCheckFrequency": frequency,
            "hoverableAltClick": payload.get("hoverableAltClick", defaults["hoverableAltClick"]) is True,
            "selectionHoldMs": max(150, min(2000, selection_hold_ms)),
            "tableRowsPerPage": max(5, min(40, table_rows_per_page)),
            "panelGapPercent": max(0.25, min(4.0, panel_gap_percent)),
            "residentHandleWidthPercent": max(2.5, min(12.0, resident_handle_width_percent)),
            "mainMenuHeightPercent": max(3.0, min(20.0, main_menu_height_percent)),
            "soundEnabled": payload.get("soundEnabled", defaults["soundEnabled"]) is True,
            "soundVolumePercent": max(0.0, min(100.0, sound_volume_percent)),
            "absentGameDesaturationPercent": max(
                0.0, min(100.0, absent_game_desaturation_percent)
            ),
            "globalMessageRarity": max(1.0, min(100.0, global_message_rarity)),
            "loadingTransitionMinimumSeconds": max(
                0.0, min(10.0, loading_transition_minimum_seconds)
            ),
            "viewPreferences": view_preferences,
        }

    def _write(self, payload: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.path)

    def snapshot(self) -> dict:
        with self._lock:
            settings = self._read()
        return {
            **settings,
            "defaultValues": self._packaged_defaults(),
            "updateCheckChoices": [
                {"value": value, "label": label}
                for value, (label, _seconds) in UPDATE_FREQUENCIES.items()
            ],
        }

    def save(self, update_check_frequency: str,
             hoverable_alt_click: bool | None = None,
             selection_hold_ms: int | None = None,
             table_rows_per_page: int | None = None,
             panel_gap_percent: float | None = None,
             main_menu_height_percent: float | None = None,
             sound_enabled: bool | None = None,
             sound_volume_percent: float | None = None) -> dict:
        """Save per-user preferences. Authenticated authoring state is never persisted."""
        if update_check_frequency not in UPDATE_FREQUENCIES:
            raise ValueError("Choose a listed update-check frequency")
        current = self.snapshot()
        if hoverable_alt_click is None:
            hoverable_alt_click = current["hoverableAltClick"]
        if selection_hold_ms is None:
            selection_hold_ms = current["selectionHoldMs"]
        if table_rows_per_page is None:
            table_rows_per_page = current["tableRowsPerPage"]
        if panel_gap_percent is None:
            panel_gap_percent = current["panelGapPercent"]
        if main_menu_height_percent is None:
            main_menu_height_percent = current["mainMenuHeightPercent"]
        if sound_enabled is None:
            sound_enabled = current["soundEnabled"]
        selection_hold_ms = max(150, min(2000, int(selection_hold_ms)))
        table_rows_per_page = max(5, min(40, int(table_rows_per_page)))
        panel_gap_percent = max(0.25, min(4.0, float(panel_gap_percent)))
        main_menu_height_percent = max(3.0, min(20.0, float(main_menu_height_percent)))
        with self._lock:
            stored = self._read()
            payload = {
                "version": 8,
                "updateCheckFrequency": update_check_frequency,
                "hoverableAltClick": bool(hoverable_alt_click),
                "selectionHoldMs": selection_hold_ms,
                "tableRowsPerPage": table_rows_per_page,
                "panelGapPercent": panel_gap_percent,
                "mainMenuHeightPercent": main_menu_height_percent,
                "soundEnabled": bool(sound_enabled),
                "viewPreferences": stored["viewPreferences"],
            }
            if sound_volume_percent is not None:
                payload["soundVolumePercent"] = max(0.0, min(100.0, float(sound_volume_percent)))
            self._write(payload)
        return self.snapshot()

    def save_packaged_defaults(self, values: dict) -> dict:
        """Save checked-in application defaults after Developer Mode authorization."""
        if not isinstance(values, dict):
            raise ValueError("Packaged defaults must be an object")
        current = self._packaged_defaults()
        for key, value in values.items():
            if key not in PACKAGED_DEFAULT_KEYS:
                raise ValueError(f"Setting cannot be a packaged default: {key}")
            current[key] = value
        frequency = str(current["updateCheckFrequency"])
        if frequency not in UPDATE_FREQUENCIES:
            raise ValueError("Choose a listed update-check frequency")
        clean = {
            "updateCheckFrequency": frequency,
            "hoverableAltClick": bool(current["hoverableAltClick"]),
            "selectionHoldMs": max(150, min(2000, int(current["selectionHoldMs"]))),
            "tableRowsPerPage": max(5, min(40, int(current["tableRowsPerPage"]))),
            "panelGapPercent": max(0.25, min(4.0, float(current["panelGapPercent"]))),
            "residentHandleWidthPercent": max(2.5, min(12.0, float(current["residentHandleWidthPercent"]))),
            "mainMenuHeightPercent": max(3.0, min(20.0, float(current["mainMenuHeightPercent"]))),
            "soundEnabled": bool(current["soundEnabled"]),
            "soundVolumePercent": max(0.0, min(100.0, float(current["soundVolumePercent"]))),
            "absentGameDesaturationPercent": max(
                0.0, min(100.0, float(current["absentGameDesaturationPercent"]))
            ),
            "globalMessageRarity": max(
                1.0, min(100.0, float(current["globalMessageRarity"]))
            ),
            "loadingTransitionMinimumSeconds": max(
                0.0, min(10.0, float(current["loadingTransitionMinimumSeconds"]))
            ),
        }
        with self._lock:
            self.defaults_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.defaults_path.with_suffix(".tmp")
            temporary.write_text(json.dumps(clean, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            temporary.replace(self.defaults_path)
        return clean

    def save_view_preference(self, key: str, value: int) -> dict:
        """Save one local-only, bounded view preference."""
        key = str(key).strip()
        if not key or len(key) > 160 or any(
                character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789:_-"
                for character in key):
            raise ValueError("Invalid view preference key")
        value = int(value)
        minimum, maximum = (5, 80) if key.startswith("rows:") else (1, 6)
        if not minimum <= value <= maximum:
            raise ValueError(f"View preference must be from {minimum} through {maximum}")
        with self._lock:
            current = self._read()
            current["viewPreferences"][key] = value
            self._write({"version": 8, **current})
        return self.snapshot()

    def clear_view_preference(self, key: str) -> dict:
        """Remove one local view override so the global setting applies."""
        key = str(key).strip()
        if not key or len(key) > 160 or any(
                character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789:_-"
                for character in key):
            raise ValueError("Invalid view preference key")
        with self._lock:
            current = self._read()
            current["viewPreferences"].pop(key, None)
            self._write({"version": 8, **current})
        return self.snapshot()

    def update_due(self, last_check: str, now: datetime | None = None) -> bool:
        frequency = self.snapshot()["updateCheckFrequency"]
        seconds = UPDATE_FREQUENCIES[frequency][1]
        if seconds is None:
            return False
        previous = parse_time(last_check)
        if previous is None or seconds == 0:
            return True
        return ((now or utc_now()) - previous).total_seconds() >= seconds
