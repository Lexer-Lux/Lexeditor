"""Cover the FF7R PAK reader without requiring an installed game.

Synthetic version 4 archives are built here in the shapes the reader must
handle. The Oodle path needs a proprietary library and a real archive, so it is
exercised only by the installed-game test, which skips when FF7R is absent.
"""

from __future__ import annotations

import os
from pathlib import Path
import struct
import sys
import unittest
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from games.ff7r import pak_reader
from games.ff7r.pak_reader import PakError, read_file, read_index

MOUNT = "../../../End/Content/GameContents/"
BLOCK_SIZE = 0x10000


def _string(text: str) -> bytes:
    raw = text.encode("latin1") + b"\0"
    return struct.pack("<i", len(raw)) + raw


def _entry_header(offset, compressed, uncompressed, compression, blocks, encrypted,
                  block_size=BLOCK_SIZE) -> bytes:
    out = struct.pack("<QQQ", offset, compressed, uncompressed)
    out += struct.pack("<I", compression)
    out += b"\0" * 20
    if compression:
        out += struct.pack("<I", len(blocks))
        for start, end in blocks:
            out += struct.pack("<QQ", start, end)
    out += bytes([1 if encrypted else 0])
    out += struct.pack("<I", block_size)
    return out


def _encrypt(data: bytes) -> bytes:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    encryptor = Cipher(algorithms.AES(pak_reader._aes_key()), modes.ECB()).encryptor()
    return encryptor.update(data) + encryptor.finalize()


def build_pak(path: Path, files: dict[str, tuple[bytes, int]], *,
              encrypt_index: bool = False, version: int = 4) -> Path:
    """Write one synthetic archive; each file maps to (payload, compression)."""
    body = bytearray()
    placed: dict[str, tuple[int, bytes]] = {}
    for name, (payload, compression) in files.items():
        offset = len(body)
        if compression == pak_reader.COMPRESSION_NONE:
            stored, blocks = payload, ()
        elif compression == pak_reader.COMPRESSION_ZLIB:
            stored = zlib.compress(payload)
            blocks = None  # placed below once the data offset is known
        else:
            raise AssertionError("fixtures cover only stored and zlib entries")
        header_len = len(_entry_header(offset, len(stored), len(payload), compression,
                                       ((0, 0),) if blocks is None else (), False))
        data_at = offset + header_len
        real_blocks = ((data_at, data_at + len(stored)),) if blocks is None else ()
        header = _entry_header(offset, len(stored), len(payload), compression,
                               real_blocks, False)
        body += header + stored
        placed[name] = (offset, header)

    index = bytearray(_string(MOUNT) + struct.pack("<I", len(files)))
    for name, (offset, header) in placed.items():
        index += _string(name) + header
    raw_index = bytes(index)
    if encrypt_index:
        raw_index = _encrypt(raw_index.ljust((len(raw_index) + 15) // 16 * 16, b"\0"))

    with path.open("wb") as handle:
        handle.write(body)
        index_offset = handle.tell()
        handle.write(raw_index)
        handle.write(bytes([1 if encrypt_index else 0]))
        handle.write(struct.pack("<II", pak_reader.PAK_MAGIC, version))
        handle.write(struct.pack("<QQ", index_offset, len(raw_index)))
        handle.write(b"\0" * 20)
    return path


class PakReaderTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.root = Path(tempfile.mkdtemp(prefix="ff7r-pak-"))
        pak_reader._index_cache.clear()

    def test_stored_entry_round_trips(self):
        payload = os.urandom(5000)
        pak = build_pak(self.root / "stored.pak", {"A/B.uasset": (payload, 0)})
        self.assertEqual(read_file(pak, "A/B.uasset"), payload)

    def test_zlib_entry_is_decompressed(self):
        payload = b"repeating data " * 900
        pak = build_pak(self.root / "zlib.pak", {"A/B.uexp": (payload, 1)})
        self.assertEqual(read_file(pak, "A/B.uexp"), payload)

    def test_encrypted_index_is_decrypted(self):
        payload = os.urandom(64)
        pak = build_pak(self.root / "enc.pak", {"A/C.uasset": (payload, 0)},
                        encrypt_index=True)
        self.assertEqual(read_file(pak, "A/C.uasset"), payload)

    def test_index_lists_every_entry(self):
        pak = build_pak(self.root / "many.pak", {
            "A/One.uasset": (b"one", 0),
            "A/Two.uasset": (b"two", 0),
        })
        self.assertEqual(sorted(read_index(pak)), ["A/One.uasset", "A/Two.uasset"])

    def test_mount_point_prefix_is_accepted(self):
        payload = b"prefixed"
        pak = build_pak(self.root / "prefix.pak", {"Menu/D.uasset": (payload, 0)})
        self.assertEqual(
            read_file(pak, "End/Content/GameContents/Menu/D.uasset"), payload)

    def test_missing_entry_is_reported(self):
        pak = build_pak(self.root / "missing.pak", {"A/B.uasset": (b"x", 0)})
        with self.assertRaises(PakError):
            read_file(pak, "A/Absent.uasset")

    def test_unsupported_version_is_refused(self):
        pak = build_pak(self.root / "v8.pak", {"A/B.uasset": (b"x", 0)}, version=8)
        with self.assertRaises(PakError):
            read_index(pak)

    def test_non_pak_is_refused(self):
        path = self.root / "bad.pak"
        path.write_bytes(os.urandom(4096))
        with self.assertRaises(PakError):
            read_index(path)

    def test_compression_four_is_custom_not_a_slot_index(self):
        # The bug this reader exists for: value 4 is the legacy Custom bitflag,
        # not an index into a three-entry Zlib/Gzip/Oodle table.
        self.assertEqual(pak_reader.COMPRESSION_CUSTOM, 4)
        self.assertNotEqual(pak_reader.COMPRESSION_CUSTOM, 3)


class InstalledGameTests(unittest.TestCase):
    """Read the real archives when FF7R is present."""

    def setUp(self):
        from games.ff7r.archive import installed_paks

        root = os.environ.get("FF7R_ROOT")
        candidates = [Path(root)] if root else [
            Path(r"D:\SteamLibrary\steamapps\common\FINAL FANTASY VII REMAKE"),
            Path(r"C:\Program Files (x86)\Steam\steamapps\common\FINAL FANTASY VII REMAKE"),
        ]
        self.root = next((p for p in candidates if p.is_dir()), None)
        if self.root is None:
            self.skipTest("FF7R is not installed")
        self.paks = installed_paks(self.root)
        if not self.paks:
            self.skipTest("no installed FF7R archives")

    def test_oodle_entry_decodes_to_a_cooked_package(self):
        if pak_reader.oodle_library() is None:
            self.skipTest("no Oodle library beside repak")
        from games.ff7r.tooling import get_file

        target = "Menu/Resident/Battle/Status.uasset"
        for pak in self.paks:
            try:
                entries = read_index(pak)
            except PakError:
                continue
            entry = entries.get(target)
            if entry is None:
                continue
            self.assertEqual(entry.compression, pak_reader.COMPRESSION_CUSTOM)
            data = get_file(pak, target)
            self.assertEqual(len(data), entry.uncompressed)
            self.assertEqual(data[:4], bytes.fromhex("c1832a9e"))
            return
        self.skipTest(f"{target} is not in the installed archives")


if __name__ == "__main__":
    unittest.main()
