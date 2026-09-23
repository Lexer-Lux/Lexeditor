"""Lexeditor's ReShade effects, switched on and tuned per game.

Every effect is one of Lexeditor's own (shaders). Its
controls are read straight out of the .fx file - the same uniforms and
annotations ReShade's own overlay reads - so a slider added to a shader shows
up on the Tweaks page without a second list to keep in step.

What is switched on, and every value, lives in the game's ReShade preset: the
plain file ReShade itself loads (PresetPath in ReShade.ini, ReShadePreset.ini
beside the loader by default). A game's defaults are that same file, kept in
the plugin as reshade-defaults.ini and set by Lexer.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import reshade_projects

DEFAULTS_NAME = "reshade-defaults.ini"
DEFAULT_PRESET = "ReShadePreset.ini"
# The order effects run in, and are listed in. Compare wraps everything else:
# its first technique saves the untouched frame, its second draws it back.
ORDER = ("AmbientOcclusion", "DepthOfField", "Bloom", "Colors", "Sharpen", "Vignette", "Compare")

_UNIFORM = re.compile(r"uniform\s+(float|int|bool)\s+(\w+)\s*<([^<>]*)>\s*=\s*([^;]+);")
_TECHNIQUE = re.compile(r"technique\s+(\w+)(?:\s*<([^<>]*)>)?")
_ANNOTATION = re.compile(r'(\w+)\s*=\s*("(?:[^"\\]|\\.)*"|[^;]+);')


def _annotations(text: str) -> dict:
    found = {}
    for key, raw in _ANNOTATION.findall(text):
        raw = raw.strip()
        found[key] = raw[1:-1] if raw.startswith('"') else raw
    return found


def _number(text, kind: str):
    text = str(text).strip()
    if kind == "bool":
        return text.lower() in ("true", "1")
    value = float(text.rstrip("fF"))
    return int(round(value)) if kind == "int" else value


def parse_effect(path: Path) -> dict:
    """One effect's techniques and controls, as ReShade's overlay would show them."""
    source = Path(path).read_text(encoding="utf-8", errors="replace")
    controls = []
    for kind, name, notes, default in _UNIFORM.findall(source):
        meta = _annotations(notes)
        if "source" in meta:
            continue
        items = [item for item in meta.get("ui_items", "").split("\\0") if item]
        control = {
            "name": name, "type": kind,
            "widget": "checkbox" if kind == "bool" else "combo" if items else meta.get("ui_type", "slider"),
            "label": meta.get("ui_label", name),
            "tooltip": meta.get("ui_tooltip", ""),
            "default": _number(default, kind),
        }
        if items:
            control["items"] = items
        for key in ("ui_min", "ui_max", "ui_step"):
            if key in meta:
                control[key[3:]] = _number(meta[key], "float")
        controls.append(control)
    techniques = []
    for name, notes in _TECHNIQUE.findall(source):
        meta = _annotations(notes or "")
        techniques.append({"name": name, "label": meta.get("ui_label", name),
                           "tooltip": meta.get("ui_tooltip", "")})
    return {"file": Path(path).name, "id": Path(path).stem, "techniques": techniques,
            "label": techniques[0]["label"] if techniques else Path(path).stem,
            "tooltip": techniques[0]["tooltip"] if techniques else "",
            "controls": controls}


def catalogue(folder: Path | None = None) -> list[dict]:
    folder = Path(folder or reshade_projects.BUNDLED_SHADERS)
    effects = [parse_effect(path) for path in sorted(folder.glob("*.fx"))]
    rank = {name: index for index, name in enumerate(ORDER)}
    return sorted(effects, key=lambda effect: (rank.get(effect["id"], len(ORDER)), effect["id"]))


# ---- The preset file -------------------------------------------------------

def read_preset(path: Path) -> tuple[dict, dict]:
    """(top-level keys, {section: {key: value}}), in file order."""
    top: dict[str, str] = {}
    sections: dict[str, dict[str, str]] = {}
    current = top
    if Path(path).is_file():
        for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith((";", "#")):
                continue
            if stripped.startswith("[") and stripped.endswith("]"):
                current = sections.setdefault(stripped[1:-1], {})
            elif "=" in stripped:
                key, value = stripped.split("=", 1)
                current[key.strip()] = value.strip()
    return top, sections


def write_preset(path: Path, top: dict, sections: dict) -> None:
    lines = [f"{key}={value}" for key, value in top.items()]
    for name, values in sections.items():
        lines += ["", f"[{name}]"] + [f"{key}={value}" for key, value in values.items()]
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def preset_path(game_root: Path) -> Path:
    """The preset ReShade loads for this game, as its ReShade.ini names it."""
    game_root = Path(game_root)
    top, sections = read_preset(game_root / reshade_projects.RESHADE_INI)
    named = sections.get("GENERAL", {}).get("PresetPath") or top.get("PresetPath") or ""
    if not named:
        return game_root / DEFAULT_PRESET
    candidate = Path(named)
    return candidate if candidate.is_absolute() else (game_root / candidate).resolve()


def _format(value, kind: str) -> str:
    if kind == "bool":
        return "1" if value else "0"
    if kind == "int":
        return str(int(value))
    return f"{float(value):.6f}"


def _technique_list(text: str) -> list[str]:
    return [item for item in (text or "").split(",") if item]


def _ordered(enabled_files: set[str], effects: list[dict]) -> list[str]:
    """ReShade's Techniques value: every technique of each on effect, in run order."""
    listed = []
    compare = None
    for effect in effects:
        if effect["file"] not in enabled_files:
            continue
        names = [f"{technique['name']}@{effect['file']}" for technique in effect["techniques"]]
        if effect["id"] == "Compare":
            compare = names
            continue
        listed += names
    if compare:
        listed = compare[:1] + listed + compare[1:]
    return listed


