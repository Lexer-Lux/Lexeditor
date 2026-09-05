"""FFNx-managed, battle-only party switching; no fixed Hext caves."""

from __future__ import annotations


DEFAULT_PARTY_SWITCH = False
PARTY_SWITCH_AVAILABLE = True

SUPPORTED_EXE_SHA256 = (
    "064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570"
)
SUPPORTED_FFNX_REVISION = "1e291885da4ddb482188b81a5198d56a1915fde6"

# Evidence for encounter 0x01FF only. These are not a generic battle-command
# API and must not be scheduled by an enabled Tweak.
PARTY_REPLACEMENT_ENTRY = 0x00497110
PARTY_REPLACEMENT_CALLBACK = 0x004971F0
PARTY_REPLACEMENT_FINISH = 0x00497270

PARTY_SWITCH_BLOCKER = (
    "FF10-style Party Switch is disabled: FF8's proved reserve replacement "
    "callback belongs to encounter 0x01FF. A safe normal-battle selector, "
    "cancel return, and one-turn command path have not been proved."
)


def _boolean(value: object, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{label} must be true or false")
    return value


def eligible_characters(exists: list[bool], blocked: list[bool],
                        party: list[int]) -> list[int]:
    """Mirror the proved reserve eligibility filter without claiming dispatch."""
    if len(exists) != 8 or len(blocked) != 8:
        raise ValueError("FF8 requires eight character eligibility values")
    current = {int(value) for value in party if 0 <= int(value) < 8}
    return [
        character_id for character_id in range(8)
        if bool(exists[character_id]) and not bool(blocked[character_id])
        and character_id not in current
    ]


def build_hext(*, enabled: bool = DEFAULT_PARTY_SWITCH) -> str:
    """The FFNx extension owns the controller hook and allocated trampoline."""
    enabled = _boolean(enabled, "FF10-style Party Switch")
    if not enabled:
        return ""
    return "# FF10-style Party Switch is managed by the FFNx native extension.\n"
