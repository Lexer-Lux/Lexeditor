"""Classify public FF7R map/input signatures without promoting them to #414 hooks.

Lexeditor's native scaffold carries two patterns sourced from the MIT-licensed
TheUnlocked/ff7r-kbm-hook project. Reading the upstream implementation provides
important negative semantics:

* the MapControl pattern identifies code used while the full-screen map is
  already open to update reticle position/zoom;
* the raw-input pattern identifies the RegisterRawInputDevices call intercepted
  once so the mod can attach Windows keyboard/mouse hooks.

Neither site is the game's map-button action or its press/release dispatch path.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .native_probe import PEImage


MAP_CONTROL_SIGNATURE = bytes.fromhex(
    "56 49 8D AB 78 FD FF FF 48 81 EC 70 03 00 00"
)
RAW_INPUT_REGISTRATION_SIGNATURE = bytes.fromhex(
    "89 5C 24 24 48 8D 4C 24 20 48 89 44 24 28"
)

MAP_CONTROL_PROVENANCE = (
    "TheUnlocked/ff7r-kbm-hook Plugin/src/Hooks/MapHook.cpp (MIT): "
    "MapControlAddress used by SetMapCursorPosition while the full-screen map is open"
)
RAW_INPUT_PROVENANCE = (
    "TheUnlocked/ff7r-kbm-hook Plugin/src/InputManager.cpp (MIT): "
    "RegisterRawInputDevicesInjectionSite used once to attach Windows input hooks"
)


def _scan_text(image: PEImage, signature: bytes, *, limit: int = 16) -> list[dict[str, Any]]:
    text = image.section(".text")
    if text is None or text.raw_size < len(signature):
        return []
    raw = image.data[text.raw_offset:text.raw_offset + text.raw_size]
    matches: list[dict[str, Any]] = []
    cursor = 0
    while len(matches) < limit:
        found = raw.find(signature, cursor)
        if found < 0:
            break
        rva = text.virtual_address + found
        function = image.runtime_function_for_rva(rva)
        matches.append({
            "fileOffset": text.raw_offset + found,
            "rva": rva,
            "va": image.image_base + rva,
            "pdataFunctionRva": function.begin_rva if function is not None else None,
            "pdataFunctionEndRva": function.end_rva if function is not None else None,
        })
        cursor = found + 1
    return matches


def probe_public_map_input_signatures(exe_path: Path) -> dict[str, Any]:
    """Report exact installed matches with source-backed semantic classifications."""
    path = Path(exe_path).resolve()
    try:
        image = PEImage.from_bytes(path.read_bytes())
    except Exception as error:
        return {
            "path": str(path),
            "scanError": str(error),
            "mapControl": {
                "matchCount": 0,
                "matches": [],
                "classification": "full-screen-map-controller",
                "mapButtonAuthority": False,
                "provenance": MAP_CONTROL_PROVENANCE,
            },
            "rawInputRegistration": {
                "matchCount": 0,
                "matches": [],
                "classification": "raw-input-device-registration",
                "mapButtonAuthority": False,
                "provenance": RAW_INPUT_PROVENANCE,
            },
        }

    map_matches = _scan_text(image, MAP_CONTROL_SIGNATURE)
    raw_input_matches = _scan_text(image, RAW_INPUT_REGISTRATION_SIGNATURE)
    return {
        "path": str(path),
        "scanError": "",
        "mapControl": {
            "matchCount": len(map_matches),
            "matches": map_matches,
            "classification": "full-screen-map-controller",
            "mapButtonAuthority": False,
            "provenance": MAP_CONTROL_PROVENANCE,
        },
        "rawInputRegistration": {
            "matchCount": len(raw_input_matches),
            "matches": raw_input_matches,
            "classification": "raw-input-device-registration",
            "mapButtonAuthority": False,
            "provenance": RAW_INPUT_PROVENANCE,
        },
        "notes": [
            "A MapControl match proves a public full-screen-map controller site, not the input action that opens the map.",
            "A raw-input-registration match proves where the public mod intercepts RegisterRawInputDevices to attach OS-level hooks, not FF7R's KeyboardMapMenu action.",
            "Issue #414 still requires the game's own map-button press/release path and an authoritative minimap visibility writer before the tap/hold runtime can be enabled.",
        ],
    }
