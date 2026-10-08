"""The DS1 mod loader: every enabled mod, combined over the game's own files.

Dark Souls Remastered reads two loose files a data mod changes: the parameter
archive and the English item-name archive. Copying one mod's whole archive
over the game's would keep only the last mod applied, so Apply instead
starts from the game's own (vanilla) files and lays each enabled mod's
changes on top, lowest load order first.

Parameters are merged by field. A mod's changes are the fields of its rows
that differ from vanilla (a bitfield is its own bits, not the whole byte);
two mods only conflict when they set the same field of the same row to
different values. A table whose layout Lexeditor does not know is merged by
whole row instead. Item names are merged by entry the same way. Anything else a mod changes in an archive member
(rows added or removed, a table's layout, a text table that is not a name
table) cannot be merged, so that member is taken whole from the last mod in
load order, and every mod that changed it is told what was dropped.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import struct
import zlib

from plugins.ds3.formats import DS3FormatError, ParamView

from . import texts
from .formats import FormatError, MAX_ARCHIVE, TABLES, deflate, inflate, schema
from .store import MARKER, RELATIVE

FILES = (RELATIVE, texts.RELATIVE)
TABLE_NAMES = {"EquipParamGoods": "Items", "EquipParamWeapon": "Weapons",
               "EquipParamProtector": "Armor", "EquipParamAccessory": "Rings", "Magic": "Spells",
               "NpcParam": "Enemies", "AtkParam_Npc": "Attacks", "SpEffectParam": "Effects",
               "BehaviorParam": "Behaviors", "Bullet": "Projectiles"}


@dataclass
class Mod:
    """One data mod in load order: its name, folder and the files it holds."""
    name: str
    folder: Path
    files: dict[Path, bytes]


@dataclass
class Conflict:
    """One part two or more mods change in ways that cannot be combined."""
    file: Path
    part: str
    mods: list[str] = field(default_factory=list)

    @property
    def winner(self) -> str:
        return self.mods[-1]

    def add(self, name: str) -> None:
        if name in self.mods:
            self.mods.remove(name)
        self.mods.append(name)


@dataclass
class Composition:
    files: dict[Path, bytes]
    conflicts: list[Conflict]

    def by_mod(self, mods: list[Mod]) -> dict[str, list[str]]:
        """Each mod's conflicts, said from that mod's side, keyed by its folder."""
        from core.mod_conflicts import lines_by_mod
        return lines_by_mod([(conflict.part, conflict.mods) for conflict in self.conflicts],
                            {mod.name: str(mod.folder) for mod in mods})


def read_mod(folder: Path, name: str) -> Mod | None:
    """A DS1 data mod's saved files, or None for a folder that is not one."""
    from .tweak_mods import checked
    folder = checked(Path(folder))
    if not (folder / MARKER).is_file():
        return None
    files = {}
    for relative in FILES:
        path = checked(folder / relative)
        if not path.is_file():
            continue
        if path.stat().st_size > MAX_ARCHIVE:
            raise ValueError(f"{name}: {path.name} is too large")
        files[relative] = path.read_bytes()
    return Mod(name, folder, files)


def active_mods(library_root: Path, project_root: Path | None = None) -> list[Mod]:
    """The data mods to combine, in the Mods tab's load order.

    Every enabled mod in the library, and the open project too: applying a
    mod is asking for it, whether or not its switch was on. A tweak mod (a
    script mod with no saved parameters) is not a data mod and is skipped.
    """
    from core import mods_service
    mods, seen = [], set()
    for row in mods_service.library_rows(Path(library_root)):
        folder = Path(row["path"]).resolve()
        if not row["enabled"] and folder != (Path(project_root).resolve() if project_root else None):
            continue
        mod = read_mod(folder, row["name"])
        if mod is not None:
            mods.append(mod)
            seen.add(folder)
    if project_root is not None and Path(project_root).resolve() not in seen:
        mod = read_mod(Path(project_root), Path(project_root).name)
        if mod is not None:
            mods.append(mod)
    return mods


