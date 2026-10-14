"""Dark Souls Remastered's in-game item text: msg/ENGLISH/item.msgbnd.dcx.

An item's name and descriptions are not part of its parameter row. The game reads them from a
text table (FMG) by the row's ID, one table per kind of item, inside this
compressed archive (the same DCX and BND3 shapes as the parameter archive,
but its members carry folder paths and repeat names). Remastered keeps two
copies of every table, IDs 10-29 and 100-120; both are read here and both
are written, so an edited item reads the same whichever copy the game uses.

FMG, as Remastered ships it (little-endian, version 1): a 0x1C-byte header,
then groups of (first index, first ID, last ID), then one string offset per
ID in the groups (0 for an ID with no text), then the strings as UTF-16LE,
each ending with a null. Reading then writing an unchanged archive returns
its exact bytes.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import struct
import zlib

from .formats import FormatError, MAX_ARCHIVE, inflate

RELATIVE = Path('msg/ENGLISH/item.msgbnd.dcx')
MENU_RELATIVE = Path('msg/ENGLISH/menu.msgbnd.dcx')
# The equipment panel's defense labels, in Menu_general_text_.fmg: MagDEF,
# FireDEF and LitngDEF beside each piece's elemental defense.
MENU_LABEL_FILE = 'Menu_general_text_.fmg'
MENU_LABELS = {'magicDefense': ('Magic defense label', 102204),
               'fireDefense': ('Fire defense label', 102205),
               'lightningDefense': ('Lightning defense label', 102206)}
MENU_LABEL_IDS = {text_id: key for key, (_display, text_id) in MENU_LABELS.items()}
# Tables with no parameter rows behind them that still merge by entry.
# Place_name_ holds the warp destination (2000-2020) and area (1000-1810)
# names the bonfire warp menu shows; the editor offers no rename surface
# for them, but a mod may carry its own bytes and the loader composes
# them entry by entry instead of taking one member whole.
MERGED_TABLES = frozenset({'Place_name_.fmg'})
# The parameter table each name table names, by the table's file name.
NAME_TABLES = {
    'EquipParamGoods': 'Item_name_.fmg',
    'EquipParamWeapon': 'Weapon_name_.fmg',
    'EquipParamProtector': 'Armor_name_.fmg',
    'EquipParamAccessory': 'Accessory_name_.fmg',
    'Magic': 'Magic_name_.fmg',
}
# The short and long description tables per parameter table. Short
# descriptions are one line (60 characters at most in the game); long
# ones are the full multi-line lore text (372 at most).
DESC_TABLES = {
    'EquipParamGoods': ('Item_description_.fmg', 'Item_long_desc_.fmg'),
    'EquipParamWeapon': ('Weapon_description_.fmg', 'Weapon_long_desc_.fmg'),
    'EquipParamProtector': ('Armor_description_.fmg', 'Armor_long_desc_.fmg'),
    'EquipParamAccessory': ('Accessory_description_.fmg', 'Accessory_long_desc_.fmg'),
    'Magic': ('Magic_description_.fmg', 'Magic_long_desc_.fmg'),
}
MAX_NAME = 200
KIND_LABELS = {'name': 'Name', 'description': 'Description',
               'longDescription': 'Full description'}
MAX_DESCRIPTION = 200
MAX_LONG_DESCRIPTION = 2000
HEADER = 0x1C


@dataclass
class Entry:
    member_id: int
    name: str
    flags: int
    data: bytes


def bnd3_entries(plain: bytes) -> list[Entry]:
    if len(plain) < 32 or plain[:4] != b'BND3' or plain[12:16] != b'\x74\0\0\0':
        raise FormatError('Unsupported text archive; expected the PC Remastered item text BND3')
    count, names_end = struct.unpack_from('<II', plain, 16)
    if not 1 <= count <= 4096 or not 32 + count * 24 <= names_end <= len(plain):
        raise FormatError('Invalid text archive directory')
    entries, spans = [], []
    for index in range(count):
        flags, size, offset, member_id, name_offset, unpacked = struct.unpack_from('<6I', plain, 32 + index * 24)
        if flags != 0x40 or size != unpacked or not names_end <= offset <= len(plain) - size:
            raise FormatError('Compressed, overlapping or invalid text archive member')
        end = plain.find(b'\0', name_offset, names_end)
        if end < 0:
            raise FormatError('Unterminated text archive member name')
        entries.append(Entry(member_id, plain[name_offset:end].decode('shift_jis'), flags, plain[offset:offset + size]))
        spans.append((offset, offset + size))
    spans.sort()
    if any(a[1] > b[0] for a, b in zip(spans, spans[1:])):
        raise FormatError('Overlapping text archive members')
    return entries


def build_bnd3(original: bytes, entries: list[Entry]) -> bytes:
    """The original directory and names, with every member's data laid out
    again in order, each starting on a 16-byte boundary as shipped."""
    count, names_end = struct.unpack_from('<II', original, 16)
    if count != len(entries):
        raise FormatError('The text archive member count changed')
    out = bytearray(original[:names_end])
    for index, entry in enumerate(entries):
        while len(out) % 16:
            out.append(0)
        offset = len(out)
        out += entry.data
        flags, _size, _offset, member_id, name_offset, _unpacked = struct.unpack_from('<6I', original, 32 + index * 24)
        struct.pack_into('<6I', out, 32 + index * 24, flags, len(entry.data), offset, member_id, name_offset, len(entry.data))
    return bytes(out)


def parse_fmg(data: bytes) -> tuple[list[tuple[int, int, int]], dict[int, str | None]]:
    """The table's groups, and the text for every ID they cover (None for none)."""
    if len(data) < HEADER or data[:4] != b'\0\0\x01\0':
        raise FormatError('Unsupported item text table')
    size, = struct.unpack_from('<I', data, 4)
    groups_count, strings_count, offsets_at = struct.unpack_from('<III', data, 12)
    if size != len(data) or offsets_at != HEADER + groups_count * 12 or offsets_at + strings_count * 4 > len(data):
        raise FormatError('Invalid item text table layout')
    groups = [struct.unpack_from('<iii', data, HEADER + index * 12) for index in range(groups_count)]
    offsets = struct.unpack_from(f'<{strings_count}i', data, offsets_at)
    texts: dict[int, str | None] = {}
    for first_index, first_id, last_id in groups:
        if first_index < 0 or last_id < first_id or first_index + (last_id - first_id) >= strings_count:
            raise FormatError('Invalid item text group')
        for step in range(last_id - first_id + 1):
            offset = offsets[first_index + step]
            if offset == 0:
                texts[first_id + step] = None
                continue
            end = offset
            while end + 1 < len(data) and data[end:end + 2] != b'\0\0':
                end += 2
            texts[first_id + step] = data[offset:end].decode('utf-16-le')
    return groups, texts


