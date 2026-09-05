"""Evidence gate for the unresolved FF8 battle mechanics in GitHub #54."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

import pefile

import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from games.ff8 import battle_issue_54 as battle
from games.ff8 import gameplay_settings
EXE = Path(r"D:\SteamLibrary\steamapps\common\FINAL FANTASY VIII\FF8_EN.exe")
FFNX = ROOT / "_scratch" / "ffnx-upstream"
EXPECTED_EXE = "064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570"
EXPECTED_FFNX = "1e291885da4ddb482188b81a5198d56a1915fde6"


def main() -> int:
    assert hashlib.sha256(EXE.read_bytes()).hexdigest() == EXPECTED_EXE
    pe = pefile.PE(str(EXE), fast_load=True)
    base = pe.OPTIONAL_HEADER.ImageBase

    def read(virtual_address: int, size: int) -> bytes:
        return pe.get_data(virtual_address - base, size)

    # The Draw dispatcher calls the exact vanilla amount function with actor,
    # monster, and magic arguments. The vanilla function clamps the result to 9.
    assert read(0x0048D54D, 17) == bytes.fromhex(
        "56 52 8B 54 24 30 52 E8 C7 27 00 00 83 C4 0C 88 44"
    )
    assert read(0x0048FD20, 9) == bytes.fromhex("53 55 56 57 E8 F7 F2 FF FF")
    assert read(0x0048FDFE, 11) == bytes.fromhex("83 F8 09 7E 05 B8 09 00 00 00 C3")

    # The complete Draw slice owns six guarded boundaries. The battle enter
    # and mode-transition paths reset its local mask. Target selection,
    # rendering and confirmation use the same current enemy mask.
    for address, expected in (
        (battle.BATTLE_ENTER_HOOK, battle.BATTLE_ENTER_ORIGINAL),
        (battle.BATTLE_EXIT_HOOK, battle.BATTLE_EXIT_ORIGINAL),
        (battle.DRAW_RESULT_HOOK, battle.DRAW_RESULT_ORIGINAL),
        (battle.DRAW_SELECT_HOOK, battle.DRAW_SELECT_ORIGINAL),
        (battle.DRAW_TARGET_MASK_HOOK, battle.DRAW_TARGET_MASK_ORIGINAL),
        (battle.DRAW_RENDER_HOOK, battle.DRAW_RENDER_ORIGINAL),
    ):
        assert read(address, len(expected)) == expected
    assert read(0x004BB030, 81).count(bytes.fromhex("83 F9 04")) == 1
    assert read(0x004BC82B, 29) == bytes.fromhex(
        "BD 08 00 00 00 B9 03 00 00 00 BA 01 00 00 00 D3 E2 85 D7 "
        "75 08 41 83 F9 07 7C EF EB 0E"
    )

    # FFNx resolves that same function and replaces that same call site with its
    # Steam-achievement wrapper. A second Hext replacement would bypass it.
    data_cpp = (FFNX / "src" / "ff8_data.cpp").read_text(encoding="utf-8")
    opengl_cpp = (FFNX / "src" / "ff8_opengl.cpp").read_text(encoding="utf-8")
    assert "battle_get_draw_magic_amount_48FD20" in data_cpp
    assert "battle_sub_48D200 + (FF8_US_VERSION ? 0x354" in opengl_cpp
    assert "replace_call(ff8_externals.battle_sub_48D200" in opengl_cpp
    assert "increaseMagicStockAndTryUnlockAchievement" in opengl_cpp

    # These symbols are the only issue-relevant battle state that official FFNx
    # currently exposes. It does not expose Shoot/ATB, fixed-command, per-enemy
    # Draw, or conditional command-label APIs.
    header = (FFNX / "src" / "ff8.h").read_text(encoding="utf-8")
    for symbol in (
        "battle_get_draw_magic_amount_48FD20", "battle_current_active_character_id",
        "battle_new_active_character_id", "battle_encounter_id", "battle_menu_sub_4A3D20",
    ):
        assert symbol in header

    save_header = (FFNX / "src" / "ff8" / "save_data.h").read_text(encoding="utf-8")
    assert "uint32_t battle_irvine;" in save_header
    assert "uint8_t magic_drawn_once[8];" in save_header
    assert '"Squall"' in (FFNX / "src" / "ff8" / "engine.h").read_text(encoding="utf-8")

    schema = json.loads((ROOT / "games" / "ff8" / "schema" / "kernel_section_fields.json").read_text(encoding="utf-8"))
    shots = next(field for field in schema["5"]["fields"] if field["offset"] == 3)
    assert shots["name"] == "shots_per_atb"
    assert shots["minimum"] == 1 and shots["maximum"] == 10
    assert shots["default_if_zero"] == 1 and not shots.get("readonly", False)
    ammo = next(field for field in schema["22"]["fields"] if field["name"] == "used_item_index")
    assert ammo["offset"] == 18 and ammo["lookup"] == "item"

    revision = subprocess.check_output(
        ["git", "-C", str(FFNX), "rev-parse", "HEAD"], text=True,
    ).strip()
    assert revision == EXPECTED_FFNX
    assert battle.DEFAULT_SHOTS_PER_ATB == 1
    assert battle.MIN_SHOTS_PER_ATB == 1
    assert battle.MAX_SHOTS_PER_ATB == 10
    for value in (1, 5, 10):
        assert battle.shots_per_atb(value) == value
    for value in (0, 11, 1.5, True, None):
        try:
            battle.shots_per_atb(value)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid shots-per-ATB value was accepted: {value!r}")

    assert battle.DRAW_STRENGTH == "vanilla"
    assert battle.draw_target_eligible(drawn_enemy_slots={1}, enemy_slot=0)
    assert not battle.draw_target_eligible(drawn_enemy_slots={1}, enemy_slot=1)
    assert battle.draw_command_available(
        drawn_enemy_slots={0}, targetable_enemy_slots={0, 1},
    )
    assert not battle.draw_command_available(
        drawn_enemy_slots={0, 1}, targetable_enemy_slots={0, 1},
    )
    for slot in (-1, 4):
        try:
            battle.draw_target_eligible(drawn_enemy_slots=set(), enemy_slot=slot)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid battle enemy slot was accepted: {slot}")

    assert battle.build_draw_patch(False) == ""
    try:
        battle.build_draw_patch(1)
    except ValueError:
        pass
    else:
        raise AssertionError("a non-boolean Draw setting was accepted")
    draw_patch = battle.build_draw_patch(True)
    assert f"{battle.DRAW_STATE:X}:8" in draw_patch
    assert f"{battle.DRAW_RESULT_HOOK:X} = " in draw_patch
    assert f"{battle.DRAW_TARGET_MASK_HOOK:X} = " in draw_patch
    assert f"{battle.DRAW_SELECT_HOOK:X} = " in draw_patch
    assert f"{battle.DRAW_RENDER_HOOK:X} = " in draw_patch
    assert "48D554 =" not in draw_patch, "FFNx's Draw wrapper call was replaced"
    # One enemy means one successful Draw for the whole party. The old patch
    # gated recording and eligibility to Quistis, which let the other actors
    # keep drawing from the same enemy.
    actor_character_address = (
        battle.BATTLE_ACTOR_BASE + battle.BATTLE_ACTOR_CHARACTER_ID
    ).to_bytes(4, "little")
    assert actor_character_address not in battle._draw_result_payload()
    assert actor_character_address not in battle._draw_target_mask_payload()
    assert actor_character_address not in battle._draw_select_payload()
    assert actor_character_address not in battle._draw_render_payload()
    assert bytes.fromhex("8B 4C 24 20 80 39 06") in battle._draw_target_mask_payload()
    assert bytes.fromhex("8B 4C 24 18 80 39 06") not in battle._draw_target_mask_payload()
    assert battle.TARGETABLE_ENEMY_MASK.to_bytes(4, "little") in battle._draw_select_payload()
    assert battle.TARGETABLE_ENEMY_MASK.to_bytes(4, "little") in battle._draw_render_payload()

    caves = [
        (battle.DRAW_ENTER_CAVE, battle._battle_enter_payload()),
        (battle.DRAW_EXIT_CAVE, battle._battle_exit_payload()),
        (battle.DRAW_RESULT_CAVE, battle._draw_result_payload()),
        (battle.DRAW_TARGET_MASK_CAVE, battle._draw_target_mask_payload()),
        (battle.DRAW_SELECT_CAVE, battle._draw_select_payload()),
        (battle.DRAW_STATE, bytes(4)),
        (battle.DRAW_RENDER_CAVE, battle._draw_render_payload()),
    ]
    for (address, payload), (next_address, _) in zip(caves, caves[1:]):
        assert address + len(payload) <= next_address
    assert caves[-1][0] + len(caves[-1][1]) <= 0x0279F600

    gameplay = (ROOT / "games" / "ff8" / "gameplay_settings.py").read_text(encoding="utf-8")
    editor = (ROOT / "games" / "ff8" / "editor.html").read_text(encoding="utf-8")
    assert "battle_issue_54.build_command_eligibility_patch(" in gameplay
    assert "draw_once=draw_once_per_enemy, better_card=better_card_enabled" in gameplay
    assert "battle_issue_54.build_draw_patch(draw_once_per_enemy)" not in gameplay
    assert '"drawOncePerEnemy"' in gameplay
    assert '"aria-label":"Draw Once per Enemy"' in editor
    assert "drawOncePerEnemy:state.data.settings.drawOncePerEnemy" in editor
    assert "After any party member successfully Draws from an enemy instance" in editor
    assert "Each party member can Draw once from each enemy instance" not in editor
    assert '"aria-label":"Command Menu Rework"' in editor
    assert "fixedCommandMenu:state.data.settings.fixedCommandMenu" in editor
    generated = gameplay_settings.build_hext(25, False, False, False, True)
    assert draw_patch.rstrip() in generated
    shoot_patch = gameplay_settings.build_hext(
        25, False, True, False, False, fixed_command_menu_enabled=True,
    )
    assert "Irvine fixed Shoot" in shoot_patch
    try:
        gameplay_settings.build_hext(
            25, False, False, False, False, fixed_command_menu_enabled="yes",
        )
    except ValueError as error:
        assert "must be true or false" in str(error)
    else:
        raise AssertionError("A non-boolean Fixed Command Menu setting was accepted")
    assert battle.build_patch(
        enabled=False, single_gf_enabled=False, fixed_command_menu_enabled=False,
    ) == ""
    for kwargs, fragment in (
        ({"enabled": True, "single_gf_enabled": False,
          "fixed_command_menu_enabled": True}, "Single GF"),
        ({"enabled": True, "single_gf_enabled": True,
          "fixed_command_menu_enabled": False}, "Fixed Command Menu"),
    ):
        try:
            battle.build_patch(**kwargs)
        except RuntimeError as error:
            assert fragment in str(error)
        else:
            raise AssertionError(f"missing dependency was accepted: {fragment}")
    try:
        battle.build_patch(
            enabled=True, single_gf_enabled=True, fixed_command_menu_enabled=True,
        )
    except RuntimeError as error:
        for blocker in battle.BLOCKERS:
            assert blocker in str(error)
    else:
        raise AssertionError("unverified battle hooks produced a runtime patch")

    print("FF8 issue #54 party-wide once-per-enemy Draw patch passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
