"""One-shot guarded integration for FF8 fixed-menu Rinoa/Angelo."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one integration seam, found {count}")
    return text.replace(old, new, 1)


def patch_fixed_command_menu() -> None:
    path = ROOT / "games/ff8/fixed_command_menu.py"
    text = path.read_text(encoding="utf-8")

    text = replace_once(
        text,
        "POST_BUILDER_CAVE = 0x0279FA40\n"
        "SWITCH_RESERVED_CAVE_START = 0x0279FB00\n"
        "LEARNED_COMMAND_CAVE = POST_BUILDER_CAVE + 0x60\n",
        "# The command-label, post-builder and learned-command helpers share the\n"
        "# existing 0x0279F9A0..0x0279FAFF fixed-command reservation. Angelo\n"
        "# needs slightly more of both variable-sized helpers, so repartition the\n"
        "# same block without crossing Switch's reserved cave at 0x0279FB00.\n"
        "POST_BUILDER_CAVE = 0x0279FA60\n"
        "SWITCH_RESERVED_CAVE_START = 0x0279FB00\n"
        "LEARNED_COMMAND_CAVE = POST_BUILDER_CAVE + 0x80\n",
        "fixed-command cave repartition",
    )

    text = replace_once(
        text,
        "CHARACTER_ID_OFFSET = 0x1C3\nSELPHIE = 5\n",
        "CHARACTER_ID_OFFSET = 0x1C3\nRINOA = 4\nSELPHIE = 5\n\n"
        "# OpenFF8's runtime Kernel layout and the current FF8 decomp agree that\n"
        "# kernel section 1 (battle commands) is resident at this address. Each\n"
        "# record is 8 bytes; bytes +5/+6 are Menu flags and TargetInfo. Copy the\n"
        "# live values so a kernel mod is not silently overwritten by this tweak.\n"
        "KERNEL_BATTLE_COMMANDS = 0x01CF3F2C\n"
        "COMBINE_COMMAND = 0x13\n"
        "COMBINE_MENU_TARGET = KERNEL_BATTLE_COMMANDS + COMBINE_COMMAND * 8 + 5\n",
        "Rinoa and Combine runtime constants",
    )

    text = replace_once(
        text,
        'SHOOT_TEXT = bytes.fromhex("57 66 6D 6D 72 00")\n'
        'SWITCH_TEXT = bytes.fromhex("57 75 67 72 61 66 00")\n'
        'SUMMON_TEXT = bytes.fromhex("57 73 6B 6B 6D 6C 00")\n',
        'SHOOT_TEXT = bytes.fromhex("57 66 6D 6D 72 00")\n'
        'SWITCH_TEXT = bytes.fromhex("57 75 67 72 61 66 00")\n'
        'SUMMON_TEXT = bytes.fromhex("57 73 6B 6B 6D 6C 00")\n'
        '# "Angelo" in FF8\'s European code page, followed by the string terminator.\n'
        'ANGELO_TEXT = bytes.fromhex("45 6C 65 63 6A 6D 00")\n',
        "Angelo label bytes",
    )

    text = replace_once(
        text,
        '    4: None,  # Rinoa: Angelo has no command-ability source record.\n',
        '    4: None,  # Rinoa: post-builder installs vanilla Combine as Angelo.\n',
        "Rinoa source comment",
    )
    text = replace_once(
        text,
        '    4: ("Rinoa", "Angelo", None),\n',
        '    4: ("Rinoa", "Angelo", COMBINE_COMMAND),\n',
        "Rinoa command audit id",
    )
    text = replace_once(
        text,
        '    # Squall and Irvine use separate guarded runtime handlers. Rinoa\'s Angelo\n'
        '    # remains unavailable. Their source slot stays empty in this vanilla-source\n'
        '    # builder, so no existing command can masquerade as the requested command.\n',
        '    # Squall and Irvine use separate guarded runtime handlers. Rinoa has no\n'
        '    # command-ability source record, so the post-builder installs the existing\n'
        '    # vanilla Combine command descriptor directly and labels it Angelo. These\n'
        '    # generic source slots remain empty so nothing can masquerade as them.\n',
        "fixed source ownership comment",
    )

    old_label = '''def _command_label_payload() -> bytes:
    """Resolve the three requested custom names without changing dispatch IDs."""
    code = _Code(COMMAND_LABEL_CAVE)
    code.add(bytes.fromhex("8B 44 24 04 3D FE 00 00 00"))
    code.branch(bytes.fromhex("0F 84"), "switch")
    code.add(bytes.fromhex("83 F8 0E"))
    code.branch(bytes.fromhex("0F 84"), "shoot")
    code.add(bytes.fromhex("83 F8 03"))
    code.branch(bytes.fromhex("0F 85"), "vanilla")
    code.add(b"\\x0F\\xB6\\x0D" + SELECTED_ACTOR.to_bytes(4, "little"))
    code.add(bytes.fromhex("83 F9 0A"))
    code.branch(bytes.fromhex("0F 87"), "vanilla")
    code.add(bytes.fromhex("69 C9 D0 01 00 00"))
    code.add(
        b"\\x80\\xB9"
        + (RUNTIME_ACTOR_BASE + CHARACTER_ID_OFFSET).to_bytes(4, "little")
        + bytes((SELPHIE,))
    )
    code.branch(bytes.fromhex("0F 85"), "vanilla")
    code.absolute(b"\\xB8", "summon")
    code.add(b"\\xC3")
    code.label("shoot")
    code.absolute(b"\\xB8", "shoot_text")
    code.add(b"\\xC3")
    code.label("switch")
    code.absolute(b"\\xB8", "switch_text")
    code.add(b"\\xC3")
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
'''
    new_label = '''def _command_label_payload() -> bytes:
    """Resolve custom fixed-menu names without changing their dispatch IDs."""
    code = _Code(COMMAND_LABEL_CAVE)
    code.add(bytes.fromhex("8B 44 24 04 3D FE 00 00 00"))
    code.branch(bytes.fromhex("0F 84"), "switch")
    code.add(bytes.fromhex("83 F8 0E"))
    code.branch(bytes.fromhex("0F 84"), "shoot")
    code.add(bytes.fromhex("83 F8 13"))
    code.branch(bytes.fromhex("0F 84"), "angelo_check")
    code.add(bytes.fromhex("83 F8 03"))
    code.branch(bytes.fromhex("0F 85"), "vanilla")
    code.add(b"\\x0F\\xB6\\x0D" + SELECTED_ACTOR.to_bytes(4, "little"))
    code.add(bytes.fromhex("83 F9 0A"))
    code.branch(bytes.fromhex("0F 87"), "vanilla")
    code.add(bytes.fromhex("69 C9 D0 01 00 00"))
    code.add(
        b"\\x80\\xB9"
        + (RUNTIME_ACTOR_BASE + CHARACTER_ID_OFFSET).to_bytes(4, "little")
        + bytes((SELPHIE,))
    )
    code.branch(bytes.fromhex("0F 85"), "vanilla")
    code.absolute(b"\\xB8", "summon")
    code.add(b"\\xC3")
    code.label("angelo_check")
    code.add(b"\\x0F\\xB6\\x0D" + SELECTED_ACTOR.to_bytes(4, "little"))
    code.add(bytes.fromhex("83 F9 0A"))
    code.branch(bytes.fromhex("0F 87"), "vanilla")
    code.add(bytes.fromhex("69 C9 D0 01 00 00"))
    code.add(
        b"\\x80\\xB9"
        + (RUNTIME_ACTOR_BASE + CHARACTER_ID_OFFSET).to_bytes(4, "little")
        + bytes((RINOA,))
    )
    code.branch(bytes.fromhex("0F 85"), "vanilla")
    code.absolute(b"\\xB8", "angelo")
    code.add(b"\\xC3")
    code.label("shoot")
    code.absolute(b"\\xB8", "shoot_text")
    code.add(b"\\xC3")
    code.label("switch")
    code.absolute(b"\\xB8", "switch_text")
    code.add(b"\\xC3")
    code.label("vanilla")
    code.add(COMMAND_LABEL_ORIGINAL)
    code.add(_near(COMMAND_LABEL_CAVE + len(code.data),
                   COMMAND_LABEL_HOOK + len(COMMAND_LABEL_ORIGINAL)))
    code.label("summon")
    code.add(SUMMON_TEXT)
    code.label("angelo")
    code.add(ANGELO_TEXT)
    code.label("shoot_text")
    code.add(SHOOT_TEXT)
    code.label("switch_text")
    code.add(SWITCH_TEXT)
    return code.finish()
'''
    text = replace_once(text, old_label, new_label, "command label resolver")

    old_post = '''def _post_builder_payload() -> bytes:
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
    code.add(b"\\x80\\xBE" + CHARACTER_ID_OFFSET.to_bytes(4, "little") + b"\\x02")
    code.branch(bytes.fromhex("0F 85"), "done")
    code.add(bytes.fromhex("C7 46 26 0E 84 40 00"))
    code.add(b"\\x80\\x3D" + shoot_issue_54.SHOOT_LOCK.to_bytes(4, "little") + b"\\x00")
    code.branch(bytes.fromhex("0F 84"), "done")
    code.add(bytes.fromhex("80 4E 29 02"))
    code.label("done")
    code.add(_near(POST_BUILDER_CAVE + len(code.data), POST_BUILDER_HOOK + 6))
    return code.finish()
'''
    new_post = '''def _post_builder_payload() -> bytes:
    """Finish Tonberry alternate, Rinoa Angelo, and the custom Irvine slot."""
    from . import shoot_issue_54

    code = _Code(POST_BUILDER_CAVE)
    code.add(POST_BUILDER_ORIGINAL)
    # Controller initialization at 0x4BBC38 points its alternate pointer to
    # actor+0x2E, the hidden fifth runtime descriptor. Flag 0x04 on the visible
    # GF slot makes the renderer draw the arrow and 0x4BC770 select that pointer.
    code.add(bytes.fromhex("80 7E 2A 21"))  # visible GF command is LV Down
    code.branch(bytes.fromhex("0F 85"), "rinoa")
    code.add(bytes.fromhex("80 7E 2E 22"))  # hidden alternate is LV Up
    code.branch(bytes.fromhex("0F 85"), "rinoa")
    code.add(bytes.fromhex("80 4E 2D 04"))
    code.label("rinoa")
    code.add(b"\\x80\\xBE" + CHARACTER_ID_OFFSET.to_bytes(4, "little") + bytes((RINOA,)))
    code.branch(bytes.fromhex("0F 85"), "irvine")
    # Runtime descriptor = command id, Menu flags, TargetInfo, disabled flags.
    # Command 0x13 is vanilla Combine; copy its live Menu+Target word rather
    # than hard-coding kernel metadata. BattleMenu_ExecuteSelectedCommand then
    # opens submenu type 8 (the native Angelo/Combine list), which owns learned
    # Angelo-move filtering and target selection.
    code.add(bytes.fromhex("C6 46 26 13 50 66 A1") + COMBINE_MENU_TARGET.to_bytes(4, "little"))
    code.add(bytes.fromhex("66 89 46 27 58 C6 46 29 00"))
    code.branch(b"\\xE9", "done")
    code.label("irvine")
    code.add(b"\\x80\\xBE" + CHARACTER_ID_OFFSET.to_bytes(4, "little") + b"\\x02")
    code.branch(bytes.fromhex("0F 85"), "done")
    code.add(bytes.fromhex("C7 46 26 0E 84 40 00"))
    code.add(b"\\x80\\x3D" + shoot_issue_54.SHOOT_LOCK.to_bytes(4, "little") + b"\\x00")
    code.branch(bytes.fromhex("0F 84"), "done")
    code.add(bytes.fromhex("80 4E 29 02"))
    code.label("done")
    code.add(_near(POST_BUILDER_CAVE + len(code.data), POST_BUILDER_HOOK + 6))
    return code.finish()
'''
    text = replace_once(text, old_post, new_post, "post-builder Angelo descriptor")

    text = replace_once(
        text,
        '        "Rinoa": ("blank", "Angelo is explicitly TBD"),\n',
        '        "Rinoa": ("Angelo", "verified vanilla Combine submenu/dispatcher"),\n',
        "Rinoa supported audit",
    )
    text = replace_once(
        text,
        '    """Emit the single owner for Tonberry alternate and Irvine Shoot slots."""\n',
        '    """Emit the single owner for Tonberry alternate, Rinoa Angelo, and Irvine Shoot."""\n',
        "post-builder component docstring",
    )
    text = replace_once(
        text,
        '        "# Fixed command post-builder: Tonberry alternate and Irvine Shoot.",\n',
        '        "# Fixed command post-builder: Tonberry alternate, Rinoa Angelo, and Irvine Shoot.",\n',
        "post-builder Hext comment",
    )
    text = replace_once(
        text,
        '    """Emit the verified builder, Switch, and repaired Shoot components."""\n',
        '    """Emit the verified builder, Angelo, Switch, and repaired Shoot components."""\n',
        "supported components docstring",
    )

    path.write_text(text, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    patch_fixed_command_menu()
    print("Integrated Rinoa Angelo through vanilla Combine")
