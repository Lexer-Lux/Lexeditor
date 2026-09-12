"""Signal Flare encounter backend tests; no game process or existing save is changed."""
from pathlib import Path
import os
import re
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
VCVARS = Path(r"C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat")


class FlarePolicyTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt" and VCVARS.exists(), "Windows C++ Build Tools required")
    def test_compiled_policy_restores_failed_requests_and_temporary_movement(self):
        header = ROOT / "games/ff8/ffnx_gameplay_extensions/ffnx-src/flare_encounter.h"
        code = '#include "' + header.as_posix() + '"\n' + r'''
#include <cstring>
int main() {
 using namespace lexeditor_flare;
 std::uint16_t field_steps=19,field_danger=23;
 std::uint8_t field_index=4,field_addend=5,field_formation=6;
 if(request_field(field_steps,field_danger,field_index,field_addend,field_formation,[&]{
     if(field_steps!=257 || field_danger!=256)throw 1;
     ++field_index;++field_addend;++field_formation;return false;
 }))return 40;
 if(field_steps!=19 || field_danger!=23 || field_index!=4 || field_addend!=5 || field_formation!=6)return 41;
 if(!request_field(field_steps,field_danger,field_index,field_addend,field_formation,[&]{
     field_danger=0;return true;
 }) || field_danger!=0)return 42;
 WorldCounters original{17,18,19,20,21,22,23}, live=original;
 std::int32_t movement=0; std::uint16_t encounter=65535; unsigned calls=0;
 bool ok=request_world(live,movement,encounter,[&](std::uint16_t *out) {
   ++calls; if(live.steps!=256 || live.danger!=255 || movement!=1) return 0;
   if(calls<3) return 0; live.steps=0;live.danger=0;*out=104;return 1;
 });
 if(!ok || calls!=3 || encounter!=104 || movement!=0 || live.danger!=0) return 1;
 live=original;movement=47;encounter=65535;calls=0;
 ok=request_world(live,movement,encounter,[&](std::uint16_t *out) {
   ++calls;++live.battle_index;*out=8;return 0;
 });
 if(ok || calls!=256 || encounter!=65535 || movement!=47 || std::memcmp(&live,&original,8)) return 2;
 try { request_world(live,movement,encounter,[&](std::uint16_t*)->int {throw 7;}); } catch(int) {}
 if(movement!=47 || std::memcmp(&live,&original,8)) return 3;
 struct Slot {std::uint8_t item_id, item_quantity;};
 Slot inventory[198]{}; inventory[0]={27,8}; inventory[197]={199,2};
 std::uint8_t remaining=99; encounter=65535; calls=0;
 auto success=[&](std::uint16_t *out){++calls;*out=105;return 1;};
 if(!use_item(inventory,199,encounter,remaining,success) || remaining!=1 ||
    inventory[197].item_quantity!=1 || encounter!=105 || calls!=1) return 4;
 if(inventory[0].item_id!=27 || inventory[0].item_quantity!=8) return 5;
 if(!use_item(inventory,199,encounter,remaining,success) || remaining ||
    inventory[197].item_id || inventory[197].item_quantity) return 6;
 encounter=65535;remaining=99;calls=0;
 if(use_item(inventory,199,encounter,remaining,success) || calls ||
    encounter!=65535 || remaining!=99) return 7;
 inventory[197]={199,2};
 if(use_item(inventory,199,encounter,remaining,[](std::uint16_t *out){*out=1;return 0;}) ||
    inventory[197].item_quantity!=2 || encounter!=65535 || remaining!=99) return 8;
 inventory[196]={199,1};
 if(use_item(inventory,199,encounter,remaining,success) || calls) return 9;
 inventory[196]={0,0};inventory[197].item_quantity=101;
 if(use_item(inventory,199,encounter,remaining,success) || calls) return 10;
 inventory[197].item_quantity=2;
 try {use_item(inventory,199,encounter,remaining,[](std::uint16_t*)->int {throw 7;});} catch(int){}
 if(inventory[197].item_quantity!=2 || encounter!=65535 || remaining!=99) return 11;
 return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix="lexeditor-flare-policy-") as temporary:
            folder = Path(temporary)
            (folder / "check.cpp").write_text(code)
            (folder / "build.cmd").write_text(
                f'@echo off\ncall "{VCVARS}" >nul\ncl /nologo /EHsc /std:c++17 check.cpp /Fe:check.exe\n')
            result = subprocess.run(["cmd", "/c", str(folder / "build.cmd")], cwd=folder,
                                    capture_output=True, text=True, timeout=60,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = subprocess.run([str(folder / "check.exe")], timeout=10,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(result.returncode, 0)


class NativeWorldSelectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Reuse existing local verifier dependency, if available. No install.
        dependency = ROOT / "_scratch/gf-spellbooks-test-deps"
        if dependency.is_dir():
            sys.path.insert(0, str(dependency))
        try:
            import unicorn
            import pefile
        except ImportError as error:
            raise unittest.SkipTest(str(error))
        from games.ff8 import paths
        from games.ff8.ffnx_issue_51 import runtime_package
        if not (paths.GAME_ROOT / "FF8_EN.exe").is_file():
            raise unittest.SkipTest("Supported private FF8 executable required")
        executable = runtime_package.verify_game_installation(paths.GAME_ROOT)
        cls.image = pefile.PE(str(executable)).get_memory_mapped_image()

    def select(self, *, forced=True, vehicle=0, disabled=False, terrain=4, region=3):
        from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
        from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_EAX, UC_X86_REG_EIP
        u = Uc(UC_ARCH_X86, UC_MODE_32)
        u.mem_map(0x400000, 0x3000000)
        u.mem_write(0x400000, self.image)
        def write(address, value, size):
            u.mem_write(address, value.to_bytes(size, "little"))
        write(0x2040068, 0x3000000, 4)
        u.mem_write(0x3000000, struct.pack("<I", 10) + bytes([3, 4, 2, 0, 0, 0]))
        write(0x2040330, 0x3001000, 4); write(0x3001000, region, 1)
        write(0x20409FC, 0x3002000, 4); write(0x300200D, terrain, 1)
        write(0x2040090, 0x3003000, 4); write(0x3003002, 24, 1)
        write(0x2036BE8, 0x3004000, 4)
        u.mem_write(0x3004020, struct.pack("<8H", *range(100, 108)))
        write(0x20409E0, vehicle, 4); write(0x1CFF6D8, 8 if disabled else 0, 1)
        write(0x2036BD8, 0, 1)
        # Stub only coordinate-to-region-cell lookup; the real selector still
        # matches region/terrain and runs its native weighted formation/RNG code.
        def stub(uc, address, size, data):
            if address == 0x553910:
                esp = uc.reg_read(UC_X86_REG_ESP)
                ret = int.from_bytes(uc.mem_read(esp, 4), "little")
                uc.reg_write(UC_X86_REG_EAX, 0)
                uc.reg_write(UC_X86_REG_ESP, esp + 4)
                uc.reg_write(UC_X86_REG_EIP, ret)
        u.hook_add(UC_HOOK_CODE, stub)
        write(0x2040A5C, 256 if forced else 0, 2)
        write(0x2040A5E, 255 if forced else 0, 1)
        write(0x20409F4, 1 if forced else 0, 4)
        write(0x3005000, 65535, 2)
        u.mem_write(0x3100000, struct.pack("<II", 0x3200000, 0x3005000))
        u.reg_write(UC_X86_REG_ESP, 0x3100000)
        u.emu_start(0x541C80, 0x3200000, count=10000)
        self.assertEqual(u.reg_read(UC_X86_REG_EIP), 0x3200000)
        return u.reg_read(UC_X86_REG_EAX), int.from_bytes(u.mem_read(0x3005000, 2), "little")

    def test_native_selector_uses_current_location_and_keeps_its_guards(self):
        if os.environ.get("LEXEDITOR_FLARE_NATIVE_WORKER") != "1":
            # Unicorn handles Windows guard-page exceptions internally.
            # Pytest's faulthandler reports these as fatal even when execution
            # succeeds. Keep emulation in a bounded unittest child instead.
            result = subprocess.run([sys.executable, str(Path(__file__).resolve()),
                                     "NativeWorldSelectorTests"],
                                    env={**os.environ, "LEXEDITOR_FLARE_NATIVE_WORKER": "1"},
                                    capture_output=True, text=True, timeout=30,
                                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return
        self.assertEqual(self.select(forced=False), (0, 65535))
        result, encounter = self.select()
        self.assertEqual(result, 1)
        self.assertIn(encounter, range(100, 108))
        for options in ({"vehicle": 0x30}, {"disabled": True}, {"terrain": 27},
                        {"terrain": 28}, {"region": 5}):
            with self.subTest(options=options):
                self.assertEqual(self.select(**options), (0, 65535))

    def test_native_inventory_accepts_new_byte_id_without_growing_save(self):
        if os.environ.get("LEXEDITOR_FLARE_NATIVE_WORKER") != "1":
            result = subprocess.run([sys.executable, str(Path(__file__).resolve()),
                                     "NativeWorldSelectorTests.test_native_inventory_accepts_new_byte_id_without_growing_save"],
                                    env={**os.environ, "LEXEDITOR_FLARE_NATIVE_WORKER": "1"},
                                    capture_output=True, text=True, timeout=30,
                                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return
        from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
        from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_EIP
        for full in (False, True):
            u = Uc(UC_ARCH_X86, UC_MODE_32)
            u.mem_map(0x400000, 0x3000000)
            u.mem_write(0x400000, self.image)
            # Last slot is the only free slot. Surround it with sentinels.
            before = b"\xa5" * 16 + b"".join(bytes([i, 1]) for i in range(1, 198))
            before += bytes([198, 1]) if full else bytes(2)
            before += b"\x5a" * 16
            u.mem_write(0x1CFE79C - 16, before)
            u.mem_write(0x3100000, struct.pack("<III", 0x3200000, 199, 3))
            u.reg_write(UC_X86_REG_ESP, 0x3100000)
            u.emu_start(0x47ED00, 0x3200000, count=10000)
            self.assertEqual(u.reg_read(UC_X86_REG_EIP), 0x3200000)
            after = bytes(u.mem_read(0x1CFE79C - 16, len(before)))
            expected = before if full else before[:-18] + bytes([199, 3]) + before[-16:]
            self.assertEqual(after, expected)
            # Native menu-exit normalization keeps a nonzero new ID/quantity.
            u.mem_write(0x3100000, struct.pack("<I", 0x3200000))
            u.reg_write(UC_X86_REG_ESP, 0x3100000)
            u.emu_start(0x4C3150, 0x3200000, count=10000)
            self.assertEqual(bytes(u.mem_read(0x1CFE79C - 16, len(before))), expected)

        # The four native metadata accessors index the file buffer directly.
        # An expanded file is required: the stock file stops before ID 199.
        from unicorn.x86_const import UC_X86_REG_EAX
        u.mem_write(0x1D2BB2C, struct.pack("<I", 0x3000000))
        u.mem_write(0x3000000, bytes(199 * 4) + bytes([21, 16, 7, 9]))
        for address, expected_byte in zip((0x4F74F0, 0x4F7500, 0x4F7510, 0x4F7520), (21, 16, 7, 9)):
            u.mem_write(0x3100000, struct.pack("<II", 0x3200000, 199))
            u.reg_write(UC_X86_REG_ESP, 0x3100000)
            u.emu_start(address, 0x3200000, count=100)
            self.assertEqual(u.reg_read(UC_X86_REG_EAX) & 255, expected_byte)

    def test_native_save_serializer_compression_and_load_preserve_new_item(self):
        if os.environ.get("LEXEDITOR_FLARE_NATIVE_WORKER") != "1":
            result = subprocess.run([sys.executable, str(Path(__file__).resolve()),
                f"{type(self).__name__}.{self._testMethodName}"], capture_output=True,
                text=True, timeout=45, env={**os.environ, "LEXEDITOR_FLARE_NATIVE_WORKER": "1"},
                creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return
        from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
        from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_EAX, UC_X86_REG_EIP
        u = Uc(UC_ARCH_X86, UC_MODE_32)
        u.mem_map(0x400000, 0x3000000); u.mem_write(0x400000, self.image)
        def write(address, value): u.mem_write(address, struct.pack("<I", value))
        def call(address, *args):
            u.mem_write(0x3100000, struct.pack("<" + "I"*(1+len(args)), 0x3200000, *args))
            u.reg_write(UC_X86_REG_ESP, 0x3100000)
            try: u.emu_start(address, 0x3200000, count=10000000)
            except Exception as error: raise RuntimeError(hex(u.reg_read(UC_X86_REG_EIP))) from error
            self.assertEqual(u.reg_read(UC_X86_REG_EIP), 0x3200000, hex(address))
            return u.reg_read(UC_X86_REG_EAX)
        # Actual savemap base from FFNx's supported intro entry operand. The
        # inventory is offset 0xB44, not the 0xB54 of an alternate file layout.
        self.assertEqual(struct.unpack_from("<I", self.image, 0x470319-0x400000)[0], 0x1CFDC58)
        original = bytes([1, 8]) + bytes(392) + bytes([199, 37])
        u.mem_write(0x1CFE79C, original)
        write(0xB86D30, 0x2900000); write(0xB8A360, 0x3008000)
        # Native save formatter writes the 8 KiB block, including both checksum
        # copies, from the live savemap. No formatter/checksum/copy stub is used.
        self.assertEqual(call(0x4E2EF0, 0, 0x3000000), 0x2000)
        block = bytes(u.mem_read(0x3000000, 0x2000))
        self.assertEqual(block[0x180+0xB44:0x180+0xB44+396], original)
        self.assertEqual(block[0x180:0x182], block[0x180+0x13A0:0x180+0x13A2])
        # Suppress only the compressor's diagnostic printf; no console/CRT OS calls.
        u.mem_write(0x55B53E, bytes.fromhex("31c0c3"))
        # The exact native compressor and decoder used by file save/load run
        # against synthetic buffers, with no file or compression stubs.
        call(0x40FE1D, 0x3000000, 0x3010000, 0x2000)
        call(0x40F852, 0x3010000, 0x3020000)
        self.assertEqual(bytes(u.mem_read(0x3020000, 0x2000)), block)
        # Run the real file-load helper too. Only OS file I/O and allocation
        # are supplied by the fixture; decompression and savemap copy stay native.
        from unicorn import UC_HOOK_CODE
        compressed_size = struct.unpack("<I", u.mem_read(0x3010000, 4))[0] + 4
        compressed = bytes(u.mem_read(0x3010000, compressed_size))
        allocations = iter((0x3030000, 0x3040000))
        def file_stub(uc, address, size, data):
            if address not in (0x55D62C, 0x55D3EE, 0x40A39A, 0x40A0F0): return
            esp = uc.reg_read(UC_X86_REG_ESP)
            ret, a, b, length = struct.unpack("<4I", uc.mem_read(esp, 16))
            result = 0
            if address == 0x55D62C: result = compressed_size if length == 2 else 0
            elif address == 0x55D3EE:
                self.assertEqual(length, compressed_size)
                uc.mem_write(b, compressed); result = compressed_size
            elif address == 0x40A39A: result = next(allocations)
            uc.reg_write(UC_X86_REG_EAX, result)
            uc.reg_write(UC_X86_REG_ESP, esp + 4); uc.reg_write(UC_X86_REG_EIP, ret)
        u.hook_add(UC_HOOK_CODE, file_stub)
        u.mem_write(0x1CFDC58, bytes(0x1400))
        self.assertEqual(call(0x4C6D60, 7, 0x1CFDC58, 0x1400, 0x180), 0x1400)
        self.assertEqual(bytes(u.mem_read(0x1CFE79C, 396)), original)
        self.assertEqual(bytes(u.mem_read(0x1CFDC58, 0x1400)), block[0x180:0x1580])


    def test_native_root_menu_exit_preserves_party_and_runs_cleanup(self):
        if os.environ.get("LEXEDITOR_FLARE_NATIVE_WORKER") != "1":
            result = subprocess.run([sys.executable, str(Path(__file__).resolve()),
                f"{type(self).__name__}.{self._testMethodName}"], capture_output=True,
                text=True, timeout=30, env={**os.environ, "LEXEDITOR_FLARE_NATIVE_WORKER": "1"},
                creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return
        from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
        from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_EAX, UC_X86_REG_EIP
        u = Uc(UC_ARCH_X86, UC_MODE_32)
        u.mem_map(0x400000, 0x3000000); u.mem_write(0x400000, self.image)
        context = 0x3000000
        u.mem_write(context+0x10, struct.pack("<H", 21))
        u.mem_write(context+0x2c, struct.pack("<H", 0x1000))
        u.mem_write(context+0x35, bytes([0,4,7]))
        u.mem_write(0x1D77079, bytes([1]))
        removed=[]
        def stub(uc, address, size, data):
            if address not in (0x4BE610,0x4BD6A0): return
            esp=uc.reg_read(UC_X86_REG_ESP)
            ret,arg=struct.unpack("<2I",uc.mem_read(esp,8))
            if address==0x4BE610: removed.append(arg)
            uc.reg_write(UC_X86_REG_EAX,0);uc.reg_write(UC_X86_REG_ESP,esp+4)
            uc.reg_write(UC_X86_REG_EIP,ret)
        u.hook_add(UC_HOOK_CODE,stub)
        for frame in range(16):
            u.mem_write(0x3100000,struct.pack("<2I",0x3200000,context))
            u.reg_write(UC_X86_REG_ESP,0x3100000)
            u.emu_start(0x4C0CF0,0x3200000,count=10000)
            self.assertEqual(u.reg_read(UC_X86_REG_EIP),0x3200000)
        self.assertEqual(removed,[context])
        self.assertEqual(bytes(u.mem_read(0x1D77079,1)),bytes([0]))
        self.assertEqual(bytes(u.mem_read(0x1CFE74C,3)),bytes([0,4,7]))
        self.assertEqual(bytes(u.mem_read(context+0x2c,2)),bytes(2))

    def test_native_field_selector_uses_local_formations_and_transition_guards(self):
        if os.environ.get("LEXEDITOR_FLARE_NATIVE_WORKER") != "1":
            result=subprocess.run([sys.executable,str(Path(__file__).resolve()),
                f"{type(self).__name__}.{self._testMethodName}"],capture_output=True,text=True,
                timeout=30,env={**os.environ,"LEXEDITOR_FLARE_NATIVE_WORKER":"1"},
                creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            return
        from unicorn import Uc,UC_ARCH_X86,UC_MODE_32
        from unicorn.x86_const import UC_X86_REG_ESP,UC_X86_REG_EIP
        u=Uc(UC_ARCH_X86,UC_MODE_32)
        u.mem_map(0x400000,0x3000000);u.mem_write(0x400000,self.image)
        def write(address,value,size=4):u.mem_write(address,value.to_bytes(size,"little"))
        # Stub only the movie/activity guard. Real local table selection,
        # native RNG, actor danger term and transition writes all execute.
        u.mem_write(0x5305B0,bytes.fromhex("b801000000c3"))
        write(0x1D9CEC9,0,1)
        write(0xB8EE90,0x3000000);write(0x1CF3D48,0x3001000)
        write(0x3001000,0x3001100);write(0x3001100,16,1)
        write(0x1CF3D78,0x3002000);write(0x3002000,0x3002100)
        u.mem_write(0x3002100,struct.pack("<4H",401,402,403,404))
        write(0x1D9CF88,0x3003000);write(0x1CD8FD0,0,2)
        guards=[{}, {0x1CFF6D8:(8,1)}, {0x1CE4760:(1,1)}, {0x1CE4760:(7,1)},
                {0x30000CF:(1,1)}, {0x1CE4868:(2,2)}, {0x1CE4868:(3,2)},
                {0x1CE4868:(4,2)}, {0x1CDC74C:(1,1)}, {0x1D9CEC9:(2,1)}]
        for guard in guards:
            disabled=bool(guard)
            for seed in range(16):
                write(0x1CE4760,0,1);write(0x1CD2EF8,0,1)
                write(0x1CFF6D8,0,1);write(0x30000CF,0,1);write(0x1CE4868,0,2)
                write(0x1CDC74C,0,1);write(0x1D9CEC9,0,1)
                for address,(value,size) in guard.items():write(address,value,size)
                write(0x1CDC740,257,2);write(0x1CDC74A,256,2)
                write(0x1CDBFEC,seed,1);write(0x1CDC6E0,0xffff,2)
                u.mem_write(0x3100000,struct.pack("<I",0x3200000));u.reg_write(UC_X86_REG_ESP,0x3100000)
                u.emu_start(0x47CA90,0x3200000,count=10000)
                self.assertEqual(u.reg_read(UC_X86_REG_EIP),0x3200000)
                self.assertEqual(bytes(u.mem_read(0x1CE4760,1)),bytes([guard.get(0x1CE4760,(0,1))[0] if disabled else 3]))
                self.assertEqual(bytes(u.mem_read(0x1CD2EF8,1)),bytes([0 if disabled else 1]))
                if not disabled:self.assertIn(struct.unpack("<H",u.mem_read(0x1CE4762,2))[0],(401,402,403,404))

    def test_native_shop_buy_sell_and_commit_keep_new_item_and_inventory_bounds(self):
        if os.environ.get("LEXEDITOR_FLARE_NATIVE_WORKER") != "1":
            result=subprocess.run([sys.executable,str(Path(__file__).resolve()),
                f"{type(self).__name__}.{self._testMethodName}"],capture_output=True,text=True,
                timeout=30,env={**os.environ,"LEXEDITOR_FLARE_NATIVE_WORKER":"1"},
                creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            return
        from unicorn import Uc,UC_ARCH_X86,UC_MODE_32
        from unicorn.x86_const import UC_X86_REG_ESP,UC_X86_REG_EIP,UC_X86_REG_EAX,UC_X86_REG_ECX,UC_X86_REG_ESI,UC_X86_REG_EDI
        u=Uc(UC_ARCH_X86,UC_MODE_32)
        u.mem_map(0x400000,0x3000000);u.mem_write(0x400000,self.image)
        def write(a,v,n=4):u.mem_write(a,v.to_bytes(n,"little"))
        stock=b"".join(bytes([i,1]) for i in range(1,198))
        u.mem_write(0x1CFE79C,stock+bytes(2)+b"BOUNDARY")
        write(0x1D8CD18+199*4,200);write(0x1D8D120+199*4,100)
        balance=1000
        for address,quantity,expected,expected_balance in [(0x4EC7AC,3,3,400),(0x4EC82B,2,1,600)]:
            u.mem_write(0x1D8D058,bytes(200))
            for item,owned in struct.iter_unpack("BB",u.mem_read(0x1CFE79C,396)):
                if item:write(0x1D8D058+item,owned,1)
            write(0x3000028,balance)
            u.reg_write(UC_X86_REG_EAX,199);u.reg_write(UC_X86_REG_ECX,quantity)
            u.reg_write(UC_X86_REG_ESI,0x3000000);u.reg_write(UC_X86_REG_EDI,4)
            u.reg_write(UC_X86_REG_ESP,0x3100000)
            u.emu_start(address,0x4ED068,count=1000)
            balance=struct.unpack("<I",u.mem_read(0x3000028,4))[0]
            self.assertEqual(balance,expected_balance)
            self.assertEqual(bytes(u.mem_read(0x1D8D058+199,1)),bytes([expected]))
            u.mem_write(0x3100000,struct.pack("<2I",0x3200000,balance))
            u.reg_write(UC_X86_REG_ESP,0x3100000)
            u.emu_start(0x4EB9F0,0x3200000,count=30000)
            self.assertEqual(u.reg_read(UC_X86_REG_EIP),0x3200000)
            self.assertEqual(bytes(u.mem_read(0x1CFE79C,404)),stock+bytes([199,expected])+b"BOUNDARY")
            self.assertEqual(struct.unpack("<I",u.mem_read(0x1CFE764,4))[0],balance)

    def test_native_item_text_lookup_matches_overlay_stock_mapping(self):
        if os.environ.get("LEXEDITOR_FLARE_NATIVE_WORKER") != "1":
            result = subprocess.run([sys.executable, str(Path(__file__).resolve()),
                                     "NativeWorldSelectorTests.test_native_item_text_lookup_matches_overlay_stock_mapping"],
                                    env={**os.environ, "LEXEDITOR_FLARE_NATIVE_WORKER": "1"},
                                    capture_output=True, text=True, timeout=30,
                                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return
        from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
        from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_EAX
        u = Uc(UC_ARCH_X86, UC_MODE_32)
        u.mem_map(0x400000, 0x3000000)
        u.mem_write(0x400000, self.image)
        # The production buy/sell guards replace exactly these instructions.
        for address in (0x4EC7A7, 0x4EC826):
            self.assertEqual(self.image[address - 0x400000:address - 0x400000 + 5],
                             bytes.fromhex("8bc18a4e48"))
        u.mem_write(0x1CF3EE4, struct.pack("<II", 0x9000, 0xa000))
        for item_id in range(199):
            base = 0x1CF7778 + item_id * 24 if item_id < 33 else 0x1CF7A0C + item_id * 4
            u.mem_write(base, struct.pack("<HH", item_id * 4, item_id * 4 + 2))
        for item_id in range(199):
            for address, extra in ((0x47EA30, 0), (0x47EA90, 2)):
                u.mem_write(0x3100000, struct.pack("<II", 0x3200000, item_id))
                u.reg_write(UC_X86_REG_ESP, 0x3100000)
                u.emu_start(address, 0x3200000, count=100)
                expected = 0x1CF3E48 + (0x9000 if item_id < 33 else 0xa000) + item_id * 4 + extra
                self.assertEqual(u.reg_read(UC_X86_REG_EAX), expected)

    def test_native_shop_lookup_can_read_seventeenth_transient_row(self):
        if os.environ.get("LEXEDITOR_FLARE_NATIVE_WORKER") != "1":
            result = subprocess.run([sys.executable, str(Path(__file__).resolve()),
                                     "NativeWorldSelectorTests.test_native_shop_lookup_can_read_seventeenth_transient_row"],
                                    env={**os.environ, "LEXEDITOR_FLARE_NATIVE_WORKER": "1"},
                                    capture_output=True, text=True, timeout=30,
                                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return
        from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
        from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_EAX
        u = Uc(UC_ARCH_X86, UC_MODE_32)
        u.mem_map(0x400000, 0x3000000)
        u.mem_write(0x400000, self.image)
        source = (ROOT / "games/ff8/ffnx_gameplay_extensions/ffnx-src/lexeditor_ff8_flare_shop.cpp").read_text()
        for name, expected in (("id_operands", 0x1D8D038), ("quantity_operands", 0x1D8D039),
                               ("end_operands", 0x1D8D058)):
            body = re.search(name + r"\[\]\s*=\s*\{([^}]+)\}", source).group(1)
            for value in body.split(","):
                address = int(value.strip(), 0)
                self.assertEqual(self.image[address - 0x400000:address - 0x400000 + 4],
                                 struct.pack("<I", expected))
        self.assertEqual(self.image[0xEC2F3:0xEC2F9], bytes.fromhex("c6464702eb11"))
        self.assertEqual(self.image[0xED0EB:0xED0EF], struct.pack("<I", 0x1D8D038))
        # Redirect only this fixture's buy-list operand; saved shop data is not
        # enlarged. The actual native helper already accepts row 16 of 198.
        u.mem_write(0x4ED0EB, struct.pack("<I", 0x3000000))
        rows = b"".join(bytes([i + 1, 100]) for i in range(16)) + bytes([199, 25]) + bytes(181 * 2)
        u.mem_write(0x3000000, rows)
        for index in range(199):
            u.mem_write(0x3100000, struct.pack("<IIII", 0x3200000, 0, 0, index))
            u.reg_write(UC_X86_REG_ESP, 0x3100000)
            u.emu_start(0x4ED0D0, 0x3200000, count=100)
            expected = index + 1 if index < 16 else (199 if index == 16 else 0)
            self.assertEqual(u.reg_read(UC_X86_REG_EAX), expected)

    def test_native_item_close_states_keep_the_menu_cleanup_path(self):
        if os.environ.get("LEXEDITOR_FLARE_NATIVE_WORKER") != "1":
            result = subprocess.run([sys.executable, str(Path(__file__).resolve()),
                                     "NativeWorldSelectorTests.test_native_item_close_states_keep_the_menu_cleanup_path"],
                                    env={**os.environ, "LEXEDITOR_FLARE_NATIVE_WORKER": "1"},
                                    capture_output=True, text=True, timeout=30,
                                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return
        from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
        from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_EAX, UC_X86_REG_EIP
        self.assertEqual(self.image[0xF8A2F:0xF8A35], bytes.fromhex("8b3d2cbbd201"))
        for state in (0x70, 0x71):
            u = Uc(UC_ARCH_X86, UC_MODE_32)
            u.mem_map(0x400000, 0x3000000)
            u.mem_write(0x400000, self.image)
            u.mem_write(0x3000010, struct.pack("<H", state))
            u.mem_write(0x1D77079, b"\x01")
            u.mem_write(0x1D751B1, b"\x00")
            calls = []
            def stub(uc, address, size, data):
                if state == 0x71 and address == 0x4FBEA9:
                    uc.emu_stop()
                elif address in (0x4AC400, 0x49FAD0, 0x4ABFB0, 0x4BE870, 0x4BE610):
                    calls.append(address)
                    esp = uc.reg_read(UC_X86_REG_ESP)
                    ret = int.from_bytes(uc.mem_read(esp, 4), "little")
                    uc.reg_write(UC_X86_REG_EAX, 0)
                    uc.reg_write(UC_X86_REG_ESP, esp + 4)
                    uc.reg_write(UC_X86_REG_EIP, ret)
            u.hook_add(UC_HOOK_CODE, stub)
            u.mem_write(0x3100000, struct.pack("<II", 0x3200000, 0x3000000))
            u.reg_write(UC_X86_REG_ESP, 0x3100000)
            u.emu_start(0x4F81F0, 0x3200000, count=30000)
            if state == 0x70:
                self.assertEqual(bytes(u.mem_read(0x3000010, 2)), b"\x71\x00")
                self.assertEqual(calls.count(0x4AC400), 2)
            else:
                self.assertEqual(calls, [0x4ABFB0, 0x4BE870, 0x4BE610])
                self.assertEqual(bytes(u.mem_read(0x1D77079, 1)), b"\x00")
                self.assertEqual(u.reg_read(UC_X86_REG_EIP), 0x4FBEA9)


if __name__ == "__main__":
    unittest.main()
