"""Modern Controls availability; the FFNx derivative owns the runtime hooks."""

from __future__ import annotations


DEFAULT_MODERN_CONTROLS = False
MODERN_CONTROLS_AVAILABLE = True
MODERN_CONTROLS_BLOCKER = ""

# FF8_EN.exe SHA-256 064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570.
# Qhimm identifies this as one of three writers to the camera tangent. Live
# testing disproved it as an always-valid right-stick injection point: this
# writer runs only in one conditional camera branch, and the resulting control
# changed with the active world-map state. Keep it only as rejected evidence.
CAMERA_YAW_HOOK = 0x00558676
CAMERA_YAW_HOOK_ORIGINAL = bytes.fromhex("66 01 05 02 ED 03 02")

# Live tests disproved both earlier input-structure hooks. They are evidence,
# not fallback paths, and generated Hext must never assign either address.
REJECTED_NORMAL_INPUT_FIELD = 0x00557634
REJECTED_NORMAL_INPUT_ORIGINAL = bytes.fromhex("8A 45 FA 84 C0")
REJECTED_SPECIAL_MODE_READ = 0x00557477
REJECTED_SPECIAL_MODE_ORIGINAL = bytes.fromhex("8B 0D A4 09 04 02")


def build_hext(enabled: bool) -> str:
    if not isinstance(enabled, bool):
        raise ValueError("Modern Controls must be true or false")
    if not enabled:
        return ""
    return "# Modern Controls uses the FFNx world-camera wrapper; no Hext input-field writes.\n"
