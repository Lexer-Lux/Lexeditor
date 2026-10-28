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
whole row instead. Rows a mod adds are added and rows it removes are
removed, by row id, so two mods that each add rows to one table (Armor
Rework's and Repair Rework's effects) both keep theirs; they conflict only
when they add the same id differently, or one removes a row another changes.
Item names are merged by entry the same way. Anything else a mod changes in
an archive member (a table's layout or header, a text table that is not a
name table) cannot be merged, so that member is taken whole from the last
mod in load order, and every mod that changed it is told what was dropped.

Map files are merged by placement field: two mods moving different
enemies, or one moving an enemy while another swaps which enemy it is,
both apply. Two mods setting the same field of one placement conflict.
A map a mod restructures (added or removed parts, or any byte outside
the placement fields) is taken whole from the last mod instead.

Character binders are merged by member: two mods changing different
animation files in one binder both apply. Two mods changing the same
member conflict. A resized member rebuilds the binder; a binder a mod
restructures (added or removed members) is taken whole from the last
mod instead.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
import struct
import zlib

from plugins.ds3.formats import DS3FormatError, ParamView

from . import texts
from .formats import FormatError, MAX_ARCHIVE, TABLES, deflate, inflate, members, pack, schema
from .msb import MAP_DIR, MAX_FILE as MAX_MAP, MsbDocument, MsbError
from .store import MARKER, RELATIVE
from .tae_store import CHR_DIR, MAX_BINDER

FILES = (RELATIVE, texts.RELATIVE, texts.MENU_RELATIVE)
MAX_MAP_FILES = 64
MAX_ANIBND_FILES = 64
TABLE_NAMES = {"EquipParamGoods": "Items", "EquipParamWeapon": "Weapons",
               "EquipParamProtector": "Armor", "EquipParamAccessory": "Rings", "Magic": "Spells",
               "NpcParam": "Enemies", "AtkParam_Npc": "Attacks", "AtkParam_Pc": "Player attacks",
               "ReinforceParamWeapon": "Weapon upgrades", "ReinforceParamProtector": "Armor upgrades",
               "EquipMtrlSetParam": "Upgrade materials", "CharaInitParam": "Starting classes",
               "ItemLotParam": "Drops", "ShopLineupParam": "Shops", "ObjActParam": "Treasure",
               "BehaviorParam": "Behaviors", "BehaviorParam_PC": "Player behaviors",
               "NpcThinkParam": "AI",
               "SpEffectParam": "Effects", "Bullet": "Projectiles"}


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


def content_files(folder: Path, name: str) -> list[tuple[Path, Path]]:
    """(key, disk path) of every file read_mod would read, without reading.

    The conflict cache stamps these instead of hashing their bytes, so an
    unchanged library costs stats, not reads. Same enumeration, same limits.
    """
    from .tweak_mods import checked
    from . import assets
    folder = checked(Path(folder))
    found = []
    for relative in FILES:
        path = checked(folder / relative)
        if not path.is_file():
            continue
        if path.stat().st_size > MAX_ARCHIVE:
            raise ValueError(f"{name}: {path.name} is too large")
        found.append((relative, path))
    maps = checked(folder / MAP_DIR)
    if maps.is_dir():
        candidates = sorted(maps.glob("*.msb"))
        if len(candidates) > MAX_MAP_FILES:
            raise ValueError(f"{name}: too many map files")
        for path in candidates:
            checked(path)
            if path.stat().st_size > MAX_MAP:
                raise ValueError(f"{name}: {path.name} is too large")
            found.append((MAP_DIR / path.name.casefold(), path))
    chars = checked(folder / CHR_DIR)
    if chars.is_dir():
        candidates = sorted(path for path in chars.glob("*.dcx")
                            if assets.is_character_file(CHR_DIR / path.name))
        if len(candidates) > MAX_ANIBND_FILES:
            raise ValueError(f"{name}: too many character files")
        for path in candidates:
            checked(path)
            if path.stat().st_size > MAX_BINDER:
                raise ValueError(f"{name}: {path.name} is too large")
            found.append((CHR_DIR / path.name.casefold(), path))
    try:
        carried = assets.scan_project(folder)
    except assets.AssetError as error:
        raise ValueError(f"{name}: {error}") from error
    for row in carried:
        relative = Path(row["relative"])
        found.append((relative, folder / relative))
    return found


def read_mod(folder: Path, name: str) -> Mod | None:
    """A DS1 data mod's saved files, or None for a folder that is not one."""
    from .tweak_mods import checked
    folder = checked(Path(folder))
    if not (folder / MARKER).is_file():
        return None
    files = {}
    for key, path in content_files(folder, name):
        files[key] = path.read_bytes()
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


