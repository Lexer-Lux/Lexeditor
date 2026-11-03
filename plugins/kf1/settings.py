"""Edit the native port's own settings, preserving ImGui sections and unknown keys."""
from __future__ import annotations

from hashlib import sha256
import json
import math
import os
from pathlib import Path
import threading

from core.plugin_files import atomic_write_group, is_link
from core.process_probe import live_processes
from core.plugin_manifest import manifest_in

LOCK = threading.RLock()
MAX_BYTES = 1024 * 1024
FIELDS = (
    {"id": "kf1.renderdistance", "label": "View distance (cells)", "kind": "number", "minimum": 0, "nonzeroMinimum": 8, "maximum": 30, "step": 1, "default": 16,
     "description": "Use 8–30 with Renderer set to Retained, or 0 for the original reach. Original visible cells remain. Fog becomes black beyond about 9.17."},
    {"id": "kf1.renderdistance.fade", "label": "Smooth distance fade", "kind": "boolean", "default": True,
     "description": "Fades geometry near the view edge. This does not change view distance or the game's fog shading."},
    {"id": "kf1.controls.holdrun", "label": "Hold to run", "kind": "boolean", "default": False,
     "description": "Doubles movement while Run is held. Modern Controls binds Circle and Left Shift to Run."},
)


def game_root() -> Path:
    spec = manifest_in(Path(__file__).parent)["installation"]
    return Path(os.environ.get(spec["rootEnv"], spec["defaultRoots"][0])).resolve()


def read_file(root: Path, name: str) -> bytes:
    path = root / name
    if is_link(root) or any(is_link(parent) for parent in (path, *path.parents) if parent == root or root in parent.parents):
        raise ValueError("Settings cannot use linked files")
    if not path.exists():
        return b""
    if path.stat().st_size > MAX_BYTES:
        raise ValueError(f"{name} exceeds the settings size limit")
    return path.read_bytes()


def verify_port(root: Path) -> None:
    marker = json.loads(read_file(root, "lexeditor-port.json"))
    if not isinstance(marker, dict) or marker.get("game") != "kf1" or marker.get("settingsVersion") != 1:
        raise ValueError("Install the supported Lexer-owned King's Field I port")
    assembly = root / "KingsField1.dll"
    if is_link(assembly) or sha256(assembly.read_bytes()).hexdigest() != marker.get("assemblySha256"):
        raise ValueError("The port assembly changed; repair its installation before editing settings")


def stopped() -> None:
    if live_processes(("KingsField1.exe",)):
        raise ValueError("King's Field I is running. Save and exit it before saving port settings.")


def parse_ini(data: bytes) -> dict[str, str]:
    section = ""
    values = {}
    for line in data.decode("utf-8-sig").splitlines():
        if line.startswith("["):
            section = line
        elif section == "[RecompOne]" and "=" in line:
            key, value = line.split("=", 1)
            key = key.casefold()
            if key in values:
                raise ValueError(f"Duplicate native setting: {key}")
            values[key] = value
    return values


def update_ini(data: bytes, changes: dict[str, str]) -> bytes:
    parse_ini(data)
    lines = data.decode("utf-8-sig").splitlines(keepends=True)
    start = next((i for i, line in enumerate(lines) if line.rstrip("\r\n") == "[RecompOne]"), None)
    if start is None:
        return ("[RecompOne]\n" + "".join(f"{key}={value}\n" for key, value in changes.items()) + "\n" + data.decode("utf-8-sig")).encode()
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("[")), len(lines))
    pending = dict(changes)
    for i in range(start + 1, end):
        key = lines[i].split("=", 1)[0].casefold()
        if key in pending:
            lines[i] = f"{key}={pending.pop(key)}\n"
    inserted = "".join(f"{key}={value}\n" for key, value in pending.items())
    if inserted and end > start + 1 and not lines[end - 1].endswith("\n"):
        lines[end - 1] += "\n"
    lines.insert(end, inserted)
    return "".join(lines).encode()


def control_profiles(root: Path) -> dict:
    data = read_file(root, "content/config/controls.json")
    marker = json.loads(read_file(root, "lexeditor-port.json"))
    if sha256(data).hexdigest() != marker.get("controlsSha256"):
        raise ValueError("The port's control profiles changed; repair its installation before running setup")
    profiles = json.loads(data)
    if not isinstance(profiles, dict) or profiles.get("version") != 1:
        raise ValueError("Unsupported native control profiles")
    for name in ("classic", "modern"):
        profile = profiles.get(name)
        if not isinstance(profile, dict) or any(not isinstance(profile.get(key), dict) for key in ("Keys", "Keys2", "Pad", "PadAnalog", "view")):
            raise ValueError("The port's control profiles are invalid")
    return profiles


def current_controls(root: Path, profiles: dict, ini: dict[str, str]) -> dict:
    data = read_file(root, "settings.json")
    config = json.loads(data)
    if not isinstance(config, dict):
        raise ValueError("The port's input settings are invalid; repair them in its F1 menu")
    selected = "custom"
    for name in ("classic", "modern"):
        profile = profiles[name]
        if all(config.get(key) == profile[key] for key in ("Keys", "Keys2", "Pad", "PadAnalog")) and all(
            ini.get(key, "1" if key == "kf1.pad.layout" else "0") == value for key, value in profile["view"].items()
        ):
            selected = name
            break
    return {"selected": selected, "sha256": sha256(data).hexdigest(), "setupComplete": ini.get("kf1.controls.setup") == "1"}


