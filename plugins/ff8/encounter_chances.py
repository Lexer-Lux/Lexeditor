"""Build the supported game's in-place world encounter probability Hext patch.

The caller must supply a loaded group-data extension: a default eight-word
record followed by one eight-word record per normal group, each totalling 256.
This module never writes the executable or chooses a storage location.
"""
from hashlib import sha256
import struct

from .executable_text import SUPPORTED_EXE_SHA256

SELECTOR_START, SELECTOR_END = 0x541E2D, 0x541EDF
DEFAULT_OUTCOMES = (38, 37, 37, 37, 36, 36, 24, 11)
# The next known world-data address is 0x1F9DC40, just beyond this bound
# relative to the wmset load destination 0x1E9DC3C. Never extend across it.
MAX_WMSET_SIZE = 0x100000
_FOOTER = struct.Struct('<8sII32s')
_MAGIC = b'LEXCHN01'
# Authored replacement, not extracted game code. The immediate at offset 50
# locates the caller's weight records relative to the normal group pointer.
# Random counter/shift updates and the one previous-scene retry are preserved.
# Alternative encounter groups use the leading default record. The normal
# group indexes its own 16-byte record after that. Zero-weight slots are
# skipped; a single slot may have all 256 outcomes.
_SELECTOR = bytes.fromhex(
    "8A 1D 61 0A 04 02 C7 45 F4 00 00 00 00 FE 05 62 0A 04 02 "
    "75 03 80 C3 0D 0F B6 05 62 0A 04 02 8A 80 20 5D C7 00 "
    "28 D8 0F B6 C0 8B 15 E8 6B 03 02 81 C2 00 01 00 00 "
    "80 7D FD 04 75 06 66 83 FF 50 7D 08 8D 4E 01 C1 E1 04 "
    "01 CA 31 C9 66 3B 04 4A 72 07 66 2B 04 4A 41 EB F3 "
    "80 7D FD 04 75 14 66 83 FF 50 7C 0E A1 80 00 04 02 "
    "8D 94 F1 80 FD FF FF EB 08 A1 E8 6B 03 02 8D 14 F1 "
    "66 8B 04 50 8B 55 08 66 89 02 66 3B 05 A0 00 04 02 "
    "75 0D FF 45 F4 83 7D F4 02 0F 8C 72 FF FF FF 88 1D "
    "61 0A 04 02 31 D2 88 15 5E 0A 04 02 C7 45 F4 01 00 00 00 EB 00"
)
_WEIGHT_OFFSET = 50
assert len(_SELECTOR) == SELECTOR_END - SELECTOR_START
assert _SELECTOR[_WEIGHT_OFFSET:_WEIGHT_OFFSET+4] == struct.pack('<I', 0x100)


def encode_weights(values: list[int] | tuple[int, ...]) -> bytes:
    """Validate one complete distribution before emitting any payload bytes."""
    if not isinstance(values, (list, tuple)) or len(values) != 8:
        raise ValueError('Encounter probabilities require exactly eight slot weights')
    if any(type(value) is not int or not 0 <= value <= 256 for value in values):
        raise ValueError('Each encounter slot weight must be an integer from 0 to 256')
    if sum(values) != 256:
        raise ValueError('Encounter slot weights must total 256')
    return struct.pack('<8H', *values)


def selector_patch(exe: bytes, weight_offset: int) -> bytes:
    if sha256(exe).hexdigest() != SUPPORTED_EXE_SHA256:
        raise ValueError('Encounter probability patches require the supported English Steam FF8 executable')
    if type(weight_offset) is not int or not 16 <= weight_offset <= 0x7FFFFFFE or weight_offset % 2:
        raise ValueError('Encounter weights require an aligned, bounded group-data offset')
    result = bytearray(_SELECTOR)
    struct.pack_into('<I', result, _WEIGHT_OFFSET, weight_offset)
    return bytes(result)


def build_hext(exe: bytes, weight_offset: int) -> str:
    patch = selector_patch(exe, weight_offset)
    return ('# Lexeditor: per-group initial world encounter chances; previous-scene retry retained.\n'
            f'{SELECTOR_START:X} = {patch.hex(" ").upper()}\n')


def _group_count(value: int) -> int:
    if type(value) is not int or not 1 <= value <= 65536:
        raise ValueError('Encounter weight storage requires a known bounded group count')
    return value


def read_extension(data: bytes, group_count: int) -> tuple[bytes, list[tuple[int, ...]]]:
    """Read only our checksummed trailer; preserve every original game byte."""
    group_count = _group_count(group_count)
    if not isinstance(data, (bytes, bytearray)) or len(data) < 192 or len(data) > MAX_WMSET_SIZE:
        raise ValueError('World encounter data is outside the supported bounded size')
    data = bytes(data)
    if len(data) < _FOOTER.size or data[-_FOOTER.size:-_FOOTER.size+8] != _MAGIC:
        return data, [DEFAULT_OUTCOMES]*group_count
    _, base_size, stored_count, digest = _FOOTER.unpack_from(data, len(data)-_FOOTER.size)
    payload_start = base_size + base_size % 2
    payload_size = (group_count+1)*16
    if (stored_count != group_count or base_size < 192
            or payload_start+payload_size+_FOOTER.size != len(data)
            or data[base_size:payload_start] != b'\0'*(base_size % 2)):
        raise ValueError('Encounter probability extension has invalid bounds or group count')
    payload = data[payload_start:payload_start+payload_size]
    if sha256(payload).digest() != digest:
        raise ValueError('Encounter probability extension checksum does not match')
    if payload[:16] != encode_weights(DEFAULT_OUTCOMES):
        raise ValueError('Alternative encounter groups require the vanilla weight record')
    records = []
    for offset in range(16, len(payload), 16):
        weights = struct.unpack_from('<8H', payload, offset)
        encode_weights(weights)
        records.append(weights)
    return data[:base_size], records


def with_weights(data: bytes, group_count: int, changes: dict[int, list[int]]) -> bytes:
    """Prepare a complete bounded output without touching files or offsets."""
    base, weights = read_extension(data, group_count)
    if not isinstance(changes, dict):
        raise ValueError('Encounter probability changes must be a group-to-weights mapping')
    prepared = []
    for group, values in changes.items():
        if type(group) is not int or not 0 <= group < group_count:
            raise ValueError('Encounter probability group is out of range')
        encode_weights(values)
        prepared.append((group, tuple(values)))
    for group, values in prepared:
        weights[group] = values
    if all(record == DEFAULT_OUTCOMES for record in weights):
        return base
    payload = encode_weights(DEFAULT_OUTCOMES) + b''.join(encode_weights(record) for record in weights)
    result_size = len(base)+len(base)%2+len(payload)+_FOOTER.size
    if result_size > MAX_WMSET_SIZE:
        raise ValueError('Encounter probability extension exceeds the bounded world-data space')
    return (base + b'\0'*(len(base)%2) + payload
            + _FOOTER.pack(_MAGIC, len(base), group_count, sha256(payload).digest()))


def extension_offset(data: bytes, group_count: int, group_start: int) -> int | None:
    base, _ = read_extension(data, group_count)
    if len(base) == len(data):
        return None
    if type(group_start) is not int or not 192 <= group_start < len(base) or group_start % 2:
        raise ValueError('Encounter probability source has an invalid group-data offset')
    return len(base)+len(base)%2-group_start