def vanilla_files(game_root: Path, paths: frozenset[Path]) -> dict[Path, bytes]:
    """The game's own bytes of each file mods change: the preserved originals
    once Lexeditor has applied, else the installed files. Only the files
    participating in this composition are read."""
    from . import deployment
    from .tweak_mods import checked
    result = {}
    from . import assets as _assets
    for relative in sorted(paths):
        path = checked(deployment.vanilla_source(Path(game_root), relative))
        if path.is_file():
            limit = (MAX_ARCHIVE if relative in FILES else MAX_MAP
                     if relative.suffix == ".msb" and relative.parent == MAP_DIR else MAX_BINDER
                     if relative.suffix == ".dcx" and relative.parent == CHR_DIR else _assets.MAX_ASSET_BYTES)
            if path.stat().st_size > limit:
                raise ValueError(f"The game's {relative.name} is too large")
            result[relative] = path.read_bytes()
    return result


def build(game_root: Path, library_root: Path, project_root: Path | None = None) -> tuple[Composition, list[Mod]]:
    mods = active_mods(library_root, project_root)
    return compose_installed(game_root, mods), mods


def compose_installed(game_root: Path, mods: list[Mod], *, conflicts_only: bool = False) -> Composition:
    """Load every mod's original assets before composing the enabled set."""
    paths = frozenset(name for mod in mods for name in mod.files)
    return compose(vanilla_files(game_root, paths), mods, conflicts_only=conflicts_only)


def _is_asset(relative: Path) -> bool:
    """A mod file no structured composer handles: a whole asset."""
    if relative in FILES:
        return False
    if relative.suffix == ".msb" and relative.parent == MAP_DIR:
        return False
    from . import assets
    return not assets.is_character_file(relative)


def compose(vanilla: dict[Path, bytes], mods: list[Mod], *, conflicts_only: bool = False) -> Composition:
    """The files every mod together changes, and what could not be combined.

    `vanilla` holds the game's own bytes of each file; `mods` is load order,
    lowest first. Only files that end up different from vanilla are returned.
    """
    from . import assets
    files, conflicts = {}, []
    if RELATIVE in vanilla:
        result = _compose_params(vanilla[RELATIVE], [(mod.name, mod.files[RELATIVE])
                                                     for mod in mods if RELATIVE in mod.files], conflicts_only=conflicts_only)
        conflicts += result[1]
        if result[0] != vanilla[RELATIVE]:
            files[RELATIVE] = result[0]
    if texts.RELATIVE in vanilla:
        result = _compose_texts(vanilla[texts.RELATIVE], [(mod.name, mod.files[texts.RELATIVE])
                                                          for mod in mods if texts.RELATIVE in mod.files], conflicts_only=conflicts_only)
        conflicts += result[1]
        if result[0] != vanilla[texts.RELATIVE]:
            files[texts.RELATIVE] = result[0]
    if texts.MENU_RELATIVE in vanilla:
        result = _compose_texts(vanilla[texts.MENU_RELATIVE], [(mod.name, mod.files[texts.MENU_RELATIVE])
                                                              for mod in mods if texts.MENU_RELATIVE in mod.files],
                                relative=texts.MENU_RELATIVE, document=texts.MenuDocument, conflicts_only=conflicts_only)
        conflicts += result[1]
        if result[0] != vanilla[texts.MENU_RELATIVE]:
            files[texts.MENU_RELATIVE] = result[0]
    for relative in sorted({path for path in list(vanilla) + [name for mod in mods for name in mod.files]
                            if path.suffix == ".msb" and path.parent == MAP_DIR}):
        have = [(mod.name, mod.files[relative]) for mod in mods if relative in mod.files]
        if relative not in vanilla:
            if have:
                files[relative] = have[-1][1]
            continue
        result = _compose_maps(vanilla[relative], have, relative)
        conflicts += result[1]
        if result[0] != vanilla[relative]:
            files[relative] = result[0]
    for relative in sorted({path for path in list(vanilla) + [name for mod in mods for name in mod.files]
                            if assets.is_character_file(path)}):
        have = [(mod.name, mod.files[relative]) for mod in mods if relative in mod.files]
        if relative not in vanilla:
            if have:
                files[relative] = have[-1][1]
            continue
        result = (_compose_esd(vanilla[relative], have, relative) if relative.name.endswith('.esd.dcx')
                  else _compose_anibnd(vanilla[relative], have, relative, conflicts_only=conflicts_only))
        conflicts += result[1]
        if result[0] != vanilla[relative]:
            files[relative] = result[0]
    for relative in sorted({name for mod in mods for name in mod.files if _is_asset(name)}):
        have = [(mod.name, mod.files[relative]) for mod in mods if relative in mod.files]
        if relative not in vanilla:
            if have:
                files[relative] = have[-1][1]
            continue
        result = _compose_anibnd(vanilla[relative], have, relative, kind="file", conflicts_only=conflicts_only)
        conflicts += result[1]
        if result[0] != vanilla[relative]:
            files[relative] = result[0]
    return Composition({} if conflicts_only else files, conflicts)


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


