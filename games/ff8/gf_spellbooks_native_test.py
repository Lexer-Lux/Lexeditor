"""Execute the issue93 candidate x86 hooks without launching or changing FF8.

Test dependencies: Unicorn and Keystone (scratch-only installation is enough).
"""
from pathlib import Path
import struct
import unittest
from keystone import Ks, KS_ARCH_X86, KS_MODE_32
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
from unicorn.x86_const import *
from . import gf_spellbooks_native as native, gf_spellbooks_native_asm as a, max_spell

EXE = Path(r"D:\SteamLibrary\steamapps\common\FINAL FANTASY VIII\FF8_EN.exe").read_bytes()
BOOK = {"schemaVersion":1,"books":[{"gfId":0,"pages":[[{"magicId":7,"abilityId":None},{"magicId":1,"abilityId":20}],[],[{"magicId":4,"abilityId":None}]]}]}
REAL = 0x1cff082
STACK = 0x3000800
END = 0x410000


def new_machine(mutation=None):
    native.verify_executable(EXE)
    vm=Uc(UC_ARCH_X86,UC_MODE_32)
    for address,size in ((0x400000,0x100000),(0x1cf0000,0x90000),(a.BASE,0x4000),(0x3000000,0x1000)):
        vm.mem_map(address,size)
    vm.mem_write(0x400000,EXE[:0x100000])
    for site,_original,code in max_spell.UNSIGNED_BATTLE_STOCK_SITES:
        vm.mem_write(site,code)
    for address,code in native.candidate_fragments(BOOK,monogamy=True,shared_magic=False).items():
        vm.mem_write(address,code)
    if mutation is not None:
        site,original,_target=native.HOOKS[mutation]
        vm.mem_write(site,original)
    vm.mem_write(0x1cff1c3,b"\0")
    vm.mem_write(0x1cfe140,b"\1\0")
    vm.mem_write(0x1d768eb,b"\0")
    vm.mem_write(0x1d768d0,struct.pack("<I",0x4c8820))
    return vm


def invoke(vm,actor=0):
    vm.mem_write(STACK,struct.pack("<II",END,actor))
    vm.reg_write(UC_X86_REG_ESP,STACK)
    vm.emu_start(0x4c8820,END,count=5000)
    assert vm.reg_read(UC_X86_REG_EIP)==END
    return vm.reg_read(UC_X86_REG_EAX)


def entry(vm,offset,magic,stock,flags=0):
    vm.mem_write(REAL+offset*5,bytes((magic,stock,0x12,0x34,flags)))


