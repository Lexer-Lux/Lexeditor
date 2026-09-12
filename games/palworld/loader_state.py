"""Read-only view of Pocketpair's ``Mods/PalModSettings.ini`` loader state."""

from __future__ import annotations

from pathlib import Path
from typing import Any


MAX_SETTINGS_BYTES = 1024 * 1024
SECTION = "palmodsettings"


class LoaderSettingsError(ValueError):
    pass


def _parse_bool(value: str) -> bool | None:
    lowered = value.strip().casefold()
    if lowered in {"true", "1", "yes", "on"}:
        return True
    if lowered in {"false", "0", "no", "off"}:
        return False
    return None


def parse_settings_bytes(raw: bytes) -> dict[str, Any]:
    if len(raw) > MAX_SETTINGS_BYTES:
        raise LoaderSettingsError(f"PalModSettings.ini exceeds the {MAX_SETTINGS_BYTES}-byte safety limit")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise LoaderSettingsError(f"PalModSettings.ini is not valid UTF-8: {error}") from error

    section = ""
    global_enabled: bool | None = None
    workshop_root = ""
    active: list[str] = []
    for line_number, raw_line in enumerate(text.splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith((";", "#")):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip().casefold()
            continue
        if section != SECTION or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().casefold()
        value = value.strip()
        if key == "bglobalenablemod":
            parsed = _parse_bool(value)
            if parsed is None:
                raise LoaderSettingsError(
                    f"PalModSettings.ini line {line_number} has invalid bGlobalEnableMod value {value!r}"
                )
            global_enabled = parsed
        elif key == "workshoprootdir":
            workshop_root = value
        elif key == "activemodlist" and value:
            active.append(value)

    return {
        "globalEnabled": global_enabled,
        "workshopRootDir": workshop_root,
        "activeModList": active,
    }


def status(game_root: Path | None, package_name: str = "") -> dict[str, Any]:
    if game_root is None:
        return {
            "available": False,
            "path": "",
            "globalEnabled": None,
            "workshopRootDir": "",
            "activeModList": [],
            "packageName": package_name,
            "listed": False,
            "active": False,
            "reason": "No Palworld installation root is selected.",
        }
    path = Path(game_root).expanduser().resolve() / "Mods" / "PalModSettings.ini"
    if not path.is_file():
        return {
            "available": False,
            "path": str(path),
            "globalEnabled": None,
            "workshopRootDir": "",
            "activeModList": [],
            "packageName": package_name,
            "listed": False,
            "active": False,
            "reason": "PalModSettings.ini does not exist yet. Palworld creates/updates it through Mod Management.",
        }
    parsed = parse_settings_bytes(path.read_bytes())
    listed = bool(package_name and package_name in parsed["activeModList"])
    globally_enabled = parsed["globalEnabled"] is True
    return {
        "available": True,
        "path": str(path),
        **parsed,
        "packageName": package_name,
        "listed": listed,
        "active": bool(globally_enabled and listed),
        "reason": (
            "Package is active in the loader configuration."
            if globally_enabled and listed
            else "Package is listed but mods are globally disabled."
            if listed
            else "Package is not listed in ActiveModList. Enable it through Palworld Options → Mod Management."
        ),
    }