def build_fmg(original: bytes, groups: list[tuple[int, int, int]], texts: dict[int, str | None]) -> bytes:
    """The table again: its groups as they were, plus a one-ID group for any
    ID that had none, each in ID order; then every text in that order."""
    covered = {first + step for _index, first, last in groups for step in range(last - first + 1)}
    spans = [(first, last) for _index, first, last in groups]
    spans += [(item, item) for item in sorted(set(texts) - covered)]
    spans.sort()
    ids = [first + step for first, last in spans for step in range(last - first + 1)]
    header = bytearray(original[:HEADER])
    offsets_at = HEADER + len(spans) * 12
    strings_at = offsets_at + len(ids) * 4
    group_table, index = bytearray(), 0
    for first, last in spans:
        group_table += struct.pack('<iii', index, first, last)
        index += last - first + 1
    offsets, strings = [], bytearray()
    for item in ids:
        text = texts.get(item)
        if text is None:
            offsets.append(0)
            continue
        offsets.append(strings_at + len(strings))
        strings += text.encode('utf-16-le') + b'\0\0'
    body = group_table + struct.pack(f'<{len(ids)}i', *offsets) + strings
    # A table ends on a 4-byte boundary, as shipped.
    body += b'\0' * (-(HEADER + len(body)) % 4)
    struct.pack_into('<I', header, 4, HEADER + len(body))
    struct.pack_into('<III', header, 12, len(spans), len(ids), offsets_at)
    return bytes(header) + bytes(body)


