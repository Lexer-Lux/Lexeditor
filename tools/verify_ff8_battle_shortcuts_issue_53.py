"""Verify FF8 native Universal Item and Enhanced Scan boundaries."""

from __future__ import annotations

import argparse
import hashlib
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.ff8 import battle_shortcuts  # noqa: E402


EXPECTED_EXE_SHA256 = (
    "064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570"
)


def rva_to_offset(image: bytes, rva: int) -> int:
    pe_offset = struct.unpack_from("<I", image, 0x3C)[0]
    if image[pe_offset : pe_offset + 4] != b"PE\0\0":
        raise AssertionError("FF8_EN.exe does not contain a valid PE header")
    section_count = struct.unpack_from("<H", image, pe_offset + 6)[0]
    optional_size = struct.unpack_from("<H", image, pe_offset + 20)[0]
    section_offset = pe_offset + 24 + optional_size
    for index in range(section_count):
        entry = section_offset + index * 40
        virtual_size, virtual_address, raw_size, raw_offset = struct.unpack_from(
            "<IIII", image, entry + 8
        )
        span = max(virtual_size, raw_size)
        if virtual_address <= rva < virtual_address + span:
            return raw_offset + rva - virtual_address
    raise AssertionError(f"RVA 0x{rva:X} is outside all PE sections")


def bytes_at_va(image: bytes, va: int, length: int, image_base: int = 0x400000) -> bytes:
    offset = rva_to_offset(image, va - image_base)
    return image[offset : offset + length]


