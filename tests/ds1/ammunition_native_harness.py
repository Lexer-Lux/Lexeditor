"""Execute the shipped Windows-x64 payload against fake native services.

Runs in a child process: faults/timeouts fail the parent test. No retail game
code, process attachment, driver, display window, or private fixture is used.
"""
from __future__ import annotations
import ctypes as C
import json
import mmap
import os
from pathlib import Path
import platform
import shutil
import struct
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
U64 = C.c_uint64
CALL = C.CFUNCTYPE(U64, U64, U64, U64, U64)
SIZE = 0x3300000
STRINGS = {0x13a1bf0: "icon", 0x13a1bd0: "icon_plate_0",
           0x13b01e8: "arrow_number_pleat_R", 0x13b0218: "arrow_number_pleat_L",
           0x13b0248: "text_arrow_number01", 0x13b0270: "text_arrow_number00",
           0x13b01a8: "F20_icon_overweight", 0x13ae108: "plate_black"}
def put(address, fmt, value):
    C.memmove(address, struct.pack(fmt, value), struct.calcsize(fmt))
def get(address, fmt):
    return struct.unpack(fmt, C.string_at(address, struct.calcsize(fmt)))[0]
def wide(address):
    chars = []
    for i in range(128):
        value = get(address + i*2, "<H")
        if not value: return "".join(chars)
        chars.append(chr(value))
    raise AssertionError("Unterminated native text")

