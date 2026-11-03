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
    {"id": "kf1.renderdistance", "label": "View distance (cells)", "kind": "number", "minimum": 0, "maximum": 30, "step": 1, "default": 16,
     "description": "Use 8–30 to extend the world, or 0 for its original reach. Original visible cells remain. Fog becomes black beyond about 9.17."},
    {"id": "kf1.renderdistance.fade", "label": "Smooth distance fade", "kind": "boolean", "default": True,
     "description": "Fades geometry near the view edge. This does not change view distance or the game's fog shading."},
    {"id": "kf1.controls.holdrun", "label": "Hold to run", "kind": "boolean", "default": True,
     "description": "Doubles movement while Run is held. The control preset binds Circle and Left Shift to Run."},
)


def game_root() -> Path:
    spec = manifest_in(Path(__file__).parent)["installation"]
    return Path(os.environ.get(spec["rootEnv"], spec["defaultRoots"][0])).resolve()


def read_file(root: Path, name: str) -> bytes:
    path = root / name
    if is_link(root) or is_link(path):
        raise ValueError("Settings cannot use linked files")
    if not path.exists():
        return b""
    if path.stat().st_size > MAX_BYTES:
        raise ValueError(f"{name} exceeds the settings size limit")
    return path.read_bytes()


def verify_port(root: Path) -> None:
    marker = json.loads(read_file(root, "lexeditor-port.json"))
    if marker.get("game") != "kf1" or marker.get("settingsVersion") != 1:
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


def write_settings(root: Path, changes: dict[str, str], *, expected: str | None = None, controls: bool = False) -> None:
    verify_port(root)
    stopped()
    original = read_file(root, "interface.ini")
    if expected is not None and sha256(original).hexdigest() != expected:
        raise ValueError("Port settings changed; reload before saving")
    outputs = {root / "interface.ini": update_ini(original, changes)}
    if controls:
        data = read_file(root, "settings.json")
        config = json.loads(data)
        # Native pad configuration plus the port's Western face permutation.
        config.setdefault("Keys", {}).update(Circle="E", R3="ShiftLeft")
        for name in ("Pad", "PadAnalog"):
            config.setdefault(name, {}).update(Cross=[0], Circle=[1, 3], Square=[10, 101], Triangle=[9, 100, 2], L1=[], R1=[], L2=[], R2=[], R3=[1])
        outputs[root / "settings.json"] = (json.dumps(config, indent=2) + "\n").encode()
    expected_hashes = {}
    for path in list(outputs):
        before = read_file(root, path.name)
        expected_hashes[path] = sha256(before).hexdigest() if path.exists() else None
        # Bounded recovery: one original and the immediately previous version.
        if path.exists():
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
            "sha256": sha256(data).hexdigest(), "sections": [{"label": "Display and controls", "fields": fields}]}


def save(body: dict) -> dict:
    changes = {}
    for field in FIELDS:
        value = body.get("values", {}).get(field["id"])
        if field["kind"] == "boolean":
            if type(value) is not bool:
                raise ValueError(f"{field['label']} needs an on/off choice")
            changes[field["id"]] = "3" if value and field["id"].endswith(".fade") else "1" if value else "0"
        else:
            if type(value) not in (int, float) or not math.isfinite(value) or (value != 0 and not 8 <= value <= 30):
                raise ValueError(f"{field['label']} must be 0 or between 8 and 30")
            changes[field["id"]] = str(value)
    if not isinstance(body.get("sha256"), str):
        raise ValueError("Reload the port settings before saving")
    with LOCK:
        write_settings(game_root(), changes, expected=body["sha256"])
        return payload()
