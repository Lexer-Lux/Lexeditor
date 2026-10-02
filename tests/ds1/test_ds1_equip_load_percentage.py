"""Synthetic profile, machine-code, and optional private-executable checks."""
from __future__ import annotations

import ctypes
import hashlib
import json
import mmap
import os
from pathlib import Path
import platform
import random
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from plugins.ds1 import equip_load_percentage as tweak
from plugins.ds1 import tweaks as manager


def assembled(source: Path, directory: Path, entry: str):
    obj, elf, binary = (directory / name for name in ("code.o", "code.elf", "code.bin"))
    subprocess.run(["as", "--64", "-o", str(obj), str(source)], check=True, capture_output=True)
    subprocess.run(["ld", "-Ttext=0", "-e", entry, "-o", str(elf), str(obj)],
                   check=True, capture_output=True)
    subprocess.run(["objcopy", "-O", "binary", "-j", ".text", str(elf), str(binary)], check=True)
    listing = subprocess.run(["nm", "-n", str(elf)], check=True, capture_output=True, text=True).stdout
    symbols = {line.split()[-1]: int(line.split()[0], 16)
               for line in listing.splitlines() if len(line.split()) == 3}
    return binary.read_bytes(), symbols


class ProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Generated fixture, not a game executable or copied game bytes.
        original = bytearray(tweak.ORIGINAL_SIZE)
        for offset, value in tweak.HEADER_ORIGINAL.items():
            struct.pack_into("<I", original, offset, value)
        original[tweak.HOOK_OFFSET:tweak.HOOK_OFFSET + 7] = tweak.HOOK_ORIGINAL
        table = tweak.OLD_TABLE_OFFSET
        for i in range(tweak.OLD_TABLE_SIZE // 12):
            struct.pack_into("<III", original, table + i * 12, 0x1000 + i * 16,
                             0x1005 + i * 16, 0x182BFFC)
        cls.original = bytes(original)
        cls.candidate = tweak._enable(cls.original)
        cls.original_hash = tweak.fingerprint(cls.original)
        cls.candidate_hash = tweak.fingerprint(cls.candidate)

    def profile(self):
        return patch.multiple(tweak, ORIGINAL_SHA256=self.original_hash,
                              PATCHED_SHA256=self.candidate_hash)

    def test_roundtrip_and_idempotence(self):
        with self.profile():
            actual = tweak.transform(self.original, True)
            self.assertEqual(actual, self.candidate)
            self.assertIs(tweak.transform(actual, True), actual)
            self.assertEqual(tweak.transform(actual, False), self.original)
            self.assertIs(tweak.transform(self.original, False), self.original)

    def test_unknown_conflicting_and_truncated_inputs_are_rejected(self):
        with self.profile():
            for original in (self.original, self.candidate):
                damaged = bytearray(original)
                damaged[12345] ^= 1
                with self.assertRaises(tweak.UnsupportedBuild):
                    tweak.transform(bytes(damaged), True)
            for blob in (b"", b"MZ", self.original[:-1], self.candidate + b"x"):
                with self.assertRaises(tweak.UnsupportedBuild):
                    tweak.transform(blob, True)

    def test_all_original_bytes_outside_declared_writes_survive(self):
        restored_prefix = bytearray(self.candidate[:len(self.original)])
        for offset in tweak.HEADER_ORIGINAL:
            restored_prefix[offset:offset + 4] = self.original[offset:offset + 4]
        restored_prefix[tweak.HOOK_OFFSET:tweak.HOOK_OFFSET + 7] = tweak.HOOK_ORIGINAL
        self.assertEqual(restored_prefix, self.original)
        self.assertEqual(len(self.candidate), tweak.PATCHED_SIZE)

    def test_original_exception_table_and_chain_survive(self):
        old = self.original[tweak.OLD_TABLE_OFFSET:tweak.OLD_TABLE_OFFSET + tweak.OLD_TABLE_SIZE]
        self.assertEqual(self.candidate[tweak.TABLE_OFFSET:tweak.TABLE_OFFSET + len(old)], old)
        start, end, unwind = struct.unpack_from("<III", self.candidate,
                                                tweak.TABLE_OFFSET + len(old))
        self.assertEqual((start, end, unwind), (
            tweak.ISLAND_RVA, tweak.ISLAND_RVA + tweak.RESUME_DISP + 4, tweak.UNWIND_RVA))
        chain_offset = tweak.ISLAND_OFFSET + tweak.UNWIND_RVA - tweak.ISLAND_RVA
        self.assertEqual(self.candidate[chain_offset:chain_offset + 16], tweak.CHAIN)
        self.assertEqual(struct.unpack_from("<I", self.candidate, 0x224)[0],
                         tweak.OLD_TABLE_SIZE + 12)

    def test_direct_jump_displacements(self):
        jump = self.candidate[tweak.HOOK_OFFSET:tweak.HOOK_OFFSET + 7]
        self.assertEqual(jump[0], 0xE9)
        self.assertEqual(tweak.HOOK_RVA + 5 + struct.unpack_from("<i", jump, 1)[0],
                         tweak.ISLAND_RVA)
        payload = self.candidate[tweak.ISLAND_OFFSET:tweak.ISLAND_OFFSET + len(tweak.ISLAND_TEMPLATE)]
        for offset, target in ((tweak.RESUME_DISP, tweak.RESUME_RVA),
                               (tweak.FALLBACK_DISP, tweak.VANILLA_FORMAT_RVA)):
            self.assertEqual(tweak.ISLAND_RVA + offset + 4 +
                             struct.unpack_from("<i", payload, offset)[0], target)
        self.assertEqual(payload[tweak.FORMAT_OFFSET:].decode("utf-16-le").rstrip("\0"),
                         "%s/%s (%.1f%%)")

    def test_hext_matches_every_native_code_write(self):
        fragment = tweak.build_hext(True)
        found = {}
        for line in fragment.splitlines():
            if not line or line.startswith("#"):
                continue
            address, text = line.split("=", 1)
            address = int(address.strip(), 16)
            for index, value in enumerate(bytes.fromhex(text)):
                found[address + index] = value
        expected = {tweak.IMAGE_BASE + rva + i: value
                    for _, rva, values in tweak.code_writes()
                    for i, value in enumerate(values)}
        self.assertEqual(found, expected)
        self.assertEqual(tweak.build_hext(False), "")

    def test_strict_boolean_and_rel32_guards(self):
        for value in (0, 1, None, "true", [], {}):
            with self.assertRaises(ValueError):
                tweak.build_hext(value)
            with self.assertRaises(ValueError):
                tweak.transform(b"", value)
        with self.assertRaises(ValueError):
            tweak.relocate_island(0, 1 << 40, 0)

    def test_native_header_changes_are_consistent(self):
        for offset, value in tweak.HEADER_PATCHED.items():
            self.assertEqual(struct.unpack_from("<I", self.candidate, offset)[0], value)
        virtual_size = struct.unpack_from("<I", self.candidate, 0x3D0)[0]
        raw_size = struct.unpack_from("<I", self.candidate, 0x3D8)[0]
        self.assertGreaterEqual(raw_size, virtual_size)
        self.assertEqual(raw_size % 512, 0)
        self.assertEqual(struct.unpack_from("<I", self.candidate, 0x1D0)[0] % 4096, 0)


NATIVE_TOOLS = (sys.platform == "linux" and platform.machine().lower() in ("x86_64", "amd64")
                and all(shutil.which(tool) for tool in ("as", "ld", "objcopy", "nm")))


@unittest.skipUnless(NATIVE_TOOLS, "x86-64 Linux GNU assembler test harness")
class MachineCodeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="lexeditor-equip-load-")
        directory = Path(cls.temp.name)
        raw, cls.symbols = assembled(Path(__file__).with_name("equip_load_shim.S"),
                                    directory, "shim_start")
        cls.memory = mmap.mmap(-1, 4096, prot=mmap.PROT_READ | mmap.PROT_WRITE | mmap.PROT_EXEC)
        cls.address = ctypes.addressof(ctypes.c_char.from_buffer(cls.memory))
        code = bytearray(raw)
        start = cls.symbols["shim_patch"]
        code[start:start + len(tweak.ISLAND_TEMPLATE)] = tweak.relocate_island(
            cls.address + start, cls.address + cls.symbols["shim_resume"],
            cls.address + cls.symbols["shim_vanilla"])
        cls.memory.write(code)
        cls.run_patch = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p)(cls.address)
        cls.valid_format = cls.address + start + tweak.FORMAT_OFFSET
        cls.vanilla_format = cls.address + cls.symbols["shim_vanilla"]

    @classmethod
    def tearDownClass(cls):
        cls.run_patch = None
        cls.memory.close()
        cls.temp.cleanup()

    def run_case(self, current, maximum, preview=-1.0, preview_max=-1.0, expected=None):
        snapshot = bytearray(0x120)
        for offset, value in ((0x14, current), (0x18, maximum), (0x40, preview), (0x44, preview_max)):
            struct.pack_into("<f", snapshot, offset, value)
        memory = ctypes.create_string_buffer(bytes(snapshot), len(snapshot))
        result = (ctypes.c_uint64 * 14)()
        self.run_patch(ctypes.addressof(memory), ctypes.addressof(result))
        self.assertEqual(memory.raw, snapshot, "No player/menu snapshot write is permitted")
        self.assertEqual(list(result)[2:9], [
            0x11223344, 0x55667788, 0x13579, 0x24680, 0x13571357, 0x24682468, 0x31415926])
        self.assertEqual(list(result)[9:12], [2**64 - 1] * 3)
        self.assertEqual(result[12], result[13], "RSP must remain unchanged")
        if expected is None:
            self.assertEqual(result[0], self.vanilla_format)
            self.assertEqual(result[1], 2**64 - 1, "Fallback must not invent a fifth argument")
        else:
            self.assertEqual(result[0], self.valid_format)
            actual = struct.unpack("<d", struct.pack("<Q", result[1]))[0]
            self.assertAlmostEqual(actual, expected, delta=max(1e-10, abs(expected) * 1e-14))

    def test_zero_normal_overloaded_and_preview_values(self):
        self.run_case(0, 100, expected=0)
        self.run_case(26.2, 64, expected=100 * struct.unpack("<f", struct.pack("<f", 26.2))[0] / 64)
        self.run_case(120, 100, expected=120)
        self.run_case(10, 80, 20, -1, expected=25)
        self.run_case(10, 80, -1, 100, expected=10)
        self.run_case(10, 80, 30, 120, expected=25)
        self.run_case(10, 80, -0.0, -1, expected=0)

    def test_invalid_values_use_vanilla_without_dividing(self):
        for cur, maximum in ((1, 0), (1, -1), (-1, 100), (float("nan"), 100),
                             (float("inf"), 100), (1, float("nan")), (1, float("inf"))):
            self.run_case(cur, maximum)
        self.run_case(10, 80, 20, 0)
        self.run_case(10, 80, float("nan"), 100)

    def test_random_float32_inputs(self):
        rng = random.Random(872)
        for _ in range(200):
            cur, maximum = (struct.unpack("<f", struct.pack("<f", rng.uniform(.01, 999)))[0]
                            for _ in range(2))
            self.run_case(cur, maximum, expected=100 * cur / maximum)

    def test_assembly_reproduces_checked_in_template(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-equip-asm-") as directory:
            raw, symbols = assembled(ROOT / "plugins/ds1/equip_load_percentage.S",
                                     Path(directory), "patch_start")
        self.assertEqual(raw, tweak.ISLAND_TEMPLATE)
        self.assertEqual(symbols["fallback_disp"], tweak.FALLBACK_DISP)
        self.assertEqual(symbols["resume_disp"], tweak.RESUME_DISP)


class DeploymentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ProfileTests.setUpClass()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="lexeditor-equip-deploy-")
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.game, self.project = self.folder / "game", self.folder / "mod"
        self.game.mkdir()
        self.project.mkdir()
        (self.project / manager.PROJECT_MARKER).touch()
        self.live = self.game / tweak.EXECUTABLE
        self.backup = self.game / manager.BACKUP_FILE
        self.live.write_bytes(ProfileTests.original)
        self.fingerprints = patch.multiple(tweak, ORIGINAL_SHA256=ProfileTests.original_hash,
                                           PATCHED_SHA256=ProfileTests.candidate_hash)
        self.fingerprints.start()
        self.addCleanup(self.fingerprints.stop)
        self.closed = patch.object(manager, "ensure_game_closed")
        self.closed.start()
        self.addCleanup(self.closed.stop)

    def store(self, read_only=False):
        return manager.TweakStore(self.game, self.project, read_only)

    def test_default_is_off_and_reading_creates_nothing(self):
        value = self.store()
        self.assertFalse(value.enabled)
        self.assertEqual(value.dirty_count, 0)
        self.assertTrue(value.snapshot(refresh=True)["available"])
        self.assertEqual(sorted(p.name for p in self.project.iterdir()), [manager.PROJECT_MARKER])
        self.assertFalse(self.backup.exists())

    def test_save_discard_and_reload_do_not_deploy(self):
        value = self.store()
        value.edit(True)
        self.assertEqual(value.dirty_count, 1)
        value.discard()
        self.assertFalse(value.enabled)
        value.edit(True)
        value.save()
        self.assertEqual(value.dirty_count, 0)
        self.assertTrue(self.store().enabled)
        self.assertEqual(self.live.read_bytes(), ProfileTests.original)
        self.assertFalse(self.backup.exists())

    def test_apply_is_explicit_and_restore_keeps_project_setting(self):
        value = self.store()
        value.edit(True)
        with self.assertRaisesRegex(ValueError, "Save or discard"):
            value.apply()
        value.save()
        self.assertTrue(value.apply()["applied"])
        self.assertEqual(self.live.read_bytes(), ProfileTests.candidate)
        self.assertEqual(self.backup.read_bytes(), ProfileTests.original)
        value.apply()
        self.assertEqual(len(list(self.game.iterdir())), 2, "Only one backup")
        value.restore()
        self.assertEqual(self.live.read_bytes(), ProfileTests.original)
        self.assertTrue(value.enabled, "Restore is not a project edit")
        value.edit(False)
        value.save()
        value.apply()
        self.assertEqual(self.live.read_bytes(), ProfileTests.original)

    def test_read_only_project_cannot_edit_save_or_apply(self):
        for value in (self.store(True), manager.TweakStore(self.game, None, False)):
            with self.assertRaises(PermissionError):
                value.edit(True)
            with self.assertRaises(PermissionError):
                value.apply()
            value.enabled = True
            with self.assertRaises(PermissionError):
                value.save()

    def test_vanilla_selection_can_explicitly_remove_installed_patch(self):
        manager.deploy(self.game, True)
        manager.TweakStore(self.game, None, True).restore()
        self.assertEqual(self.live.read_bytes(), ProfileTests.original)

    def test_modified_live_file_is_never_overwritten(self):
        manager.deploy(self.game, True)
        damaged = bytearray(self.live.read_bytes())
        damaged[1234] ^= 1
        self.live.write_bytes(damaged)
        for enabled in (True, False):
            with self.assertRaises(tweak.UnsupportedBuild):
                manager.deploy(self.game, enabled)
            self.assertEqual(self.live.read_bytes(), damaged)
        self.assertFalse(self.store().snapshot(refresh=True)["available"])

    def test_missing_or_changed_backup_refuses_restore(self):
        manager.deploy(self.game, True)
        self.backup.unlink()
        with self.assertRaisesRegex(ValueError, "backup|original"):
            manager.deploy(self.game, False)
        self.backup.write_bytes(b"not an original")
        with self.assertRaises(ValueError):
            manager.deploy(self.game, False)
        self.assertEqual(self.live.read_bytes(), ProfileTests.candidate)

    def test_failed_atomic_install_leaves_live_and_backup_intact(self):
        with patch.object(manager, "atomic_write", side_effect=OSError("locked")):
            with self.assertRaises(OSError):
                manager.deploy(self.game, True)
        self.assertEqual(self.live.read_bytes(), ProfileTests.original)
        self.assertEqual(self.backup.read_bytes(), ProfileTests.original)
        manager.deploy(self.game, True)
        self.assertEqual(self.live.read_bytes(), ProfileTests.candidate)

    def test_external_settings_conflict_is_not_overwritten(self):
        value = self.store()
        value.edit(True)
        path = self.project / manager.SETTING_FILE
        text = json.dumps({"schema": 1, tweak.TWEAK_ID: True})
        path.write_text(text)
        with self.assertRaisesRegex(ValueError, "changed outside"):
            value.save()
        self.assertEqual(path.read_text(), text)
        value.discard()
        self.assertTrue(value.enabled)
        self.assertEqual(value.dirty_count, 0)

    def test_invalid_settings_and_non_boolean_values_are_rejected(self):
        value = self.store()
        for candidate in (0, 1, "", [], {}, None):
            with self.assertRaises(ValueError):
                value.edit(candidate)
        path = self.project / manager.SETTING_FILE
        for candidate in ([], {"schema": 1, tweak.TWEAK_ID: 1},
                          {"schema": 2, tweak.TWEAK_ID: True},
                          {"schema": 1, tweak.TWEAK_ID: True, "unknown": 7}):
            path.write_text(json.dumps(candidate))
            with self.assertRaises(ValueError):
                self.store()
        path.write_bytes(b"x" * 4097)
        with self.assertRaises(ValueError):
            self.store()

    def test_symlink_and_hardlink_are_rejected(self):
        target = self.folder / "alias"
        try:
            target.symlink_to(self.live)
        except OSError:
            pass  # Windows may require developer mode for this part.
        else:
            with self.assertRaisesRegex(ValueError, "symlink"):
                manager.read_executable(target)
            target.unlink()
        os.link(self.live, target)
        with self.assertRaisesRegex(ValueError, "hard link"):
            manager.read_executable(self.live)

    def test_project_inside_game_is_rejected(self):
        inside = self.game / "mod"
        inside.mkdir()
        (inside / manager.PROJECT_MARKER).touch()
        with self.assertRaisesRegex(ValueError, "outside"):
            manager.TweakStore(self.game, inside, False)


class PrivateBuildTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("LEXEDITOR_DS1_EXE"), "Private executable not supplied")
    def test_real_build_roundtrip(self):
        path = Path(os.environ["LEXEDITOR_DS1_EXE"])
        original = path.read_bytes()
        self.assertEqual(tweak.identify(original), "vanilla")
        candidate = tweak.transform(original, True)
        self.assertEqual(tweak.identify(candidate), "enabled")
        self.assertEqual(tweak.transform(candidate, False), original)


if __name__ == "__main__":
    unittest.main()
