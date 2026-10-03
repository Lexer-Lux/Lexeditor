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
