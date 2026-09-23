"""Reversible FF7R graphics tweaks backed by the standard UE4 Engine.ini path.

FFVIIHook unlocks loading of the game's standard user INI files. Lexeditor never
assumes that an arbitrary proxy DLL is sufficient: enabling an INI-backed tweak
requires a recognizable INI-unlocker candidate next to ff7remake_.exe. The
managed block is appended at the end of Engine.ini so it wins over earlier
values while preserving all unrelated user configuration.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any


GRAPHICS_SCHEMA_VERSION = 1
GRAPHICS_CONFIG_NAME = "LexeditorFF7RGraphicsTweaks.json"
GRAPHICS_TWEAKS_ASSET = "Lexeditor/GraphicsTweaks"

INI_PROXY_CANDIDATES = (
    "xinput1_3.dll",
    "dxgi.dll",
    "X3DAudio1_7.dll",
    "XAPOFX1_5.dll",
)

# FFVIIHook's documented purpose is to unlock the standard UE4 INI path. These
# markers are deliberately conservative: a random proxy DLL with the same file
# name must not make Lexeditor claim Engine.ini support is verified.
INI_UNLOCKER_MARKERS = (
    "FFVIIHook",
    "Engine.ini",
    "WindowsNoEditor",
    "ff7remake_",
    "ConsoleVariables",
)

MANAGED_BEGIN = "; BEGIN LEXEDITOR FF7R EYE ADAPTATION"
MANAGED_END = "; END LEXEDITOR FF7R EYE ADAPTATION"
EYE_ADAPTATION_CVAR = "r.EyeAdaptationQuality=0"
MANAGED_BLOCK = (
    f"{MANAGED_BEGIN}\n"
    "[SystemSettings]\n"
    f"{EYE_ADAPTATION_CVAR}\n"
    f"{MANAGED_END}\n"
)

DEFAULT_GRAPHICS_CONFIG = {
    "schemaVersion": GRAPHICS_SCHEMA_VERSION,
    "disableEyeAdaptation": False,
}


def config_path(project_root: Path) -> Path:
    return Path(project_root) / "runtime" / GRAPHICS_CONFIG_NAME


def engine_ini_path() -> Path:
    override = os.environ.get("LEXEDITOR_FF7R_ENGINE_INI")
    if override:
        return Path(override).expanduser().resolve()
    return (
        Path.home()
        / "Documents"
        / "My Games"
        / "FINAL FANTASY VII REMAKE"
        / "Saved"
        / "Config"
        / "WindowsNoEditor"
        / "Engine.ini"
    )


def validate_graphics_config(value: dict) -> dict:
    if not isinstance(value, dict):
        raise ValueError("graphics tweak config must be an object")
    allowed = {"schemaVersion", "disableEyeAdaptation"}
    if set(value) - allowed:
        raise ValueError("graphics tweak config contains unsupported fields")
    if value.get("schemaVersion", GRAPHICS_SCHEMA_VERSION) != GRAPHICS_SCHEMA_VERSION:
        raise ValueError("unsupported FF7R graphics tweak config schema")
    disabled = value.get("disableEyeAdaptation", False)
    if not isinstance(disabled, bool):
        raise ValueError("disableEyeAdaptation must be boolean")
    return {
        "schemaVersion": GRAPHICS_SCHEMA_VERSION,
        "disableEyeAdaptation": disabled,
    }


def load_graphics_config(project_root: Path) -> dict:
    target = config_path(project_root)
    if not target.is_file():
        return dict(DEFAULT_GRAPHICS_CONFIG)
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Could not read FF7R graphics tweak config: {error}") from error
    return validate_graphics_config(payload)


def save_graphics_config(project_root: Path, value: dict) -> dict:
    validated = validate_graphics_config(value)
    target = config_path(project_root)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(validated, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, target)
    reread = load_graphics_config(project_root)
    if reread != validated:
        raise RuntimeError("FF7R graphics tweak config failed atomic readback")
    return reread


def _marker_hits(data: bytes) -> list[str]:
    hits: list[str] = []
    folded = data.lower()
    for marker in INI_UNLOCKER_MARKERS:
        ascii_marker = marker.encode("ascii").lower()
        utf16_marker = marker.encode("utf-16-le").lower()
        if ascii_marker in folded or utf16_marker in folded:
            hits.append(marker)
    return hits


def detect_ini_unlocker(game_root: Path) -> dict:
    binary_root = Path(game_root) / "End" / "Binaries" / "Win64"
    candidates = []
    for name in INI_PROXY_CANDIDATES:
        path = binary_root / name
        if not path.is_file():
            continue
        try:
            data = path.read_bytes()
        except OSError as error:
            candidates.append({
                "path": str(path),
                "name": name,
                "size": None,
                "markers": [],
                "verified": False,
                "error": str(error),
            })
            continue
        markers = _marker_hits(data)
        # Require explicit Engine.ini evidence plus at least one FF7R/config
        # context marker. Merely finding a proxy DLL is a candidate, not proof.
        verified = "Engine.ini" in markers and any(
            marker in markers
            for marker in ("FFVIIHook", "WindowsNoEditor", "ff7remake_", "ConsoleVariables")
        )
        candidates.append({
            "path": str(path),
            "name": name,
            "size": len(data),
            "markers": markers,
            "verified": verified,
            "error": "",
        })
    verified = [row for row in candidates if row["verified"]]
    return {
        "candidatePresent": bool(candidates),
        "verified": bool(verified),
        "candidates": candidates,
        "verifiedPaths": [row["path"] for row in verified],
    }


def _read_ini(target: Path) -> tuple[str, bool]:
    if not target.is_file():
        return "", False
    raw = target.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    try:
        text = raw.decode("utf-8-sig" if bom else "utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(
            f"FF7R Engine.ini is not valid UTF-8 and cannot be safely edited: {target}"
        ) from error
    return text, bom


def _encode_ini(text: str, bom: bool) -> bytes:
    return text.encode("utf-8-sig" if bom else "utf-8")


def _managed_span(text: str) -> tuple[int, int] | None:
    begins = [match.start() for match in re.finditer(re.escape(MANAGED_BEGIN), text)]
    ends = [match.end() for match in re.finditer(re.escape(MANAGED_END), text)]
    if not begins and not ends:
        return None
    if len(begins) != 1 or len(ends) != 1 or begins[0] >= ends[0]:
        raise ValueError(
            "FF7R Engine.ini contains malformed or duplicate Lexeditor eye-adaptation markers"
        )
    start, end = begins[0], ends[0]
    if end < len(text) and text[end:end + 2] == "\r\n":
        end += 2
    elif end < len(text) and text[end] in "\r\n":
        end += 1
    return start, end


def remove_managed_block(text: str) -> str:
    span = _managed_span(text)
    if span is None:
        return text
    start, end = span
    # If Lexeditor inserted a separating blank line, remove it too while never
    # touching non-whitespace user content.
    prefix_start = start
    if start >= 2 and text[start - 2:start] == "\n\n":
        prefix_start = start - 1
    elif start >= 4 and text[start - 4:start] == "\r\n\r\n":
        prefix_start = start - 2
    return text[:prefix_start] + text[end:]


def apply_managed_block(text: str) -> str:
    base = remove_managed_block(text)
    if base and not base.endswith(("\n", "\r")):
        base += "\n"
    if base and not base.endswith("\n\n"):
        base += "\n"
    return base + MANAGED_BLOCK


def managed_override_state(target: Path) -> dict:
    try:
        text, _bom = _read_ini(target)
    except (OSError, ValueError) as error:
        return {
            "present": False,
            "effectiveAtEnd": False,
            "error": str(error),
        }
    try:
        span = _managed_span(text)
    except ValueError as error:
        return {
            "present": False,
            "effectiveAtEnd": False,
            "error": str(error),
        }
    if span is None:
        return {"present": False, "effectiveAtEnd": False, "error": ""}
    start, end = span
    block = text[start:end]
    present = EYE_ADAPTATION_CVAR.casefold() in block.casefold()
    effective = present and not text[end:].strip()
    return {"present": present, "effectiveAtEnd": effective, "error": ""}


def graphics_status(game_root: Path, project_root: Path) -> dict:
    config = load_graphics_config(project_root)
    ini = engine_ini_path()
    unlocker = detect_ini_unlocker(game_root)
    managed = managed_override_state(ini)
    requested = config["disableEyeAdaptation"]
    deploy_ready = (not requested) or unlocker["verified"]
    notes: list[str] = []
    if requested and not unlocker["verified"]:
        if unlocker["candidatePresent"]:
            notes.append(
                "An FF7R proxy DLL is present, but Lexeditor could not verify that it unlocks Engine.ini loading."
            )
        else:
            notes.append(
                "No recognized FFVIIHook/INI-unlocker candidate was found next to ff7remake_.exe."
            )
    if managed["error"]:
        notes.append(managed["error"])
    if managed["present"] and not managed["effectiveAtEnd"]:
        notes.append(
            "The Lexeditor eye-adaptation block is not the final Engine.ini content; redeploy to restore override precedence."
        )
    notes.append(
        "Eye adaptation uses UE's r.EyeAdaptationQuality=0 CVar only; Lexeditor does not alter authored brightness, fades, or unrelated post-processing settings."
    )
    notes.append(
        "Managed Engine.ini presence proves the configuration was written, not that an unverified game process honored it; installed-game visual verification is still required."
    )
    return {
        "schemaVersion": GRAPHICS_SCHEMA_VERSION,
        "config": config,
        "configPath": str(config_path(project_root)),
        "engineIniPath": str(ini),
        "engineIniExists": ini.is_file(),
        "iniUnlockerCandidatePresent": unlocker["candidatePresent"],
        "iniUnlockerVerified": unlocker["verified"],
        "iniUnlockerCandidates": unlocker["candidates"],
        "disableEyeAdaptationRequested": requested,
        "managedOverridePresent": managed["present"],
        "managedOverrideEffectiveAtEnd": managed["effectiveAtEnd"],
        "deployReady": deploy_ready,
        "notes": " ".join(notes),
    }


def deploy_graphics_tweaks(game_root: Path, project_root: Path) -> dict:
    config = load_graphics_config(project_root)
    target = engine_ini_path()
    status = graphics_status(game_root, project_root)
    enabled = config["disableEyeAdaptation"]
    if enabled and not status["iniUnlockerVerified"]:
        raise RuntimeError(
            "Eye Adaptation cannot be deployed: FFVIIHook/Engine.ini loading is not verified for this install"
        )

    text, bom = _read_ini(target)
    updated = apply_managed_block(text) if enabled else remove_managed_block(text)
    changed = updated != text
    if changed:
        if not updated:
            try:
                target.unlink()
            except FileNotFoundError:
                pass
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_suffix(target.suffix + ".lexeditor.tmp")
            temporary.write_bytes(_encode_ini(updated, bom))
            os.replace(temporary, target)

    after = graphics_status(game_root, project_root)
    if enabled and not (
        after["managedOverridePresent"] and after["managedOverrideEffectiveAtEnd"]
    ):
        raise RuntimeError("Eye Adaptation Engine.ini override failed write/readback validation")
    if not enabled and after["managedOverridePresent"]:
        raise RuntimeError("Eye Adaptation Engine.ini override failed to remove cleanly")
    return {
        "path": str(target),
        "changed": changed,
        "disableEyeAdaptation": enabled,
        "managedOverridePresent": after["managedOverridePresent"],
        "iniUnlockerVerified": after["iniUnlockerVerified"],
        "restartRequired": True,
    }


def canonical_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
