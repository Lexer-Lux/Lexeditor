"""Read-only browser for Dark Souls Remastered menu and dialogue scripts.

The game's menus and NPC dialogue run as ESD state machines (see esd.py):
menu/ingame.menuesdbnd.dcx and menu/common.menuesdbnd.dcx hold the menu
scripts, and script/talk/*.talkesdbnd.dcx holds one archive per conversation.
Each archive is DCX-compressed BND3 holding .esd members. The Scripts tab
lists every state in those archives and shows one state's commands and
conditions as plain data; the client renders the text.
"""

from __future__ import annotations

from pathlib import Path

from . import esd, formats
from .formats import FormatError

MENU_ARCHIVES = {"ingame": Path("menu/ingame.menuesdbnd.dcx"),
                 "common": Path("menu/common.menuesdbnd.dcx")}
TALK_DIR = Path("script/talk")
TALK_SUFFIX = ".talkesdbnd.dcx"
SCOPES = ("ingame", "common", "talk")

# Parsed archives per game root, so reopening the tab does not reparse.
# An archive maps member name to its Esd, or None when the archive holds
# no scripts (m14_02_00_00 ships empty and members() refuses it).
_CACHE: dict[str, dict[str, dict[str, "esd.Esd | None"]]] = {}


class ScriptError(ValueError):
    """A script listing cannot be shown; nothing is changed."""


def _game_root(root) -> Path:
    if root is None:
        raise ScriptError("Select the installed game before browsing its scripts")
    return Path(root)


def _talk_id(filename: str) -> str:
    """A talk archive's short id: t01-00_00_00.talkesdbnd.dcx -> t01-00_00_00."""
    if filename.endswith(TALK_SUFFIX):
        return filename[:-len(TALK_SUFFIX)]
    return filename


def _read_archive(path: Path) -> dict[str, "esd.Esd | None"]:
    """Every script in one archive, keyed by member name."""
    try:
        plain = formats.inflate(path.read_bytes())
    except (FormatError, OSError):
        return {}
    try:
        entries = formats.members(plain)
    except FormatError:
        return {}
    scripts = {}
    for name, member in entries.items():
        try:
            scripts[name] = esd.parse(bytes(plain[member.offset:member.offset + member.size]))
        except FormatError:
            continue
    return scripts


def _archives(root) -> dict[str, dict[str, "esd.Esd | None"]]:
    """All script archives under one game root, parsed once and cached."""
    game_root = _game_root(root)
    key = str(game_root)
    cached = _CACHE.get(key)
    if cached is None:
        cached = {}
        for archive, relative in MENU_ARCHIVES.items():
            path = game_root / relative
            cached[archive] = _read_archive(path) if path.is_file() else {}
        talk: dict[str, "esd.Esd | None"] = {}
        folder = game_root / TALK_DIR
        if folder.is_dir():
            for path in sorted(folder.glob("*" + TALK_SUFFIX)):
                talk[_talk_id(path.name)] = _read_archive(path)
        cached["talk"] = talk
        _CACHE[key] = cached
    return cached


def list_rows(root, scope: str) -> list[dict]:
    """One row per state: archive, script, group and state id."""
    if scope not in SCOPES:
        raise ScriptError(f"Unknown script scope {scope!r}")
    archives = _archives(root)
    rows = []
    if scope in MENU_ARCHIVES:
        members = archives[scope]
        for name in sorted(members):
            parsed = members[name]
            if parsed is None:
                continue
            for group in sorted(parsed.state_groups):
                for state in sorted(parsed.state_groups[group]):
                    rows.append({"table": "ScriptState",
                                 "id": f"{scope}/{name}/{group}/{state}",
                                 "name": f"{name} · state {state}",
                                 "values": {"archive": scope, "script": name,
                                            "group": group, "state": state}})
    else:
        for archive in sorted(archives["talk"]):
            for name in sorted(archives["talk"][archive]):
                parsed = archives["talk"][archive][name]
                if parsed is None:
                    continue
                for group in sorted(parsed.state_groups):
                    for state in sorted(parsed.state_groups[group]):
                        rows.append({"table": "ScriptState",
                                     "id": f"talk/{archive}/{name}/{group}/{state}",
                                     "name": f"{name} · state {state}",
                                     "values": {"archive": archive, "script": name,
                                                "group": group, "state": state}})
    return rows


def _text(data: bytes) -> str:
    try:
        return esd.disassemble(data)
    except FormatError:
        return "<unreadable expression %s>" % bytes(data).hex()


def _command(command: "esd.Command") -> dict:
    return {"bank": command.bank, "id": command.id,
            "args": [_text(arg) for arg in command.args]}


def _condition(condition: "esd.Condition") -> dict:
    return {"evaluator": _text(condition.evaluator),
            "target": condition.target_state,
            "pass": [_command(item) for item in condition.pass_commands],
            "sub": [_condition(item) for item in condition.subconditions]}


def read_state(root, state_id: str) -> dict:
    """One state's command lists and condition tree as plain data."""
    parts = state_id.split("/")
    if len(parts) == 4:
        scope, member, group, state = parts
        archives = _archives(root)
        archive = scope
        if scope in MENU_ARCHIVES:
            parsed = archives[scope].get(member)
        else:
            parsed = None
    elif len(parts) == 5:
        scope, archive, member, group, state = parts
        if scope != "talk":
            raise ScriptError(f"Unknown script {state_id!r}")
        archives = _archives(root)
        parsed = archives["talk"].get(archive, {}).get(member)
    else:
        raise ScriptError(f"Unknown script {state_id!r}")
    try:
        node = parsed.state_groups[int(group)][int(state)] if parsed is not None else None
    except (KeyError, TypeError, ValueError):
        node = None
    if node is None:
        raise ScriptError(f"Unknown script {state_id!r}")
    return {"archive": archive, "script": member,
            "group": int(group), "state": int(state),
            "entry": [_command(item) for item in node.entry_commands],
            "exit": [_command(item) for item in node.exit_commands],
            "while": [_command(item) for item in node.while_commands],
            "conditions": [_condition(item) for item in node.conditions]}


def clear_cache() -> None:
    """Forget parsed archives; tests use this to isolate game roots."""
    _CACHE.clear()
