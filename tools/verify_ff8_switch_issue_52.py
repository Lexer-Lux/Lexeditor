"""Static and mutation checks for the guarded issue #52 Squall Switch slice."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import sys

from capstone import Cs, CS_ARCH_X86, CS_MODE_32
import pefile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.ff8 import fixed_command_menu as menu
from games.ff8 import switch_issue_52 as switch


EXE = Path(r"D:\SteamLibrary\steamapps\common\FINAL FANTASY VIII\FF8_EN.exe")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def image_bytes(pe: pefile.PE, address: int, length: int) -> bytes:
    rva = address - pe.OPTIONAL_HEADER.ImageBase
    return pe.get_memory_mapped_image()[rva:rva + length]


def call_targets(payload: bytes, address: int) -> set[int]:
    decoder = Cs(CS_ARCH_X86, CS_MODE_32)
    targets: set[int] = set()
    for instruction in decoder.disasm(payload, address):
        if instruction.mnemonic == "call" and instruction.op_str.startswith("0x"):
            targets.add(int(instruction.op_str, 16))
    return targets


def validate_refresh(payload: bytes) -> None:
    require(bytes.fromhex("B9 08 00 00 00 66 21 17 81 C7 98 00 00 00 49") in payload,
            "Switch does not clear the selected GF from all eight character masks")
    require(bytes.fromhex("66 89 5F 58") in payload,
            "Switch does not write the one-GF mask to the selected character")
    require(switch.SWITCH_SAVE_PTR.to_bytes(4, "little") in payload,
            "Switch does not preserve the selected character save pointer")
    require(payload.count(switch.SWITCH_CHAR_ID.to_bytes(4, "little")) >= 3,
            "Switch does not preserve and reload the character ID for both parsers")
    targets = call_targets(payload, switch.REFRESH_CAVE)
    require(switch.PARSE_CHARACTER in targets, "character rebuild call is missing")
    require(switch.PARSE_MAGIC in targets, "magic metadata rebuild call is missing")
    require(switch.CLONE_CAVE in targets, "selective live battle copy is missing")
    require(0x0048B310 not in targets, "unsafe full battle refresh returned")


def validate_clone(payload: bytes) -> None:
    require(bytes.fromhex("89 8A 28 7B D2 01") not in payload,
            "selective copy overwrites live current HP")
    require(bytes.fromhex("89 82 2C 7B D2 01") in payload,
            "selective copy does not update maximum HP")
    targets = call_targets(payload, switch.CLONE_CAVE)
    require(switch.UPDATE_LOW_HP in targets, "low-HP status refresh is missing")
    require(0x0048B310 not in targets, "unsafe full battle refresh returned")
    require(0x0047E330 not in targets, "volatile battle-effect refresh returned")


require(EXE.is_file(), "installed FF8_EN.exe is missing")
require(sha256(EXE.read_bytes()).hexdigest() == menu.SUPPORTED_EXE_SHA256,
        "installed FF8_EN.exe is not the researched Steam English build")
pe = pefile.PE(str(EXE), fast_load=True)

for address, original in (
    (switch.DESCRIPTOR_HOOK, switch.DESCRIPTOR_ORIGINAL),
    (switch.LABEL_HOOK, switch.LABEL_ORIGINAL),
    (switch.DESCRIPTION_HOOK, switch.DESCRIPTION_ORIGINAL),
    (switch.COMMAND_CONFIRM_HOOK, switch.COMMAND_CONFIRM_ORIGINAL),
):
    require(image_bytes(pe, address, len(original)) == original,
            f"Switch hook bytes changed at {address:#x}")
require(image_bytes(pe, switch.REGISTER_SLOT, 20) == bytes.fromhex(
    "8B 44 24 04 8B 54 24 0C 80 C9 FF 8D 04 80 8D 04 85 28 66 D7"),
    "battle overlay registration entry changed")
require(image_bytes(pe, switch.PARSE_CHARACTER, 10) == bytes.fromhex(
    "53 8B 5C 24 08 56 8B 74 24 10"),
    "character parser entry changed")
require(image_bytes(pe, switch.PARSE_MAGIC, 10) == bytes.fromhex(
    "53 8B 54 24 0C 55 56 57 8B 7C"),
    "magic parser entry changed")
require(image_bytes(pe, 0x0048B344, len(switch._DERIVED_TEMPLATE)) ==
        switch._DERIVED_TEMPLATE,
        "derived-state copy source differs from the verified executable")

descriptor = switch._descriptor_payload()
label = switch._resolver_payload(
    switch.LABEL_CAVE, switch.LABEL_ORIGINAL, switch.SWITCH_TEXT)
description = switch._resolver_payload(
    switch.DESCRIPTION_CAVE, switch.DESCRIPTION_ORIGINAL,
    switch.SWITCH_DESCRIPTION)
command_confirm = switch._command_confirm_payload()
update = switch._update_payload()
close = switch._close_payload()
draw = switch._draw_payload()
refresh = switch._refresh_payload()
clone = switch._clone_payload()

require(bytes.fromhex("80 BE C3 01 00 00 00") in descriptor,
        "Switch descriptor is not restricted to Squall")
require(bytes.fromhex("C7 46 26 FE A0 00 00") in descriptor,
        "Squall slot 2 does not receive the guarded implicit-self Switch marker")
require(bytes.fromhex("C7 46 26 FE A0 18 00") not in descriptor,
        "Switch still uses the crashing vanilla single-target descriptor")
for payload, text in ((label, switch.SWITCH_TEXT),
                      (description, switch.SWITCH_DESCRIPTION)):
    require(bytes.fromhex("3D FE 00 00 00") in payload,
            "synthetic Switch marker can reach a vanilla text table")
    require(text in payload, "stable custom Switch text is absent")

require(bytes.fromhex("80 3F FE") in command_confirm,
        "command-confirmation diversion does not inspect the selected Switch descriptor")
for value in (switch.ACTIVE_SLOT, switch.SELECTED_ACTOR):
    require(value.to_bytes(4, "little") in command_confirm,
            f"command-confirmation guard omits {value:#x}")
require(bytes.fromhex("83 F8 0A") in command_confirm and
        bytes.fromhex("80 BA") in command_confirm,
        "command-confirmation diversion does not prove the selected Squall actor")
state_targets = call_targets(command_confirm, switch.COMMAND_CONFIRM_CAVE)
for target in (switch.REGISTER_SLOT, switch.SET_SLOT_STATE, switch.HIDE_SLOT):
    require(target in state_targets, f"overlay setup call is missing: {target:#x}")
require(switch.CLOSE_CAVE.to_bytes(4, "little") in command_confirm,
        "overlay has no close callback")
require(switch.COMMAND_CONFIRM_ORIGINAL in command_confirm,
        "non-Switch command confirmation is not replayed")
require(switch.COMMAND_CONFIRM_HOOK < 0x004BC770,
        "Switch diversion no longer runs before FF8's target builder")
switch_source = Path(switch.__file__).read_text(encoding="utf-8")
require("STATE12_HOOK" not in switch_source and "_state12_payload" not in switch_source,
        "late post-target Switch interception returned")

for mask in (0x10, 0x08, 0x1000, 0x4000):
    require(mask.to_bytes(4, "little") in update or
            (mask < 0x100 and bytes((mask,)) in update),
            f"Switch input mask is missing: {mask:#x}")
require(switch.REFRESH_CAVE in call_targets(update, switch.UPDATE_CAVE),
        "GF confirmation does not run the selective refresh")
require(switch.CLOSE_CAVE in call_targets(update, switch.UPDATE_CAVE),
        "confirm/cancel does not return to the command menu")
require(switch.GF_DATA_BASE.to_bytes(4, "little") in draw,
        "overlay does not render the saved GF names")
require(switch.DRAW_TEXT in call_targets(draw, switch.DRAW_CAVE),
        "overlay does not use the verified battle text renderer")

require(bytes.fromhex("6A 00 6A 00 6A 00 6A 05") in close,
        "close callback does not unregister overlay slot 5")
require(b"\xC6\x05" + switch.CONTROLLER_STATE.to_bytes(4, "little") + b"\x07" in close,
        "close callback does not restore top-level command selection")
require(b"\x66\xC7\x05" + switch.CONTROLLER_READY.to_bytes(4, "little") +
        bytes.fromhex("00 10") in close,
        "close callback does not restore the command-ready word")
validate_refresh(refresh)
validate_clone(clone)

# Mutation checks ban the two defects found in the interrupted implementation.
bad_refresh = refresh.replace(bytes.fromhex("66 89 5F 58"),
                              bytes.fromhex("66 89 9F C0 FF FF FF"), 1)
try:
    validate_refresh(bad_refresh)
except AssertionError:
    pass
else:
    raise AssertionError("wrong-character GF-mask mutation was accepted")
bad_clone = bytearray(clone)
hp_store = 0x0048B35E - 0x0048B344
bad_clone[hp_store:hp_store + 6] = bytes.fromhex("89 8A 28 7B D2 01")
try:
    validate_clone(bytes(bad_clone))
except AssertionError:
    pass
else:
    raise AssertionError("live-current-HP overwrite mutation was accepted")

caves = (
    (switch.DESCRIPTOR_CAVE, descriptor), (switch.LABEL_CAVE, label),
    (switch.DESCRIPTION_CAVE, description), (switch.COMMAND_CONFIRM_CAVE, command_confirm),
    (switch.UPDATE_CAVE, update), (switch.CLOSE_CAVE, close),
    (switch.DRAW_CAVE, draw), (switch.REFRESH_CAVE, refresh),
    (switch.CLONE_CAVE, clone),
)
for (address, payload), (next_address, _) in zip(caves, caves[1:]):
    require(address + len(payload) <= next_address,
            f"Switch cave overlaps after {address:#x}")
require(caves[-1][0] + len(caves[-1][1]) <= switch.STATE_BASE,
        "Switch clone overlaps its persistent state")

component = switch.build_component()
for hook in (switch.DESCRIPTOR_HOOK, switch.LABEL_HOOK,
             switch.DESCRIPTION_HOOK, switch.COMMAND_CONFIRM_HOOK):
    require(f"{hook:X} = " in component,
            f"Switch component omits hook {hook:#x}")
combined = menu.build_supported_components()
for hook in (switch.DESCRIPTOR_HOOK, switch.DESCRIPTION_HOOK,
             switch.COMMAND_CONFIRM_HOOK):
    require(f"{hook:X} = " in combined,
            f"fixed-command composition omits Squall Switch hook {hook:#x}")
for cave in (switch.DESCRIPTOR_CAVE, switch.LABEL_CAVE,
             switch.DESCRIPTION_CAVE, switch.COMMAND_CONFIRM_CAVE,
             switch.UPDATE_CAVE, switch.CLOSE_CAVE, switch.DRAW_CAVE,
             switch.REFRESH_CAVE, switch.CLONE_CAVE):
    require(f"{cave:X} = " in combined,
            f"fixed-command composition omits Squall Switch cave {cave:#x}")
require("Switch needs a new battle dispatcher" not in " ".join(menu.BLOCKERS),
        "resolved Switch blocker remains in the fixed-command contract")
require(not menu.BLOCKERS,
        "resolved fixed-command composition still reports a blocker")
require(not any("GF Magic" in blocker for blocker in menu.BLOCKERS),
        "unrelated GF Magic-page work still blocks the fixed command order")
require("# Irvine fixed Shoot:" in combined,
        "supported fixed-command composition omits Irvine Shoot")
require(f"{menu.COMMAND_LABEL_HOOK:X} = " in combined,
        "supported composition omits the shared Shoot/Switch/Summon labels")
require(combined.count(f"{menu.COMMAND_LABEL_HOOK:X} = ") == 1,
        "supported composition has more than one owner for command labels")
require(combined.count(f"{menu.POST_BUILDER_HOOK:X} = ") == 1,
        "supported composition has more than one owner for post-build descriptors")

print("FF8 issue #52 guarded Squall Switch overlay and selective refresh passed")