def require_bytes(image: bytes, va: int, expected_hex: str, purpose: str) -> None:
    expected = bytes.fromhex(expected_hex)
    actual = bytes_at_va(image, va, len(expected))
    if actual != expected:
        raise AssertionError(
            f"{purpose} changed at 0x{va:X}: expected {expected.hex()}, "
            f"found {actual.hex()}"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--exe",
        type=Path,
        default=Path(r"D:\SteamLibrary\steamapps\common\FINAL FANTASY VIII\FF8_EN.exe"),
    )
    args = parser.parse_args()

    image = args.exe.read_bytes()
    digest = hashlib.sha256(image).hexdigest()
    if digest != EXPECTED_EXE_SHA256:
        raise AssertionError(
            "The installed FF8_EN.exe is not the researched Steam English build: "
            f"{digest}"
        )

    # The retained Universal Item hook is inside the battle command controller.
    require_bytes(
        image,
        battle_shortcuts.COMMAND_INPUT_HOOK,
        battle_shortcuts.COMMAND_INPUT_ORIGINAL.hex(),
        "battle command confirmation",
    )
    require_bytes(
        image,
        battle_shortcuts.COMMAND_INPUT_HOOK + len(battle_shortcuts.COMMAND_INPUT_ORIGINAL),
        battle_shortcuts.COMMAND_STATE_STORE.hex(),
        "battle command state transition",
    )

    assert battle_shortcuts.DEFAULT_ENHANCED_SCAN is False
    assert battle_shortcuts.DEFAULT_SCANNED_TARGET_SCAN is False
    assert battle_shortcuts.ENHANCED_SCAN_AVAILABLE is True
    assert battle_shortcuts.build_hext(universal_item=False) == ""

    item_patch = battle_shortcuts.build_hext(universal_item=True)
    assert f"{battle_shortcuts.COMMAND_INPUT_HOOK:X} = E9" in item_patch
    assert battle_shortcuts.ITEM_DESCRIPTOR_BYTES == bytes.fromhex("04 82 D4 00")
    payload = battle_shortcuts._command_payload(
        universal_item=True,
        scanned_target_scan=False,
    )
    assert len(payload) == battle_shortcuts.CODE_CAVE_LENGTH
    assert payload.startswith(b"\x90" * 8)

    def assert_router_state_lifecycle(router: bytes) -> None:
        store = battle_shortcuts.COMMAND_STATE_STORE
        assert router.count(store) == 1, "command state must be written exactly once"
        store_at = router.index(store)
        item_test_at = router.index(bytes.fromhex("A8 08"))
        assert store_at < item_test_at, "shortcut can execute before command state is set"

    assert_router_state_lifecycle(payload)
    state_mutant = payload.replace(battle_shortcuts.COMMAND_STATE_STORE,
                                   b"\x90" * len(battle_shortcuts.COMMAND_STATE_STORE), 1)
    try:
        assert_router_state_lifecycle(state_mutant)
    except AssertionError:
        pass
    else:
        raise AssertionError("missing command-state store passed the router contract")

    # The old shortcut intercepted a Look action, guessed that target selection
    # already existed, and queued a synthetic effect event. None of those bytes
    # or hooks may survive in a generated patch.
    forbidden_patch_fragments = (
        "A8 04",
        "Look Left",
        "50AD65 =",
        "279F300",
        "279F4A0",
        "1CFE964",
    )
    for fragment in forbidden_patch_fragments:
        assert fragment not in item_patch

    module_text = (ROOT / "games" / "ff8" / "battle_shortcuts.py").read_text(
        encoding="utf-8"
    )
    for forbidden_source in (
        "def _scan_payload",
        "def _scan_completion_payload",
        "SCAN_COMPLETION_HOOK",
        "SCANNED_ENEMY_BITS",
        "CURRENT_TARGET_MASK",
        "DINPUT_RIGHT_STICK_BUTTON",
        "R3_LATCH",
        "RIGHT_STICK_BUTTON_MASK",
    ):
        assert forbidden_source not in module_text

    # A direct-target descriptor is not a proved native Scan path. At
    # 0x004BC89C the direct branch copies the descriptor command and explicitly
    # writes action 0. The retired patch changed that record to action 50 after
    # confirmation and then intercepted the queue, stock, and teardown paths.
    # It crashed in live use. Enhanced Scan must instead enter the native Magic
    # controller and retain its target selector, action producer, and queue.
    require_bytes(image, 0x004BC89C,
                  "8A 12 88 11 C6 41 01 00 66 89 71 02",
                  "direct-target record builder")
    require_bytes(image, battle_shortcuts.INSTANT_COMMAND_BRANCH,
                  "F6 C2 20 0F 84 D4 00 00 00", "instant-command branch")
    require_bytes(image, battle_shortcuts.DIRECT_TARGET_BRANCH,
                  "F6 C3 80 0F 84 A7 00 00 00", "direct native-target branch")
    require_bytes(image, battle_shortcuts.MAGIC_CONTROLLER_TAIL,
                  battle_shortcuts.MAGIC_CONTROLLER_TAIL_ORIGINAL.hex(),
                  "native Magic controller tail call")
    require_bytes(image, battle_shortcuts.MAGIC_TARGET_CANCEL,
                  battle_shortcuts.MAGIC_TARGET_CANCEL_ORIGINAL.hex(),
                  "native Magic target cancel")
    require_bytes(image, battle_shortcuts.MAGIC_ACTION_FINISH,
                  battle_shortcuts.MAGIC_ACTION_FINISH_ORIGINAL.hex(),
                  "native Magic post-queue transition")
    require_bytes(image, 0x004FE5E4, "E8 E7 D0 FB FF", "native Magic action producer")
    require_bytes(image, 0x004FE6D6, "E8 35 CF FB FF", "native Magic action queue")

    scan_patch = battle_shortcuts.build_hext(scanned_target_scan=True)
    scan_router = bytes.fromhex(
        scan_patch.split(f"{battle_shortcuts.CODE_CAVE:X} = ", 1)[1].splitlines()[0]
    )
    assert bytes((0xA8, battle_shortcuts.CARD_GAME_INPUT_MASK)) in scan_router
    assert battle_shortcuts.SCAN_DESCRIPTOR_BYTES == bytes.fromhex("02 00 00 00")
    assert battle_shortcuts.SCAN_LIST_BYTES == bytes.fromhex("32 01 80 54 00")
    assert f"{battle_shortcuts.MAGIC_CONTROLLER_TAIL:X} = E9" in scan_patch
    assert f"{battle_shortcuts.MAGIC_TARGET_CANCEL:X} = E9" in scan_patch
    assert f"{battle_shortcuts.MAGIC_ACTION_FINISH:X} = E9" in scan_patch
    for retired_hook in (0x004BC89C, 0x00484D20, 0x0048D7E3,
                         0x00486A10, 0x0084D51F):
        assert f"{retired_hook:X} =" not in scan_patch
    init_payload = battle_shortcuts._scan_init_payload()
    assert battle_shortcuts.SCAN_LIST_CALLBACK.to_bytes(4, "little") in init_payload
    assert battle_shortcuts.MAGIC_LIST_CALLBACK.to_bytes(4, "little") in init_payload
    assert bytes.fromhex("C6 44 24 10 06") in battle_shortcuts._scan_cancel_payload()
    assert bytes.fromhex("C6 44 24 10 06") in battle_shortcuts._scan_finish_payload()

    scan_only_patch = battle_shortcuts.build_hext(
        scanned_target_scan=True, universal_item=False,
    )
    for forbidden_input in ("A8 04", "A8 08", "RIGHT_STICK", "DINPUT"):
        assert forbidden_input not in scan_only_patch

    # Ban both crashing descriptors and every component of the synthetic
    # post-confirm record conversion. A later repair must prove a native Scan
    # producer instead of restoring these names under a new address.
    for forbidden_source in (
        "02 A0 54 00",
        "02 A0 D4 00",
        "SCAN_RECORD_MARKER",
        "def _record_payload",
        "def _queue_payload",
        "def _stock_check_payload",
        "def _stock_mutate_payload",
        "def _scan_teardown_payload",
        "RECORD_HOOK",
        "QUEUE_CAVE",
        "MAGIC_STOCK_CHECK_CAVE",
        "MAGIC_STOCK_MUTATE_CAVE",
        "SCAN_TEARDOWN_CAVE",
    ):
        assert forbidden_source not in module_text

    for invalid in (0, 1, "true", None):
        try:
            battle_shortcuts.build_hext(universal_item=invalid)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Universal Item accepted {invalid!r}")
        try:
            battle_shortcuts.build_hext(scanned_target_scan=invalid)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Enhanced Scan accepted {invalid!r}")

    print("Issue #53 native Universal Item and Enhanced Scan boundaries passed")


if __name__ == "__main__":
    main()