class Harness:
    def __init__(self):
        self.temp = tempfile.TemporaryDirectory(prefix="lexeditor-ammunition-native-")
        self.abi = None
        if os.name == "nt":
            self.api = C.WinDLL("kernel32", use_last_error=True)
            self.api.VirtualAlloc.argtypes = [C.c_void_p, C.c_size_t, C.c_uint32, C.c_uint32]
            self.api.VirtualAlloc.restype = C.c_void_p
            self.api.VirtualFree.argtypes = [C.c_void_p, C.c_size_t, C.c_uint32]
            self.api.VirtualFree.restype = C.c_int
            self.base = self.api.VirtualAlloc(None, SIZE, 0x3000, 0x40)
            if not self.base: raise OSError(C.get_last_error(), "VirtualAlloc")
        else:
            compiler = shutil.which("cc") or shutil.which("clang")
            if not compiler: raise RuntimeError("Native fixture requires a C compiler")
            target = Path(self.temp.name)/"abi.so"
            subprocess.run([compiler, "-shared", "-fPIC", "-O2",
                            str(Path(__file__).with_name("ammunition_test_abi.c")),
                            "-o", str(target)], check=True, capture_output=True)
            self.abi = C.CDLL(str(target))
            self.abi.set_callback.argtypes = [C.c_uint, CALL]
            self.abi.invoke.argtypes = [C.c_void_p,U64,U64,U64,U64]
            self.abi.invoke.restype = U64
            self.mapping = mmap.mmap(-1, SIZE, prot=mmap.PROT_READ|mmap.PROT_WRITE|mmap.PROT_EXEC)
            self.base = C.addressof(C.c_char.from_buffer(self.mapping))
        import sys
        sys.path.insert(0, str(ROOT))
        from plugins.ds1.ammunition_controls import _payload
        self.payload, data = _payload()
        C.memmove(self.base + self.payload["rva"], data, len(data))
        for offset, text in STRINGS.items():
            raw = (text+"\0").encode("utf-16le")
            C.memmove(self.base + offset, raw, len(raw))
        self.callbacks, self.errors, self.buffers = [], [], []
        self.children, self.texts, self.visible, self.icons = {}, {}, {}, {}
        self.calls = {}
        self.params = {}
        self.flags = 0
        self.install(0x532b20, self.param)
        self.install(0x71ac10, lambda *_: self.flags)
        self.install(0x681ee0, lambda *_: 0)
        self.install(0xed6020, self.child)
        self.install(0xedbdb0, self.show)
        self.install(0xed83c0, self.show)
        self.install(0xedbd90, self.set_text)
        for address in (0x678500, 0x677990, 0x676e80, 0x67bb20, 0x399410):
            self.install(address, lambda *args, a=address: self.called(a, args))
        self.install(0x71abd0, lambda i,*_: 1 if i in (0x78,0x79) else 37)
        self.icon_thunk = self.callback(self.icon)
        self.vtable = self.buffer(0xe0)
        put(self.vtable + 0xd8, "<Q", self.icon_thunk)
        self.manager = self.buffer(0x20)
        self.world = self.buffer(0x80)
        self.player = self.buffer(0x900)
        self.other_player = self.buffer(0x900)
        self.data = self.buffer(0x700)
        self.actor = self.buffer(0x100)
        self.ctrl = self.buffer(0x300)
        self.context = self.buffer(0x200)
        self.pad = self.buffer(0x400)
        self.stack = self.buffer(0x80)
        self.table1 = self.buffer(0x200)
        self.table2 = self.buffer(0x200)
        self.gauge = self.buffer(0x600)
        self.gauge_root = self.widget()
        put(self.gauge + 0x4f8, "<Q", self.gauge_root)
        for name in ("F20-01_arrow", "category_r2", "targetsite"):
            self.add_child(self.gauge_root, name)
        self.weapon_param = self.buffer(0x120)
        self.params[10000] = self.weapon_param
        for i, item in enumerate((20000,20100,20200,20300)):
            p = self.buffer(0x120)
            put(p+0xba, "<H", 110+i)
            self.params[item] = p
        self.reset()

    def buffer(self, size):
        value = C.create_string_buffer(size)
        self.buffers.append(value)
        return C.addressof(value)
    def callback(self, function):
        index = len(self.callbacks)
        if index >= 16: raise AssertionError("Fixture callback bound")
        def safe(*args):
            try: return function(*args) or 0
            except BaseException as error:
                self.errors.append(repr(error))
                return 0
        callback = CALL(safe)
        self.callbacks.append(callback)
        if self.abi:
            self.abi.set_callback(index, callback)
            return C.cast(getattr(self.abi, f"thunk{index}"), C.c_void_p).value
        return C.cast(callback, C.c_void_p).value
    def install(self, rva, function):
        thunk = self.callback(function)
        raw = b"\xff\x25\0\0\0\0" + struct.pack("<Q", thunk)
        C.memmove(self.base+rva, raw, len(raw))
    def invoke(self, entry, *args):
        address = self.base + self.payload["entrypoints"][entry]
        args = list(args) + [0]*(4-len(args))
        result = self.abi.invoke(address,*args) if self.abi else CALL(address)(*args)
        assert not self.errors, self.errors
        return result
    def param(self, ref, item, *_):
        C.memset(ref,0,40)
        put(ref,"<I",item & 0xffffffff)
        put(ref+8,"<Q",self.params.get(item,0))
    def called(self, address, args):
        self.calls[address] = self.calls.get(address,0)+1
        return 0
    def child(self, root, name, *_):
        return self.children.get((root,wide(name)),0)
    def show(self, child, visible, *_):
        self.visible[child]=bool(visible)
        flag=get(child+0x28,"<B")
        put(child+0x28,"<B",(flag&~2)|(2 if visible else 0))
    def set_text(self, child, text, *_):
        self.texts[child]=wide(text)
    def icon(self, child, prop, variant, *_):
        assert prop==0x1388
        assert get(variant+8,"<i")==2
        self.icons[child]=get(variant,"<i")
    def widget(self):
        widget=self.buffer(0x300)
        put(widget,"<Q",self.vtable if hasattr(self,"vtable") else 0)
        for offset in (0x214,0x22c,0x230): put(widget+offset,"<i",-1)
        return widget
    def add_child(self, widget, name):
        child=self.widget()
        self.children[widget,name]=child
        self.show(child,1)
        return child
    def arrow(self, kind):
        widget=self.widget()
        put(widget+0x208,"<i",kind)
        for name in STRINGS.values(): self.add_child(widget,name)
        return widget
    def reset(self, kind=10, stance=3, hand=1):
        C.memset(self.base+self.payload["scratchRva"],0,128)
        self.flags=0
        put(self.base+0x1c8a530,"<Q",self.manager)
        put(self.manager+0x10,"<Q",self.data)
        put(self.base+0x1c77e50,"<Q",self.world)
        put(self.world+0x68,"<Q",self.player)
        put(self.base+0x1c7b648,"<Q",0)
        put(self.ctrl+0x10,"<Q",self.player)
        put(self.ctrl+0x48,"<Q",self.context)
        put(self.player+0x840,"<Q",self.actor)
        put(self.player+0x3f8,"<i",100)
        put(self.player+0x525,"<B",0)
        C.memset(self.context,0,0x200)
        put(self.weapon_param+0xe2,"<B",kind)
        equip=self.data+0x280
        saved=self.data+0x300
        for a in (saved,self.actor):
            put(a+8,"<i",stance)
            put(a+0xc,"<i",0)
            put(a+0x10,"<i",0)
            put(a+0x24,"<i",10000 if hand==0 else -1)
            put(a+0x28,"<i",10000 if hand==1 else -1)
            for off in (0x14,0x18,0x1c,0x20): put(a+off,"<i",0)
        put(equip+0x130,"<i",8)
        put(equip+0x140,"<i",2)
        put(equip+0x150,"<Q",self.table1)
        put(equip+0x158,"<Q",self.table2)
        for slot,index,item,value in ((4,0,20000,11),(6,3,20100,22),(5,1,20200,33),(7,4,20300,44)):
            put(equip+0x24+slot*4,"<i",index)
            put(saved+0x24+slot*4,"<i",item)
            put(self.actor+0x24+slot*4,"<i",item)
            table=self.table1 if index<2 else self.table2
            put(table+index*0x1c+8,"<i",value)
        # Wrong split-relative addressing reads these decoys.
        put(self.table2+8,"<i",9876)
        put(self.table2+0x1c+8,"<i",9877)
    def selected(self,kind=10,hand=1):
        offset=(0x14 if kind==10 else 0x1c)+hand*4
        a=get(self.actor+offset,"<i")
        assert a==get(self.data+0x300+offset,"<i")
        return a
    def step(self,raw,busy=False,admit=True,queued=-1):
        put(self.stack+0x3b,"<B",bool(raw&1))
        put(self.stack+0x3c,"<B",bool(raw&2))
        put(self.ctrl+0x100,"<B",4 if busy else 0)
        put(self.context+0x1a0,"<B",1 if admit else 0)
        for off,value in ((0x84,bool(raw&1) and admit),(0x89,bool(raw&2) and admit),
                          (0x8b,bool(raw&1) and admit),(0x1c4,0),(0x90,0x5a)):
            put(self.pad+off,"<B",value)
        put(self.pad+0x224,"<i",queued)
        before=C.string_at(self.table1,0x200)+C.string_at(self.table2,0x200)
        self.invoke("ammo_route",self.ctrl,self.pad,self.stack)
        assert get(self.pad+0x90,"<B")==0x5a
        assert get(self.player+0x3f8,"<i")==100
        assert before==C.string_at(self.table1,0x200)+C.string_at(self.table2,0x200)
        return get(self.pad+0x84,"<B"),get(self.pad+0x89,"<B")

    def close(self):
        if os.name=="nt": self.api.VirtualFree(self.base,0,0x8000)
        else: self.mapping.close()
        self.temp.cleanup()

