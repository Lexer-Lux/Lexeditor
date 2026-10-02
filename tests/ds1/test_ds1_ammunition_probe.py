"""Synthetic safety/slot tests. No retail asset is bundled or required."""
from __future__ import annotations

import contextlib
import ctypes
import importlib.util
import io
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock

TOOL = Path(__file__).resolve().parents[2] / "tools" / "ds1_ammunition_probe.py"
spec = importlib.util.spec_from_file_location("ds1_ammunition_probe", TOOL)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def synthetic_pe() -> bytearray:
    data = bytearray(0x600)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 0x80)
    data[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<HH", data, 0x84, 0x8664, 2)
    struct.pack_into("<H", data, 0x94, 0xF0)
    struct.pack_into("<H", data, 0x98, 0x20B)
    struct.pack_into("<Q", data, 0xB0, 0x140000000)
    struct.pack_into("<I", data, 0xD0, 0x4000)
    for offset, rva, raw in ((0x188, 0x1000, 0x200), (0x1B0, 0x3000, 0x400)):
        data[offset:offset + 8] = b".text\0\0\0"
        struct.pack_into("<IIII", data, offset + 8, 0x300, rva, 0x200, raw)
    data[0x200:0x204] = b"ONE!"
    data[0x400:0x404] = b"TWO!"
    return data


class FakeMemory:
    base = 0x140000000
    singleton = 0x200000
    player = 0x300000
    table1 = 0x400000
    table2 = 0x500000

    def __init__(self):
        self.memory = {}
        self.reads = []
        self.put(self.base + probe.GAME_DATA_RVA, "<Q", self.singleton)
        self.put(self.singleton + 0x10, "<Q", self.player)
        self.equip = self.player + 0x280
        self.write(self.equip, bytes(0x160))
        self.put(self.equip + 0x130, "<i", 8)
        self.put(self.equip + 0x140, "<i", 2)
        self.put(self.equip + 0x150, "<Q", self.table1)
        self.put(self.equip + 0x158, "<Q", self.table2)
        for index, (_, slot) in enumerate(probe.SLOTS):
            self.put(self.equip + 0xA4 + slot * 4, "<i", 1000 + index)
            self.put(self.equip + 0x24 + slot * 4, "<i", index)
            table = self.table1 if index < 2 else self.table2
            self.put(table + index * 0x1C + 8, "<i", 10 + index)
        # Decoys catch the tempting but incorrect (index - split) addressing.
        self.put(self.table2 + 8, "<i", 9876)
        self.put(self.table2 + 0x1C + 8, "<i", 9877)

    def write(self, address, data):
        self.memory.update((address + index, byte) for index, byte in enumerate(data))

    def put(self, address, fmt, value):
        self.write(address, struct.pack(fmt, value))

    def read(self, address, size):
        self.reads.append((address, size))
        try:
            return bytes(self.memory[address + index] for index in range(size))
        except KeyError as error:
            raise probe.ProbeError("Synthetic unmapped address") from error

    def sample(self):
        return probe.sample_ammunition(self.read, self.base)


class PEChecks(unittest.TestCase):
    def test_duplicate_section_names_resolve_by_rva(self):
        image = probe.PEImage(bytes(synthetic_pe()))
        self.assertEqual(image.read_rva(0x1000, 4), b"ONE!")
        self.assertEqual(image.read_rva(0x3000, 4), b"TWO!")

    def test_virtual_tail_is_not_raw_data(self):
        image = probe.PEImage(bytes(synthetic_pe()))
        for rva, size in ((0x1200, 4), (0x11FF, 2), (-1, 1), (0x1000, 0)):
            with self.subTest(rva=rva, size=size), self.assertRaises(probe.ProbeError):
                image.read_rva(rva, size)

    def test_truncated_headers(self):
        data = synthetic_pe()
        for size in (0, 1, 0x3F, 0x83, 0x97, 0x187, 0x1D7, 0x5FF):
            with self.subTest(size=size), self.assertRaises(probe.ProbeError):
                probe.PEImage(bytes(data[:size]))

    def test_wrong_machine_or_magic(self):
        for offset, value in ((0x84, 0x14C), (0x98, 0x10B), (0x86, 0), (0x86, 97)):
            data = synthetic_pe()
            struct.pack_into("<H", data, offset, value)
            with self.subTest(offset=offset, value=value), self.assertRaises(probe.ProbeError):
                probe.PEImage(bytes(data))

    def test_bad_signatures(self):
        for offset in (0, 0x80):
            data = synthetic_pe()
            data[offset] = 0
            with self.subTest(offset=offset), self.assertRaises(probe.ProbeError):
                probe.PEImage(bytes(data))

    def test_section_overlaps_or_overflows(self):
        for offset, value in ((0x1BC, 0x1100), (0x1C4, 0x210),
                              (0x1BC, 0x4000), (0x1C4, 0xFFFFFFFF)):
            data = synthetic_pe()
            struct.pack_into("<I", data, offset, value)
            with self.subTest(offset=offset), self.assertRaises(probe.ProbeError):
                probe.PEImage(bytes(data))

    def test_unknown_file_refused_and_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "DarkSoulsRemastered.exe"
            before = bytes(synthetic_pe())
            path.write_bytes(before)
            with self.assertRaisesRegex(probe.ProbeError, "Unrecognized"):
                probe.inspect_executable(path)
            self.assertEqual(path.read_bytes(), before)

    def test_cli_unknown_build_never_attaches(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "DarkSoulsRemastered.exe"
            path.write_bytes(synthetic_pe())
            output = io.StringIO()
            with mock.patch.object(probe, "WindowsReader") as attach, contextlib.redirect_stdout(output):
                self.assertEqual(probe.main([str(path), "--pid", "1234"]), 2)
            attach.assert_not_called()
            self.assertIs(json.loads(output.getvalue())["gameplayPatchImplemented"], False)

    def test_file_size_is_bounded(self):
        with mock.patch.object(Path, "open", return_value=io.BytesIO(b"x" * 33)), \
                mock.patch.object(probe, "MAX_FILE", 32):
            with self.assertRaisesRegex(probe.ProbeError, "limit"):
                probe.inspect_executable(Path("synthetic.exe"))


class SlotChecks(unittest.TestCase):
    def test_reads_four_distinct_slots_without_mutation(self):
        memory = FakeMemory()
        original = memory.memory.copy()
        result = memory.sample()
        self.assertEqual([s["rawSlot"] for s in result["slots"]], [4, 6, 5, 7])
        self.assertEqual([s["itemId"] for s in result["slots"]], [1000, 1001, 1002, 1003])
        self.assertEqual([s["quantity"] for s in result["slots"]], [10, 11, 12, 13])
        self.assertEqual(original, memory.memory)
        self.assertFalse(result["atomic"])

    def test_selected_ammo_is_not_the_slot_binding(self):
        memory = FakeMemory()
        before = memory.sample()
        for offset in (0x94, 0x98, 0x9C, 0xA0):
            memory.put(memory.equip + offset, "<i", 1)
        self.assertEqual(memory.sample(), before)

    def test_zero_is_different_from_unequipped_and_missing(self):
        memory = FakeMemory()
        memory.put(memory.table1 + 8, "<i", 0)
        memory.put(memory.equip + 0xA4 + 6 * 4, "<i", -1)
        memory.put(memory.equip + 0x24 + 5 * 4, "<i", -1)
        slots = memory.sample()["slots"]
        self.assertEqual([(s["state"], s["quantity"]) for s in slots],
                         [("empty", 0), ("unequipped", None),
                          ("missingInventory", None), ("equipped", 13)])

    def test_shared_inventory_entry_is_reported_in_each_slot(self):
        memory = FakeMemory()
        memory.put(memory.equip + 0x24 + 6 * 4, "<i", 0)
        memory.put(memory.equip + 0xA4 + 6 * 4, "<i", 1000)
        slots = memory.sample()["slots"]
        self.assertEqual((slots[0]["quantity"], slots[1]["quantity"]), (10, 10))

    def test_out_of_bounds_inventory_index_has_no_fallback(self):
        memory = FakeMemory()
        for value in (-2, 8, 0x7FFFFFFF):
            memory.put(memory.equip + 0x24 + 4 * 4, "<i", value)
            slot = memory.sample()["slots"][0]
            self.assertEqual(slot["state"], "missingInventory")
            self.assertIsNone(slot["quantity"])

    def test_invalid_inventory_bounds(self):
        for count, split in ((-1, 0), (8, -1), (8, 1_000_001), (1_000_001, 2)):
            memory = FakeMemory()
            memory.put(memory.equip + 0x130, "<i", count)
            memory.put(memory.equip + 0x140, "<i", split)
            with self.subTest(count=count, split=split), self.assertRaises(probe.ProbeError):
                memory.sample()

    def test_split_above_count_still_uses_first_table(self):
        memory = FakeMemory()
        memory.put(memory.equip + 0x130, "<i", 1)
        memory.put(memory.equip + 0x140, "<i", 2)
        slots = memory.sample()["slots"]
        self.assertEqual(slots[0]["quantity"], 10)
        self.assertEqual(slots[1]["state"], "missingInventory")

    def test_null_or_invalid_tables_refused(self):
        for table in (0, 1, 0xFFFFFFFFFFFFFFF0):
            memory = FakeMemory()
            memory.put(memory.equip + 0x158, "<Q", table)
            with self.subTest(table=table), self.assertRaises(probe.ProbeError):
                memory.sample()

    def test_negative_quantity_and_invalid_id_refused(self):
        for address, value in ((FakeMemory.table1 + 8, -1),
                               (FakeMemory.player + 0x280 + 0xA4 + 16, -2)):
            memory = FakeMemory()
            memory.put(address, "<i", value)
            with self.subTest(address=address), self.assertRaises(probe.ProbeError):
                memory.sample()

    def test_null_roots_are_not_reported_as_empty_ammo(self):
        for address in (FakeMemory.base + probe.GAME_DATA_RVA, FakeMemory.singleton + 0x10):
            memory = FakeMemory()
            memory.put(address, "<Q", 0)
            with self.subTest(address=address):
                self.assertEqual(memory.sample(), {"state": "noPlayerData", "slots": []})

    def test_short_and_invalid_reads(self):
        for address, size in ((0, 4), (0x10000, 0), (0x10000, 4097),
                              (0x7FFFFFFFFFFF, 8)):
            with self.subTest(address=address, size=size), self.assertRaises(probe.ProbeError):
                probe.read_exact(lambda *_: b"", address, size)
        with self.assertRaisesRegex(probe.ProbeError, "Incomplete"):
            probe.read_exact(lambda *_: b"\0", 0x10000, 4)

    def test_changing_sample_has_bounded_retries(self):
        memory = FakeMemory()
        calls = 0

        def unstable(address, size):
            nonlocal calls
            if address == memory.table1 + 8:
                calls += 1
                memory.put(address, "<i", calls)
            return memory.read(address, size)

        with self.assertRaisesRegex(probe.ProbeError, "changed"):
            probe.sample_ammunition(unstable, memory.base)
        self.assertEqual(calls, 6)

    def test_same_counts_do_not_hide_changed_inventory_identity(self):
        memory = FakeMemory()
        memory.put(memory.table1 + 0x1C + 8, "<i", 10)
        original = probe._sample(memory.read, memory.base)
        memory.put(memory.equip + 0x24 + 4 * 4, "<i", 1)
        replacement = probe._sample(memory.read, memory.base)
        self.assertNotEqual(original, replacement)


class TransportChecks(unittest.TestCase):
    def test_non_windows_refused_before_loading_api(self):
        path = Path("DarkSoulsRemastered.exe")
        with mock.patch.object(probe.os, "name", "posix"):
            with self.assertRaisesRegex(probe.ProbeError, "64-bit Python on Windows"):
                probe.WindowsReader(1234, path)

    def test_close_is_idempotent(self):
        reader = probe.WindowsReader.__new__(probe.WindowsReader)
        reader.handle, reader.api = 123, mock.Mock()
        reader.close()
        reader.close()
        reader.api.CloseHandle.assert_called_once_with(123)

    def test_closed_reader_refuses_read(self):
        reader = probe.WindowsReader.__new__(probe.WindowsReader)
        reader.handle = None
        with self.assertRaisesRegex(probe.ProbeError, "closed"):
            reader.read(0x10000, 4)

    def test_windows_transport_reads_own_process_only(self):
        if os.name != "nt":
            self.skipTest("Windows transport, not installed-game acceptance")
        # Exercise WinAPI signatures, module enumeration, RPM and handle lifetime
        # on CI's OWN Python process. Mock game identity/build checks only here.
        import sys
        expected = Path(sys.executable)
        sentinel = ctypes.create_string_buffer(b"read-only sentinel")
        same_path = probe._same_path
        with mock.patch.object(probe, "_same_path", side_effect=lambda left, _right:
                               same_path(left, expected)), \
                mock.patch.object(probe, "inspect_executable", return_value={}), \
                mock.patch.object(probe, "GUARDS", ()):
            with probe.WindowsReader(os.getpid(), Path("DarkSoulsRemastered.exe")) as reader:
                self.assertGreater(reader.base, 0)
                self.assertEqual(reader.read(ctypes.addressof(sentinel), ctypes.sizeof(sentinel)), sentinel.raw)
            self.assertIsNone(reader.handle)

    def test_windows_structure_layout(self):
        if os.name != "nt":
            self.skipTest("Windows WCHAR/DWORD ABI")
        self.assertEqual(ctypes.sizeof(probe.ModuleEntry), 1080)
        self.assertEqual(probe.ModuleEntry.modBaseAddr.offset, 24)
        self.assertEqual(probe.ModuleEntry.szExePath.offset, 560)


class PrivateFixtureCheck(unittest.TestCase):
    def test_explicit_private_executable(self):
        path = os.environ.get("LEXEDITOR_DS1_PROBE_EXE")
        if not path:
            self.skipTest("No explicit private executable; synthetic tests cover CI")
        report = probe.inspect_executable(Path(path))
        self.assertTrue(report["recognizedBuild"])
        self.assertEqual(report["size"], 50_286_344)
        self.assertFalse(report["gameplayPatchImplemented"])


if __name__ == "__main__":
    unittest.main()
