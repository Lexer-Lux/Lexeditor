"""Guarded fixed four-slot command builder for Lexeditor issue #52."""

from __future__ import annotations


SUPPORTED_EXE_SHA256 = "064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570"

# savemap_ff8_character, confirmed by official FFNx src/ff8/save_data.h.
CHARACTER_STRIDE = 0x98
COMMANDS_OFFSET = 0x50
GF_MASK_OFFSET = 0x58

# Installed Steam English FF8_EN.exe. Official FFNx resolves the same functions
# through battle_main_loop -> 0x4A2690 -> 0x4A6660 -> 0x4A3D20.
RESET_AND_PARSE_CHARACTER = 0x00495530
COMMAND_DESCRIPTOR_BUILD = 0x00495729
COMMAND_DESCRIPTOR_BUILD_ORIGINAL = bytes.fromhex("8D BF 38 E1 CF 01")
BATTLE_COMMAND_CONTROLLER = 0x004BB710
SELECTED_DESCRIPTOR_RESOLVER = 0x004BB510
SELECTED_DESCRIPTOR_POINTER = 0x01D76834
EXECUTE_SELECTED_DESCRIPTOR = 0x004BBCC1
LIMIT_ALTERNATE_FLAG_WRITE = 0x0049433A

# Runtime descriptors begin at actor + 0x1E and use four bytes per menu slot.
RUNTIME_COMMANDS_OFFSET = 0x1E
RUNTIME_COMMAND_DESCRIPTOR_SIZE = 4
RUNTIME_COMMAND_SLOT_COUNT = 5
ALTERNATE_COMMAND_FLAG = 0x04

BUILDER_CAVE = 0x0279F900
COMMAND_LABEL_CAVE = 0x0279F9A0
POST_BUILDER_CAVE = 0x0279FA40
SWITCH_RESERVED_CAVE_START = 0x0279FB00
LEARNED_COMMAND_CAVE = POST_BUILDER_CAVE + 0x60
GF_LEARNED_BITS = 0x01CFDCBC
GF_SAVE_STRIDE = 0x44

POST_BUILDER_HOOK = 0x00495805
POST_BUILDER_ORIGINAL = bytes.fromhex("8B 86 90 01 00 00")

COMMAND_LABEL_HOOK = 0x0047EBD0
COMMAND_LABEL_ORIGINAL = bytes.fromhex(
    "8B 44 24 04 66 8B 04 C5 2C 3F CF 01"
)
SELECTED_ACTOR = 0x01D76844
RUNTIME_ACTOR_BASE = 0x01CFF000
RUNTIME_ACTOR_STRIDE = 0x1D0
CHARACTER_ID_OFFSET = 0x1C3
SELPHIE = 5

# FF8's encoded text bytes. This resolver keeps synthetic Switch readable,
# renames command 0x0E from Shot to the requested Shoot, and shows GF as Summon
# only while Selphie is the selected battle actor.
SHOOT_TEXT = bytes.fromhex("57 66 6D 6D 72 00")
SWITCH_TEXT = bytes.fromhex("57 75 67 72 61 66 00")
SUMMON_TEXT = bytes.fromhex("57 73 6B 6B 6D 6C 00")

# Source IDs consumed by the vanilla descriptor builder. They are command
# ability IDs, not battle-command IDs. The vanilla builder translates them
# through kernel section 13 and applies its normal target and availability data.
MAGIC_SOURCE_ABILITY = 0x14
EMPTY_SOURCE_ABILITY = 0xFF
CHARACTER_SOURCE_ABILITIES = {
    0: None,  # Squall: Switch needs a new dispatcher and label.
    1: 0x1D,  # Zell: Defend.
    2: None,  # Irvine: custom Shoot is not vanilla Shot.
    3: 0x16,  # Quistis: Draw.
    4: None,  # Rinoa: Angelo has no command-ability source record.
    5: 0x15,  # Selphie: vanilla GF command, shown as Summon by the custom menu.
}
GF_SOURCE_ABILITIES = {
    0: 0x19,   # Quezacotl: Card.
    2: 0x1B,   # Ifrit: Mad Rush.
    3: 0x1C,   # Siren: Treatment.
    4: 0x1D,   # Brothers: Defend.
    5: 0x1E,   # Diablos: Darkside.
    7: 0x1F,   # Leviathan: Recover.
    8: 0x20,   # Pandemona: Absorb.
    10: 0x21,  # Alexander: Revive.
    11: 0x1A,  # Doomtrain: Doom.
    13: 0x24,  # Cactuar: Kamikaze.
    14: 0x22,  # Tonberry: LV Down. LV Up needs the alternate handler.
    15: 0x25,  # Eden: Devour.
}