def vanilla_files(game_root: Path) -> dict[Path, bytes]:
    """The game's own bytes of each file mods change: the preserved originals
    once Lexeditor has applied, else the installed files."""
    from . import deployment
    from .tweak_mods import checked
    result = {}
    for relative in FILES:
        path = checked(deployment.vanilla_source(Path(game_root), relative))
        if path.is_file():
            if path.stat().st_size > MAX_ARCHIVE:
                raise ValueError(f"The game's {relative.name} is too large")
            result[relative] = path.read_bytes()
    return result


def build(game_root: Path, library_root: Path, project_root: Path | None = None) -> tuple[Composition, list[Mod]]:
    mods = active_mods(library_root, project_root)
    return compose(vanilla_files(game_root), mods), mods


def compose(vanilla: dict[Path, bytes], mods: list[Mod]) -> Composition:
    """The files every mod together changes, and what could not be combined.

    `vanilla` holds the game's own bytes of each file; `mods` is load order,
    lowest first. Only files that end up different from vanilla are returned.
    """
    files, conflicts = {}, []
    if RELATIVE in vanilla:
        result = _compose_params(vanilla[RELATIVE], [(mod.name, mod.files[RELATIVE])
                                                     for mod in mods if RELATIVE in mod.files])
        conflicts += result[1]
        if result[0] != vanilla[RELATIVE]:
            files[RELATIVE] = result[0]
    if texts.RELATIVE in vanilla:
        result = _compose_texts(vanilla[texts.RELATIVE], [(mod.name, mod.files[texts.RELATIVE])
                                                          for mod in mods if texts.RELATIVE in mod.files])
        conflicts += result[1]
        if result[0] != vanilla[texts.RELATIVE]:
            files[texts.RELATIVE] = result[0]
    return Composition(files, conflicts)


# --- Parameters ------------------------------------------------------------

def _row_spans(payload: bytes) -> list[tuple[int, int, int]] | None:
    """(start, end, row id) of every row's data in a PARAM, or None if unreadable."""
    try:
        param = ParamView(payload)
    except (DS3FormatError, UnicodeDecodeError, struct.error):
        return None
    size = param.detected_row_size
    if size is None and len(param.rows) == 1:
        size = param.strings_offset - param.rows[0].data_offset
    if not size or size <= 0:
        return None
    spans = sorted((row.data_offset, row.data_offset + size, row.row_id) for row in param.rows)
    if any(end > len(payload) for _start, end, _row in spans):
        return None
    return spans


WIDTHS = {"u8": 1, "s8": 1, "dummy8": 1, "u16": 2, "s16": 2, "f64": 8}


class _Units:
    """The pieces a table's row is merged by: its fields, else the whole row.

    A unit is (offset, width, mask, label): the bytes it spans, which of their
    bits it owns (all of them, or a bitfield's), and its name for conflicts.
    Bytes no field describes are a unit each, so nothing is left unmerged.
    """

    def __init__(self):
        self._tables: dict[tuple[str, int], list] = {}

    def of(self, member: str, row_size: int) -> list[tuple[int, int, int, str]]:
        table = member.removesuffix(".param")
        key = (table, row_size)
        if key not in self._tables:
            self._tables[key] = self._build(table, row_size)
        return self._tables[key]

    @staticmethod
    def _build(table: str, row_size: int) -> list[tuple[int, int, int, str]]:
        whole = [(0, row_size, (1 << (8 * row_size)) - 1, "whole row")]
        if table not in TABLES or TABLES[table][0] != row_size:
            return whole
        try:
            specs = [item["spec"] for item in schema(table)["fields"]]
        except (FormatError, OSError, ValueError):
            return whole
        units, covered = [], bytearray(row_size)
        for spec in specs:
            width = WIDTHS.get(spec.dtype, 4)
            if spec.bit_size is not None:
                mask = ((1 << spec.bit_size) - 1) << spec.bit_offset
            else:
                width *= spec.array_length
                mask = (1 << (8 * width)) - 1
            if spec.offset + width > row_size:
                return whole
            units.append((spec.offset, width, mask, spec.label or spec.key))
            covered[spec.offset:spec.offset + width] = b"\1" * width
        for index, used in enumerate(covered):
            if not used:
                units.append((index, 1, 0xFF, f"byte {index}"))
        return units


