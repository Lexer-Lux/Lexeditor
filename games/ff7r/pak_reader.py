"""Read entries directly from FF7R's installed PAK archives.

The pinned `repak` helper cannot read this game's archives. FF7R ships PAK
version 4, which predates Unreal's named compression table, so repak assumes a
dense three-slot list of Zlib, Gzip and Oodle. Version 4 actually stores the
field as the legacy bitflag, where 1 is Zlib, 2 is Gzip and 4 is Custom, and
FF7R uses Custom for Oodle. repak converts the stored value with ``n - 1``, so a
stored 4 becomes slot 3 and indexes past its own table, which panics. Every
compressed entry hits this: of 72,214 entries in one shipped archive, 65,909
are stored with compression 4 and only 6,305 are uncompressed.

This module reads the index and entry payloads itself so the plugin does not
depend on that defect being fixed upstream. repak stays responsible for
listing, packing and archive info, which it performs correctly.

Oodle payloads are decoded through the Oodle shared library already required by
`oodle_loader`, or the copy the game itself ships. No decoder is bundled here.
"""

from __future__ import annotations

import ctypes
import struct
import threading
import zlib
from dataclasses import dataclass
from pathlib import Path

from .tooling import FF7R_AES_KEY, repak_path

PAK_MAGIC = 0x5A6F12E1
# Legacy bitflag values, not indices into a table.
COMPRESSION_NONE = 0
COMPRESSION_ZLIB = 1
COMPRESSION_GZIP = 2
COMPRESSION_CUSTOM = 4
SUPPORTED_VERSIONS = (4,)
_ENTRY_HASH_SIZE = 20
_AES_BLOCK = 16

_OODLE_NAMES = ("oo2core_9_win64.dll", "oo2core_7_win64.dll")
_oodle_lock = threading.Lock()
_oodle = None
_index_cache: dict[tuple[str, int, int], dict[str, "Entry"]] = {}
_index_lock = threading.Lock()


class PakError(RuntimeError):
    """The archive could not be read."""


@dataclass(frozen=True)
class Entry:
    name: str
    offset: int
    compressed: int
    uncompressed: int
    compression: int
    blocks: tuple[tuple[int, int], ...]
    encrypted: bool
    block_size: int


def _aes_key() -> bytes:
    text = FF7R_AES_KEY[2:] if FF7R_AES_KEY.lower().startswith("0x") else FF7R_AES_KEY
    return bytes.fromhex(text)


def _decrypt(data: bytes) -> bytes:
    if len(data) % _AES_BLOCK:
        raise PakError("encrypted region is not a whole number of AES blocks")
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    decryptor = Cipher(algorithms.AES(_aes_key()), modes.ECB()).decryptor()
    return decryptor.update(data) + decryptor.finalize()


def oodle_library() -> Path | None:
    """Locate an Oodle shared library without downloading one."""
    for name in _OODLE_NAMES:
        candidate = repak_path().with_name(name)
        if candidate.is_file():
            return candidate
    return None


def _oodle_decompress(payload: bytes, expected: int) -> bytes:
    global _oodle
    with _oodle_lock:
        if _oodle is None:
            library = oodle_library()
            if library is None:
                raise PakError(
                    "An Oodle library is required to read this archive. Place "
                    f"one of {', '.join(_OODLE_NAMES)} beside repak."
                )
            handle = ctypes.WinDLL(str(library))
            function = handle.OodleLZ_Decompress
            function.restype = ctypes.c_size_t
            function.argtypes = [
                ctypes.c_char_p, ctypes.c_size_t, ctypes.c_char_p, ctypes.c_size_t,
                ctypes.c_int, ctypes.c_int, ctypes.c_int,
                ctypes.c_void_p, ctypes.c_size_t,
                ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                ctypes.c_int,
            ]
            _oodle = function
    buffer = ctypes.create_string_buffer(expected + 64)
    # fuzzSafe on, no CRC check, silent, default decoder memory, threadPhase all.
    written = _oodle(payload, len(payload), buffer, expected,
                     1, 0, 0, None, 0, None, None, None, 0, 3)
    if written != expected:
        raise PakError(f"Oodle returned {written} bytes, expected {expected}")
    return buffer.raw[:expected]


def _read_string(data: bytes, offset: int) -> tuple[str, int]:
    length = struct.unpack_from("<i", data, offset)[0]
    offset += 4
    if length >= 0:
        text = data[offset:offset + max(0, length - 1)].decode("latin1")
        return text, offset + length
    count = -length
    text = data[offset:offset + count * 2].decode("utf-16-le")[:-1]
    return text, offset + count * 2