# Every valid GF bit has an explicit result. GFs omitted from Lexer's requested
# command map receive an empty fourth slot. No nearby command is substituted.
GF_SOURCE_TABLE = tuple(GF_SOURCE_ABILITIES.get(gf_id, EMPTY_SOURCE_ABILITY)
                        for gf_id in range(16))
GF_ALTERNATE_SOURCE_TABLE = tuple(
    0x23 if gf_id == 14 else EMPTY_SOURCE_ABILITY for gf_id in range(16)
)
CHARACTER_SOURCE_TABLE = tuple(
    EMPTY_SOURCE_ABILITY if CHARACTER_SOURCE_ABILITIES[character_id] is None
    else CHARACTER_SOURCE_ABILITIES[character_id]
    for character_id in range(6)
)

# FF8 battle-command IDs from kernel section 1. None means the requested command
# has no matching vanilla dispatcher and needs a new handler.
CHARACTER_COMMANDS = {
    0: ("Squall", "Switch", None),
    1: ("Zell", "Defend", 23),
    2: ("Irvine", "Shoot", None),
    3: ("Quistis", "Draw", 6),
    4: ("Rinoa", "Angelo", None),
    5: ("Selphie", "Summon", 3),
}

# GF IDs come from FFNx's savemap ordering. Commands use kernel section 1 IDs.
GF_COMMANDS = {
    0: ("Quezacotl", "Card", 29, None),
    2: ("Ifrit", "Mad Rush", 24, None),
    3: ("Siren", "Treatment", 25, None),
    4: ("Brothers", "Defend", 23, None),
    5: ("Diablos", "Darkside", 28, None),
    7: ("Leviathan", "Recover", 26, None),
    8: ("Pandemona", "Absorb", 32, None),
    10: ("Alexander", "Revive", 27, None),
    11: ("Doomtrain", "Doom", 30, None),
    13: ("Cactuar", "Kamikaze", 31, None),
    14: ("Tonberry", "LV Down", 33, 34),
    15: ("Eden", "Devour", 7, None),
}

SINGLE_GF_DEPENDENCY = (
    "Fixed Command Menu requires Monogamy because one GF supplies the "
    "GF-specific fourth command."
)

BLOCKERS: tuple[str, ...] = ()


def single_gf_id(gf_mask: int) -> int | None:
    """Return the one selected GF, and reject a multi-GF construction input."""
    mask = int(gf_mask) & 0xFFFF
    if mask == 0:
        return None
    if mask & (mask - 1):
        raise ValueError("Fixed Command Menu requires a Monogamy-compatible one-GF mask")
    return mask.bit_length() - 1


def fixed_source_commands(character_id: int, gf_mask: int) -> tuple[int, int, int, int]:
    """Return the four source records for slots after the fixed Attack slot."""
    character_id = int(character_id)
    if character_id not in CHARACTER_SOURCE_ABILITIES:
        raise ValueError("Character ID must be from 0 to 5")
    # Squall and Irvine use separate guarded runtime handlers. Rinoa's Angelo
    # remains unavailable. Their source slot stays empty in this vanilla-source
    # builder, so no existing command can masquerade as the requested command.
    character_source = CHARACTER_SOURCE_TABLE[character_id]
    gf_id = single_gf_id(gf_mask)
    gf_source = EMPTY_SOURCE_ABILITY if gf_id is None else GF_SOURCE_TABLE[gf_id]
    gf_alternate = (
        EMPTY_SOURCE_ABILITY if gf_id is None else GF_ALTERNATE_SOURCE_TABLE[gf_id]
    )
    return MAGIC_SOURCE_ABILITY, character_source, gf_source, gf_alternate


