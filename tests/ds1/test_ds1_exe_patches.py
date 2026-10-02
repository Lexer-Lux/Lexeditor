"""The DS1 executable combiner places, relocates and merges tweak patches safely.

Runs against a small synthetic PE32+ so it needs no game files: the real
build's fingerprint is swapped for the synthetic one for each test.
"""
from __future__ import annotations

import hashlib
import struct
import unittest
from unittest import mock

from plugins.ds1 import exe_patches

NT = 0x80
OPTIONAL = NT + 24
SECTIONS = OPTIONAL + 0xF0
LAYOUT = [  # name, rva, vsize, raw, raw size, flags
    (b".text", 0x1000, 0x1000, 0x400, 0x1000, 0x60000020),
    (b".data", 0x2000, 0x100, 0x1400, 0x200, 0xC0000040),
    (b".pdata", 0x3000, 0x18, 0x1600, 0x200, 0x40000040),
    (b".text", 0x4000, 0x1000, 0x1800, 0x1000, 0x60000020),
]
CERT = (0x2800, 0x40)
HOOK_A, HOOK_B = 0x1200, 0x1300
UNWIND = 0x1100


def synthetic() -> bytes:
    data = bytearray(CERT[0] + CERT[1])
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, NT)
    data[NT:NT + 4] = b"PE\0\0"
    struct.pack_into("<HH", data, NT + 4, 0x8664, len(LAYOUT))
    struct.pack_into("<H", data, NT + 20, 0xF0)
    struct.pack_into("<H", data, OPTIONAL, 0x20B)
    struct.pack_into("<II", data, OPTIONAL + 32, 0x1000, 0x200)  # section, file alignment
    struct.pack_into("<I", data, OPTIONAL + 108, 16)  # NumberOfRvaAndSizes
    struct.pack_into("<I", data, OPTIONAL + 4, 0x2000)
    struct.pack_into("<I", data, OPTIONAL + 56, 0x5000)
    struct.pack_into("<I", data, OPTIONAL + 64, 0x12345)
    struct.pack_into("<II", data, OPTIONAL + 112 + 3 * 8, 0x3000, 0x18)
    struct.pack_into("<II", data, OPTIONAL + 112 + 4 * 8, *CERT)
    for index, (name, rva, vsize, raw, raw_size, flags) in enumerate(LAYOUT):
        at = SECTIONS + index * 40
        data[at:at + 8] = name.ljust(8, b"\0")
        struct.pack_into("<IIII", data, at + 8, vsize, rva, raw_size, raw)
        struct.pack_into("<I", data, at + 36, flags)
    struct.pack_into("<IIIIII", data, 0x1600, 0x1000, 0x1010, UNWIND, 0x1020, 0x1030, UNWIND)
    data[0x400 + UNWIND - 0x1000] = 0x01
    data[0x400 + HOOK_A - 0x1000:0x400 + HOOK_A - 0x1000 + 5] = bytes.fromhex("E8 00 00 00 00")
    data[0x400 + HOOK_B - 0x1000:0x400 + HOOK_B - 0x1000 + 7] = bytes.fromhex("48 8D 15 00 00 00 00")
    return bytes(data)


VANILLA = synthetic()


# A minimal UNWIND_INFO (version 1, no codes), then the function it covers.
def island(name, code="01000000" + "C3" * 12, **extra):
    return {"name": name, "code": code, "functions": [[4, 12, 0]], **extra}