def _read_entry(data: bytes, offset: int, name: str) -> tuple[Entry, int]:
    start, compressed, uncompressed = struct.unpack_from("<QQQ", data, offset)
    offset += 24
    compression = struct.unpack_from("<I", data, offset)[0]
    offset += 4 + _ENTRY_HASH_SIZE
    blocks: list[tuple[int, int]] = []
    if compression != COMPRESSION_NONE:
        count = struct.unpack_from("<I", data, offset)[0]
        offset += 4
        for _ in range(count):
            blocks.append(struct.unpack_from("<QQ", data, offset))
            offset += 16
    flags = data[offset]
    offset += 1
    block_size = struct.unpack_from("<I", data, offset)[0]
    offset += 4
    return Entry(name, start, compressed, uncompressed, compression,
                 tuple(blocks), bool(flags & 1), block_size), offset


def read_index(pak: Path) -> dict[str, Entry]:
    """Parse and cache one archive's entry index."""
    pak = Path(pak)
    stat = pak.stat()
    key = (str(pak.resolve()), stat.st_size, int(stat.st_mtime))
    with _index_lock:
        cached = _index_cache.get(key)
    if cached is not None:
        return cached

    with pak.open("rb") as handle:
        handle.seek(stat.st_size - 45)
        footer = handle.read(45)
        encrypted_index = footer[0]
        magic, version = struct.unpack_from("<II", footer, 1)
        index_offset, index_size = struct.unpack_from("<QQ", footer, 9)
        if magic != PAK_MAGIC:
            raise PakError(f"{pak.name} is not an Unreal PAK archive")
        if version not in SUPPORTED_VERSIONS:
            raise PakError(f"{pak.name} uses unsupported PAK version {version}")
        handle.seek(index_offset)
        raw = handle.read(index_size)

    index = _decrypt(raw) if encrypted_index else raw
    mount, offset = _read_string(index, 0)
    count = struct.unpack_from("<I", index, offset)[0]
    offset += 4
    entries: dict[str, Entry] = {}
    for _ in range(count):
        name, offset = _read_string(index, offset)
        entry, offset = _read_entry(index, offset, name)
        entries[name.replace("\\", "/")] = entry

    with _index_lock:
        _index_cache[key] = entries
    return entries


def _decompress_block(entry: Entry, payload: bytes, expected: int) -> bytes:
    if entry.compression == COMPRESSION_ZLIB:
        return zlib.decompress(payload)
    if entry.compression == COMPRESSION_GZIP:
        return zlib.decompress(payload, 16 + zlib.MAX_WBITS)
    if entry.compression == COMPRESSION_CUSTOM:
        return _oodle_decompress(payload, expected)
    raise PakError(f"unsupported compression value {entry.compression}")


def read_file(pak: Path, internal_path: str) -> bytes:
    """Return one entry's bytes, decompressing and decrypting as needed."""
    pak = Path(pak)
    name = internal_path.replace("\\", "/")
    entries = read_index(pak)
    entry = entries.get(name)
    if entry is None:
        # Callers may pass the full cooked path including the mount point.
        for prefix in ("End/Content/GameContents/",):
            if name.startswith(prefix):
                entry = entries.get(name[len(prefix):])
                if entry is not None:
                    break
    if entry is None:
        raise PakError(f"{internal_path} is not in {pak.name}")

    with pak.open("rb") as handle:
        if entry.compression == COMPRESSION_NONE:
            # The entry header is repeated at the payload offset.
            handle.seek(entry.offset)
            header = handle.read(4096)
            _, consumed = _read_entry(header, 0, entry.name)
            handle.seek(entry.offset + consumed)
            data = handle.read(entry.compressed)
            if entry.encrypted:
                padded = (len(data) + _AES_BLOCK - 1) // _AES_BLOCK * _AES_BLOCK
                data = _decrypt(data.ljust(padded, b"\0"))
            return data[:entry.uncompressed]

        out = bytearray()
        for start, end in entry.blocks:
            # Block bounds are absolute file offsets in this PAK version.
            handle.seek(start)
            payload = handle.read(end - start)
            if entry.encrypted:
                padded = (len(payload) + _AES_BLOCK - 1) // _AES_BLOCK * _AES_BLOCK
                payload = _decrypt(payload.ljust(padded, b"\0"))
            expected = min(entry.block_size, entry.uncompressed - len(out))
            out += _decompress_block(entry, payload, expected)
        if len(out) != entry.uncompressed:
            raise PakError(
                f"{internal_path} decoded to {len(out)} bytes, expected {entry.uncompressed}"
            )
        return bytes(out)
