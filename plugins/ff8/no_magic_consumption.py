"""No Magic Consumption as a Hext patch: casting a spell leaves its stock alone.

This used to be a hook in the FFNx derivative (lexeditor_ff8_stock_tweaks.cpp).
It is two small edits, so it lives here now (AGENTS.md, Game patches: Hext
first), shows on the next launch, and needs no driver rebuild. Lexeditor
leaves the driver's copy switched off (`enable_ff8_no_magic_consumption =
false`); if it were on, it would find these bytes changed and refuse to hook.

Against FF8_EN.exe SHA-256 064d466b...9570:

- Battle: 004FE709 subtracts the cast count from a list entry's stock. The
  same list controller serves Magic and Item, so the patch skips the debit
  only while the list callback at [01D768D0] is the Magic list (004C8820);
  Item keeps its debit. It hooks after the stock load, so Max Spell's
  signed-byte repair at 004FE706 stays intact, and resumes at the native
  branch targets (004FE711 kept, 004FE715 emptied) so the zero-stock cleanup
  still runs.
- Field menu: 004F3027 `dec bl` debits a spell cast from the menu after its
  effect has succeeded. It becomes two NOPs. Discard, transfer, Refine and
  stock removal use other paths and are unchanged.
"""

from __future__ import annotations

DEFAULT_NO_MAGIC_CONSUMPTION = False

BATTLE_HOOK = 0x004FE709
BATTLE_ORIGINAL = bytes.fromhex("2B C7 79 04 33 C0")  # sub eax,edi; jns +4; xor eax,eax
BATTLE_KEPT = 0x004FE711
BATTLE_EMPTIED = 0x004FE715
LIST_CALLBACK = 0x01D768D0
MAGIC_LIST = 0x004C8820
FIELD_DEBIT = 0x004F3027
FIELD_ORIGINAL = bytes.fromhex("FE CB")  # dec bl

CAVE = 0x027AB800

ASSEMBLY = f"""
    cmp dword ptr [{LIST_CALLBACK:#x}], {MAGIC_LIST:#x}
    jne debit
    movzx eax, byte ptr [ecx]
    push {BATTLE_KEPT:#x}
    ret
debit:
    sub eax, edi
    jns kept
    xor eax, eax
    push {BATTLE_EMPTIED:#x}
    ret
kept:
    push {BATTLE_KEPT:#x}
    ret
"""

# Assembled at CAVE from ASSEMBLY; tests/ff8/test_ff8_no_magic_consumption.py
# re-assembles it (keystone) and runs it under unicorn.
CODE = bytes.fromhex(
    "81 3D D0 68 D7 01 20 88 4C 00 75 09 0F B6 01 68"
    "11 E7 4F 00 C3 29 F8 79 08 31 C0 68 15 E7 4F 00"
    "C3 68 11 E7 4F 00 C3"
)


def _assemble() -> bytes:
    import keystone
    ks = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)
    return bytes(ks.asm(ASSEMBLY, CAVE)[0])


def build_hext(enabled: bool) -> str:
    """The patch, or nothing: vanilla spell consumption when the tweak is off."""
    if not isinstance(enabled, bool):
        raise ValueError("No Magic Consumption must be true or false")
    if not enabled:
        return ""
    jump = b"\xE9" + (CAVE - (BATTLE_HOOK + 5)).to_bytes(4, "little", signed=True) + b"\x90"
    return "\n".join((
        "# No Magic Consumption: casting leaves spell stock unchanged; Items are still used up.",
        f"{CAVE:X}:{len(CODE):X}",
        f"{CAVE:X} = {CODE.hex(' ').upper()}",
        f"{BATTLE_HOOK:X} = {jump.hex(' ').upper()}",
        f"{FIELD_DEBIT:X} = 90 90",
        "",
    ))


def verified_hooks() -> list[tuple[int, bytes]]:
    return [(BATTLE_HOOK, BATTLE_ORIGINAL), (FIELD_DEBIT, FIELD_ORIGINAL)]