class _Code:
    def __init__(self, address: int):
        self.address = address
        self.data = bytearray()
        self.labels: dict[str, int] = {}
        self.relative_fixups: list[tuple[int, str]] = []
        self.absolute_fixups: list[tuple[int, str]] = []
        self.short_fixups: list[tuple[int, str]] = []

    def short(self, opcode: int, label: str) -> None:
        self.data.append(opcode)
        self.short_fixups.append((len(self.data), label))
        self.data.append(0)

    def add(self, data: bytes) -> None:
        self.data.extend(data)

    def label(self, name: str) -> None:
        self.labels[name] = len(self.data)

    def branch(self, opcode: bytes, label: str) -> None:
        self.data.extend(opcode)
        self.relative_fixups.append((len(self.data), label))
        self.data.extend(b"\0\0\0\0")

    def absolute(self, prefix: bytes, label: str, suffix: bytes = b"") -> None:
        self.data.extend(prefix)
        self.absolute_fixups.append((len(self.data), label))
        self.data.extend(b"\0\0\0\0")
        self.data.extend(suffix)

    def finish(self) -> bytes:
        for offset, label in self.short_fixups:
            delta = self.labels[label] - offset - 1
            assert -128 <= delta <= 127
            self.data[offset] = delta & 255
        for offset, label in self.relative_fixups:
            delta = self.address + self.labels[label] - (self.address + offset + 4)
            self.data[offset:offset + 4] = delta.to_bytes(4, "little", signed=True)
        for offset, label in self.absolute_fixups:
            target = self.address + self.labels[label]
            self.data[offset:offset + 4] = target.to_bytes(4, "little")
        return bytes(self.data)


def _near(source: int, target: int) -> bytes:
    return b"\xE9" + (target - source - 5).to_bytes(4, "little", signed=True)


def _builder_payload() -> bytes:
    """Redirect the vanilla source loop to one process-local four-byte row."""
    code = _Code(BUILDER_CAVE)
    code.add(COMMAND_DESCRIPTOR_BUILD_ORIGINAL)  # EDI = this character's saved command row
    code.add(b"\x60")  # preserve every live builder register
    code.absolute(bytes.fromhex("C7 05"), "source", bytes.fromhex("FF FF FF FF"))
    code.absolute(bytes.fromhex("C6 05"), "source", bytes((MAGIC_SOURCE_ABILITY,)))
    code.add(bytes.fromhex("0F B6 86 C3 01 00 00 83 F8 05"))
    code.short(0x77, "gf")
    code.absolute(bytes.fromhex("8A 88"), "characters")
    code.absolute(bytes.fromhex("88 0D"), "source_1")
    code.label("gf")
    code.add(bytes.fromhex("8B 3C 24 0F B7 47 08 85 C0"))
    code.short(0x74, "done")
    code.add(bytes.fromhex("8D 48 FF 85 C1"))
    code.short(0x75, "done")
    code.add(bytes.fromhex("0F BC C0"))
    code.absolute(bytes.fromhex("8A 88"), "gfs")
    code.add(b"\xE8" + (LEARNED_COMMAND_CAVE - (BUILDER_CAVE + len(code.data) + 5)).to_bytes(4, "little", signed=True))
    code.absolute(bytes.fromhex("88 0D"), "source_2")
    code.absolute(bytes.fromhex("8A 88"), "gf_alternates")
    code.add(b"\xE8" + (LEARNED_COMMAND_CAVE - (BUILDER_CAVE + len(code.data) + 5)).to_bytes(4, "little", signed=True))
    code.absolute(bytes.fromhex("88 0D"), "source_3")
    code.label("done")
    code.absolute(bytes.fromhex("C7 04 24"), "source")  # POPAD restores redirected EDI
    code.add(b"\x61")
    code.add(_near(BUILDER_CAVE + len(code.data), COMMAND_DESCRIPTOR_BUILD + 6))
    code.label("characters")
    code.add(bytes(CHARACTER_SOURCE_TABLE))
    code.label("gfs")
    code.add(bytes(GF_SOURCE_TABLE))
    code.label("gf_alternates")
    code.add(bytes(GF_ALTERNATE_SOURCE_TABLE))
    code.label("source")
    code.add(bytes((MAGIC_SOURCE_ABILITY, EMPTY_SOURCE_ABILITY,
                    EMPTY_SOURCE_ABILITY, EMPTY_SOURCE_ABILITY)))
    # Aliases target individual bytes in the source row.
    code.labels["source_1"] = code.labels["source"] + 1
    code.labels["source_2"] = code.labels["source"] + 2
    code.labels["source_3"] = code.labels["source"] + 3
    return code.finish()


