"""List FF8_EN.exe instructions that directly reference character magic data.

This is an evidence tool for issue #51. It reads the verified executable and
prints code references. It does not patch or write the executable.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import struct

import pefile
from capstone import CS_AC_WRITE, CS_ARCH_X86, CS_MODE_32, Cs
from capstone.x86 import (
    X86_INS_CALL,
    X86_INS_JMP,
    X86_INS_RET,
    X86_OP_IMM,
    X86_OP_MEM,
    X86_OP_REG,
)


CHARACTER_BASE = 0x01CFE0E8
CHARACTER_STRIDE = 0x98
CHARACTER_COUNT = 8
MAGIC_OFFSET = 0x10
MAGIC_SIZE = 0x40


@dataclass(frozen=True)
class DirectReference:
    address: int
    raw: bytes
    mnemonic: str
    operands: str
    references: tuple[tuple[str, int, str], ...]
    writes_magic: bool = False


@dataclass(frozen=True)
class DerivedReference:
    address: int
    raw: bytes
    mnemonic: str
    operands: str
    source_address: int
    source_register: str
    displacement: int
    writes_magic: bool = False


@dataclass(frozen=True)
class ProvedWriterFamily:
    """A derived or bulk writer family proved against the supported executable."""

    name: str
    transaction_entry: int
    writer_guards: tuple[tuple[int, bytes], ...]
    ownership: str


PROVED_WRITER_FAMILIES = (
    ProvedWriterFamily(
        "battle_to_saved_commit",
        0x00486CD0,
        ((0x00486D22, bytes.fromhex("88 51 ff")),
         (0x00486D28, bytes.fromhex("88 11"))),
        "battle teardown adopts only an already-equal canonical actor pool",
    ),
    ProvedWriterFamily(
        "saved_inventory_swap",
        0x004CB4A0,
        ((0x004CB503, bytes.fromhex("88 58 fd")),
         (0x004CB50A, bytes.fromhex("88 58 fe")),
         (0x004CB50F, bytes.fromhex("88 1e")),
         (0x004CB515, bytes.fromhex("88 5c 28 fe"))),
        "preserve canonical stock across the private character-data swap",
    ),
    ProvedWriterFamily(
        "battle_callback_transaction",
        0x004FDD90,
        ((0x004FE715, bytes.fromhex("c6 41 ff 00")),
         (0x004FE719, bytes.fromhex("88 01"))),
        "reconcile only when callback 0x004C8820 is stored at 0x01D768D0",
    ),
    ProvedWriterFamily(
        "initial_inventory_constructor",
        0x0047F320,
        ((0x0047F6C1, bytes.fromhex("88 41 ff")),
         (0x0047F6C4, bytes.fromhex("c6 01 32")),
         (0x0047F6DC, bytes.fromhex("88 4f fd")),
         (0x0047F6DF, bytes.fromhex("c6 47 fe 32"))),
        "runs before activation; preserve canonical if reached while active",
    ),
    ProvedWriterFamily(
        "script_inventory_constructor",
        0x00482610,
        ((0x00482AF6, bytes.fromhex("88 41 ff")),
         (0x00482AF9, bytes.fromhex("c6 01 32")),
         (0x00482B11, bytes.fromhex("88 59 fd")),
         (0x00482B14, bytes.fromhex("c6 41 fe 32"))),
        "preserve canonical in active normal mode; vanilla while suspended",
    ),
    ProvedWriterFamily(
        "battle_actor_clear",
        0x00495530,
        ((0x0049566D, bytes.fromhex("88 50 ff")),
         (0x00495670, bytes.fromhex("88 10")),
         (0x00495672, bytes.fromhex("88 50 01")),
         (0x00495675, bytes.fromhex("88 50 fe")),
         (0x00495678, bytes.fromhex("88 50 fd"))),
        "initialization only; every caller follows with 0x00495960",
    ),
    ProvedWriterFamily(
        "saved_stock_normalizer",
        0x004BE790,
        ((0x004BE7DD, bytes.fromhex("88 1e")),
         (0x004BE7DF, bytes.fromhex("88 5e 01"))),
        "adopt the completed normalized inventory and mirror it",
    ),
    ProvedWriterFamily(
        "transfer_zero_cleanup",
        0x004C3120,
        ((0x004C313D, bytes.fromhex("c6 00 00")),),
        "owned by the disabled or replaced transfer family",
    ),
    ProvedWriterFamily(
        "field_magic_reorder",
        0x004F0030,
        ((0x004F0097, bytes.fromhex("c6 00 00")),
         (0x004F009B, bytes.fromhex("c6 00 00")),
         (0x004F00B7, bytes.fromhex("88 01")),
         (0x004F00BA, bytes.fromhex("88 11"))),
        "reconcile after the complete reorder returns",
    ),
    ProvedWriterFamily(
        "field_controller_snapshot_restore",
        0x004F02F0,
        ((0x004F42D5, bytes.fromhex("88 10")),
         (0x004F4338, bytes.fromhex("88 10"))),
        "preserve canonical across the two-character private-data exchange",
    ),
    ProvedWriterFamily(
        "field_add_inner",
        0x0047EE13,
        ((0x0047EE6D, bytes.fromhex("88 04 4d f9 e0 cf 01")),
         (0x0047EE91, bytes.fromhex("88 98 f8 e0 cf 01")),
         (0x0047EEA0, bytes.fromhex("88 88 f9 e0 cf 01"))),
        "owned by the outer 0x0047EE00 field-add transaction",
    ),
    ProvedWriterFamily(
        "battle_magic_prepare",
        0x00486A23,
        ((0x00486A93, bytes.fromhex("88 01")),
         (0x00486AA4, bytes.fromhex("88 88 82 f0 cf 01")),
         (0x00486AB2, bytes.fromhex("88 98 83 f0 cf 01")),
         (0x00486B0E, bytes.fromhex("88 88 83 f0 cf 01")),
         (0x00486B1B, bytes.fromhex("c6 80 82 f0 cf 01 00"))),
        "battle-private staging only; the saved commit is 0x00486CD0",
    ),
    ProvedWriterFamily(
        "battle_magic_clear_actor",
        0x00495960,
        ((0x004959B1, bytes.fromhex("88 59 ff")),
         (0x004959B7, bytes.fromhex("88 19"))),
        "battle-private staging only; the saved commit is 0x00486CD0",
    ),
    ProvedWriterFamily(
        "stock_add_core",
        0x004C2C70,
        ((0x004C2CD8, bytes.fromhex("88 42 01")),
         (0x004C2D11, bytes.fromhex("88 99 f8 e0 cf 01")),
         (0x004C2D17, bytes.fromhex("88 81 f9 e0 cf 01"))),
        "owned by the add wrapper or the blocked transfer family",
    ),
    ProvedWriterFamily(
        "stock_remove_core",
        0x004C2D50,
        ((0x004C2D99, bytes.fromhex("c6 06 00")),
         (0x004C2DBA, bytes.fromhex("88 56 01"))),
        "owned by the remove wrapper or the blocked transfer family",
    ),
    ProvedWriterFamily(
        "magic_menu_remove_inner",
        0x004F2EA7,
        ((0x004F3029, bytes.fromhex("88 1c 45 f9 e0 cf 01")),
         (0x004F304E, bytes.fromhex("c6 80 f8 e0 cf 01 00"))),
        "owned by the outer 0x004F02F0 controller transaction",
    ),
    ProvedWriterFamily(
        "magic_menu_transfer_source_inner",
        0x004F3EF0,
        ((0x004F3FA3, bytes.fromhex("88 0c 75 f9 e0 cf 01")),
         (0x004F3FBE, bytes.fromhex("88 04 55 f9 e0 cf 01"))),
        "owned by the outer 0x004F02F0 controller transaction",
    ),
    ProvedWriterFamily(
        "magic_menu_transfer_target_inner",
        0x004F3FF8,
        ((0x004F4149, bytes.fromhex("88 04 4d f9 e0 cf 01")),
         (0x004F4166, bytes.fromhex("88 14 4d f9 e0 cf 01"))),
        "owned by the outer 0x004F02F0 controller transaction",
    ),
    ProvedWriterFamily(
        "magic_menu_swap_inner",
        0x004F4808,
        ((0x004F4821, bytes.fromhex("88 14 4d f8 e0 cf 01")),
         (0x004F483F, bytes.fromhex("88 14 4d f9 e0 cf 01")),
         (0x004F485D, bytes.fromhex("88 14 4d f8 e0 cf 01")),
         (0x004F487B, bytes.fromhex("88 14 4d f9 e0 cf 01"))),
        "owned by the outer 0x004F02F0 controller transaction",
    ),
    ProvedWriterFamily(
        "transfer_clear_inner",
        0x004F5B8C,
        ((0x004F5BA1, bytes.fromhex("c6 04 55 f8 e0 cf 01 00")),
         (0x004F5BBC, bytes.fromhex("c6 04 4d f9 e0 cf 01 00"))),
        "owned by the blocked transfer family",
    ),
    ProvedWriterFamily(
        "transfer_move",
        0x004F6030,
        ((0x004F60C7, bytes.fromhex("88 96 f8 e0 cf 01")),
         (0x004F60CD, bytes.fromhex("88 96 f9 e0 cf 01")),
         (0x004F60E8, bytes.fromhex("88 9e f8 e0 cf 01")),
         (0x004F60F6, bytes.fromhex("88 8e f9 e0 cf 01"))),
        "owned by the blocked transfer family",
    ),
    ProvedWriterFamily(
        "transfer_swap_inner",
        0x004F619C,
        ((0x004F62A4, bytes.fromhex("88 8e f9 e0 cf 01")),
         (0x004F62BF, bytes.fromhex("88 9e f8 e0 cf 01")),
         (0x004F62C5, bytes.fromhex("88 8e f9 e0 cf 01"))),
        "owned by the blocked transfer family",
    ),
    ProvedWriterFamily(
        "transfer_restore_inner",
        0x004F6300,
        ((0x004F646B, bytes.fromhex("c6 86 f8 e0 cf 01 00")),
         (0x004F647C, bytes.fromhex("c6 86 f9 e0 cf 01 00")),
         (0x004F6501, bytes.fromhex("c6 87 f8 e0 cf 01 00")),
         (0x004F6508, bytes.fromhex("c6 87 f9 e0 cf 01 00")),
         (0x004F654C, bytes.fromhex("88 88 f8 e0 cf 01")),
         (0x004F6552, bytes.fromhex("88 90 f9 e0 cf 01")),
         (0x004F6568, bytes.fromhex("88 98 f8 e0 cf 01")),
         (0x004F656E, bytes.fromhex("88 90 f9 e0 cf 01"))),
        "owned by the blocked transfer family",
    ),
    ProvedWriterFamily(
        "draw_commit_inner",
        0x0054F06A,
        ((0x0054F1DA, bytes.fromhex("88 0c 45 f8 e0 cf 01")),
         (0x0054F1E1, bytes.fromhex("88 14 45 f9 e0 cf 01"))),
        "owned by the outer 0x0054E9B0 Draw transaction",
    ),
    ProvedWriterFamily(
        "redistribution_sum",
        0x0056DB50,
        ((0x0056DBC8, bytes.fromhex("c6 04 55 f9 e0 cf 01 64")),
         (0x0056DC35, bytes.fromhex("88 0c 45 f9 e0 cf 01")),
         (0x0056DCA3, bytes.fromhex("88 88 f8 e0 cf 01")),
         (0x0056DCA9, bytes.fromhex("88 98 f9 e0 cf 01"))),
        "owned by the blocked redistribution family",
    ),
)

PROVED_BULK_WRITER_FAMILIES = (
    ProvedWriterFamily(
        "scenario_bulk_overwrite_restore",
        0x004C99E0,
        ((0x004C9A11, bytes.fromhex("f3 a5")),
         (0x004CADB7, bytes.fromhex("f3 a5"))),
        "suspend before overwrite and resume after the 0x004CADA0 restore",
    ),
)


COPY_HELPER_BATTLE_STOCK_READ_CALLS = (
    0x004DA4B1, 0x004DAB97, 0x004DACF3, 0x004DBC2B, 0x004DBD55,
    0x004DBFCB, 0x004DC597, 0x004DC8B1, 0x004DC947, 0x004DCA2B,
    0x004DCDDA, 0x004DD3CC, 0x004DD4D3, 0x004DDE3F, 0x004DE6F8,
    0x004DF46A, 0x004DF503, 0x004DF576, 0x004DF67E, 0x004E03DD,
)
COPY_HELPER_SAVED_STOCK_READ_CALL = 0x004E2F34
COPY_HELPER_SAVED_STOCK_WRITE_CALL = 0x004E4F1E
COPY_HELPER_NON_LIVE_CALLS = (0x004E2F17, 0x004E3032, 0x004E3ED6, 0x004E3EE8)

PROVED_TRANSACTION_CALLERS = {
    0x00486CD0: (0x0048B8E9,),
    0x004CB4A0: (
        0x004CB412, 0x004CB447, 0x004CB5CA, 0x004CBEAE,
        0x004CBEE3, 0x004CBF39, 0x004CC413,
    ),
    0x00486A10: (0x004859FE, 0x00485B06, 0x0048D57E, 0x00493EE7),
    0x00495960: (0x0048B883, 0x0048B97B, 0x00495F14, 0x0049721B),
    0x00495530: (0x0048B874, 0x00495F05, 0x0049720C),
    0x004F0030: (0x004F4AAC,),
    0x004C3120: (
        0x004F5AA6, 0x004F5BC8, 0x004F6057, 0x004F616E,
        0x004F617B, 0x004F65B1, 0x004F65B7,
    ),
    0x004C99E0: (0x004DA1FD, 0x004D48D5, 0x004CFB02, 0x004CCBBD),
    0x004CADA0: (0x004C9E0E, 0x004CA7FA),
}

# Exact E8 caller sets for every affine writer-family entry. Empty tuples are
# deliberate: these are internal blocks or indirect callback entries.
AFFINE_WRITER_FAMILY_CALLERS = {
    0x0047EE13: (),
    0x0047F320: (0x0047F13F,),
    0x00482A20: (),
    0x00486A23: (),
    0x00486CD0: (0x0048B8E9,),
    0x00495530: (0x0048B874, 0x00495F05, 0x0049720C),
    0x00495960: (0x0048B883, 0x0048B97B, 0x00495F14, 0x0049721B),
    0x004BE790: (
        0x004BE874, 0x004C0C15, 0x004C0F58, 0x004C2D39, 0x004C2DE6,
        0x004C2F50, 0x004C2F63, 0x004D7B1F, 0x004D7C17, 0x004DA4BE,
        0x004DABA9, 0x004DAD05, 0x004DBC3D, 0x004DBD6A, 0x004DBFE0,
        0x004DC5A9, 0x004DC8C3, 0x004DC959, 0x004DCA3D, 0x004DCDEC,
        0x004DD3DE, 0x004DD4E5, 0x004DDE4D, 0x004DE706, 0x004DF477,
        0x004DF515, 0x004DF588, 0x004DF690, 0x004E03EA, 0x004E04D5,
        0x004F09A7, 0x004F09B2, 0x004F0D8C, 0x004F0DEF, 0x004F137B,
        0x004F13DE, 0x004F1609, 0x004F166C, 0x004F1B29, 0x004F3080,
        0x004F42DC, 0x004F433F, 0x004F473B, 0x004F479E, 0x004F4886,
        0x004F4891, 0x004F5AB1, 0x004F5BD3, 0x004F6009, 0x004F6015,
        0x004FB238,
    ),
    0x004C2C70: (0x004C2D31, 0x004F5FDE),
    0x004C2D50: (0x004C2DE0, 0x004F5FF5),
    0x004C3120: (
        0x004F5AA6, 0x004F5BC8, 0x004F6057, 0x004F616E,
        0x004F617B, 0x004F65B1, 0x004F65B7,
    ),
    0x004CB4A0: (
        0x004CB412, 0x004CB447, 0x004CB5CA, 0x004CBEAE,
        0x004CBEE3, 0x004CBF39, 0x004CC413,
    ),
    0x004F004F: (),
    0x004F2EA7: (),
    0x004F3EF0: (),
    0x004F3FF8: (),
    0x004F41B9: (),
    0x004F4808: (),
    0x004F5B8C: (),
    0x004F6030: (0x004F1DC0,),
    0x004F619C: (),
    0x004F6300: (
        0x004F0D27, 0x004F1316, 0x004F1749,
        0x004F3FDF, 0x004F4277, 0x004F48ED,
    ),
    0x004FE6CE: (),
    0x0054F06A: (),
    0x0056DB50: (0x0051E778,),
}

GENERIC_LIST_CONTROLLER_DIRECT_CALLS = (0x004C8316,)
GENERIC_LIST_CONTROLLER_TAIL_CALLS = (
    0x004C7CF0, 0x004C7EEE, 0x004C8590, 0x004C880F, 0x004C88A5,
)
GENERIC_LIST_CONTROLLER_REGISTRATIONS = (
    0x004C82A8, 0x004C8577, 0x004C87C7, 0x004C8867,
)
BATTLE_MAGIC_CALLBACK_REGISTRATION = 0x004BC8F8
BATTLE_MAGIC_CALLBACK = 0x004C8820
BATTLE_MAGIC_CALLBACK_GLOBAL = 0x01D768D0

SCENARIO_BULK_SHAPE_GUARDS = {
    # One 0x98-byte record per iteration, ending after all eight records.
    0x004C9A02: bytes.fromhex("b9 26 00 00 00"),
    0x004C9A0B: bytes.fromhex("81 c2 98 00 00 00"),
    0x004C9A11: bytes.fromhex("f3 a5"),
    0x004C9A22: bytes.fromhex("05 98 00 00 00"),
    0x004C9A28: bytes.fromhex("3d a8 e5 cf 01"),
    # Restore all eight records in one 0x130-dword copy.
    0x004CADA7: bytes.fromhex("b9 30 01 00 00"),
    0x004CADAC: bytes.fromhex("8d b0 90 74 02 00"),
    0x004CADB2: bytes.fromhex("bf e8 e0 cf 01"),
    0x004CADB7: bytes.fromhex("f3 a5"),
}


def classify(value: int) -> str | None:
    for character in range(CHARACTER_COUNT):
        record = CHARACTER_BASE + character * CHARACTER_STRIDE
        if record <= value < record + CHARACTER_STRIDE:
            offset = value - record
            area = "magic" if MAGIC_OFFSET <= offset < MAGIC_OFFSET + MAGIC_SIZE else "record"
            return f"character={character} offset=0x{offset:02X} area={area}"
    return None


def find_direct_references(executable: Path, *, magic_only: bool = False) -> list[DirectReference]:
    """Return absolute-address operands inside FF8 character records.

    This is deliberately a lower-bound audit. It cannot classify instructions
    that first load a character-record base and later dereference offset 0x10.
    """
    pe = pefile.PE(str(executable), fast_load=True)
    image_base = pe.OPTIONAL_HEADER.ImageBase
    text = next(section for section in pe.sections if section.Name.rstrip(b"\0") == b".text")
    code = text.get_data()
    start = image_base + text.VirtualAddress

    decoder = Cs(CS_ARCH_X86, CS_MODE_32)
    decoder.detail = True
    decoder.skipdata = True
    found: list[DirectReference] = []
    for instruction in decoder.disasm(code, start):
        if instruction.id == 0:
            continue
        references: list[tuple[str, int, str]] = []
        writes_magic = False
        for operand in instruction.operands:
            if operand.type == X86_OP_MEM:
                label = classify(operand.mem.disp & 0xFFFFFFFF)
                if label:
                    references.append(("mem", operand.mem.disp & 0xFFFFFFFF, label))
                    writes_magic = writes_magic or (
                        "area=magic" in label and bool(operand.access & CS_AC_WRITE)
                    )
            elif operand.type == X86_OP_IMM:
                label = classify(operand.imm & 0xFFFFFFFF)
                if label:
                    references.append(("imm", operand.imm & 0xFFFFFFFF, label))
        if magic_only:
            references = [reference for reference in references if "area=magic" in reference[2]]
        if references:
            found.append(
                DirectReference(
                    instruction.address,
                    bytes(instruction.bytes),
                    instruction.mnemonic,
                    instruction.op_str,
                    tuple(references),
                    writes_magic,
                )
            )
    return found


def find_local_derived_references(executable: Path) -> list[DerivedReference]:
    """Find same-basic-block dereferences of a proved character-record base.

    This adds evidence without pretending to be whole-program data-flow.  A
    register becomes tracked only when one instruction directly loads an
    address inside the eight character records.  Calls and control-flow edges
    clear the state.  A later memory operand using that register is reported
    only when its constant displacement is inside the 64-byte magic field.
    """
    pe = pefile.PE(str(executable), fast_load=True)
    image_base = pe.OPTIONAL_HEADER.ImageBase
    text = next(section for section in pe.sections if section.Name.rstrip(b"\0") == b".text")
    code = text.get_data()
    start = image_base + text.VirtualAddress

    decoder = Cs(CS_ARCH_X86, CS_MODE_32)
    decoder.detail = True
    decoder.skipdata = True
    tracked: dict[int, tuple[int, str]] = {}
    found: list[DerivedReference] = []
    for instruction in decoder.disasm(code, start):
        if instruction.id == 0:
            tracked.clear()
            continue

        for operand in instruction.operands:
            if operand.type != X86_OP_MEM or not operand.mem.base:
                continue
            provenance = tracked.get(operand.mem.base)
            if provenance is None:
                continue
            displacement = int(operand.mem.disp)
            if MAGIC_OFFSET <= displacement < MAGIC_OFFSET + MAGIC_SIZE:
                found.append(DerivedReference(
                    instruction.address,
                    bytes(instruction.bytes),
                    instruction.mnemonic,
                    instruction.op_str,
                    provenance[0],
                    provenance[1],
                    displacement,
                    bool(operand.access & CS_AC_WRITE),
                ))

        _reads, writes = instruction.regs_access()
        for register in writes:
            tracked.pop(register, None)

        if instruction.mnemonic in {"lea", "mov"} and len(instruction.operands) >= 2:
            destination, source = instruction.operands[:2]
            if destination.type == X86_OP_REG:
                source_value = None
                if source.type == X86_OP_IMM:
                    source_value = source.imm & 0xFFFFFFFF
                elif (instruction.mnemonic == "lea" and source.type == X86_OP_MEM
                      and not source.mem.base):
                    source_value = source.mem.disp & 0xFFFFFFFF
                label = classify(source_value) if source_value is not None else None
                if label and "area=record" in label:
                    tracked[destination.reg] = (
                        instruction.address,
                        instruction.reg_name(destination.reg),
                    )

        if instruction.id in {X86_INS_CALL, X86_INS_JMP, X86_INS_RET} or instruction.group(1):
            tracked.clear()
    return found


def missing_proved_writer_families(
    executable: Path,
    *,
    image_override: bytes | None = None,
) -> tuple[str, ...]:
    """Return families whose exact proved writer guards are not present.

    The old same-block scan is not a completeness contract. This guard set
    makes every known cross-block, callback, and string-writer family explicit.
    `image_override` exists so the verifier can mutation-test every family
    without changing the installed executable.
    """
    executable = Path(executable)
    image = image_override if image_override is not None else executable.read_bytes()
    pe = pefile.PE(data=image, fast_load=True)
    missing: list[str] = []
    for family in PROVED_WRITER_FAMILIES:
        covered = True
        for address, guard in family.writer_guards:
            rva = address - pe.OPTIONAL_HEADER.ImageBase
            offset = pe.get_offset_from_rva(rva)
            if image[offset:offset + len(guard)] != guard:
                covered = False
                break
        if not covered:
            missing.append(family.name)
    pe.close()
    return tuple(missing)


def direct_call_sites(executable: Path, target: int) -> tuple[int, ...]:
    """Return all E8 call sites for one target in the executable text."""
    pe = pefile.PE(str(executable), fast_load=True)
    image_base = pe.OPTIONAL_HEADER.ImageBase
    text = next(section for section in pe.sections if section.Name.rstrip(b"\0") == b".text")
    code = text.get_data()
    start = image_base + text.VirtualAddress
    sites: list[int] = []
    for offset in range(len(code) - 4):
        if code[offset] != 0xE8:
            continue
        displacement = struct.unpack_from("<i", code, offset + 1)[0]
        site = start + offset
        if (site + 5 + displacement) & 0xFFFFFFFF == target:
            sites.append(site)
    pe.close()
    return tuple(sites)


def verify_copy_helper_stock_roles(executable: Path) -> tuple[str, ...]:
    """Verify every 0x0049A7B0 call that can overlap saved or battle stock."""
    executable = Path(executable)
    image = executable.read_bytes()
    pe = pefile.PE(data=image, fast_load=True)
    base = pe.OPTIONAL_HEADER.ImageBase
    errors: list[str] = []

    battle_prefix = bytes.fromhex(
        "68 d0 01 00 00 68 b0 b3 d8 01 68 00 f0 cf 01"
    )
    for call in COPY_HELPER_BATTLE_STOCK_READ_CALLS:
        call_offset = pe.get_offset_from_rva(call - base)
        if image[call_offset - len(battle_prefix):call_offset] != battle_prefix:
            errors.append(f"battle stock read arguments changed at 0x{call:08X}")

    # 0x004E2F34 receives arg1=live map (source), arg2=ESI (destination),
    # arg3=0x13A4. The pushes are the last three argument instructions.
    serializer = COPY_HELPER_SAVED_STOCK_READ_CALL
    serializer_offset = pe.get_offset_from_rva(serializer - base)
    serializer_prefix = bytes.fromhex("68 a4 13 00 00 56 68 58 dc cf 01")
    if image[serializer_offset - len(serializer_prefix):serializer_offset] != serializer_prefix:
        errors.append("save serializer copy arguments changed")

    # Load has intervening checksum work between its three pushes. Pin each
    # argument separately and the call target through direct_call_sites.
    load_guards = {
        0x004E4EF5: bytes.fromhex("68 a4 13 00 00"),
        0x004E4F01: bytes.fromhex("68 58 dc cf 01"),
        0x004E4F06: bytes.fromhex("57"),
    }
    for address, guard in load_guards.items():
        offset = pe.get_offset_from_rva(address - base)
        if image[offset:offset + len(guard)] != guard:
            errors.append(f"load copy argument changed at 0x{address:08X}")

    expected_calls = set(COPY_HELPER_BATTLE_STOCK_READ_CALLS)
    expected_calls.update((
        COPY_HELPER_SAVED_STOCK_READ_CALL,
        COPY_HELPER_SAVED_STOCK_WRITE_CALL,
        *COPY_HELPER_NON_LIVE_CALLS,
    ))
    actual_calls = set(direct_call_sites(executable, 0x0049A7B0))
    if actual_calls != expected_calls:
        errors.append("0x0049A7B0 caller set changed")
    pe.close()
    return tuple(errors)


def _clusters(references: list[DirectReference | DerivedReference],
              gap: int = 0x200) -> list[tuple[int, int, int]]:
    if not references:
        return []
    clusters: list[tuple[int, int, int]] = []
    first = previous = references[0].address
    count = 1
    for reference in references[1:]:
        if reference.address - previous > gap:
            clusters.append((first, previous, count))
            first = reference.address
            count = 0
        previous = reference.address
        count += 1
    clusters.append((first, previous, count))
    return clusters


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("executable", type=Path)
    parser.add_argument("--magic-only", action="store_true")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--writes", action="store_true")
    parser.add_argument("--derived", action="store_true")
    args = parser.parse_args()

    if args.derived:
        references = find_local_derived_references(args.executable)
    else:
        references = find_direct_references(args.executable, magic_only=args.magic_only)
    if args.writes:
        references = [reference for reference in references if reference.writes_magic]
    if args.summary:
        kind = "local derived references" if args.derived else "direct references"
        print(f"{kind}: {len(references)}")
        print("lower bound: cross-block and interprocedural data flow is not classified")
        for first, last, count in _clusters(references):
            print(f"0x{first:08X}-0x{last:08X}\t{count}")
        return 0

    for reference in references:
        if isinstance(reference, DirectReference):
            refs = "; ".join(
                f"{kind}=0x{value:08X} {label}"
                for kind, value, label in reference.references
            )
        else:
            refs = (
                f"derived-from=0x{reference.source_address:08X} "
                f"{reference.source_register}+0x{reference.displacement:X}"
            )
        raw = reference.raw.hex(" ")
        print(
            f"0x{reference.address:08X}\t{raw:<32}\t"
            f"{reference.mnemonic} {reference.operands}\t{refs}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