def _compose_params(vanilla: bytes, mods: list[tuple[str, bytes]], *, conflicts_only: bool = False) -> tuple[bytes, list[Conflict]]:
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
    if conflicts_only or all(new.data == old.data for new, old in zip(output, entries)):
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


# A DS1 PARAM: a 48-byte header, a 12-byte directory entry per row (id, data
# offset, name offset), the rows' data, then their names. The game's own
# tables keep the data back to back in directory order with each name in
# row order after it, and the header's strings field is the data end
# rounded up to 16; every such table is rebuilt byte for byte by
# _write_table. A mod's tool may lay its table out otherwise (rows appended
# one at a time), so a mod's rows are read through the directory.
_HEADER, _STRIDE = 48, 12


def _table_rows(payload: bytes, size: int) -> list[tuple[int, bytes | None, bytes]] | None:
    """(id, raw name or None, data) of every row, in directory order, or None."""
    if len(payload) < _HEADER or payload[0x2C] != 0 or payload[0x2D] != 2 or payload[0x2E] & ~1:
        return None
    count, = struct.unpack_from("<H", payload, 10)
    if _HEADER + _STRIDE * count > len(payload):
        return None
    terminator = b"\0\0" if payload[0x2E] & 1 else b"\0"
    rows = []
    for index in range(count):
        row_id, offset, name_offset = struct.unpack_from("<iII", payload, _HEADER + _STRIDE * index)
        if offset + size > len(payload):
            return None
        name = None
        if name_offset:
            end = payload.find(terminator, name_offset)
            while end >= 0 and len(terminator) == 2 and (end - name_offset) % 2:
                end = payload.find(terminator, end + 1)
            if not 0 < name_offset < len(payload) or end < 0:
                return None
            name = payload[name_offset:end]
        rows.append((row_id, name, payload[offset:offset + size]))
    return rows


