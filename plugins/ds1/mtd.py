"""Bounded, read-only DS1 material definitions for preview shading.

Block/string layout cross-checked against SoulsFormats' MTD reader and
the installed Remastered material binders. This decodes data only; it
does not emulate the game's compiled shaders or write material files.
Reference: https://github.com/JKAnderson/SoulsFormats/blob/master/SoulsFormats/Formats/MTD.cs
"""
import math
import struct
from functools import lru_cache
from pathlib import Path

from core.plugin_files import read_bounded
from .formats import FormatError, inflate, members

MAX_FILE = 1024 * 1024
MAX_BINDER = 32 * 1024 * 1024


class _Reader:
    def __init__(self, data):
        if not 48 <= len(data) <= MAX_FILE:
            raise FormatError('Invalid material-definition size')
        self.data, self.at, self.end = data, 0, len(data)

    def read(self, count):
        if not 0 <= count <= self.end-self.at:
            raise FormatError('Material-definition value exceeds its block')
        value = self.data[self.at:self.at+count]
        self.at += count
        return value

    def integer(self):
        return struct.unpack('<i', self.read(4))[0]

    def marker(self, expected):
        if self.read(1)[0] != expected:
            raise FormatError('Invalid material-definition marker')
        self.read(-self.at % 4)

    def string(self, marker):
        size = self.integer()
        if not 0 <= size <= 4096:
            raise FormatError('Material-definition string is too large')
        try:
            value = self.read(size).decode('shift_jis')
        except UnicodeError as error:
            raise FormatError('Invalid material-definition string') from error
        self.marker(marker)
        return value

    def block(self, kind, version, marker):
        if self.integer() != 0:
            raise FormatError('Invalid material-definition block')
        size = self.integer()
        end = self.at + size
        if size < 12 or end > self.end or self.integer() != kind or self.integer() != version:
            raise FormatError('Invalid material-definition block bounds or type')
        self.marker(marker)
        parent, self.end = self.end, end
        return parent

    def finish(self, parent):
        if self.at != self.end:
            raise FormatError('Material-definition block length does not match its values')
        self.end = parent

    def expect(self, value):
        if self.integer() != value:
            raise FormatError('Invalid material-definition constant')

    def count(self, limit):
        count = self.integer()
        if not 0 <= count <= limit:
            raise FormatError('Too many material-definition entries')
        return count


def read(data):
    reader = _Reader(data)
    file = reader.block(0, 3, 0x01)
    header = reader.block(1, 2, 0xB0)
    if reader.string(0x34) != 'MTD ':
        raise FormatError('Not a material definition')
    reader.expect(1000)
    reader.finish(header)
    reader.marker(1)
    body = reader.block(2, 4, 0xA3)
    shader = reader.string(0xA3)
    reader.string(3)
    reader.expect(1)
    lists = reader.block(3, 4, 0xA3)
    reader.expect(0)
    reader.marker(3)
    parameters = {}
    types = {'bool': (0x1000, 0xC0, '?'), 'int': (0x1001, 0xC5, 'i'),
             'int2': (0x1001, 0xC5, 'ii'), 'float': (0x1002, 0xCA, 'f'),
             'float2': (0x1002, 0xCA, 'ff'), 'float3': (0x1002, 0xCA, 'fff'),
             'float4': (0x1002, 0xCA, 'ffff')}
    for _ in range(reader.count(256)):
        parameter = reader.block(4, 4, 0xA3)
        name, kind = reader.string(0xA3), reader.string(4)
        if name in parameters or kind not in types:
            raise FormatError('Duplicate or unsupported material-definition parameter')
        reader.expect(1)
        block_type, marker, fmt = types[kind]
        value = reader.block(block_type, 1, marker)
        reader.expect(len(fmt))
        values = struct.unpack('<'+fmt, reader.read(struct.calcsize('<'+fmt)))
        if any(isinstance(part, float) and not math.isfinite(part) for part in values):
            raise FormatError('Non-finite material-definition parameter')
        parameters[name] = list(values)
        reader.finish(value)
        reader.marker(4)
        reader.expect(0)
        reader.finish(parameter)
    reader.marker(3)
    for _ in range(reader.count(64)):
        texture = reader.block(0x2000, 3, 0xA3)
        reader.string(0x35)
        reader.integer()
        reader.marker(0x35)
        reader.integer()
        reader.finish(texture)
    for parent in (lists, body, file):
        reader.marker(4)
        reader.expect(0)
        reader.finish(parent)
    if reader.at != len(data):
        raise FormatError('Trailing material-definition data')
    return {'shader': shader, 'parameters': parameters}


@lru_cache(maxsize=4)
def _binder(path, stamp):
    with Path(path).open('rb') as stream:
        raw = read_bounded(stream, MAX_BINDER+1)
    if len(raw) > MAX_BINDER:
        raise FormatError('Material binder is too large')
    plain = inflate(raw, max_size=MAX_BINDER) if raw.startswith(b'DCX\0') else raw
    return plain, members(plain)


@lru_cache(maxsize=128)
def definition(path, stamp, name):
    """A named definition, or None when that binder does not contain it."""
    plain, entries = _binder(path, stamp)
    entry = entries.get(name)
    return None if entry is None else read(plain[entry.offset:entry.offset+entry.size])
