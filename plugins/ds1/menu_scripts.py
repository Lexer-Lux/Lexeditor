"""DS1 menu scripts (ESD): let tweak mods add commands to menu state machines.

Dark Souls Remastered draws its menus from scripts in menu/ingame.menuesdbnd.dcx
and menu/common.menuesdbnd.dcx: DCX-compressed BND3 archives of `.esd` members
(see esd.py for the file layout). Each state machine is states with entry, exit
and while commands plus conditions, each with pass commands and optional
subconditions at any depth.

A tweak mod asks for commands after an existing one: `after` names a command
(bank, id and its exact disassembled args, as esd.disassemble renders them) and
the new `commands` are inserted right after it, in the same command list
(whichever list it is in: entry, exit, while, or a condition's pass commands at
any depth). Exactly one command in the named script must match `after`, since
an anchor that matches nothing, or more than one command, does not say where
the new commands go. Later specs can anchor on commands an earlier mod added:
every spec's changes for an archive apply in order to the same scripts.

Composing with no applicable changes returns the original bytes unchanged; a
changed archive keeps every untouched member byte-identical and is recompressed
with the same DCX framing as the original.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from . import esd, formats

RELATIVE = {"ingame": Path("menu/ingame.menuesdbnd.dcx"),
            "common": Path("menu/common.menuesdbnd.dcx")}
# The Steam Remastered build that exe_patches supports; measured from the install.
VANILLA = {
    "ingame": (47685, "94ff410319d06daf08e79d4266364a59c44dcaa953cd0c920774195b6e33782c"),
    "common": (14660, "dbe152641af2142a9e27d7615e06ec041d211d7b8583e0bbad5df2da9accfb44"),
}
MAX_CHANGES = 64
MAX_COMMANDS = 64


class ScriptError(ValueError):
    """A menu script patch is not acceptable; nothing changed."""

    def __init__(self, message: str, *, folders=()):
        self.folders = tuple(folders)
        super().__init__(message)


def _check_command(value: object, owner: str, what: str) -> dict:
    """One validated command: bank, id and assembled args, with text kept."""
    if (not isinstance(value, dict) or set(value) != {"bank", "id", "args"}
            or type(value["bank"]) is not int or value["bank"] not in (1, 5, 6, 7)
            or type(value["id"]) is not int or not 0 <= value["id"] <= 0x7FFFFFFF
            or not isinstance(value.get("args"), list)):
        raise ScriptError(f"{owner}: {what} names bank (1, 5, 6 or 7), id and args")
    texts = value["args"]
    if any(type(arg) is not str for arg in texts):
        raise ScriptError(f"{owner}: {what} args are esd.disassemble text")
    try:
        arg_bytes = [esd.assemble(arg) for arg in texts]
    except ValueError as error:
        raise ScriptError(f"{owner}: {what} has an arg the scripts cannot use: {error}") from error
    return {"bank": value["bank"], "id": value["id"], "args": list(texts), "arg_bytes": arg_bytes}


def validate(spec: object, owner: str) -> dict:
    """A tweak's esd/<id>.json: {"version": 1, "changes": [...]}."""
    if not isinstance(spec, dict) or spec.get("version") != 1 or set(spec) != {"version", "changes"}:
        raise ScriptError(f"{owner}: a script patch needs version 1 with changes")
    changes = spec.get("changes")
    if not isinstance(changes, list) or not 1 <= len(changes) <= MAX_CHANGES:
        raise ScriptError(f"{owner}: list between 1 and {MAX_CHANGES} script changes")
    clean = []
    for change in changes:
        if not isinstance(change, dict) or set(change) != {"archive", "script", "after", "commands"}:
            raise ScriptError(f"{owner}: a script change names archive, script, after and commands")
        if change["archive"] not in RELATIVE:
            raise ScriptError(f"{owner}: archive is ingame or common, not {change['archive']!r}")
        if not isinstance(change["script"], str) or not change["script"]:
            raise ScriptError(f"{owner}: a script change names its .esd member")
        after = _check_command(change["after"], owner, "after")
        commands = change["commands"]
        if not isinstance(commands, list) or not 1 <= len(commands) <= MAX_COMMANDS:
            raise ScriptError(f"{owner}: list between 1 and {MAX_COMMANDS} new commands")
        clean.append({"archive": change["archive"], "script": change["script"], "after": after,
                      "commands": [_check_command(command, owner, "a new command")
                                   for command in commands]})
    return {"owner": owner, "changes": clean}


