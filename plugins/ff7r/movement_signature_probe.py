"""Read-only classification of the public FF7R raw-joystick movement signature.

The exact byte pattern comes from TheUnlocked/ff7r-kbm-hook (MIT). In that
project it is explicitly described as the site immediately after raw joystick
X/Y values are fetched, where the hook clamps stick magnitude to force walking.
That makes it useful installed-build provenance for input processing, but it is
not evidence for an authoritative sprint-speed/velocity coefficient.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .native_probe import PEImage


JOYSTICK_MOVEMENT_SIGNATURE = bytes.fromhex(
    "F3 44 0F 10 55 40 F3 0F 10 8B 18 07 00 00"
)
JOYSTICK_MOVEMENT_PROVENANCE = (
    "TheUnlocked/ff7r-kbm-hook Plugin/src/Hooks/MovementHook.cpp (MIT): "
    "pattern immediately after raw joystick values are fetched"
)


def probe_public_joystick_movement_signature(exe_path: Path) -> dict[str, Any]:
    """Find the public input signature in one installed executable, read-only."""
    path = Path(exe_path).resolve()
    try:
        data = path.read_bytes()
        image = PEImage.from_bytes(data)
    except Exception as error:
        return {
            "path": str(path),
            "matchCount": 0,
            "matches": [],
            "scanError": str(error),
            "provenance": JOYSTICK_MOVEMENT_PROVENANCE,
            "classification": "raw-joystick-input-post-fetch",
            "sprintSpeedAuthority": False,
        }

    text = image.section(".text")
    if text is None or text.raw_size < len(JOYSTICK_MOVEMENT_SIGNATURE):
        return {
            "path": str(path),
            "matchCount": 0,
            "matches": [],
            "scanError": "PE .text section is missing or too small",
            "provenance": JOYSTICK_MOVEMENT_PROVENANCE,
            "classification": "raw-joystick-input-post-fetch",
            "sprintSpeedAuthority": False,
        }

    raw = data[text.raw_offset:text.raw_offset + text.raw_size]
    matches = []
    cursor = 0
    while len(matches) < 16:
        found = raw.find(JOYSTICK_MOVEMENT_SIGNATURE, cursor)
        if found < 0:
            break
        rva = text.virtual_address + found
        runtime_function = image.runtime_function_for_rva(rva)
        matches.append({
            "fileOffset": text.raw_offset + found,
            "rva": rva,
            "va": image.image_base + rva,
            "pdataFunctionRva": (
                runtime_function.begin_rva if runtime_function is not None else None
            ),
            "pdataFunctionEndRva": (
                runtime_function.end_rva if runtime_function is not None else None
            ),
        })
        cursor = found + 1

    return {
        "path": str(path),
        "matchCount": len(matches),
        "matches": matches,
        "scanError": "",
        "provenance": JOYSTICK_MOVEMENT_PROVENANCE,
        "classification": "raw-joystick-input-post-fetch",
        "sprintSpeedAuthority": False,
        "notes": [
            "The upstream hook changes raw X/Y stick magnitude to create walking input.",
            "A unique installed match validates the public input-processing site only; it does not identify movement velocity, root-motion displacement, dash state, or sprint authority.",
            "Better Sprint must not scale this input site and describe the result as a sprint-speed multiplier.",
        ],
    }