def _compose_params(vanilla: bytes, mods: list[tuple[str, bytes]]) -> tuple[bytes, list[Conflict]]:
    base = inflate(vanilla)
    entries = texts.bnd3_entries(base)
    names = [entry.name.replace("\\", "/").rsplit("/", 1)[-1] for entry in entries]
    plains = []
    for name, data in mods:
        try:
            plain = inflate(data)
            mod_entries = texts.bnd3_entries(plain)
        except FormatError as error:
            raise ValueError(f"{name}: its parameter archive cannot be read ({error})") from error
        plains.append((name, {entry.name.replace("\\", "/").rsplit("/", 1)[-1]: entry.data for entry in mod_entries}))
    units = _Units()
    conflicts: list[Conflict] = []
    output = []
    for entry, member in zip(entries, names):
        data, member_conflicts = _merge_member(member, entry.data,
                                               [(name, members.get(member)) for name, members in plains], units)
        conflicts += member_conflicts
        output.append(texts.Entry(entry.member_id, entry.name, entry.flags, data))
    if all(new.data == old.data for new, old in zip(output, entries)):
        return vanilla, conflicts
    if all(len(new.data) == len(old.data) for new, old in zip(output, entries)):
        # Same sizes: write each member back in place, keeping the shipped layout.
        plain = bytearray(base)
        for new, (_flags, _size, offset) in zip(output, _directory(base)):
            plain[offset:offset + len(new.data)] = new.data
        return deflate(vanilla, bytes(plain)), conflicts
    return deflate(vanilla, texts.build_bnd3(base, output)), conflicts


def _directory(plain: bytes) -> list[tuple[int, int, int]]:
    count, = struct.unpack_from("<I", plain, 16)
    return [struct.unpack_from("<3I", plain, 32 + index * 24) for index in range(count)]


def _merge_member(member: str, vanilla: bytes, mods: list[tuple[str, bytes | None]],
                  units: _Units) -> tuple[bytes, list[Conflict]]:
    """One PARAM: every mod's changed fields on top of vanilla, or the last whole one."""
    spans = _row_spans(vanilla)
    merged = bytearray(vanilla)
    owners: dict[tuple[int, int, int], str] = {}  # (row start, unit offset, mask) -> mod
    conflicts: dict[tuple, Conflict] = {}
    whole: list[tuple[str, bytes]] = []  # mods whose change cannot be merged by field
    touched: list[str] = []
    table = TABLE_NAMES.get(member.removesuffix(".param"), member.removesuffix(".param"))
    for name, data in mods:
        if data is None or data == vanilla:
            continue
        touched.append(name)
        if spans is None or len(data) != len(vanilla) or not _rows_only(vanilla, data, spans):
            whole.append((name, data))
            continue
        for start, end, row_id in spans:
            if data[start:end] == vanilla[start:end]:
                continue
            for offset, width, mask, label in units.of(member, end - start):
                at = start + offset
                theirs = int.from_bytes(data[at:at + width], "little") & mask
                if theirs == int.from_bytes(vanilla[at:at + width], "little") & mask:
                    continue
                current = int.from_bytes(merged[at:at + width], "little")
                key = (start, offset, mask)
                if key in owners and owners[key] != name and current & mask != theirs:
                    part = f"{table} {row_id}, {label}"
                    conflict = conflicts.setdefault((row_id, offset, mask), Conflict(RELATIVE, part))
                    conflict.add(owners[key])
                    conflict.add(name)
                merged[at:at + width] = ((current & ~mask) | theirs).to_bytes(width, "little")
                owners[key] = name
    if whole:
        # A whole-member change is kept only if it loads last; no other change
        # to this member, before or after it, can be kept beside it.
        winner = touched[-1]
        conflict = Conflict(RELATIVE, f"{table} (whole table)")
        for name in touched:
            conflict.add(name)
        result = next((data for name, data in whole if name == winner), bytes(merged))
        return result, [conflict] if len(touched) > 1 else []
    return bytes(merged), list(conflicts.values())