def write_settings(root: Path, changes: dict[str, str], *, expected: str | None = None,
                   profile: str | None = None, expected_controls: str | None = None, replace_custom: bool = False) -> None:
    verify_port(root)
    stopped()
    present = {root / "interface.ini": (root / "interface.ini").exists()}
    original = read_file(root, "interface.ini")
    if expected is not None and sha256(original).hexdigest() != expected:
        raise ValueError("Port settings changed; reload before saving")
    changes = dict(changes)
    outputs = {}
    snapshots = {root / "interface.ini": original}
    if profile is not None:
        if profile not in ("keep", "classic", "modern"):
            raise ValueError("Choose Keep current bindings, Classic Controls or Modern Controls")
        profiles = control_profiles(root)
        current = current_controls(root, profiles, parse_ini(original))
        if not isinstance(expected_controls, str) or current["sha256"] != expected_controls:
            raise ValueError("Input bindings changed; reload before running setup")
        data = read_file(root, "settings.json")
        if sha256(data).hexdigest() != expected_controls:
            raise ValueError("Input bindings changed; reload before running setup")
        config = json.loads(data)
        if profile != "keep":
            if current["selected"] == "custom" and not replace_custom:
                raise ValueError("Confirm replacing your custom bindings before applying a preset")
            selected = profiles[profile]
            config.update({key: selected[key] for key in ("Keys", "Keys2", "Pad", "PadAnalog")})
            changes.update(selected["view"])
            outputs[root / "settings.json"] = (json.dumps(config, indent=2) + "\n").encode()
            snapshots[root / "settings.json"] = data
            present[root / "settings.json"] = True
        changes["kf1.controls.setup"] = "1"
    outputs[root / "interface.ini"] = update_ini(original, changes)
    expected_hashes = {}
    for path in list(outputs):
        before = snapshots[path]
        expected_hashes[path] = sha256(before).hexdigest() if present[path] else None
        # Bounded recovery: one original and the immediately previous version.
        if present[path]:
            for suffix in (".lexeditor-original", ".lexeditor-previous"):
                backup = root / (path.name + suffix)
                if suffix.endswith("original") and backup.exists():
                    continue
                old = read_file(root, backup.name)
                outputs[backup] = before
                expected_hashes[backup] = sha256(old).hexdigest() if backup.exists() else None
    stopped()
    atomic_write_group(outputs, expected_hashes, limit=8 * MAX_BYTES)


def payload(root: Path | None = None) -> dict:
    root = root or game_root()
    verify_port(root)
    data = read_file(root, "interface.ini")
    values = parse_ini(data)
    fields = []
    for definition in FIELDS:
        field = dict(definition)
        raw = values.get(field["id"])
        if field["kind"] == "boolean":
            field["value"] = float(raw) > 0 if raw is not None else field["default"]
        else:
            field["value"] = float(raw) if raw is not None else field["default"]
        fields.append(field)
    return {"available": True, "runtime": "Verdite1", "path": str(root / "interface.ini"),
            "sha256": sha256(data).hexdigest(), "controls": current_controls(root, control_profiles(root), values),
            "sections": [{"label": "Display and controls", "fields": fields}]}


def setup_controls(body: dict) -> dict:
    if not isinstance(body.get("sha256"), str):
        raise ValueError("Reload the settings before running setup")
    if body.get("profile", "keep") not in ("keep", "classic", "modern"):
        raise ValueError("Choose Keep current bindings, Classic Controls or Modern Controls")
    with LOCK:
        write_settings(game_root(), {}, expected=body["sha256"], profile=body.get("profile", "keep"),
                       expected_controls=body.get("controlsSha256"), replace_custom=body.get("replaceCustom") is True)
        return payload()


def save(body: dict) -> dict:
    if not isinstance(body.get("values"), dict):
        raise ValueError("Settings values must be an object")
    changes = {}
    for field in FIELDS:
        value = body.get("values", {}).get(field["id"])
        if field["kind"] == "boolean":
            if type(value) is not bool:
                raise ValueError(f"{field['label']} needs an on/off choice")
            changes[field["id"]] = "3" if value and field["id"].endswith(".fade") else "1" if value else "0"
        else:
            if type(value) not in (int, float) or not math.isfinite(value) or (value != 0 and not field["nonzeroMinimum"] <= value <= field["maximum"]):
                raise ValueError(f"{field['label']} must be 0 or between 8 and 30")
            changes[field["id"]] = str(value)
    if not isinstance(body.get("sha256"), str):
        raise ValueError("Reload the port settings before saving")
    with LOCK:
        root = game_root()
        if body["values"]["kf1.renderdistance.fade"]:
            existing = parse_ini(read_file(root, "interface.ini")).get("kf1.renderdistance.fade", "0")
            band = float(existing)
            if math.isfinite(band) and band > 0:
                changes["kf1.renderdistance.fade"] = existing
        write_settings(root, changes, expected=body["sha256"])
        return payload()
