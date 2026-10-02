"""Execute the PE display island on Windows and Linux without a game or assembler."""
import ctypes
import math
import mmap
import os
from pathlib import Path
import platform
import random
import shutil
import struct
import subprocess
import sys

import pytest

from plugins.ds1 import equip_load_percentage as patch

ROOT = Path(__file__).resolve().parents[2]
SYSV = bytes.fromhex("5341544155564883ec484989fb4989d44989e50fae5c2438410fae54242c48b8f0debc9a7856341249b8887766554433221149b91122334455667788f3410f6f0424f3410f6f4c241048c7442420ffffffff48c7442428ffffffff9c418f442420410fae5c2428488d1d0800000049895c243041ffe39c418f442438410fae5c244049894424484d894424504d894c2458f3410f7f442460f3410f7f4c24704989942480000000488b44242049898424880000004989a424900000004d89ac2498000000488b44242849898424a00000000fae5424384883c4485e415d415c5bc3")
WINDOWS = bytes.fromhex("5341544155564883ec484989cb4889d64d89c44989e50fae5c2438410fae54242c48b8f0debc9a7856341249b8887766554433221149b91122334455667788f3410f6f0424f3410f6f4c241048c7442420ffffffff48c7442428ffffffff9c418f442420410fae5c2428488d1d0800000049895c243041ffe39c418f442438410fae5c244049894424484d894424504d894c2458f3410f7f442460f3410f7f4c24704989942480000000488b44242049898424880000004989a424900000004d89ac2498000000488b44242849898424a00000000fae5424384883c4485e415d415c5bc3")


class ExecutableMemory:
    def __init__(self):
        self.length = 0x3000
        if os.name == "nt":
            self.api = ctypes.WinDLL("kernel32", use_last_error=True)
            for name, result, args in [
                ("VirtualAlloc", ctypes.c_void_p, [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32, ctypes.c_uint32]),
                ("VirtualProtect", ctypes.c_int, [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32, ctypes.c_void_p]),
                ("VirtualFree", ctypes.c_int, [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32]),
                ("FlushInstructionCache", ctypes.c_int, [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]),
            ]:
                fn = getattr(self.api, name)
                fn.restype, fn.argtypes = result, args
            self.address = self.api.VirtualAlloc(None, self.length, 0x3000, 0x04)
            assert self.address
        else:
            self.mapping = mmap.mmap(-1, self.length, prot=mmap.PROT_READ|mmap.PROT_WRITE)
            self.address = ctypes.addressof(ctypes.c_char.from_buffer(self.mapping))

    def write(self, offset, raw):
        ctypes.memmove(self.address+offset, bytes(raw), len(raw))

    def seal(self):
        if os.name == "nt":
            old = ctypes.c_uint32()
            assert self.api.VirtualProtect(self.address, 0x2000, 0x20, ctypes.byref(old))
            assert self.api.FlushInstructionCache(ctypes.c_void_p(-1), self.address, 0x2000)
        else:
            api = ctypes.CDLL(None)
            api.mprotect.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int]
            assert api.mprotect(self.address, 0x2000, mmap.PROT_READ|mmap.PROT_EXEC) == 0

    def close(self):
        if os.name == "nt":
            assert self.api.VirtualFree(self.address, 0, 0x8000)
        else:
            self.mapping.close()



SUPPORTED = (os.name == "nt" or sys.platform == "linux") and platform.machine().lower() in ("amd64", "x86_64")