class TextDocument:
    """The item name and description tables of one item.msgbnd.dcx, editable by item."""

    ARCHIVE_LABEL = 'item text archive'

    def _parse_table(self, filename: str) -> bool:
        wanted = set(NAME_TABLES.values()) | {name for pair in DESC_TABLES.values() for name in pair}
        return filename in wanted | MERGED_TABLES

    def _required_tables(self) -> set[str]:
        return set(NAME_TABLES.values()) | {name for pair in DESC_TABLES.values() for name in pair}

    def __init__(self, source: bytes):
        if len(source) > MAX_ARCHIVE:
            raise FormatError(f'The {self.ARCHIVE_LABEL} is too large.')
        self.original = source
        self.plain = inflate(source)
        self.entries = bnd3_entries(self.plain)
        self.tables: dict[int, tuple[list, dict]] = {}
        self.original_texts: dict[int, dict] = {}
        for position, entry in enumerate(self.entries):
            if self._parse_table(entry.name.replace('\\', '/').rsplit('/', 1)[-1]):
                groups, texts = parse_fmg(entry.data)
                self.tables[position] = (groups, texts)
                self.original_texts[position] = dict(texts)
        missing = self._required_tables() - {self._file(position) for position in self.tables}
        if missing:
            raise FormatError(f'The {self.ARCHIVE_LABEL} has no {", ".join(sorted(missing))}')

    def _file(self, position: int) -> str:
        return self.entries[position].name.replace('\\', '/').rsplit('/', 1)[-1]

    def _copies_of(self, filename: str) -> list[int]:
        # The later copy (the higher member ID) is the one shown when they differ.
        return sorted((position for position in self.tables if self._file(position) == filename),
                      key=lambda position: self.entries[position].member_id, reverse=True)

    def _copies(self, table: str) -> list[int]:
        if table not in NAME_TABLES:
            return []
        return self._copies_of(NAME_TABLES[table])

    def name(self, table: str, row_id: int) -> str | None:
        for position in self._copies(table):
            text = self.tables[position][1].get(row_id)
            if text:
                return text
        return None

    def renamable(self, table: str) -> bool:
        return bool(self._copies(table))

    def describable(self, table: str) -> bool:
        return table in DESC_TABLES and all(self._copies_of(filename) for filename in DESC_TABLES[table])

    def description(self, table: str, row_id: int, long: bool = False) -> str | None:
        if table not in DESC_TABLES:
            return None
        for position in self._copies_of(DESC_TABLES[table][long]):
            text = self.tables[position][1].get(row_id)
            if text:
                return text
        return None

    def original_description(self, table: str, row_id: int, long: bool = False):
        for position in self._copies_of(DESC_TABLES[table][long]):
            if row_id in self.original_texts[position]:
                return self.original_texts[position][row_id]
        return None

    def set_description(self, table: str, row_id: int, value, long: bool = False):
        if not self.describable(table):
            raise FormatError('These records have no in-game description to change.')
        limit = MAX_LONG_DESCRIPTION if long else MAX_DESCRIPTION
        text = str(value).replace('\r\n', '\n').replace('\r', '\n')
        if any(ord(char) < 32 and (char != '\n' or not long) for char in text):
            raise FormatError('A description holds text and, for a full description, line breaks.')
        if not text.strip():
            text = None
        elif len(text) > limit:
            if long:
                raise FormatError(f'A full description is up to {limit} characters.')
            raise FormatError(f'A description is one line of up to {limit} characters.')
        for position in self._copies_of(DESC_TABLES[table][long]):
            self.tables[position][1][row_id] = text
        return text

    def rename(self, table: str, row_id: int, name: str) -> str:
        if not self.renamable(table):
            raise FormatError('These records have no in-game name to change.')
        name = str(name).strip()
        if not name or len(name) > MAX_NAME or any(ord(char) < 32 for char in name):
            raise FormatError(f'A name is 1 to {MAX_NAME} characters on one line.')
        for position in self._copies(table):
            self.tables[position][1][row_id] = name
        return name

    @property
    def dirty(self) -> set[tuple[str, str, int]]:
        changed = set()
        kinds = [('name', table, NAME_TABLES[table]) for table in NAME_TABLES]
        kinds += [(role, table, filename) for table, (short, full) in DESC_TABLES.items()
                  for role, filename in (('description', short), ('longDescription', full))]
        for kind, table, filename in kinds:
            for position in self._copies_of(filename):
                texts, before = self.tables[position][1], self.original_texts[position]
                changed |= {(kind, table, item) for item in texts if texts.get(item) != before.get(item)}
        return changed

    def export(self) -> bytes:
        if not self.dirty:
            return self.original
        entries = list(self.entries)
        for position, (groups, texts) in self.tables.items():
            if texts != self.original_texts[position]:
                old = entries[position]
                entries[position] = Entry(old.member_id, old.name, old.flags, build_fmg(old.data, groups, texts))
        plain = build_bnd3(self.plain, entries)
        compressed = zlib.compress(plain, 9)
        header = bytearray(self.original[:76])
        struct.pack_into('>II', header, 28, len(plain), len(compressed))
        return bytes(header) + compressed


class MenuDocument(TextDocument):
    """One menu.msgbnd.dcx, editable by menu entry. Every FMG member merges

    by entry in the mod loader; the equipment defense labels are editable
    in the Text tab. Both copies of a table are read and
    written, as with item text.
    """

    ARCHIVE_LABEL = 'menu text archive'

    def _parse_table(self, filename: str) -> bool:
        return filename.endswith('.fmg')

    def _required_tables(self) -> set[str]:
        return {MENU_LABEL_FILE}

    @staticmethod
    def _label_entry(key: str) -> tuple[str, int]:
        try:
            return MENU_LABELS[key]
        except KeyError:
            raise FormatError('Unknown menu label') from None

    def label(self, key: str) -> str | None:
        _display, text_id = self._label_entry(key)
        for position in self._copies_of(MENU_LABEL_FILE):
            text = self.tables[position][1].get(text_id)
            if text:
                return text
        return None

    def original_label(self, key: str) -> str | None:
        _display, text_id = self._label_entry(key)
        for position in self._copies_of(MENU_LABEL_FILE):
            if text_id in self.original_texts[position]:
                return self.original_texts[position][text_id]
        return None

    def set_label(self, key: str, value) -> str:
        _display, text_id = self._label_entry(key)
        text = str(value).strip()
        if not text or len(text) > MAX_NAME or any(ord(char) < 32 for char in text):
            raise FormatError(f'A menu label is 1 to {MAX_NAME} characters on one line.')
        for position in self._copies_of(MENU_LABEL_FILE):
            self.tables[position][1][text_id] = text
        return text

    @property
    def dirty(self) -> set[str]:
        changed = set()
        for key, (_display, text_id) in MENU_LABELS.items():
            for position in self._copies_of(MENU_LABEL_FILE):
                texts, before = self.tables[position][1], self.original_texts[position]
                if texts.get(text_id) != before.get(text_id):
                    changed.add(key)
        return changed
