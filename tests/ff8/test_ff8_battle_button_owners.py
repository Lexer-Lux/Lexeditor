"""Every battle tweak owns its own button, so none can set off another.

Lexer: "scan with R3, items with R1, party switch with L1, timed hits/blocks
with square. it shouldn't even be possible" for one to trigger another.
Each owner's bit is read from the code that tests it; the driver sources are
checked for the same bits, since they are built separately.
"""
from pathlib import Path

from plugins.ff8 import battle_shortcuts, party_switch_issue_62, timed_hits

ROOT = Path(__file__).resolve().parents[2]

OWNERS = {
    "Universal Item (R1)": battle_shortcuts.UNIVERSAL_ITEM_INPUT_MASK,
    "Party Switch (L1)": party_switch_issue_62.PARTY_SWITCH_INPUT_MASK,
    "Timed Hits and Blocks (Square)": timed_hits.SQUARE,
    "Enhanced Scan (R3)": battle_shortcuts.SCAN_INPUT_MASK,
}


def test_no_two_battle_tweaks_share_a_button():
    seen = {}
    for owner, bit in OWNERS.items():
        assert bit and bit & (bit - 1) == 0, f"{owner} must be exactly one button"
        assert bit not in seen, f"{owner} and {seen.get(bit)} both use 0x{bit:X}"
        seen[bit] = owner


def test_the_patches_test_the_bits_they_claim():
    router = battle_shortcuts._command_payload(universal_item=True, scanned_target_scan=True)
    assert bytes((0xA8, battle_shortcuts.UNIVERSAL_ITEM_INPUT_MASK)) in router
    assert battle_shortcuts.SCAN_INPUT_TEST in router
    assert bytes((0xF6, 0x41, 0x12, timed_hits.SQUARE)) in timed_hits.CODE
    switch = (ROOT / "plugins/ff8/ffnx_party_switch/ffnx-src/lexeditor_ff8_party_switch.cpp").read_text(encoding="utf-8")
    assert f"(edge&{party_switch_issue_62.PARTY_SWITCH_INPUT_MASK})" in switch
    controls = (ROOT / "plugins/ff8/ffnx_modern_controls/lexeditor_ff8_modern_controls.cpp").read_text(encoding="utf-8")
    assert f"kR3Function = 0x{battle_shortcuts.SCAN_INPUT_MASK:x}" in controls


def test_the_right_trigger_is_r1_only_while_shot_is_open():
    """RT used to be R1 for the whole battle, so it opened Universal Item."""
    controls = (ROOT / "plugins/ff8/ffnx_modern_controls/lexeditor_ff8_modern_controls.cpp").read_text(encoding="utf-8")
    body = controls[controls.index("int translate_battle_keys"):controls.index("int __cdecl translate_held")]
    shot = body.index("if (shot_open) {")
    assert body.count("bits |= kR1Function") == 1
    assert shot < body.index("bits |= kR1Function") < body.index("}", shot + 20) + 200