@pytest.mark.skipif(not SUPPORTED, reason="x64 Windows/Linux native harness")
def test_pe_payload_arguments_and_floating_point_modes():
    """Run production bytes, replacing only their documented relocations."""
    memory = ExecutableMemory()
    try:
        memory.write(0, WINDOWS if os.name == "nt" else SYSV)
        start, capture, fallback = (memory.address+offset for offset in (0x1000,0x1300,0x1400))
        memory.write(0x1000, patch.relocate_island(start,capture,fallback))
        memory.write(0x1300, b"\x41\xff\x64\x24\x30")  # jmp [r12+48], adapter capture
        memory.write(0x1400, "%s/%s\0".encode("utf-16-le"))
        memory.seal()
        call = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(memory.address)
        def check(bits, mxcsr):
            snapshot, output = ctypes.create_string_buffer(96), ctypes.create_string_buffer(176)
            struct.pack_into("<I",output,44,mxcsr)
            for offset,value in zip((0x14,0x18,0x40,0x44),bits):
                struct.pack_into("<I",snapshot,offset,value)
            before=snapshot.raw
            call(start,ctypes.addressof(snapshot),ctypes.addressof(output))
            raw=output.raw
            cur,maximum,preview,preview_max=bits
            if preview==0x80000000: preview=0
            if preview_max==0x80000000: preview_max=0
            if preview<0x80000000: cur=preview
            if preview_max<0x80000000: maximum=preview_max
            valid=cur<0x7f800000 and 0x00800000<=maximum<0x7f800000
            fmt=struct.unpack_from("<Q",raw,128)[0]
            if not valid:
                assert fmt==fallback, (bits,mxcsr,"invalid load must use original format")
                assert raw[136:144]==b"\xff"*8
            else:
                assert fmt==start+patch.FORMAT_OFFSET
                floats=[struct.unpack("<f",struct.pack("<I",v))[0] for v in (cur,maximum)]
                # DAZ, when enabled by the caller, treats subnormal input as zero.
                if mxcsr&0x40 and cur<0x00800000: floats[0]=0.0
                expected=100*floats[0]/floats[1]
                actual=struct.unpack_from("<d",raw,136)[0]
                assert math.isfinite(actual)
                assert math.isclose(actual,expected,rel_tol=1e-14,abs_tol=1e-90),(bits,mxcsr,actual,expected)
            assert snapshot.raw==before, "menu/player snapshot was changed"
            assert struct.unpack_from("<Q",raw,80)[0]==0x1122334455667788
            assert struct.unpack_from("<Q",raw,88)[0]==0x8877665544332211
            assert raw[144:152]==raw[152:160], "RSP changed"
            assert raw[160:168]==b"\xff"*8, "neighboring outgoing argument overwritten"
            # MXCSR exception status flags are volatile; its control bits are not.
            assert struct.unpack_from("<I",raw,64)[0]&0xffffffc0==mxcsr&0xffffffc0
        fbits=lambda x:struct.unpack("<I",struct.pack("<f",x))[0]
        baseline=[fbits(x) for x in (20,80,-1,-1)]
        edge=[0,0x80000000,1,0x007fffff,0x00800000,0x7f7fffff,
              0x7f800000,0xff800000,0x7fc00000,0x7f800001,0xffc00000,0xbf800000]
        cases=[[fbits(x) for x in values] for values in
               [(0,80,-1,-1),(20,80,-1,-1),(40,80,-1,-1),(80,80,-1,-1),
                (120,80,-1,-1),(10,80,25,100),(10,80,-1,120),(10,80,20,-1),
                (1,3,-1,-1),(-0.0,80,-1,-1),(20,0,-1,-1),(20,80,-1,-0.0)]]
        for slot in range(4):
            for value in edge:
                bits=baseline.copy();bits[slot]=value;cases.append(bits)
        rng=random.Random(872)
        cases.extend([[rng.getrandbits(32) for _ in range(4)] for _ in range(2000)])
        for mode in (0x1f80,0x9fc0,0x1fa0,0x3f80,0x5f80):
            for bits in cases: check(bits,mode)
    finally:
        memory.close()


def test_abi_adapter_rebuild_matches_both_calling_conventions(tmp_path):
    if not all(shutil.which(tool) for tool in ("as","ld","objcopy")):
        pytest.skip("GNU assembler unavailable; native execution test still runs")
    source=Path(__file__).with_name("equip_load_abi_adapter.S")
    for windows,expected in ((False,SYSV),(True,WINDOWS)):
        obj,elf,binary=[tmp_path/name for name in ("adapter.o","adapter.elf","adapter.bin")]
        args=["as","--64"]
        if windows: args+=["--defsym","WINDOWS=1"]
        subprocess.run([*args,str(source),"-o",str(obj)],check=True,capture_output=True)
        subprocess.run(["ld","-Ttext=0","-e","entry","-o",str(elf),str(obj)],check=True,capture_output=True)
        subprocess.run(["objcopy","-O","binary","-j",".text",str(elf),str(binary)],check=True)
        assert binary.read_bytes()==expected