def _rows_only(vanilla: bytes, data: bytes, spans: list[tuple[int, int, int]]) -> bool:
    """True when every byte outside the row data is unchanged."""
    cursor = 0
    for start, end, _row in spans:
        if data[cursor:start] != vanilla[cursor:start]:
            return False
        cursor = max(cursor, end)
    return data[cursor:] == vanilla[cursor:]


# --- Item names --------------------------------------------------------------

def _compose_texts(vanilla: bytes, mods: list[tuple[str, bytes]]) -> tuple[bytes, list[Conflict]]:
    base = texts.TextDocument(vanilla)
    merged = {position: dict(table[1]) for position, table in base.tables.items()}
    owners: dict[tuple[str, int], str] = {}
    conflicts: dict[tuple[str, int], Conflict] = {}
    whole: dict[int, list[tuple[str, bytes]]] = {}
    touched, foreign = [], []  # a foreign archive (other members) is taken whole
    for name, data in mods:
        if data == vanilla:
            continue
        touched.append(name)
        try:
            document = texts.TextDocument(data)
        except FormatError as error:
            raise ValueError(f"{name}: its item-name archive cannot be read ({error})") from error
        if [(entry.member_id, entry.name) for entry in document.entries] != \
                [(entry.member_id, entry.name) for entry in base.entries]:
            foreign.append((name, data))
            continue
        for position, entry in enumerate(document.entries):
            if position in base.tables:
                file = base._file(position)
                before, after = base.original_texts[position], document.tables[position][1]
                for item in set(before) | set(after):
                    if after.get(item) == before.get(item):
                        continue
                    key = (file, item)
                    if key in owners and owners[key] != name and merged[position].get(item) != after.get(item):
                        conflict = conflicts.setdefault(key, Conflict(texts.RELATIVE, f"Name {item} ({file.removesuffix('_.fmg').replace('_', ' ')})"))
                        conflict.add(owners[key])
                        conflict.add(name)
                    merged[position][item] = after.get(item)
                    owners[key] = name
            elif entry.data != base.entries[position].data:
                whole.setdefault(position, []).append((name, entry.data))
    entries = list(base.entries)
    changed = False
    for position, (groups, original) in base.tables.items():
        if merged[position] != base.original_texts[position]:
            old = entries[position]
            entries[position] = texts.Entry(old.member_id, old.name, old.flags,
                                            texts.build_fmg(old.data, groups, merged[position]))
            changed = True
    result = list(conflicts.values())
    if foreign:
        # Only the whole archive can be used: the last mod's, if it is one of these.
        conflict = Conflict(texts.RELATIVE, "Item text archive (whole file)")
        for name in touched:
            conflict.add(name)
        if touched[-1] == foreign[-1][0]:
            return foreign[-1][1], [conflict] if len(touched) > 1 else []
        result.append(conflict)
    for position, changes in whole.items():
        old = entries[position]
        entries[position] = texts.Entry(old.member_id, old.name, old.flags, changes[-1][1])
        changed = True
        if len(changes) > 1:
            conflict = Conflict(texts.RELATIVE, f"{base._file(position)} (whole text table)")
            for name, _data in changes:
                conflict.add(name)
            result.append(conflict)
    if not changed:
        return vanilla, result
    plain = texts.build_bnd3(base.plain, entries)
    compressed = zlib.compress(plain, 9)
    header = bytearray(vanilla[:76])
    struct.pack_into(">II", header, 28, len(plain), len(compressed))
    return bytes(header) + compressed, result