class CombinerTests(unittest.TestCase):
    def setUp(self):
        for key, value in (("VANILLA_SIZE", len(VANILLA)),
                           ("VANILLA_SHA256", hashlib.sha256(VANILLA).hexdigest())):
            patcher = mock.patch.object(exe_patches, key, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def compose(self, *specs):
        return exe_patches.compose(VANILLA, [exe_patches.validate(spec, f"tweak {i}") for i, spec in enumerate(specs)])

    def test_nothing_enabled_is_the_untouched_original(self):
        self.assertEqual(self.compose(), VANILLA)
        self.assertEqual(self.compose({"version": 1}), VANILLA)

    def test_two_tweaks_share_one_layout(self):
        fixed = {"version": 1, "islands": [island("payload", rva=0x6000)],
                 "hooks": [{"rva": HOOK_A, "original": "E800000000",
                            "branch": {"opcode": "E8", "island": "payload", "offset": 4}}]}
        moving = {"version": 1, "islands": [island("display", code="01000000" + "E8" + "00" * 4 + "C3" * 7,
                                                    relocations=[{"at": 5, "rel32": 0x1000}])],
                  "hooks": [{"rva": HOOK_B, "original": "488D1500000000",
                             "branch": {"opcode": "E9", "island": "display", "offset": 0}, "pad": "9090"}],
                  "sectionVirtualSize": {".data": 0x180}}
        out = self.compose(fixed, moving)
        last = SECTIONS + 3 * 40
        # Islands start past every original byte, the certificate included.
        self.assertEqual(out[0x1800 + 0x6000 - 0x4000:][:16], bytes.fromhex("01000000" + "C3" * 12))
        display = 0x6010
        self.assertEqual(struct.unpack_from("<i", out, 0x1800 + display - 0x4000 + 5)[0], 0x1000 - (display + 9))
        # Hooks branch into their own islands.
        self.assertEqual(out[0x400 + HOOK_A - 0x1000], 0xE8)
        self.assertEqual(struct.unpack_from("<i", out, 0x400 + HOOK_A - 0x1000 + 1)[0], 0x6004 - (HOOK_A + 5))
        hook_b = out[0x400 + HOOK_B - 0x1000:][:7]
        self.assertEqual(hook_b[0], 0xE9)
        self.assertEqual(hook_b[5:], b"\x90\x90")
        self.assertEqual(struct.unpack_from("<i", hook_b, 1)[0], display - (HOOK_B + 5))
        # One exception table: the originals plus both islands, sorted.
        table_rva, table_size = struct.unpack_from("<II", out, OPTIONAL + 112 + 3 * 8)
        rows = list(struct.iter_unpack("<III", out[0x1800 + table_rva - 0x4000:][:table_size]))
        self.assertEqual(rows, [(0x1000, 0x1010, UNWIND), (0x1020, 0x1030, UNWIND),
                                (0x6004, 0x600C, 0x6000), (display + 4, display + 12, display)])
        # Headers describe the one combined layout.
        raw_size = len(out) - 0x1800
        self.assertEqual(len(out) % 0x200, 0)
        self.assertEqual(struct.unpack_from("<II", out, last + 8), (raw_size, 0x4000))
        self.assertEqual(struct.unpack_from("<I", out, last + 16)[0], raw_size)
        image = struct.unpack_from("<I", out, OPTIONAL + 56)[0]
        self.assertEqual(image, (0x4000 + raw_size + 0xFFF) & ~0xFFF)
        self.assertEqual(struct.unpack_from("<I", out, OPTIONAL + 64)[0], 0)
        self.assertEqual(struct.unpack_from("<II", out, OPTIONAL + 112 + 4 * 8), (0, 0))
        self.assertEqual(struct.unpack_from("<I", out, SECTIONS + 40 + 8)[0], 0x180)
        # Every byte nobody declared is unchanged.
        changed = {i for i in range(len(VANILLA)) if out[i] != VANILLA[i]}
        allowed = set(range(0x400 + HOOK_A - 0x1000, 0x400 + HOOK_A - 0x1000 + 5))
        allowed |= set(range(0x400 + HOOK_B - 0x1000, 0x400 + HOOK_B - 0x1000 + 7))
        allowed |= set(range(0x80, SECTIONS + 4 * 40))
        self.assertEqual(changed - allowed, set())

    def test_the_result_is_a_valid_pe(self):
        try:
            import pefile
        except ImportError:
            self.skipTest("pefile is not installed")
        out = self.compose({"version": 1, "islands": [island("payload")]})
        parsed = pefile.PE(data=out)
        starts = [entry.struct.BeginAddress for entry in parsed.DIRECTORY_ENTRY_EXCEPTION]
        self.assertEqual(starts, sorted(starts))
        self.assertIn(0x6004, starts)

    def test_refusals(self):
        cases = {
            "not the vanilla build": lambda: exe_patches.compose(VANILLA[:-1] + b"\1", []),
            "hook site differs": lambda: self.compose({"version": 1, "hooks": [{"rva": HOOK_A, "original": "E900000000", "bytes": "9090909090"}]}),
            "two tweaks, one instruction": lambda: self.compose(
                {"version": 1, "hooks": [{"rva": HOOK_A, "original": "E800000000", "bytes": "9090909090"}]},
                {"version": 1, "hooks": [{"rva": HOOK_A + 1, "original": "00000000", "bytes": "90909090"}]}),
            "fixed islands overlap": lambda: self.compose({"version": 1, "islands": [island("a", rva=0x6000)]},
                                                          {"version": 1, "islands": [island("b", rva=0x6008)]}),
            "fixed island inside the original image": lambda: self.compose({"version": 1, "islands": [island("a", rva=0x4800)]}),
            "replacement longer than the instruction": lambda: self.compose(
                {"version": 1, "hooks": [{"rva": HOOK_A, "original": "E800000000", "bytes": "909090909090"}]}),
            "unwind data is not version 1": lambda: self.compose({"version": 1, "islands": [island("a", code="02000000" + "C3" * 12)]}),
            "section grows into the next": lambda: self.compose({"version": 1, "sectionVirtualSize": {".data": 0x1001}}),
            "unsupported description": lambda: self.compose({"version": 2}),
        }
        for label, action in cases.items():
            with self.subTest(label), self.assertRaises(exe_patches.PatchError):
                action()


if __name__ == "__main__":
    unittest.main()
