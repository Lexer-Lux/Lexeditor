"""Native equip-load percentage text for one reviewed Remastered executable.

This is a disabled-by-default experimental tweak, not a renderer or DLL.
The native formatter keeps ownership of the strings and their comparison
colours. See equip_load_percentage.md for static evidence and remaining
in-game acceptance. No player-state or roll-mechanics writes occur.
"""
from __future__ import annotations

import hashlib
import struct

TWEAK_ID = "equip_load_percentage"
LABEL = "Equip Load Percentage"
HELP = ("Adds a percentage beside the menu's current/max equip load. "
        "Experimental: appearance and updates still need in-game testing. "
        "Close the game before applying, and test offline.")
DEFAULT_ENABLED = False
EXECUTABLE = "DarkSoulsRemastered.exe"
ORIGINAL_SIZE = 50286344
PATCHED_SIZE = 0x3148200
ORIGINAL_SHA256 = "a45aaa36dd2f6cc151670a639ea5547043cf38ea79ff4178b963c6ed71f98d7b"
PATCHED_SHA256 = "a1cf3ba8dc98419f67682bbd9f5af4f8c564bf512ba47a7f1fa94670b1d43290"
IMAGE_BASE = 0x140000000
HOOK_RVA = 0x6B3E58
HOOK_OFFSET = 0x6B3258
RESUME_RVA = 0x6B3E5F
VANILLA_FORMAT_RVA = 0x13BC140
ISLAND_RVA = 0x319E000
ISLAND_OFFSET = 0x2FF5800
UNWIND_RVA = 0x319E0B0
TABLE_RVA = 0x319E0C0
TABLE_OFFSET = 0x2FF58C0
OLD_TABLE_OFFSET = 0x1B64E00
OLD_TABLE_SIZE = 0x1528BC
FALLBACK_DISP = 126
RESUME_DISP = 131
FORMAT_OFFSET = 144
HOOK_ORIGINAL = bytes.fromhex("488d15e182d000")
HEADER_ORIGINAL = {
    0x19C: 0x319B000, 0x1D0: 0x319B000, 0x1D8: 0x2FF5493,
    0x220: 0x1D0B000, 0x224: 0x1528BC, 0x228: 0x2FF2800,
    0x22C: 0x2708, 0x3D0: 0x1182000, 0x3D8: 0x1182000,
}
HEADER_PATCHED = {
    0x19C: 0x32f0a00, 0x1D0: 0x32F1000, 0x1D8: 0,
    0x220: TABLE_RVA, 0x224: OLD_TABLE_SIZE + 12, 0x228: 0,
    0x22C: 0, 0x3D0: 0x12D7988, 0x3D8: 0x12D7A00,
}
# GNU as --64, linked at zero, then objcopy -O binary -j .text.
# Only the two external PC-relative displacements need relocation.
ISLAND_TEMPLATE = bytes.fromhex(
    "448b56148b46403d00000080750231c085c078034189c2448b5e188b46443d00"
    "000080750231c085c078034189c34585d278484181fa0000807f733f4181fb00"
    "00800072364181fb0000807f732d66410f6ec2f30f5ac066410f6ecbf30f5ac9"
    "f20f5ec1f20f59051c000000660fd6442420488d1517000000eb07488d150000"
    "0000e900000000000000000000005940250073002f0025007300200028002500"
    "2e00310066002500250029000000"
)
CHAIN = bytes((0x21, 0, 0, 0)) + struct.pack("<III", 0x6B3740, 0x6B3F38, 0x182BFFC)


class UnsupportedBuild(ValueError):
    """Reject another version, conflict, corruption, or partial application."""