def _command_label_payload() -> bytes:
    """Resolve the three requested custom names without changing dispatch IDs."""
    code = _Code(COMMAND_LABEL_CAVE)
    code.add(bytes.fromhex("8B 44 24 04 3D FE 00 00 00"))
    code.branch(bytes.fromhex("0F 84"), "switch")
    code.add(bytes.fromhex("83 F8 0E"))
    code.branch(bytes.fromhex("0F 84"), "shoot")
    code.add(bytes.fromhex("83 F8 03"))
    code.branch(bytes.fromhex("0F 85"), "vanilla")
    code.add(b"\x0F\xB6\x0D" + SELECTED_ACTOR.to_bytes(4, "little"))
    code.add(bytes.fromhex("83 F9 0A"))
    code.branch(bytes.fromhex("0F 87"), "vanilla")
    code.add(bytes.fromhex("69 C9 D0 01 00 00"))
    code.add(
        b"\x80\xB9"
        + (RUNTIME_ACTOR_BASE + CHARACTER_ID_OFFSET).to_bytes(4, "little")
        + bytes((SELPHIE,))
    )
    code.branch(bytes.fromhex("0F 85"), "vanilla")
    code.absolute(b"\xB8", "summon")
    code.add(b"\xC3")
    code.label("shoot")
    code.absolute(b"\xB8", "shoot_text")
    code.add(b"\xC3")
    code.label("switch")
    code.absolute(b"\xB8", "switch_text")
    code.add(b"\xC3")
    code.label("vanilla")
    code.add(COMMAND_LABEL_ORIGINAL)
    code.add(_near(COMMAND_LABEL_CAVE + len(code.data),
                   COMMAND_LABEL_HOOK + len(COMMAND_LABEL_ORIGINAL)))
    code.label("summon")
    code.add(SUMMON_TEXT)
    code.label("shoot_text")
    code.add(SHOOT_TEXT)
    code.label("switch_text")
    code.add(SWITCH_TEXT)
    return code.finish()


def _learned_command_payload() -> bytes:
    """Keep CL only when GF EAX has learned that source ability bit."""
    code = _Code(LEARNED_COMMAND_CAVE)
    code.add(bytes.fromhex("80 F9 FF"))
    code.short(0x74, "return")
    code.add(bytes.fromhex("52 53 0F B6 D1 6B D8 44"))
    code.add(bytes.fromhex("0F A3 93") + GF_LEARNED_BITS.to_bytes(4, "little"))
    code.short(0x72, "learned")
    code.add(bytes.fromhex("B1 FF"))
    code.label("learned")
    code.add(bytes.fromhex("5B 5A"))
    code.label("return")
    code.add(b"\xC3")
    return code.finish()


def _post_builder_payload() -> bytes:
    """Finish Tonberry's alternate descriptor and the custom Irvine slot."""
    from . import shoot_issue_54

    code = _Code(POST_BUILDER_CAVE)
    code.add(POST_BUILDER_ORIGINAL)
    # Controller initialization at 0x4BBC38 points its alternate pointer to
    # actor+0x2E, the hidden fifth runtime descriptor. Flag 0x04 on the visible
    # GF slot makes the renderer draw the arrow and 0x4BC770 select that pointer.
    code.add(bytes.fromhex("80 7E 2A 21"))  # visible GF command is LV Down
    code.branch(bytes.fromhex("0F 85"), "irvine")
    code.add(bytes.fromhex("80 7E 2E 22"))  # hidden alternate is LV Up
    code.branch(bytes.fromhex("0F 85"), "irvine")
    code.add(bytes.fromhex("80 4E 2D 04"))
    code.label("irvine")
    code.add(b"\x80\xBE" + CHARACTER_ID_OFFSET.to_bytes(4, "little") + b"\x02")
    code.branch(bytes.fromhex("0F 85"), "done")
    code.add(bytes.fromhex("C7 46 26 0E 84 40 00"))
    code.add(b"\x80\x3D" + shoot_issue_54.SHOOT_LOCK.to_bytes(4, "little") + b"\x00")
    code.branch(bytes.fromhex("0F 84"), "done")
    code.add(bytes.fromhex("80 4E 29 02"))
    code.label("done")
    code.add(_near(POST_BUILDER_CAVE + len(code.data), POST_BUILDER_HOOK + 6))
    return code.finish()