def _lists(script: esd.Esd):
    """Every command list in a script, including pass commands at any depth."""
    for states in script.state_groups.values():
        for state in states.values():
            yield state.entry_commands
            yield state.exit_commands
            yield state.while_commands
            stack = list(state.conditions)
            while stack:
                condition = stack.pop()
                yield condition.pass_commands
                stack.extend(condition.subconditions)


def _insert(parsed: esd.Esd, change: dict, owner: str) -> None:
    """Insert one change's commands after its anchor, wherever that list is."""
    after = change["after"]
    found = []
    for commands in _lists(parsed):
        for index, command in enumerate(commands):
            if command.bank != after["bank"] or command.id != after["id"]:
                continue
            try:
                texts = [esd.disassemble(arg) for arg in command.args]
            except ValueError:
                continue
            if texts == after["args"]:
                found.append((commands, index))
    if len(found) != 1:
        detail = "no command" if not found else f"{len(found)} commands"
        raise ScriptError(f"{owner}: {change['script']} has {detail} matching "
                          f"{after['bank']}:{after['id']} {after['args']!r}")
    commands, index = found[0]
    new = [esd.Command(item["bank"], item["id"], list(item["arg_bytes"])) for item in change["commands"]]
    commands[index + 1:index + 1] = new


def compose(original_dcx: bytes, specs: list[dict], archive: str) -> bytes:
    """Every spec's changes for one archive applied in order to its scripts."""
    if archive not in RELATIVE:
        raise ScriptError(f"unknown menu script archive {archive!r}")
    wanted = [(spec["owner"], spec.get("folder"), change) for spec in specs for change in spec["changes"]
              if change["archive"] == archive]
    if not wanted:
        return original_dcx
    plain = formats.inflate(original_dcx)
    table = formats.members(plain)
    parsed: dict[str, esd.Esd] = {}
    owners: dict[str, list[str]] = {}
    for owner, folder, change in wanted:
        name = change["script"]
        if name not in table:
            raise ScriptError(f"{owner}: {archive} has no script {name}", folders=[folder] if folder else [])
        if name not in parsed:
            try:
                parsed[name] = esd.parse(bytes(plain[table[name].offset:table[name].offset + table[name].size]))
            except ValueError as error:
                raise ScriptError(f"{owner}: {name} is not a script the game can run: {error}",
                                  folders=[folder] if folder else []) from error
        owners.setdefault(name, []).append(owner)
        try:
            _insert(parsed[name], change, owner)
        except ScriptError as error:
            raise ScriptError(str(error), folders=[folder] if folder else []) from error
    items = {name: bytes(plain[entry.offset:entry.offset + entry.size]) for name, entry in table.items()}
    for name, script in parsed.items():
        try:
            items[name] = script.to_bytes()
        except ValueError as error:
            raise ScriptError(f"{', '.join(owners[name])}: {name} no longer builds: {error}") from error
    return formats.deflate(original_dcx, formats.pack(plain, items))


def is_vanilla(data: bytes, archive: str) -> bool:
    """Whether data is the shipped archive, by size and SHA-256."""
    try:
        size, digest = VANILLA[archive]
    except KeyError:
        raise ScriptError(f"unknown menu script archive {archive!r}") from None
    return len(data) == size and hashlib.sha256(data).hexdigest() == digest
