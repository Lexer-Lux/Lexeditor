from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import sys

import pefile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.ff8 import fixed_command_menu as menu


EXE = Path(r"D:\SteamLibrary\steamapps\common\FINAL FANTASY VIII\FF8_EN.exe")
KERNEL = Path(
    r"C:\Users\Lexer\AppData\Local\Lexeditor\game-data\ff8\baseline\en\main\kernel.bin"
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def image_bytes(pe: pefile.PE, address: int, length: int) -> bytes:
    rva = address - pe.OPTIONAL_HEADER.ImageBase
    return pe.get_memory_mapped_image()[rva:rva + length]


require(EXE.is_file(), "installed FF8_EN.exe is missing")
require(sha256(EXE.read_bytes()).hexdigest() == menu.SUPPORTED_EXE_SHA256,
        "installed FF8_EN.exe is not the researched Steam English build")
pe = pefile.PE(str(EXE), fast_load=True)

# ResetAndParseBattleAndFieldCharacter reads the character id from argument 1.
require(image_bytes(pe, menu.RESET_AND_PARSE_CHARACTER, 10) ==
        bytes.fromhex("53 8B 5C 24 08 56 8B 74 24 10"),
        "character parser entry bytes changed")

# The parser converts the character-relative command array into consecutive
# four-byte runtime descriptors. This is the safe construction boundary.
require(image_bytes(pe, menu.COMMAND_DESCRIPTOR_BUILD, 23) == bytes.fromhex(
    "8D BF 38 E1 CF 01 BD 01 00 00 00 8D 46 25 2B EF 8A 0F 80 F9 14 0F 82"),
    "command descriptor builder bytes changed")
require(image_bytes(pe, menu.COMMAND_DESCRIPTOR_BUILD,
                    len(menu.COMMAND_DESCRIPTOR_BUILD_ORIGINAL)) ==
        menu.COMMAND_DESCRIPTOR_BUILD_ORIGINAL,
        "fixed-builder hook bytes changed")
require(image_bytes(pe, menu.POST_BUILDER_HOOK,
                    len(menu.POST_BUILDER_ORIGINAL)) ==
        menu.POST_BUILDER_ORIGINAL,
        "shared post-builder hook bytes changed")

# Main-command setup points the alternate descriptor at hidden runtime slot 4.
require(image_bytes(pe, 0x004BBC2C, 24) == bytes.fromhex(
    "8D 91 1E F0 CF 01 8D 89 2E F0 CF 01 89 15 34 68 D7 01"
    " 89 0D 38 68 D7 01"),
    "alternate-command pointer setup changed")
# The generic resolver requires flag 0x04 and swaps to controller+8.
require(image_bytes(pe, 0x004BC783, 28) == bytes.fromhex(
    "8A 46 1A 84 C0 74 15 F6 43 03 04 74 0F 8B 46 08 C6 46 1A 40"
    " 89 44 24 14 8B D8 EB 04"),
    "generic alternate-command resolver changed")
# The renderer uses the same flag to draw the existing right-arrow affordance.
require(image_bytes(pe, 0x004BCB87, 5) == bytes.fromhex("F6 C3 04 74 44"),
        "alternate-command arrow renderer changed")

# The battle controller resolves actor + selected slot * 4 + 0x1E.
require(image_bytes(pe, menu.SELECTED_DESCRIPTOR_RESOLVER, 37) == bytes.fromhex(
    "0F BE 05 44 68 D7 01 8D 0C C5 00 00 00 00 2B C8 8D 14 88 33 C0"
    " A0 43 68 D7 01 8D 0C 90 8D 04 8D 1E F0 CF 01 C3"),
    "selected-command descriptor resolver bytes changed")
require(image_bytes(pe, menu.EXECUTE_SELECTED_DESCRIPTOR, 6) ==
        bytes.fromhex("F6 40 03 04 74 1F"),
        "alternate-command dispatch test changed")
require(image_bytes(pe, menu.LIMIT_ALTERNATE_FLAG_WRITE, 22) == bytes.fromhex(
    "8A 86 21 F0 CF 01 74 0C 0C 04 88 86 21 F0 CF 01 5E 5B 59 C3 24 FB"),
    "vanilla Limit alternate-flag writer changed")

require(menu.CHARACTER_COMMANDS[3] == ("Quistis", "Draw", 6),
        "Quistis must use Draw")
require(menu.CHARACTER_COMMANDS[2] == ("Irvine", "Shoot", None),
        "Irvine's visible command name must be Shoot")
require(menu.CHARACTER_COMMANDS[5] == ("Selphie", "Summon", 3),
        "Selphie must use GF/Summon")
require(menu.GF_COMMANDS[14] == ("Tonberry", "LV Down", 33, 34),
        "Tonberry must retain both LV commands")
require(menu.GF_COMMANDS[15][2] == 7, "Eden must use Devour")

# The extracted vanilla kernel proves every source ability handed to the
# original descriptor builder. Section 13 starts at header offset index 12;
# command ability 0x14 is record zero and battle command is byte 5.
require(KERNEL.is_file(), "extracted vanilla kernel.bin is missing")
kernel = KERNEL.read_bytes()
section_count = int.from_bytes(kernel[:4], "little")
offsets = [int.from_bytes(kernel[4 + index * 4:8 + index * 4], "little")
           for index in range(section_count)]
section_13 = kernel[offsets[12]:offsets[13]]


def battle_command(source_ability: int) -> int:
    record = source_ability - 0x14
    require(0 <= record < len(section_13) // 8,
            f"source ability is outside kernel section 13: {source_ability:#x}")
    return section_13[record * 8 + 5]


require(battle_command(menu.MAGIC_SOURCE_ABILITY) == 2,
        "Magic source no longer maps to Magic")
require(battle_command(0x22) == 33 and battle_command(0x23) == 34,
        "Tonberry LV Down/LV Up source records changed")
for character_id, source in menu.CHARACTER_SOURCE_ABILITIES.items():
    if source is not None:
        require(battle_command(source) == menu.CHARACTER_COMMANDS[character_id][2],
                f"character source mismatch for {menu.CHARACTER_COMMANDS[character_id][0]}")
for gf_id, source in menu.GF_SOURCE_ABILITIES.items():
    require(battle_command(source) == menu.GF_COMMANDS[gf_id][2],
            f"GF source mismatch for {menu.GF_COMMANDS[gf_id][0]}")

require(menu.single_gf_id(0) is None, "empty GF mask must stay empty")
require(menu.single_gf_id(1 << 14) == 14, "Tonberry mask must resolve to Tonberry")
try:
    menu.single_gf_id((1 << 2) | (1 << 3))
except ValueError:
    pass
else:
    raise AssertionError("multi-GF construction input was accepted")
require(menu.fixed_source_commands(3, 1 << 15) == (0x14, 0x16, 0x25, 0xFF),
        "Quistis/Eden fixed source order changed")
require(menu.fixed_source_commands(3, 1 << 3) == (0x14, 0x16, 0x1C, 0xFF),
        "Quistis with Siren must be Attack, Magic, Draw, Treatment")
require(menu.fixed_source_commands(3, 1 << 14) == (0x14, 0x16, 0x22, 0x23),
        "Quistis with Tonberry must put LV Up in the hidden alternate descriptor")
require(menu.fixed_source_commands(1, 1 << 4) == (0x14, 0x1D, 0x1D, 0xFF),
        "Zell/Brothers fixed source order changed")
require(menu.fixed_source_commands(5, 1 << 0) == (0x14, 0x15, 0x19, 0xFF),
        "Selphie/Quezacotl fixed source order changed")
require(menu.fixed_source_commands(2, 1 << 2) == (0x14, 0xFF, 0x1B, 0xFF),
        "Irvine must reserve his custom Shoot slot")
require(menu.fixed_source_commands(0, 1 << 2) == (0x14, 0xFF, 0x1B, 0xFF),
        "Squall must reserve his custom Switch slot")
require(menu.fixed_source_commands(4, 1 << 3) == (0x14, 0xFF, 0x1C, 0xFF),
        "Rinoa's Angelo placeholder must remain unavailable without blocking Siren")
require(bytes(menu.CHARACTER_SOURCE_TABLE) == bytes.fromhex("FF 1D FF 16 FF 15"),
        "character source table differs from the supported-command contract")
require(bytes(menu.GF_SOURCE_TABLE) == bytes.fromhex(
    "19 FF 1B 1C 1D 1E FF 1F 20 FF 21 1A FF 24 22 25"),
    "GF source table differs from the requested sixteen-GF contract")
for gf_id in range(16):
    result = menu.fixed_source_commands(3, 1 << gf_id)
    require(result == (0x14, 0x16, menu.GF_SOURCE_TABLE[gf_id],
                       menu.GF_ALTERNATE_SOURCE_TABLE[gf_id]),
            f"GF source row {gf_id} changed")
for gf_id in (1, 6, 9, 12):
    require(menu.GF_SOURCE_TABLE[gf_id] == 0xFF,
            f"GF {gf_id} received a guessed command")
require(menu.fixed_source_commands(3, 0) == (0x14, 0x16, 0xFF, 0xFF),
        "empty GF mask must leave the GF slot empty")
try:
    menu.fixed_source_commands(3, (1 << 2) | (1 << 3))
except ValueError:
    pass
else:
    raise AssertionError("multi-GF builder input was accepted")

payload = menu._builder_payload()
labels = menu._command_label_payload()
require(bytes(menu.CHARACTER_SOURCE_TABLE) in payload,
        "character source table is absent from builder payload")
require(bytes(menu.GF_SOURCE_TABLE) in payload,
        "GF source table is absent from builder payload")
require(bytes(menu.GF_ALTERNATE_SOURCE_TABLE) in payload,
        "GF alternate-source table is absent from builder payload")
require(bytes.fromhex("0F B7 47 08 85 C0") in payload,
        "builder does not read the GF mask at saved commands +8")
require(bytes.fromhex("8D 48 FF 85 C1") in payload,
        "builder does not reject a non-single GF mask")
require(bytes.fromhex("C7 04 24") in payload,
        "builder does not redirect the preserved EDI source pointer")
require(bytes.fromhex("88 0D") in payload,
        "builder does not write the hidden alternate source")
require(menu.BUILDER_CAVE + len(payload) <= menu.SWITCH_RESERVED_CAVE_START,
        "builder overlaps the reserved Switch cave")
require(menu.COMMAND_LABEL_ORIGINAL in labels,
        "shared command label resolver does not preserve vanilla labels")
require(bytes.fromhex("3D FE 00 00 00") in labels and
        bytes.fromhex("83 F8 FE") not in labels,
        "Switch marker comparison is not an unsigned command-ID comparison")
require(menu.SHOOT_TEXT in labels and menu.SWITCH_TEXT in labels and
        menu.SUMMON_TEXT in labels,
        "shared command label resolver omits a requested visible name")
require(bytes.fromhex("83 F8 0E") in labels,
        "shared command label resolver does not identify vanilla Shot")
require(bytes.fromhex("83 F8 03") in labels and
        menu.SELECTED_ACTOR.to_bytes(4, "little") in labels and
        bytes.fromhex("69 C9 D0 01 00 00") in labels and
        bytes((menu.SELPHIE,)) in labels,
        "Summon label is not restricted to Selphie's selected actor")
require(menu.COMMAND_LABEL_CAVE + len(labels) <= menu.SWITCH_RESERVED_CAVE_START,
        "shared command label resolver overlaps the reserved Switch cave")
component = menu.build_builder_component()
require(f"{menu.COMMAND_DESCRIPTOR_BUILD:X} = " in component,
        "builder component does not patch the verified engine boundary")
require(f"{menu.BUILDER_CAVE:X} = " in component,
        "builder component contains no executable payload")
require("Attack, Magic, character, GF" in component,
        "builder component lost its exact slot-order contract")
post = menu._post_builder_payload()
require(bytes.fromhex("80 7E 2A 21") in post and
        bytes.fromhex("80 7E 2E 22") in post and
        bytes.fromhex("80 4E 2D 04") in post,
        "Tonberry LV Down does not point to the LV Up alternate descriptor")
require(bytes.fromhex("C7 46 26 0E 84 40 00") in post,
        "shared post-builder lost Irvine Shoot")
require(menu.POST_BUILDER_CAVE + len(post) <= menu.SWITCH_RESERVED_CAVE_START,
        "shared post-builder overlaps the Switch caves")
require(menu.build_patch(enabled=False, single_gf_enabled=False) == "",
        "disabled mode must emit no patch")
try:
    menu.build_patch(enabled=True, single_gf_enabled=False)
except RuntimeError as error:
    require(menu.SINGLE_GF_DEPENDENCY in str(error),
            "enabled mode must require Single GF")
else:
    raise AssertionError("fixed commands were enabled without Single GF")
enabled = menu.build_patch(enabled=True, single_gf_enabled=True)
require(not menu.BLOCKERS, "resolved fixed command menu still reports blockers")
require(f"{menu.COMMAND_DESCRIPTOR_BUILD:X} = " in enabled,
        "enabled fixed command menu omits the source builder")
require(f"{menu.POST_BUILDER_HOOK:X} = " in enabled,
        "enabled fixed command menu omits the shared post-builder")

supported = menu.supported_command_audit()
require(supported["Squall"] ==
        ("Switch", "static-verified custom dispatcher; runtime test required"),
        "Squall supported-command audit changed")
require(supported["Irvine"] ==
        ("Shoot", "static-verified custom dispatcher; runtime test required"),
        "Irvine supported-command audit changed")
require(supported["Rinoa"] == ("blank", "Angelo is explicitly TBD"),
        "Rinoa must remain fail closed")

print("FF8 fixed-command engine boundary and complete supported composition passed")