def supported_command_audit() -> dict[str, tuple[str, str]]:
    """Describe only the character commands backed by a proved dispatcher."""
    return {
        "Squall": ("Switch", "static-verified custom dispatcher; runtime test required"),
        "Zell": ("Defend", "verified vanilla dispatcher"),
        "Irvine": ("Shoot", "static-verified custom dispatcher; runtime test required"),
        "Quistis": ("Draw", "verified vanilla dispatcher"),
        "Rinoa": ("blank", "Angelo is explicitly TBD"),
        "Selphie": ("Summon", "verified vanilla GF dispatcher"),
    }


def build_builder_component() -> str:
    """Emit only the verified construction slice; dispatch stays separate."""
    payload = _builder_payload()
    if BUILDER_CAVE + len(payload) > COMMAND_LABEL_CAVE:
        raise AssertionError("Fixed-command builder overlaps the command-label resolver")
    hook = _near(COMMAND_DESCRIPTOR_BUILD, BUILDER_CAVE) + b"\x90"
    return "\n".join((
        "# Fixed command descriptor builder: Attack, Magic, character, GF.",
        f"{BUILDER_CAVE:X}:{len(payload):X}",
        f"{COMMAND_DESCRIPTOR_BUILD:X} = {hook.hex(' ').upper()}",
        f"{BUILDER_CAVE:X} = {payload.hex(' ').upper()}",
        "",
    ))


def build_post_builder_component() -> str:
    """Emit the single owner for Tonberry alternate and Irvine Shoot slots."""
    payload = _post_builder_payload()
    if POST_BUILDER_CAVE + len(payload) > LEARNED_COMMAND_CAVE:
        raise AssertionError("Shared post-builder overlaps the Switch cave")
    hook = _near(POST_BUILDER_HOOK, POST_BUILDER_CAVE) + b"\x90"
    gate = _learned_command_payload()
    assert LEARNED_COMMAND_CAVE + len(gate) <= SWITCH_RESERVED_CAVE_START
    return "\n".join((
        "# Fixed command post-builder: Tonberry alternate and Irvine Shoot.",
        f"{POST_BUILDER_CAVE:X}:{len(payload):X}",
        f"{POST_BUILDER_HOOK:X} = {hook.hex(' ').upper()}",
        f"{POST_BUILDER_CAVE:X} = {payload.hex(' ').upper()}",
        f"{LEARNED_COMMAND_CAVE:X}:{len(gate):X}",
        f"{LEARNED_COMMAND_CAVE:X} = {gate.hex(' ').upper()}",
        "",
    ))


def build_supported_components() -> str:
    """Emit the verified builder, Switch, and repaired Shoot components."""
    from . import switch_issue_52
    from . import shoot_issue_54

    # Remove Switch's older one-name hook before Shoot emits the shared resolver.
    # The combined patch must have one owner for this engine boundary; relying
    # on duplicate Hext assignment order would not be a safe composition rule.
    switch_component = switch_issue_52.build_component()
    label_assignment = f"{COMMAND_LABEL_HOOK:X} = "
    switch_component = "\n".join(
        line for line in switch_component.splitlines()
        if not line.startswith(label_assignment)
    ) + "\n"
    shoot_component = shoot_issue_54.build_component()
    post_assignment = f"{POST_BUILDER_HOOK:X} = "
    shoot_component = "\n".join(
        line for line in shoot_component.splitlines()
        if not line.startswith(post_assignment)
    ) + "\n"
    return (build_builder_component() + build_post_builder_component()
            + switch_component + shoot_component)


def build_patch(*, enabled: bool, single_gf_enabled: bool = False) -> str:
    """Return the fixed command composition only under Monogamy."""
    if not isinstance(enabled, bool) or not isinstance(single_gf_enabled, bool):
        raise ValueError("Fixed Command Menu and Monogamy must be true or false")
    if not enabled:
        return ""
    if not single_gf_enabled:
        raise RuntimeError(SINGLE_GF_DEPENDENCY)
    if BLOCKERS:
        raise RuntimeError("Fixed Command Menu is not ready: " + " ".join(BLOCKERS))
    return build_supported_components()