def fingerprint(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def identify(blob: bytes) -> str:
    if len(blob) not in (ORIGINAL_SIZE, PATCHED_SIZE):
        raise UnsupportedBuild("This executable size is not a supported Remastered build")
    digest = fingerprint(blob)
    if len(blob) == ORIGINAL_SIZE and digest == ORIGINAL_SHA256:
        return "vanilla"
    if len(blob) == PATCHED_SIZE and digest == PATCHED_SHA256:
        return "enabled"
    raise UnsupportedBuild("Unsupported or externally modified executable; no bytes were changed")


def relocate_island(address: int, resume: int, vanilla_format: int) -> bytes:
    """Use absolute addresses or RVAs consistently; all code is PC-relative."""
    result = bytearray(ISLAND_TEMPLATE)
    for offset, target in ((FALLBACK_DISP, vanilla_format), (RESUME_DISP, resume)):
        displacement = target - address - offset - 4
        if not -(1 << 31) <= displacement < (1 << 31):
            raise ValueError("The display hook is outside rel32 range")
        struct.pack_into("<i", result, offset, displacement)
    return bytes(result)


def code_writes() -> tuple[tuple[int, int, bytes], ...]:
    jump = b"\xe9" + struct.pack("<i", ISLAND_RVA - HOOK_RVA - 5) + b"\x90\x90"
    return ((ISLAND_OFFSET, ISLAND_RVA,
             relocate_island(ISLAND_RVA, RESUME_RVA, VANILLA_FORMAT_RVA)),
            (HOOK_OFFSET, HOOK_RVA, jump))


def _enable(original: bytes) -> bytes:
    """Caller must validate the complete original fingerprint first."""
    for offset, expected in HEADER_ORIGINAL.items():
        if struct.unpack_from("<I", original, offset)[0] != expected:
            raise UnsupportedBuild("The executable headers do not match the profile")
    if original[HOOK_OFFSET:HOOK_OFFSET + 7] != HOOK_ORIGINAL:
        raise UnsupportedBuild("The native formatting instruction does not match the profile")
    result = bytearray(original)
    result.extend(b"\0" * (PATCHED_SIZE - len(original)))
    for offset, value in HEADER_PATCHED.items():
        struct.pack_into("<I", result, offset, value)
    # No apparent code cave is assumed free: allocate after ALL original
    # file bytes, including its retained but now invalid certificate.
    for offset, _rva, replacement in code_writes():
        result[offset:offset + len(replacement)] = replacement
    chain_offset = ISLAND_OFFSET + UNWIND_RVA - ISLAND_RVA
    result[chain_offset:chain_offset + len(CHAIN)] = CHAIN
    # Extend the already executable, read-only final section. Keep every
    # existing function-table entry unchanged; append our higher-address
    # entry and point the loader at this complete, sorted replacement table.
    table = original[OLD_TABLE_OFFSET:OLD_TABLE_OFFSET + OLD_TABLE_SIZE]
    result[TABLE_OFFSET:TABLE_OFFSET + OLD_TABLE_SIZE] = table
    struct.pack_into("<III", result, TABLE_OFFSET + OLD_TABLE_SIZE,
                     ISLAND_RVA, ISLAND_RVA + RESUME_DISP + 4, UNWIND_RVA)
    return bytes(result)


def _disable(candidate: bytes) -> bytes:
    """Inverse of this exact profile, not a restore-over-arbitrary-mods operation."""
    original = bytearray(candidate[:ORIGINAL_SIZE])
    for offset, value in HEADER_ORIGINAL.items():
        struct.pack_into("<I", original, offset, value)
    original[HOOK_OFFSET:HOOK_OFFSET + 7] = HOOK_ORIGINAL
    return bytes(original)


def transform(blob: bytes, enabled: bool) -> bytes:
    """Exact-build, idempotent, fully reversible transformation in memory."""
    if type(enabled) is not bool:
        raise ValueError("Equip Load Percentage must be true or false")
    current = identify(blob)
    if (current == "enabled") == enabled:
        return blob
    result = _enable(blob) if enabled else _disable(blob)
    expected = PATCHED_SHA256 if enabled else ORIGINAL_SHA256
    if fingerprint(result) != expected:
        raise UnsupportedBuild("The complete output failed its fingerprint check")
    return result


def build_hext(enabled: bool) -> str:
    """Focused native-code Hext fragment for the prepared image.

    The file deployment also prepares PE section/unwind metadata. This text
    alone is NOT an independently installable live-process patch.
    """
    if type(enabled) is not bool:
        raise ValueError("Equip Load Percentage must be true or false")
    if not enabled:
        return ""
    lines = [
        "# Remastered Equip Load Percentage: prepared-image fragment.",
        f"# Source SHA-256: {ORIGINAL_SHA256}",
        "# Requires this module's PE preparation; not a standalone live patch.",
    ]
    for _offset, rva, replacement in code_writes():
        for offset in range(0, len(replacement), 32):
            lines.append(f"{IMAGE_BASE + rva + offset:X} = "
                         + replacement[offset:offset + 32].hex(" ").upper())
    return "\n".join(lines) + "\n"
