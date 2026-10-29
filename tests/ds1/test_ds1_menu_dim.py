"""Shared dimmed talk options: one loader-owned table for every mod's text IDs.

The detours run under Unicorn with their relocations resolved, so the
draw switch, the confirmation guard and the restored registers are checked
as executed code rather than as bytes.
"""
from __future__ import annotations

import json
import os
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from unicorn import Uc, UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_64
from unicorn.x86_const import (UC_X86_REG_EFLAGS, UC_X86_REG_RAX, UC_X86_REG_RCX, UC_X86_REG_RDI,
                               UC_X86_REG_RDX, UC_X86_REG_RIP, UC_X86_REG_RSI, UC_X86_REG_RSP)

from plugins.ds1 import exe_patches, menu_dim, tweak_mods

BASE = 0x140000000
ISLAND = 0x150000000
STACK = 0x160000000
ROW = 0x170000000
WORKER = "LEXEDITOR_MENU_DIM_WORKER"


def run(spec, offset, regs):
    island = spec["islands"][0]
    code = bytearray.fromhex(island["code"])
    for relocation in island["relocations"]:
        target = BASE + relocation["rel32"]
        struct.pack_into("<i", code, relocation["at"], target - (ISLAND + relocation["at"] + 4))
    exits = {BASE + menu_dim.DRAW_CONTINUE, BASE + menu_dim.SELECT_CONTINUE, BASE + menu_dim.SELECT_REJECT}
    uc = Uc(UC_ARCH_X86, UC_MODE_64)
    uc.mem_map(ISLAND, 0x10000)
    uc.mem_write(ISLAND, bytes(code))
    uc.mem_map(STACK, 0x10000)
    uc.mem_map(ROW, 0x1000)
    uc.mem_map(BASE + 0x66B000, 0x1000)
    uc.hook_add(UC_HOOK_CODE, lambda engine, *_: engine.emu_stop(), begin=BASE + 0x66B000, end=BASE + 0x66BFFF)
    uc.reg_write(UC_X86_REG_RSP, STACK + 0x8000)
    uc.reg_write(UC_X86_REG_EFLAGS, 0x246)
    for name, value in regs.items():
        if name == "row":
            uc.mem_write(ROW, struct.pack("<ii", *value))
        else:
            uc.reg_write(name, value)
    uc.emu_start(ISLAND + offset, 0, count=10000)  # stops on reaching the game's code
    if uc.reg_read(UC_X86_REG_RIP) not in exits:
        raise AssertionError(f"detour ended at {uc.reg_read(UC_X86_REG_RIP):#x}")
    return uc


def joined(*ids):
    dims = [menu_dim.validate({"version": 1, "textIds": list(group)}, f"Mod {n}") for n, group in enumerate(ids)]
    return menu_dim.patch_spec(dims)


@unittest.skipUnless(os.environ.get(WORKER) == "1", "runs in the child DetourChildTest starts")
class DetourExecution(unittest.TestCase):
    spec = staticmethod(joined)

    def draw(self, spec, text_id, sil=0):
        uc = run(spec, 0, {"row": (text_id, 5), UC_X86_REG_RDI: ROW, UC_X86_REG_RSI: sil,
                           UC_X86_REG_RAX: 0x1234, UC_X86_REG_RCX: 77})
        self.assertEqual(uc.reg_read(UC_X86_REG_RIP), BASE + menu_dim.DRAW_CONTINUE)
        self.assertEqual(uc.reg_read(UC_X86_REG_RCX), 0x1234)
        self.assertEqual(uc.reg_read(UC_X86_REG_RSP), STACK + 0x8000)
        return uc.reg_read(UC_X86_REG_RDX) & 0xFFFFFFFF

    def select(self, spec, text_id):
        uc = run(spec, menu_dim.SELECT_OFFSET, {"row": (text_id, 9), UC_X86_REG_RDX: ROW,
                                                UC_X86_REG_RAX: 0xAAAA, UC_X86_REG_RCX: 0xCCCC})
        self.assertEqual(uc.reg_read(UC_X86_REG_RSP), STACK + 0x8000)
        self.assertEqual(uc.reg_read(UC_X86_REG_RCX), 0xCCCC)
        if uc.reg_read(UC_X86_REG_RIP) == BASE + menu_dim.SELECT_REJECT:
            self.assertEqual(uc.reg_read(UC_X86_REG_RAX), 0xAAAA)
            self.assertEqual(uc.reg_read(UC_X86_REG_RDX), ROW)
            return None
        self.assertEqual(uc.reg_read(UC_X86_REG_RIP), BASE + menu_dim.SELECT_CONTINUE)
        self.assertEqual(uc.reg_read(UC_X86_REG_RDX), 0)
        return uc.reg_read(UC_X86_REG_RAX)

    def test_listed_rows_dim_and_refuse_confirmation(self):
        spec = self.spec([150072302, 150072308], [42, 150072302])
        for rid in (42, 150072302, 150072308):
            self.assertEqual(self.draw(spec, rid), 1)
            self.assertIsNone(self.select(spec, rid))
        for rid in (43, 150072309, -1, 0):
            self.assertEqual(self.draw(spec, rid, sil=0), 0)
            self.assertEqual(self.draw(spec, rid, sil=1), 1)
            self.assertEqual(self.select(spec, rid), 9)

    def test_unused_row_keeps_native_switch(self):
        spec = self.spec([7])
        uc = run(spec, 0, {UC_X86_REG_RDI: 0, UC_X86_REG_RSI: 1, UC_X86_REG_RAX: 5})
        self.assertEqual(uc.reg_read(UC_X86_REG_RIP), BASE + menu_dim.DRAW_CONTINUE)
        self.assertEqual(uc.reg_read(UC_X86_REG_RDX) & 0xFFFFFFFF, 1)


