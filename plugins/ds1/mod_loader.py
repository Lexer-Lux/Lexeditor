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

from dataclasses import dataclass, field
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
               "BehaviorParam": "Behaviors", "NpcThinkParam": "AI",
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
        candidates = sorted(chars.glob("*.anibnd.dcx"))
        if len(candidates) > MAX_ANIBND_FILES:
            raise ValueError(f"{name}: too many character files")
        for path in candidates:
            checked(path)
            if path.stat().st_size > MAX_BINDER:
                raise ValueError(f"{name}: {path.name} is too large")
            found.append((CHR_DIR / path.name.casefold(), path))
    from . import assets
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


def vanilla_files(game_root: Path, extra: frozenset[Path] = frozenset()) -> dict[Path, bytes]:
    """The game's own bytes of each file mods change: the preserved originals
    once Lexeditor has applied, else the installed files. `extra` names asset
    files to load beyond the structured sets."""
    from . import deployment
    from .tweak_mods import checked
    result = {}
    for relative in FILES:
        path = checked(deployment.vanilla_source(Path(game_root), relative))
        if path.is_file():
            if path.stat().st_size > MAX_ARCHIVE:
                raise ValueError(f"The game's {relative.name} is too large")
            result[relative] = path.read_bytes()
    maps = Path(game_root) / MAP_DIR
    if maps.is_dir():
        for path in sorted(maps.glob("*.msb")):
            relative = MAP_DIR / path.name.casefold()
            source = checked(deployment.vanilla_source(Path(game_root), relative))
            if source.is_file():
                if source.stat().st_size > MAX_MAP:
                    raise ValueError(f"The game's {relative.name} is too large")
                result[relative] = source.read_bytes()
    chars = Path(game_root) / CHR_DIR
    if chars.is_dir():
        for path in sorted(chars.glob("*.anibnd.dcx")):
            relative = CHR_DIR / path.name.casefold()
            source = checked(deployment.vanilla_source(Path(game_root), relative))
            if source.is_file():
                if source.stat().st_size > MAX_BINDER:
                    raise ValueError(f"The game's {relative.name} is too large")
                result[relative] = source.read_bytes()
    from . import assets as _assets
    for relative in sorted(extra):
        if relative in result:
            continue
        source = checked(deployment.vanilla_source(Path(game_root), relative))
        if source.is_file():
            if source.stat().st_size > _assets.MAX_ASSET_BYTES:
                raise ValueError(f"The game's {relative.name} is too large")
            result[relative] = source.read_bytes()
    return result


def build(game_root: Path, library_root: Path, project_root: Path | None = None) -> tuple[Composition, list[Mod]]:
    mods = active_mods(library_root, project_root)
    extra = frozenset(name for mod in mods for name in mod.files if _is_asset(name))
    return compose(vanilla_files(game_root, extra), mods), mods


def _is_asset(relative: Path) -> bool:
    """A mod file no structured composer handles: a whole asset."""
    if relative in FILES:
        return False
    if relative.suffix == ".msb" and relative.parent == MAP_DIR:
        return False
    return not (relative.suffix == ".dcx" and relative.parent == CHR_DIR)


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
    if texts.MENU_RELATIVE in vanilla:
        result = _compose_texts(vanilla[texts.MENU_RELATIVE], [(mod.name, mod.files[texts.MENU_RELATIVE])
                                                              for mod in mods if texts.MENU_RELATIVE in mod.files],
                                relative=texts.MENU_RELATIVE, document=texts.MenuDocument)
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
                            if path.suffix == ".dcx" and path.parent == CHR_DIR}):
        have = [(mod.name, mod.files[relative]) for mod in mods if relative in mod.files]
        if relative not in vanilla:
            if have:
                files[relative] = have[-1][1]
            continue
        result = _compose_anibnd(vanilla[relative], have, relative)
        conflicts += result[1]
        if result[0] != vanilla[relative]:
            files[relative] = result[0]
    for relative in sorted({name for mod in mods for name in mod.files if _is_asset(name)}):
        have = [(mod.name, mod.files[relative]) for mod in mods if relative in mod.files]
        if relative not in vanilla:
            if have:
                files[relative] = have[-1][1]
            continue
        result = _compose_anibnd(vanilla[relative], have, relative, kind="file")
        conflicts += result[1]
        if result[0] != vanilla[relative]:
            files[relative] = result[0]
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
                       document=texts.TextDocument) -> tuple[bytes, list[Conflict]]:
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
    if not changed:
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

def _whole_anibnd(changed: list[tuple[str, bytes]], relative: Path, kind: str = "character file") -> tuple[bytes, list[Conflict]]:
    touched = [name for name, _data in changed]
    if len(touched) < 2:
        return changed[-1][1], []
    conflict = Conflict(relative, f"{relative.name} (whole {kind})")
    for name in touched:
        conflict.add(name)
    return changed[-1][1], [conflict]


def _compose_anibnd(vanilla: bytes, mods: list[tuple[str, bytes]], relative: Path, kind: str = "character file") -> tuple[bytes, list[Conflict]]:
    """Every mod's changed binder members over vanilla's, or the last whole file."""
    changed = [(name, data) for name, data in mods if data != vanilla]
    if not changed:
        return vanilla, []
    try:
        base_plain = inflate(vanilla)
        base_members = members(base_plain)
        plains = []
        for name, data in changed:
            plain = inflate(data)
            plains.append((name, plain, members(plain)))
    except FormatError:
        return _whole_anibnd(changed, relative, kind)
    for _name, _plain, owned in plains:
        if set(owned) != set(base_members):
            return _whole_anibnd(changed, relative, kind)
    winners: dict[str, bytes] = {}
    owners: dict[str, str] = {}
    conflicts: dict[str, Conflict] = {}
    for name, plain, owned in plains:
        for member, entry in owned.items():
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
    items = {member: bytes(base_plain[entry.offset:entry.offset + entry.size])
             for member, entry in base_members.items()}
    items.update(winners)
    if all(len(items[member]) == base_members[member].size for member in items):
        merged = bytearray(base_plain)
        for member, data in winners.items():
            base = base_members[member]
            merged[base.offset:base.offset + base.size] = data
        return deflate(vanilla, bytes(merged)), list(conflicts.values())
    return deflate(vanilla, pack(base_plain, items)), list(conflicts.values())
