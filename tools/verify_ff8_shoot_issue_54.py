"""Static and mutation checks for the complete issue #54 Shoot component."""

from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import pefile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from games.ff8 import shoot_issue_54 as shoot
from games.ff8 import battle_shortcuts
from games.ff8 import fixed_command_menu as menu

EXE = Path(r"D:\SteamLibrary\steamapps\common\FINAL FANTASY VIII\FF8_EN.exe")
SHA = "064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570"


def validate_finish_stack(payload: bytes) -> None:
    expected = shoot._near(shoot.FINISH_CAVE, shoot.UNREGISTER_UI, b"\xE8")
    assert payload[:5] == expected
    assert payload[:3] != bytes.fromhex("83 C4 04")


def main() -> int:
    assert hashlib.sha256(EXE.read_bytes()).hexdigest() == SHA
    pe = pefile.PE(str(EXE), fast_load=True)
    base = pe.OPTIONAL_HEADER.ImageBase
    read = lambda address, size: pe.get_data(address - base, size)
    for address, expected in (
        (shoot.DESCRIPTOR_HOOK, shoot.DESCRIPTOR_ORIGINAL),
        (shoot.QUEUE_CALL, shoot.QUEUE_ORIGINAL),
        (shoot.POST_FIRE_HOOK, shoot.POST_FIRE_ORIGINAL),
        (shoot.SHOT_UI_UNREGISTER_CALL, shoot.SHOT_UI_UNREGISTER_ORIGINAL),
        (shoot.READY_HOOK, shoot.READY_ORIGINAL),
        (menu.COMMAND_LABEL_HOOK, menu.COMMAND_LABEL_ORIGINAL),
    ):
        assert read(address, len(expected)) == expected
    assert read(0x004BC467, 19) == bytes.fromhex(
        "A1 18 67 D7 01 33 FF 85 C0 0F BE D9 7E 32 BE 21 67 D7 01"
    )
    # The builder has just completed four descriptors at 0x495805. ESI is the
    # actor base, and the selected-descriptor resolver uses ESI+0x1E+slot*4.
    assert read(0x004957F5, 22) == bytes.fromhex(
        "47 83 C0 04 8D 0C 2F 83 F9 04 0F 8C 34 FF FF FF 8B 86 90 01 00 00"
    )
    assert 0x1E + shoot.CHARACTER_SLOT * 4 == 0x26
    assert read(0x004ADB96, 35) == bytes.fromhex(
        "6A 00 E8 03 C9 00 00 6A 00 E8 0C C9 00 00 6A 00 6A 00 6A 00 6A 06 "
        "E8 1F BF 00 00 83 C4 18 5E 5B 83 C4 08"
    )
    descriptor = shoot._descriptor_payload()
    queue = shoot._queue_payload()
    post = shoot._post_fire_payload()
    finish = shoot._finish_payload()
    ready = shoot._ready_payload()
    labels = menu._command_label_payload()
    assert bytes.fromhex("C7 46 26 0E 84 40 00") in descriptor
    assert bytes.fromhex("80 4E 29 02") in descriptor
    assert bytes.fromhex("83 7C 24 0C 0E") in queue
    assert bytes.fromhex("83 7C 24 08 0E") not in queue
    assert bytes.fromhex("8B 4C 24 08") in queue
    assert bytes.fromhex("8B 4C 24 04") not in queue
    assert shoot.ACTIVE_SLOT.to_bytes(4, "little") in queue
    assert shoot.QUEUE_FUNCTION.to_bytes(4, "little") not in queue  # relative tail jump
    assert shoot.IRVINE_WEAPON_ID.to_bytes(4, "little") in post
    assert (shoot.WEAPON_BASE + shoot.SHOTS_OFFSET).to_bytes(4, "little") in post
    assert b"\x80\x3D" + shoot.ACTIVE_STATE.to_bytes(4, "little") + b"\x00" in post
    assert b"\x80\x3D" + shoot.ACTIVE_STATE.to_bytes(4, "little") + b"\x01" not in post
    assert bytes.fromhex("8D 44 08 FF 52 33 D2 F7 F1 5A") in post
    # The unregister CALL is replaced by a JMP. The cave therefore enters with
    # the original six cdecl arguments still on the stack and no detour return
    # address. Removing four bytes here corrupts the slot argument and caller
    # frame; that was the player-reported Shoot crash.
    validate_finish_stack(finish)
    crashing_finish = bytes.fromhex("83 C4 04") + finish
    try:
        validate_finish_stack(crashing_finish)
    except AssertionError:
        pass
    else:
        raise AssertionError("the crashing pre-unregister stack adjustment was accepted")
    assert shoot.RETURN_TO_COMMANDS != shoot.UNREGISTER_UI
    assert shoot.SHOOT_LOCK.to_bytes(4, "little") in finish
    assert shoot.SHOOT_LOCK.to_bytes(4, "little") in ready
    assert bytes.fromhex("83 F8 0E") in labels
    assert bytes.fromhex("3D FE 00 00 00") in labels
    assert bytes.fromhex("83 F8 FE") not in labels
    assert menu.SHOOT_TEXT in labels
    assert menu.SWITCH_TEXT in labels
    assert menu.SUMMON_TEXT in labels
    caves = [(shoot.DESCRIPTOR_CAVE, descriptor), (shoot.QUEUE_CAVE, queue),
             (shoot.POST_FIRE_CAVE, post),
             (shoot.FINISH_CAVE, finish), (shoot.READY_CAVE, ready)]
    for (address, payload), (next_address, _) in zip(caves, caves[1:]):
        assert address + len(payload) <= next_address
    assert caves[-1][0] + len(caves[-1][1]) <= shoot.ACTIVE_STATE
    assert battle_shortcuts.CODE_CAVE + battle_shortcuts.CODE_CAVE_LENGTH <= shoot.DESCRIPTOR_CAVE
    fragment = shoot.build_component()
    for hook in (shoot.DESCRIPTOR_HOOK, shoot.QUEUE_CALL, shoot.POST_FIRE_HOOK,
                 shoot.SHOT_UI_UNREGISTER_CALL, shoot.READY_HOOK,
                 menu.COMMAND_LABEL_HOOK):
        assert f"{hook:X} = " in fragment
    print("FF8 issue #54 fixed Shoot queue, ATB, return and lock component passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