class DetourChildTest(unittest.TestCase):
    def test_detours_execute(self):
        # Unicorn handles Windows guard-page exceptions internally; pytest's
        # faulthandler reports them as fatal anyway, so emulate in a child.
        result = subprocess.run([sys.executable, str(Path(__file__).resolve()), "DetourExecution"],
                                env={**os.environ, WORKER: "1", "PYTHONPATH": str(Path(__file__).resolve().parents[2])},
                                capture_output=True, text=True, timeout=60,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Ran 2 tests", result.stderr)


class MenuDimTest(unittest.TestCase):
    spec = staticmethod(joined)

    def test_description_is_one_loader_owned_patch(self):
        self.assertIsNone(menu_dim.patch_spec([]))
        self.assertIsNone(self.spec([]))
        spec = exe_patches.validate(self.spec([3, 1], [2]), menu_dim.OWNER)
        self.assertEqual([hook["rva"] for hook in spec["hooks"]], [menu_dim.DRAW_RVA, menu_dim.SELECT_RVA])
        table = bytes.fromhex(self.spec([3, 1], [2])["islands"][0]["code"])[len(menu_dim.CODE):]
        self.assertEqual(struct.unpack(f"<{len(table) // 4}I", table), (1, 2, 3, 0xFFFFFFFF))

    def test_bad_files_are_refused(self):
        for value in ({"version": 2, "textIds": []}, {"version": 1, "textIds": [-1]},
                      {"version": 1, "textIds": ["5"]}, {"version": 1, "textIds": [], "x": 1},
                      {"version": 1, "textIds": list(range(menu_dim.MAX_IDS + 1))}):
            with self.assertRaises(ValueError):
                menu_dim.validate(value, "Mod")

    def test_build_specs_joins_every_mods_ids(self):
        with tempfile.TemporaryDirectory() as temp:
            rows = []
            for name, ids in (("a", [5, 6]), ("b", [6, 7])):
                folder = Path(temp) / name
                (folder / menu_dim.FOLDER).mkdir(parents=True)
                (folder / menu_dim.FOLDER / f"{name}.json").write_text(
                    json.dumps({"version": 1, "textIds": ids}), encoding="utf-8")
                rows.append({"id": name, "name": name.upper(), "path": str(folder), "enabled": True})
            with mock.patch.object(tweak_mods, "tweak_rows", return_value=rows), \
                    mock.patch.object(tweak_mods.mod_requires, "check_enabled"), \
                    mock.patch.object(tweak_mods, "ensure_loader_mod"), \
                    mock.patch.object(tweak_mods.script_mods, "build_batch"), \
                    mock.patch.object(tweak_mods, "loader_mod_state", return_value=(True, True)):
                specs = tweak_mods.build_specs(Path(temp))
            self.assertEqual([spec["owner"] for spec in specs], [menu_dim.OWNER])
            table = specs[0]["islands"][0]["code"][len(menu_dim.CODE):]
            self.assertEqual(struct.unpack("<4I", table), (5, 6, 7, 0xFFFFFFFF))
            with mock.patch.object(tweak_mods, "tweak_rows", return_value=rows), \
                    mock.patch.object(tweak_mods.mod_requires, "check_enabled"), \
                    mock.patch.object(tweak_mods, "ensure_loader_mod"), \
                    mock.patch.object(tweak_mods.script_mods, "build_batch"), \
                    mock.patch.object(tweak_mods, "loader_mod_state", return_value=(True, False)):
                with self.assertRaisesRegex(tweak_mods.TweakError, "A and B require"):
                    tweak_mods.build_specs(Path(temp))


if __name__ == "__main__":
    unittest.main()