def _standard_tail(payload: bytes, size: int, rows: list) -> bytes | None:
    """The bytes after the names when the table has the game's own layout."""
    count = len(rows)
    data_start = _HEADER + _STRIDE * count
    data_end = data_start + size * count
    if (not count or struct.unpack_from("<H", payload, 4)[0] != data_start
            or struct.unpack_from("<I", payload, 0)[0] != (data_end + 15) // 16 * 16):
        return None
    terminator = 2 if payload[0x2E] & 1 else 1
    cursor = data_end
    for index in range(count):
        _id, offset, name_offset = struct.unpack_from("<iII", payload, _HEADER + _STRIDE * index)
        if offset != data_start + index * size:
            return None
        if name_offset:
            if name_offset != cursor:
                return None
            cursor += len(rows[index][1]) + terminator
    return payload[cursor:]


def _write_table(header: bytes, size: int, rows: list, tail: bytes) -> bytes:
    """A PARAM in the game's own layout, rows in the order given."""
    terminator = b"\0\0" if header[0x2E] & 1 else b"\0"
    count = len(rows)
    if count > 0xFFFF:
        raise ValueError("A table can hold at most 65535 rows")
    data_start = _HEADER + _STRIDE * count
    data_end = data_start + size * count
    directory, data, names = bytearray(), bytearray(), bytearray()
    for index, (row_id, name, payload) in enumerate(rows):
        name_offset = 0
        if name is not None:
            name_offset = data_end + len(names)
            names += name + terminator
        directory += struct.pack("<iII", row_id, data_start + index * size, name_offset)
        data += payload
    result = bytearray(header[:_HEADER]) + directory + data + names + tail
    strings = (data_end + 15) // 16 * 16
    # The strings field never points past the end: a table with short or no
    # names is padded to it.
    result += bytes(max(0, strings - len(result)))
    struct.pack_into("<I", result, 0, strings)
    struct.pack_into("<H", result, 4, data_start)
    struct.pack_into("<H", result, 10, count)
    return bytes(result)


def _merge_rows(member: str, table: str, vanilla: bytes, mods: list[tuple[str, bytes]],
                units: "_Units") -> tuple[bytes, list[Conflict]] | None:
    """Every mod's rows over vanilla's, by row id: changed rows by field, added
    rows added, removed rows removed. None when a table cannot be read so."""
    spans = _row_spans(vanilla)
    if spans is None:
        return None
    size = spans[0][1] - spans[0][0]
    base = _table_rows(vanilla, size)
    tail = _standard_tail(vanilla, size, base) if base else None
    if base is None or tail is None or len({row_id for row_id, _n, _d in base}) != len(base):
        return None
    order = [row_id for row_id, _n, _d in base]
    original = {row_id: (name, data) for row_id, name, data in base}
    rows = {row_id: [name, bytearray(data)] for row_id, name, data in base}
    owners: dict[tuple, str] = {}
    added_by: dict[int, tuple[str, bytes]] = {}
    removed_by: dict[int, str] = {}
    conflicts: dict[tuple, Conflict] = {}

    def conflict(key: tuple, part: str, *names: str) -> None:
        entry = conflicts.setdefault(key, Conflict(RELATIVE, part))
        for name in names:
            entry.add(name)

    for name, data in mods:
        # Only rows and names may differ: a different header is a different table.
        if data[6:10] != vanilla[6:10] or data[12:_HEADER] != vanilla[12:_HEADER]:
            return None
        theirs = _table_rows(data, size)
        if theirs is None or len({row_id for row_id, _n, _d in theirs}) != len(theirs):
            return None
        present = {row_id for row_id, _n, _d in theirs}
        for row_id in original:
            if row_id not in present:
                removed_by[row_id] = name
        for row_id, row_name, row_data in theirs:
            if row_id not in original:
                earlier = added_by.get(row_id)
                if earlier and earlier[1] != row_data:
                    conflict(("added", row_id), f"{table} {row_id} (added by both)", earlier[0], name)
                added_by[row_id] = (name, row_data)
                rows[row_id] = [row_name, bytearray(row_data)]
                continue
            vanilla_name, vanilla_data = original[row_id]
            if row_name != vanilla_name:
                rows[row_id][0] = row_name
            if row_data == vanilla_data:
                continue
            merged = rows[row_id][1]
            for offset, width, mask, label in units.of(member, size):
                value = int.from_bytes(row_data[offset:offset + width], "little") & mask
                if value == int.from_bytes(vanilla_data[offset:offset + width], "little") & mask:
                    continue
                current = int.from_bytes(merged[offset:offset + width], "little")
                key = (row_id, offset, mask)
                if key in owners and owners[key] != name and current & mask != value:
                    conflict(key, f"{table} {row_id}, {label}", owners[key], name)
                merged[offset:offset + width] = ((current & ~mask) | value).to_bytes(width, "little")
                owners[key] = name
    for row_id, name in removed_by.items():
        changers = sorted({owner for (owned_row, *_rest), owner in owners.items() if owned_row == row_id} - {name})
        if changers:
            conflict(("removed", row_id), f"{table} {row_id} (removed by one, changed by another)", *changers, name)
        rows.pop(row_id, None)
    # Added rows go after the nearest lower id already in the table, as the
    # game's own tables are (almost) sorted.
    for row_id in sorted(added_by):
        position = len(order)
        for index in range(len(order) - 1, -1, -1):
            if order[index] < row_id:
                position = index + 1
                break
        else:
            position = 0
        order.insert(position, row_id)
    result = [(row_id, rows[row_id][0], bytes(rows[row_id][1])) for row_id in order if row_id in rows]
    return _write_table(vanilla, size, result, tail), list(conflicts.values())


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
        # Rows added or removed: merged by row id, every mod's rows kept.
        changed = [(name, data) for name, data in mods if data is not None and data != vanilla]
        by_row = _merge_rows(member, table, vanilla, changed, units)
        if by_row is not None:
            return by_row
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


# --- Item text ---------------------------------------------------------------

def _compose_texts(vanilla: bytes, mods: list[tuple[str, bytes]], *, relative=texts.RELATIVE,
                       document=texts.TextDocument, conflicts_only: bool = False) -> tuple[bytes, list[Conflict]]:
    base = document(vanilla)
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
            other = document(data)
        except FormatError as error:
            label = "menu text" if relative == texts.MENU_RELATIVE else "item-name"
            raise ValueError(f"{name}: its {label} archive cannot be read ({error})") from error
        if [(entry.member_id, entry.name) for entry in other.entries] != \
                [(entry.member_id, entry.name) for entry in base.entries]:
            foreign.append((name, data))
            continue
        for position, entry in enumerate(other.entries):
            if position in base.tables:
                file = base._file(position)
                before, after = base.original_texts[position], other.tables[position][1]
                for item in set(before) | set(after):
                    if after.get(item) == before.get(item):
                        continue
                    key = (file, item)
                    if key in owners and owners[key] != name and merged[position].get(item) != after.get(item):
                        # Merged-only tables (Place_name_) hold names too.
                        role = ('Name' if file in texts.NAME_TABLES.values() or file in texts.MERGED_TABLES
                                else 'Full description' if 'long_desc' in file else 'Description')
                        if relative == texts.MENU_RELATIVE:
                            role = 'Menu label'
                        conflict = conflicts.setdefault(key, Conflict(relative, f"{role} {item} ({file.removesuffix('_.fmg').replace('_', ' ')})"))
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
        title = "Menu text archive (whole file)" if relative == texts.MENU_RELATIVE else "Item text archive (whole file)"
        conflict = Conflict(relative, title)
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
            conflict = Conflict(relative, f"{base._file(position)} (whole text table)")
            for name, _data in changes:
                conflict.add(name)
            result.append(conflict)
    if conflicts_only or not changed:
        return vanilla, result
    plain = texts.build_bnd3(base.plain, entries)
    compressed = zlib.compress(plain, 9)
    header = bytearray(vanilla[:76])
    struct.pack_into(">II", header, 28, len(plain), len(compressed))
    return bytes(header) + compressed, result


# --- Maps ------------------------------------------------------------------

def _outside_same(base: MsbDocument, other: MsbDocument) -> bool:
    """True when every byte outside the placement fields is unchanged."""
    spans = sorted((start, start + size) for _key, _field, start, size, _label, _name in base.merge_units())
    cursor = 0
    for start, end in spans:
        if other.plain[cursor:start] != base.plain[cursor:start]:
            return False
        cursor = max(cursor, end)
    return other.plain[cursor:] == base.plain[cursor:]


def _whole_map(vanilla: bytes, changed: list[tuple[str, bytes]], relative: Path) -> tuple[bytes, list[Conflict]]:
    touched = [name for name, _data in changed]
    if len(touched) < 2:
        return changed[-1][1], []
    conflict = Conflict(relative, f"{relative.name} (whole map)")
    for name in touched:
        conflict.add(name)
    return changed[-1][1], [conflict]


def _compose_maps(vanilla: bytes, mods: list[tuple[str, bytes]], relative: Path) -> tuple[bytes, list[Conflict]]:
    """Every mod's placement fields over vanilla's, or the last whole map."""
    changed = [(name, data) for name, data in mods if data != vanilla]
    if not changed:
        return vanilla, []
    try:
        base = MsbDocument(vanilla, relative.name)
        docs = [(name, MsbDocument(data, relative.name)) for name, data in changed]
    except MsbError:
        return _whole_map(vanilla, changed, relative)
    keys = [(part["type"], part["id"]) for part in base.parts]
    units = base.merge_units()
    for _name, doc in docs:
        if len(doc.plain) != len(base.plain):
            return _whole_map(vanilla, changed, relative)
        if [(part["type"], part["id"]) for part in doc.parts] != keys:
            return _whole_map(vanilla, changed, relative)
        if not _outside_same(base, doc):
            return _whole_map(vanilla, changed, relative)
    merged = bytearray(vanilla)
    owners: dict[tuple, str] = {}
    conflicts: dict[tuple, Conflict] = {}
    for name, doc in docs:
        for key, field, start, size, label, pname in units:
            theirs = bytes(doc.plain[start:start + size])
            if theirs == bytes(base.plain[start:start + size]):
                continue
            current = bytes(merged[start:start + size])
            unit = (key, field)
            if unit in owners and owners[unit] != name and current != theirs:
                part = f"{relative.name} {pname}, {label}"
                entry = conflicts.setdefault(unit, Conflict(relative, part))
                entry.add(owners[unit])
                entry.add(name)
            merged[start:start + size] = theirs
            owners[unit] = name
    return bytes(merged), list(conflicts.values())


# --- Characters ------------------------------------------------------------

def _compose_esd(vanilla: bytes, mods: list[tuple[str, bytes]], relative: Path) -> tuple[bytes, list[Conflict]]:
    """Compose loose character states by field, just like embedded scripts."""
    from . import esd_merge
    changed = [(name, data) for name, data in mods if data != vanilla]
    if not changed:
        return vanilla, []
    try:
        original = inflate(vanilla)
        variants = [(name, inflate(data)) for name, data in changed]
        combined, collisions = esd_merge.compose(original, variants, talk_options=False)
    except FormatError:
        return _whole_anibnd(changed, relative, kind="character script")
    conflicts = []
    for part, names in collisions:
        conflict = Conflict(relative, part)
        for name in names:
            conflict.add(name)
        conflicts.append(conflict)
    return (vanilla if combined == original else deflate(vanilla, combined)), conflicts


def _whole_anibnd(changed: list[tuple[str, bytes]], relative: Path, kind: str = "character file") -> tuple[bytes, list[Conflict]]:
    touched = [name for name, _data in changed]
    if len(touched) < 2:
        return changed[-1][1], []
    conflict = Conflict(relative, f"{relative.name} (whole {kind})")
    for name in touched:
        conflict.add(name)
    return changed[-1][1], [conflict]


def _compose_anibnd(vanilla: bytes, mods: list[tuple[str, bytes]], relative: Path, kind: str = "character file", *, conflicts_only: bool = False) -> tuple[bytes, list[Conflict]]:
    """Every mod's changed binder members over vanilla's, or the last whole file."""
    changed = [(name, data) for name, data in mods if data != vanilla]
    if not changed:
        return vanilla, []
    if len({data for _name, data in changed}) == 1:
        return changed[-1][1], []
    from .assets import MAX_ASSET_BYTES
    try:
        base_plain = inflate(vanilla, max_size=MAX_ASSET_BYTES)
        base_members = members(base_plain)
        plains = []
        for name, data in changed:
            plain = inflate(data, max_size=MAX_ASSET_BYTES)
            plains.append((name, plain, members(plain)))
    except FormatError:
        return _whole_anibnd(changed, relative, kind)
    for _name, _plain, owned in plains:
        if set(owned) != set(base_members):
            return _compose_bnd3_directory(vanilla, base_plain, plains, changed, relative, kind, conflicts_only=conflicts_only)
    winners: dict[str, bytes] = {}
    owners: dict[str, str] = {}
    conflicts: dict[str, Conflict] = {}
    combined_esd = {}
    for member, base in base_members.items():
        if not member.lower().endswith('.esd'):
            continue
        original = bytes(base_plain[base.offset:base.offset + base.size])
        variants = [(name, bytes(plain[owned[member].offset:owned[member].offset + owned[member].size]))
                    for name, plain, owned in plains]
        if len({data for _, data in variants if data != original}) < 2:
            continue
        from . import esd_merge
        try:
            combined, collisions = esd_merge.compose(original, variants)
        except FormatError:
            continue  # Unknown ESD layouts keep the existing member conflict.
        combined_esd[member] = combined
        for part, names in collisions:
            key = f'{member}/{part}'
            conflict = conflicts.setdefault(key, Conflict(relative, key))
            for name in names:
                conflict.add(name)
    for name, plain, owned in plains:
        for member, entry in owned.items():
            if member in combined_esd:
                continue
            base = base_members[member]
            theirs = bytes(plain[entry.offset:entry.offset + entry.size])
            if theirs == bytes(base_plain[base.offset:base.offset + base.size]):
                continue
            if member in owners and owners[member] != name and winners[member] != theirs:
                entry_conflict = conflicts.setdefault(member, Conflict(relative, member))
                entry_conflict.add(owners[member])
                entry_conflict.add(name)
            winners[member] = theirs
            owners[member] = name
    winners.update(combined_esd)
    if conflicts_only:
        return vanilla, list(conflicts.values())
    items = {member: bytes(base_plain[entry.offset:entry.offset + entry.size])
             for member, entry in base_members.items()}
    items.update(winners)
    if all(len(items[member]) == base_members[member].size for member in items):
        merged = bytearray(base_plain)
        for member, data in winners.items():
            base = base_members[member]
            merged[base.offset:base.offset + base.size] = data
        return deflate(vanilla, bytes(merged), max_size=MAX_ASSET_BYTES), list(conflicts.values())
    return deflate(vanilla, pack(base_plain, items), max_size=MAX_ASSET_BYTES), list(conflicts.values())


def _compose_bnd3_directory(vanilla, base_plain, plains, changed, relative, kind, *, conflicts_only=False):
    """Added, removed and replaced members combine as independent records."""
    from .assets import MAX_ASSET_BYTES
    key = lambda entry: entry.name.replace('\\', '/').rsplit('/', 1)[-1]
    try:
        base_entries = texts.bnd3_entries(base_plain)
        base = {key(e): e for e in base_entries}
        variants = []
        for name, plain, _members in plains:
            if plain[:16] != base_plain[:16] or plain[24:32] != base_plain[24:32]:
                return _whole_anibnd(changed, relative, kind)
            entries = texts.bnd3_entries(plain)
            variant = {key(e): e for e in entries}
            if len(variant) != len(entries):
                return _whole_anibnd(changed, relative, kind)
            variants.append((name, variant))
    except FormatError:
        return _whole_anibnd(changed, relative, kind)
    result, owners, conflicts = dict(base), {}, {}
    for name, variant in variants:
        for member in base.keys() | variant.keys():
            theirs = variant.get(member)
            if theirs == base.get(member):
                continue
            if member in owners and result.get(member) != theirs:
                collision = conflicts.setdefault(member, Conflict(relative, member))
                collision.add(owners[member])
                collision.add(name)
            owners[member] = name
            if theirs is None:
                result.pop(member, None)
            else:
                result[member] = theirs
    # Directory additions do not prevent the existing ESD composer from
    # combining independent state-machine edits to a retained member.
    for member, original in base.items():
        if not member.lower().endswith('.esd') or any(member not in variant for _, variant in variants):
            continue
        edits = [(name, variant[member]) for name, variant in variants]
        if len({entry.data for _name, entry in edits if entry.data != original.data}) < 2:
            continue
        if any((entry.member_id, entry.name, entry.flags) !=
               (original.member_id, original.name, original.flags) for _, entry in edits):
            continue
        from . import esd_merge
        try:
            combined, collisions = esd_merge.compose(original.data, [(name, entry.data) for name, entry in edits])
        except FormatError:
            continue
        result[member] = replace(original, data=combined)
        conflicts.pop(member, None)
        for part, names in collisions:
            part_key = f'{member}/{part}'
            collision = conflicts.setdefault(part_key, Conflict(relative, part_key))
            for name in names:
                collision.add(name)
    entries = [result[key(e)] for e in base_entries if key(e) in result]
    entries += sorted((e for name, e in result.items() if name not in base),
                      key=lambda e: (e.member_id, e.name))
    if len({e.member_id for e in entries}) != len(entries):
        return _whole_anibnd(changed, relative, kind)
    if conflicts_only:
        return vanilla, list(conflicts.values())
    plain = texts.build_bnd3(base_plain, entries)
    return deflate(vanilla, plain, max_size=MAX_ASSET_BYTES), list(conflicts.values())
CHANGE_LIMIT = 1000
FIELD_LIMIT = 25


def _short(text, limit):
    """One line of a text entry, cut for a list row."""
    flat = ' '.join(str(text or '').split())
    return flat if len(flat) <= limit else flat[:limit - 1].rstrip() + '\u2026'


def _changed_units(units, old: bytes, new: bytes):
    """The labels of the fields whose bits differ between two rows."""
    if len(old) != len(new):
        return ['(different row size)']
    fields = []
    for offset, width, mask, label in units:
        before = int.from_bytes(old[offset:offset + width], 'little')
        after = int.from_bytes(new[offset:offset + width], 'little')
        if (before ^ after) & mask:
            fields.append(label)
    return fields[:FIELD_LIMIT]


def _param_changes(mod_plain: bytes, vanilla_plain: bytes, labels, notes):
    """Changed, added and removed parameter rows, in archive order."""
    changes = []
    try:
        mod_members = {name: bytes(mod_plain[member.offset:member.offset + member.size])
                       for name, member in members(mod_plain).items()}
        vanilla_members = {name: bytes(vanilla_plain[member.offset:member.offset + member.size])
                           for name, member in members(vanilla_plain).items()}
    except FormatError as error:
        notes.append(f'the parameter archive cannot be read ({error})')
        return changes
    units = _Units()
    for member, vanilla_data in vanilla_members.items():
        mod_data = mod_members.get(member)
        if mod_data is None or mod_data == vanilla_data:
            continue
        table = member.removesuffix('.param')
        spans = _row_spans(vanilla_data)
        base = _table_rows(vanilla_data, spans[0][1] - spans[0][0]) if spans else None
        spans = _row_spans(mod_data)
        other = _table_rows(mod_data, spans[0][1] - spans[0][0]) if spans else None
        if base is None or other is None:
            notes.append(f'{member} cannot be compared row by row')
            continue
        size = len(base[0][2]) if base else 0
        by_id = {row_id: data for row_id, _name, data in other}
        fields = units.of(member, size) if size else []
        for row_id, _name, data in base:
            mine = by_id.get(row_id)
            if mine is None:
                changes.append({'table': table, 'id': row_id, 'label': labels[1](table, row_id),
                                'fields': [], 'added': False, 'removed': True,
                                'before': None, 'after': None})
            elif bytes(mine) != bytes(data):
                changes.append({'table': table, 'id': row_id, 'label': labels[0](table, row_id),
                                'fields': _changed_units(fields, bytes(data), bytes(mine)),
                                'added': False, 'removed': False, 'before': None, 'after': None})
        known = {row_id for row_id, _name, _data in base}
        for row_id, _name, _data in other:
            if row_id not in known:
                changes.append({'table': table, 'id': row_id, 'label': labels[0](table, row_id),
                                'fields': [], 'added': True, 'removed': False,
                                'before': None, 'after': None})
    return changes


def _text_maps(document):
    """{file name: {id: text}} with later copies winning, like the game."""
    merged = {}
    for position, (_groups, mapping) in document.tables.items():
        merged.setdefault(document._file(position), {}).update(mapping)
    return merged


def _text_changes(mod_doc, vanilla_doc, menu: bool):
    """Changed, added and removed text entries, by file then id."""
    changes = []
    mine, base = _text_maps(mod_doc), _text_maps(vanilla_doc)
    for file in list(mine) + [name for name in base if name not in mine]:
        pretty = file.removesuffix('_.fmg').removesuffix('.fmg').replace('_', ' ')
        table = f'Menu {pretty}' if menu else pretty
        after, before = mine.get(file, {}), base.get(file, {})
        for item in sorted(set(after) | set(before)):
            old, new = before.get(item), after.get(item)
            if old == new:
                continue
            changes.append({'table': table, 'id': item,
                            'label': _short(new if new is not None else old, 80),
                            'fields': [], 'added': old is None, 'removed': new is None,
                            'before': _short(old, 120) if old is not None else None,
                            'after': _short(new, 120) if new is not None else None})
    return changes


def _labeled(mod_params: bytes | None, vanilla_params: bytes, texts_doc):
    """Display-name lookups for the changed rows, mod names first."""
    from .formats import ItemDocument
    try:
        mod_doc = ItemDocument(mod_params) if mod_params is not None else None
        if mod_doc is not None:
            mod_doc.texts = texts_doc
    except FormatError:
        mod_doc = None
    try:
        vanilla_doc = ItemDocument(vanilla_params)
    except FormatError:
        vanilla_doc = None

    def label(document, table, row_id):
        if document is not None:
            try:
                return document.display_name(table, row_id)
            except (FormatError, KeyError, StopIteration):
                pass
        return f'{table} {row_id}'

    return (lambda table, row_id: label(mod_doc, table, row_id),
            lambda table, row_id: label(vanilla_doc, table, row_id))


def _vanilla_bytes(game_root: Path, relative: Path, notes: list, what: str):
    """One game file as vanilla shipped it: the preserved original once
    Lexeditor has applied, else the installed file. None (with a note)
    when the original cannot be verified or nothing is installed."""
    from . import deployment
    try:
        source = deployment.vanilla_source(Path(game_root), relative)
    except RuntimeError as error:
        notes.append(f"{what} cannot be compared: {error}")
        return None
    if not source.is_file():
        notes.append(f"The game has no {what} to compare this mod against.")
        return None
    return source.read_bytes()


def describe_changes(folder: Path, game_root: Path | None):
    """Every record one mod changes against vanilla: params, then texts.

    Returns {'changes': [...], 'truncated': bool, 'total': int, 'note': str}.
    Each change carries its table, id, display label, changed field
    labels (parameters) or before/after text (texts), and added/removed
    flags. Vanilla means the preserved originals once Lexeditor has
    applied: the live files may hold a deployed mod instead, and
    comparing against those would report that mod's rows as this
    one's. Map, character and asset files are file-level changes;
    they show under the mod's files, not here. Without the game
    installed there is no vanilla to compare, so the list stays
    empty and the note says so.
    """
    folder = Path(folder)
    changes, notes = [], []
    if game_root is None:
        notes.append('Locate the game to compare records against vanilla.')
        return {'changes': changes, 'truncated': False, 'note': ' '.join(notes)}
    game_root = Path(game_root)
    mod_params = folder / RELATIVE
    params = (mod_params.read_bytes() if mod_params.is_file() else None, None)
    if params[0] is not None:
        params = (params[0], _vanilla_bytes(game_root, RELATIVE, notes,
                                          "parameter archive"))
    texts_doc = None
    for candidate in (folder / texts.RELATIVE, game_root / texts.RELATIVE):
        if not candidate.is_file():
            continue
        try:
            texts_doc = texts.TextDocument(candidate.read_bytes())
            break
        except FormatError as error:
            notes.append(f'{candidate.name} cannot be read ({error})')
    if params[0] is not None and params[1] is not None:
        try:
            plains = (inflate(params[0]), inflate(params[1]))
        except FormatError as error:
            notes.append(f'the parameter archive cannot be read ({error})')
            plains = None
        if plains is not None:
            changes += _param_changes(plains[0], plains[1],
                                      _labeled(params[0], params[1], texts_doc), notes)
    for relative, document in ((texts.RELATIVE, texts.TextDocument),
                               (texts.MENU_RELATIVE, texts.MenuDocument)):
        mod_file = folder / relative
        if not mod_file.is_file():
            continue
        what = "menu text" if document is texts.MenuDocument else "item text"
        base_bytes = _vanilla_bytes(game_root, relative, notes, what)
        if base_bytes is None:
            continue
        try:
            mine, base = document(mod_file.read_bytes()), document(base_bytes)
        except FormatError as error:
            notes.append(f'{relative.name} cannot be read ({error})')
            continue
        if mine.plain == base.plain:
            continue
        changes += _text_changes(mine, base, menu=document is texts.MenuDocument)
    total = len(changes)
    truncated = total > CHANGE_LIMIT
    return {'changes': changes[:CHANGE_LIMIT], 'truncated': truncated,
            'total': total, 'note': ' '.join(notes)}


def loaded_files(folder: Path):
    """Mod-folder-relative files the loader reads, casefolded for matching."""
    from .tweak_mods import checked
    folder = checked(Path(folder))
    try:
        pairs = content_files(folder, folder.name)
    except (ValueError, OSError):
        return []
    found = set()
    for _key, disk in pairs:
        try:
            found.add(disk.relative_to(folder).as_posix().casefold())
        except ValueError:
            continue
    return sorted(found)