# ---- What the Tweaks page reads and changes --------------------------------

def state(game_root: Path | None, defaults: Path | None = None) -> dict:
    effects = catalogue()
    path = preset_path(game_root) if game_root else None
    top, sections = read_preset(path) if path else ({}, {})
    on = {item.split("@", 1)[-1] for item in _technique_list(top.get("Techniques", ""))}
    rows = []
    for effect in effects:
        saved = sections.get(effect["file"], {})
        values = {}
        for control in effect["controls"]:
            try:
                values[control["name"]] = (_number(saved[control["name"]], control["type"])
                                           if control["name"] in saved else control["default"])
            except ValueError:
                values[control["name"]] = control["default"]
        rows.append({**effect, "enabled": effect["file"] in on, "values": values})
    return {"effects": rows, "presetPath": str(path) if path else "",
            "hasDefaults": bool(defaults and Path(defaults).is_file()),
            "defaultsPath": str(defaults) if defaults else ""}


def _effect(file: str) -> dict:
    effect = next((row for row in catalogue() if row["file"] == file), None)
    if effect is None:
        raise ValueError(f"No Lexeditor effect called {file}")
    return effect


def set_enabled(game_root: Path, file: str, enabled: bool) -> None:
    effects = catalogue()
    _effect(file)
    path = preset_path(game_root)
    top, sections = read_preset(path)
    on = {item.split("@", 1)[-1] for item in _technique_list(top.get("Techniques", ""))}
    on = (on | {file}) if enabled else (on - {file})
    order = _ordered({row["file"] for row in effects}, effects)
    top["Techniques"] = ",".join(_ordered(on, effects))
    top["TechniqueSorting"] = ",".join(order)
    write_preset(path, top, sections)


def set_value(game_root: Path, file: str, name: str, value) -> None:
    control = next((row for row in _effect(file)["controls"] if row["name"] == name), None)
    if control is None:
        raise ValueError(f"{file} has no setting called {name}")
    if control["type"] == "bool":
        value = bool(value)
    else:
        value = float(value)
        if "min" in control:
            value = max(control["min"], value)
        if "max" in control:
            value = min(control["max"], value)
        if "items" in control:
            value = max(0, min(len(control["items"]) - 1, int(round(value))))
    path = preset_path(game_root)
    top, sections = read_preset(path)
    sections.setdefault(file, {})[name] = _format(value, control["type"])
    write_preset(path, top, sections)


def reset(game_root: Path, defaults: Path | None) -> None:
    """Back to the game's defaults, or to every effect off at its shader defaults."""
    path = preset_path(game_root)
    if defaults and Path(defaults).is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(defaults, path)
        return
    write_preset(path, {"Techniques": "", "TechniqueSorting": ",".join(
        _ordered({row["file"] for row in catalogue()}, catalogue()))}, {})


def ensure_preset(game_root: Path, defaults: Path | None) -> None:
    if not preset_path(game_root).is_file():
        reset(game_root, defaults)


def save_defaults(game_root: Path, defaults: Path) -> None:
    """Make this game's current look its defaults (Developer Mode only)."""
    source = preset_path(game_root)
    if not source.is_file():
        raise ValueError("There is no preset in this game to save yet.")
    top, sections = read_preset(source)
    known = {row["file"] for row in catalogue()}
    # Only Lexeditor's own effects belong in a default; leftovers from other
    # shader packs would name effects nobody else has.
    top = {key: value for key, value in top.items() if key in ("Techniques", "TechniqueSorting")}
    top["Techniques"] = ",".join(item for item in _technique_list(top.get("Techniques", ""))
                                 if item.split("@", 1)[-1] in known)
    top["TechniqueSorting"] = ",".join(_ordered(known, catalogue()))
    write_preset(Path(defaults), top, {name: values for name, values in sections.items() if name in known})