class NativeSpellbookTests(unittest.TestCase):
    def test_assembly_matches_and_caves_do_not_overlap(self):
        ks=Ks(KS_ARCH_X86,KS_MODE_32)
        for address,source in a.SOURCES.items():
            self.assertEqual(bytes(ks.asm(source,address)[0]),bytes.fromhex(native.CODE[address]))
        spans=sorted((p,p+len(b)) for p,b in native.candidate_fragments(BOOK,monogamy=True,shared_magic=False).items())
        self.assertTrue(all(left[1]<=right[0] for left,right in zip(spans,spans[1:])))

    def test_projection_preserves_real_inventory_and_native_flags(self):
        vm=new_machine()
        entry(vm,0,4,255)
        entry(vm,5,1,150)
        entry(vm,19,7,2,2)
        original=bytes(vm.mem_read(REAL,160))
        self.assertEqual(invoke(vm),a.VIEWS)
        self.assertEqual(bytes(vm.mem_read(a.VIEWS,10)),bytes((7,2,0x12,0x34,2,1,150,0x12,0x34,2)))
        self.assertEqual(bytes(vm.mem_read(a.VIEWS+40,5)),bytes((4,255,0x12,0x34,0)))
        self.assertEqual(bytes(vm.mem_read(REAL,160)),original)
        self.assertEqual(struct.unpack("<I",vm.mem_read(a.MAPS,4))[0],REAL+19*5)
        vm.mem_write(0x1cfdcbc+2,b"\x10") # ability20 belongs to GF0
        invoke(vm)
        self.assertEqual(bytes(vm.mem_read(a.VIEWS+9,1)),b"\0")
        self.assertEqual(bytes(vm.mem_read(a.VIEWS+4,1)),b"\2") # native restriction remains

    def test_missing_gf_and_ambiguous_gf_fall_back(self):
        for mask in (0,3,2): # none, ambiguous, GF1 without configured book
            vm=new_machine(); vm.mem_write(0x1cfe140,struct.pack("<H",mask))
            self.assertEqual(invoke(vm),REAL)
            self.assertEqual(bytes(vm.mem_read(a.ACTIVE,1)),b"\0")
        vm=new_machine(); vm.mem_write(0x1cff1c3,b"\xff")
        self.assertEqual(invoke(vm),REAL)
        vm=new_machine()
        self.assertEqual(invoke(vm,3),REAL+3*0x1d0)

    def test_zero_and_locked_rows_are_present_in_view(self):
        vm=new_machine(); invoke(vm)
        self.assertEqual(bytes(vm.mem_read(a.VIEWS,5)),bytes((7,0,0,0,2)))
        self.assertEqual(bytes(vm.mem_read(a.VIEWS+5,5)),bytes((1,0,0,0,2)))
        vm.reg_write(UC_X86_REG_ESI,a.VIEWS)
        vm.emu_start(0x4c8a0c,0x4c8a22,count=20)
        self.assertEqual(vm.reg_read(UC_X86_REG_EIP),0x4c8a22)
        vm.reg_write(UC_X86_REG_ESI,a.VIEWS+10) # blank padding remains blank
        vm.emu_start(0x4c8a0c,0x4c8a18,count=20)
        self.assertEqual(vm.reg_read(UC_X86_REG_EIP),0x4c8a18)

    def test_disabled_row_quantity_and_page_extent(self):
        vm=new_machine(); invoke(vm)
        vm.reg_write(UC_X86_REG_ESI,a.VIEWS)
        vm.reg_write(UC_X86_REG_EBX,0)
        vm.reg_write(UC_X86_REG_ESP,STACK)
        vm.emu_start(0x4c8a47,0x4c8a4e,count=20)
        self.assertEqual(vm.reg_read(UC_X86_REG_EIP),0x4c8a4e)
        self.assertEqual(vm.reg_read(UC_X86_REG_ESP),STACK+0x1c)
        vm.reg_write(UC_X86_REG_EBX,0)
        vm.emu_start(0x4fdeb4,0x4fded9,count=30)
        self.assertEqual(bytes(vm.mem_read(0x1d768f1,1)),b"\3")

    def test_actual_debit_targets_owned_spell_id_after_reorder(self):
        for stock,used in ((1,1),(2,1),(150,3),(255,3)):
            vm=new_machine(); entry(vm,19,7,stock); entry(vm,0,4,88)
            invoke(vm)
            vm.mem_write(0x1d76904,bytes((used,))+bytes(31))
            vm.reg_write(UC_X86_REG_EDX,0)
            vm.reg_write(UC_X86_REG_ESI,32)
            vm.reg_write(UC_X86_REG_ECX,a.VIEWS+1)
            vm.reg_write(UC_X86_REG_EBP,0)
            vm.reg_write(UC_X86_REG_ESP,STACK)
            vm.emu_start(0x4fe6ff,0x4fe723,count=3000)
            remaining=stock-used
            self.assertEqual(bytes(vm.mem_read(REAL+19*5,2)),bytes((7 if remaining else 0,remaining)))
            self.assertEqual(bytes(vm.mem_read(REAL,2)),bytes((4,88)))
            invoke(vm)
            self.assertEqual(bytes(vm.mem_read(a.VIEWS,2)),bytes((7,remaining)))

    def test_original_callback_mutation_fails_projection(self):
        self.assertNotEqual(invoke(new_machine(0)),a.VIEWS)

    def test_native_selector_rejects_zero_locked_and_reserved(self):
        from unicorn import UC_HOOK_CODE
        for stock, learned, reserved, native_disabled, enabled in ((0,True,0,False,False),(2,False,0,False,False),(2,True,0,False,True),(2,True,2,False,False),(2,True,0,True,False)):
            vm=new_machine(); entry(vm,5,1,stock,2 if native_disabled else 0)
            if learned: vm.mem_write(0x1cfdcbe,b"\x10")
            vm.mem_write(0x1d768f6,b"\0")
            vm.mem_write(0x1d768ec,b"\1")
            vm.mem_write(0x1d768f2,b"\0") # reservation-aware generic branch
            vm.mem_write(0x1d76905,bytes((reserved,)))
            vm.reg_write(UC_X86_REG_EBP,0)
            vm.reg_write(UC_X86_REG_ESP,STACK)
            def stop(vm, address, size, data):
                if address in (0x4fe2c3,0x4fe2e5): vm.emu_stop()
            vm.hook_add(UC_HOOK_CODE,stop)
            vm.emu_start(0x4fe277,END,count=5000)
            self.assertEqual(vm.reg_read(UC_X86_REG_EIP),0x4fe2c3 if enabled else 0x4fe2e5)

    def test_native_queue_uses_spell_id_and_keeps_display_index_for_cancel(self):
        vm=new_machine()
        vm.mem_write(STACK,struct.pack("<6I",END,2,4,3,8,0))
        vm.reg_write(UC_X86_REG_ESP,STACK)
        vm.emu_start(0x4bb6d0,END,count=100)
        self.assertEqual(bytes(vm.mem_read(0x1d76720,2)),bytes((2,4)))
        self.assertEqual(struct.unpack("<I",vm.mem_read(0x1d76724,4))[0],8)
        vm.mem_write(STACK,struct.pack("<2I",END,0))
        vm.reg_write(UC_X86_REG_ESP,STACK)
        vm.emu_start(0x4bb540,END,count=100)
        self.assertEqual(vm.reg_read(UC_X86_REG_EAX),8)
        vm.reg_write(UC_X86_REG_ESP,STACK)
        vm.emu_start(0x4bb610,0x484d20,count=100)
        args=struct.unpack("<5I",vm.mem_read(vm.reg_read(UC_X86_REG_ESP)+4,20))
        self.assertEqual(args,(0,0,2,4,3))

    def test_gray_zero_quantity_uses_same_native_color_argument_as_name(self):
        for color in (0,7):
            vm=new_machine()
            vm.reg_write(UC_X86_REG_ESI,a.VIEWS)
            vm.reg_write(UC_X86_REG_EBX,color)
            vm.mem_write(STACK,struct.pack("<4I",11,22,33,0))
            vm.reg_write(UC_X86_REG_ESP,STACK)
            vm.emu_start(0x4c8a68,0x4a3400,count=100)
            args=struct.unpack("<6I",vm.mem_read(vm.reg_read(UC_X86_REG_ESP)+4,24))
            self.assertEqual(args,(11,22,33,0,0,color))

    def test_restoring_debit_hook_loses_owned_stock_postcondition(self):
        vm=new_machine(1); entry(vm,19,7,2);invoke(vm)
        vm.mem_write(0x1d76904,b"\1"+bytes(31))
        for reg,value in ((UC_X86_REG_EDX,0),(UC_X86_REG_ESI,32),(UC_X86_REG_ECX,a.VIEWS+1),(UC_X86_REG_EBP,0),(UC_X86_REG_ESP,STACK)):
            vm.reg_write(reg,value)
        vm.emu_start(0x4fe6ff,0x4fe723,count=3000)
        self.assertNotEqual(bytes(vm.mem_read(REAL+19*5,2)),bytes((7,1)))

    def test_composed_hext_has_no_patch_or_allocation_overlaps(self):
        import re
        from . import gameplay_settings
        def spans(text):
            writes=[]; allocations=[]
            for line in text.splitlines():
                if match:=re.fullmatch(r"([0-9A-F]+) = ([0-9A-F ]+)",line):
                    begin=int(match[1],16);writes.append((begin,begin+len(bytes.fromhex(match[2]))))
                elif match:=re.fullmatch(r"([0-9A-F]+):([0-9A-F]+)",line):
                    begin=int(match[1],16);allocations.append((begin,begin+int(match[2],16)))
            return writes,allocations
        spell_writes,spell_allocations=spans(native.build_hext(BOOK,monogamy=True,shared_magic=False,executable=EXE))
        for limit in (1,100,150,255):
            base=gameplay_settings.build_hext(0,single_gf_enabled=True,max_spell_enabled=True,max_spell_value=limit,flat_stat_abilities_enabled=True,streamlined_draw_enabled=True,draw_once_per_enemy=True,better_card_enabled=True,auto_sort=True,auto_sort_magic=True,enhanced_ability_menu=True)
            writes,allocations=spans(base)
            for left in spell_writes:
                self.assertFalse(any(left[0]<right[1] and right[0]<left[1] for right in writes),hex(left[0]))
            for left in spell_allocations:
                self.assertFalse(any(left[0]<right[1] and right[0]<left[1] for right in allocations))
            for begin,end in spell_writes:
                if begin>=a.BASE:
                    self.assertTrue(any(start<=begin and end<=stop for start,stop in spell_allocations))

    def test_native_candidate_refuses_incompatible_modes(self):
        for mono,shared in ((False,False),(True,True)):
            with self.assertRaises(ValueError): native.candidate_fragments(BOOK,monogamy=mono,shared_magic=shared)
        with self.assertRaises(ValueError): native.build_hext(BOOK,monogamy=True,shared_magic=False,executable=b"bad")
        self.assertTrue(native.RUNTIME_READY)
        self.assertEqual(native.build_hext({"schemaVersion":1,"books":[]},monogamy=True,shared_magic=False,executable=EXE),"")


if __name__=="__main__":unittest.main()
