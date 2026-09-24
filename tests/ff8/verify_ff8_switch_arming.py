"""Squall's Switch menu ignores the press that opened it, executed in an emulator.

The confirming press was still in FF8's repeat word on the first frames, and
the menu read it as confirm or cancel: the GF names flashed for a frame and the
menu closed. The update now waits for every key to be released first.
"""
from __future__ import annotations

# Dev caches and outputs live in the temp folder, never in the checkout.
DEV_CACHE = __import__("pathlib").Path(__import__("tempfile").gettempdir()) / "lexeditor-dev"
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.append(str(DEV_CACHE / "gf-spellbooks-test-deps"))
import unicorn  # noqa: E402
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ESP, UC_X86_REG_EIP  # noqa: E402

from plugins.ff8 import switch_issue_52 as s  # noqa: E402

STACK, RETURN = 0x30F0000, 0x30E0000


def frame(vm, keys: int, log: list) -> None:
    def read_input(uc, *_):
        uc.reg_write(UC_X86_REG_EAX, keys)
        esp = uc.reg_read(UC_X86_REG_ESP)
        uc.reg_write(UC_X86_REG_ESP, esp + 4)
        uc.reg_write(UC_X86_REG_EIP, struct.unpack("<I", uc.mem_read(esp, 4))[0])
    hooks = [vm.hook_add(unicorn.UC_HOOK_CODE, read_input, begin=s.READ_INPUT, end=s.READ_INPUT)]
    for name, address in (("close", s.CLOSE_CAVE), ("refresh", s.REFRESH_CAVE)):
        def stub(uc, *_, name=name):
            log.append(name)
            esp = uc.reg_read(UC_X86_REG_ESP)
            uc.reg_write(UC_X86_REG_ESP, esp + 4)
            uc.reg_write(UC_X86_REG_EIP, struct.unpack("<I", uc.mem_read(esp, 4))[0])
        hooks.append(vm.hook_add(unicorn.UC_HOOK_CODE, stub, begin=address, end=address))
    vm.mem_write(STACK - 4, struct.pack("<I", RETURN))
    vm.reg_write(UC_X86_REG_ESP, STACK - 4)
    vm.emu_start(s.UPDATE_CAVE, RETURN, count=2000)
    for hook in hooks:
        vm.hook_del(hook)


def main() -> int:
    vm = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_32)
    vm.mem_map(0x0400000, 0x2600000)
    vm.mem_map(0x3000000, 0x100000)
    vm.mem_write(RETURN, b"\xC3")
    vm.mem_write(s.UPDATE_CAVE, s._update_payload())
    vm.mem_write(s.SWITCH_ACTIVE, b"\x01")
    vm.mem_write(s.SWITCH_SELECTION, b"\x00")
    log: list = []
    for held in (0x08, 0x10, 0x48):   # the opening press, whatever its bits
        frame(vm, held, log)
        assert not log and vm.mem_read(s.SWITCH_ACTIVE, 1)[0] == 1, log
    frame(vm, 0, log)
    assert not log and vm.mem_read(s.SWITCH_ACTIVE, 1)[0] == 2
    frame(vm, 0x10, log)
    assert log == ["close"], log
    log.clear()
    frame(vm, 0x08, log)
    assert log == ["refresh", "close"], log
    print("Switch: the opening press is ignored until released; confirm and cancel work after.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