def run():
    h=Harness()
    count=0
    def ok(value):
        nonlocal count
        assert value
        count+=1
    try:
        for kind in (10,11):
            for mask,slot in ((1,0),(2,1),(3,0)):
                h.reset(kind)
                ok(h.step(mask)==(1,0) and h.selected(kind)==slot)
            h.reset(kind)
            ok(h.step(2)==(1,0))
            ok(h.step(2,True)==(1,0))
            ok(h.step(0,True)==(0,0) and h.selected(kind)==1)
            ok(h.step(1,True,False)==(0,0) and h.selected(kind)==1)
            # Pending primary request must not change any bolt in a multi-shot burst.
            for remaining in (9,8,7):
                put(h.table2+3*0x1c+8,"<i",remaining)
                ok(h.step(0,True,False)==(0,0) and h.selected(kind)==1)
            ok(h.step(0,False)==(1,0) and h.selected(kind)==0)
            h.reset(kind,2,0)
            ok(h.step(2)==(1,0) and h.selected(kind,0)==1)
            h.reset(kind)
            ok(h.step(0,queued=5)==(1,0) and h.selected(kind)==1)
            ok(get(h.pad+0x224,"<i")==-1)
        h.reset(10,1)
        ok(h.step(2)==(1,0))
        for a in (h.actor,h.data+0x300): put(a+8,"<i",3)
        ok(h.step(2,True)==(1,0) and h.selected()==1)
        for kind in (0,1,9,12):
            h.reset(kind)
            ok(h.step(2)==(0,1))
        h.reset()
        put(h.world+0x68,"<Q",h.other_player)
        ok(h.step(2)==(0,1))
        h.reset()
        h.flags=1
        ok(h.step(2)==(0,1) and h.selected()==0)
        h.reset()
        put(h.context+0xa4,"<I",0x08000000)
        ok(h.step(2)==(0,1))
        h.reset()
        put(h.actor+0x28,"<i",-1)
        ok(h.step(2)==(0,1))
        h.reset()
        put(h.data+0x308,"<i",2)
        ok(h.step(2)==(0,1))
        for kind,first,second in ((10,11,22),(11,33,44)):
            h.reset(kind)
            right,left=h.arrow(4),h.arrow(5)
            h.invoke("ammo_hud_arrow",right,1)
            h.invoke("ammo_hud_arrow",left,0)
            ok(h.texts[h.children[right,"text_arrow_number01"]]==str(first))
            ok(h.texts[h.children[left,"text_arrow_number00"]]==str(second))
            ok(h.icons[h.children[right,"icon"]]!=h.icons[h.children[left,"icon"]])
            h.invoke("ammo_hud_visibility",left)
            ok(h.visible[left] and not h.visible[h.children[left,"plate_black"]])
            # A genuine zero is not an unequipped slot.
            index=3 if kind==10 else 4
            put(h.table2+index*0x1c+8,"<i",0)
            h.invoke("ammo_hud_arrow",left,0)
            h.invoke("ammo_hud_visibility",left)
            ok(h.texts[h.children[left,"text_arrow_number00"]]=="0")
            ok(h.visible[h.children[left,"icon_plate_0"]] and h.visible[h.children[left,"plate_black"]])
            # Both slots must refresh when their new quantities happen to match.
            put(h.table2+index*0x1c+8,"<i",first)
            h.invoke("ammo_hud_arrow",left,0)
            ok(h.texts[h.children[left,"text_arrow_number00"]]==str(first))
        h.reset()
        primary=h.arrow(4)
        put(h.table1+8,"<i",2147483647)
        h.invoke("ammo_hud_arrow",primary,1)
        ok(h.texts[h.children[primary,"text_arrow_number01"]]=="2147483647")
        put(h.data+0x280+0x24+4*4,"<i",-1)
        h.invoke("ammo_hud_arrow",primary,1)
        ok(h.texts[h.children[primary,"text_arrow_number01"]]=="-")
        for identifier in (0x78,0x79,0x96):
            ok(h.invoke("ammo_hud_mode",identifier)==(0 if identifier!=0x96 else 37))
        h.invoke("ammo_reticle",h.gauge)
        for name in ("F20-01_arrow","category_r2"):
            ok(not h.visible[h.children[h.gauge_root,name]])
        ok(h.visible[h.children[h.gauge_root,"targetsite"]])
        put(h.weapon_param+0xe2,"<B",1)
        h.invoke("ammo_reticle",h.gauge)
        for name in ("F20-01_arrow","category_r2"):
            ok(h.visible[h.children[h.gauge_root,name]])
        h.invoke("ammo_hud_arrow",primary,1)
        ok(h.calls.get(0x678500)==1)
        ok(h.invoke("ammo_hud_mode",0x78)==1)
        h.reset()
        right,left=h.arrow(4),h.arrow(5)
        before=h.calls.get(0x676e80,0)
        h.invoke("ammo_hud_shortcut",right)
        ok(h.calls.get(0x676e80,0)==before)
        h.invoke("ammo_hud_shortcut",left)
        ok(h.calls.get(0x676e80,0)==before+1)
        print(f"native payload: {count} assertions passed (fake services, not in-game acceptance)")
    finally:
        h.close()
if __name__=="__main__": run()
