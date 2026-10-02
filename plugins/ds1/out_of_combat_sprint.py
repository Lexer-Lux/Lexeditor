"""Build-specific sprint-only stamina patch for issue #856.

The source is always a fingerprinted private installation image. No original
executable bytes are bundled. The 509-byte leaf routine is authored separately
in out_of_combat_sprint_x64.S; tests reproduce it with GNU binutils.
"""
from __future__ import annotations

import hashlib
import struct

EXECUTABLE = "DarkSoulsRemastered.exe"
ORIGINAL_SIZE = 50_286_344
ORIGINAL_SHA256 = "a45aaa36dd2f6cc151670a639ea5547043cf38ea79ff4178b963c6ed71f98d7b"
PATCHED_SHA256 = '3f3d50136759a991bac25ab8698414a5545495a0f0fa05ef811d361b422efdae'
HOOK_RVA = 0x319B000
SPRINT_CALL_RVA = 0x31FD7A
NATIVE_CHARGE_RVA = 0x339680
WORLD_RVA = 0x1C77E50
BATTLE_GETTER_RVA = 0x392B80
NO_BATTLE_GETTER_RVA = 0x391820
HANDLE_ACCESSOR_RVA = 0x139DB00
ADDED_SIZE = 512
NATIVE_CODE = bytes.fromhex(
    "83faff0f8577e619fd4c8b0540ceadfe4d85c00f84da010000493948680f85d00100004885c90f84c701000083b9e803"
    "0000000f8eba010000458b58384181fb004000000f87a90100004585db0f84a00100004d8b50404d85d20f8493010000"
    "4d6bdb384d01d30f8286010000498b124885d274094839ca0f85750100004983c2384d39da72e64531c94b8b84c84004"
    "00004885c00f844a010000448b184181fb004000000f87480100004585db0f84310100004c8b50084d85d20f84320100"
    "004d6bdb384d01d30f8225010000498b124885d20f84fe0000004839ca0f84f500000083bae8030000000f8ee8000000"
    "488b52704885d20f84db000000488b024885c00f84ea000000488b80c8000000488d1509671ffd4839d00f84b8000000"
    "488d15597a1ffd4839d00f85c3000000498b12488b5270488b92300200004885d20f8491000000488b52304885d20f84"
    "8400000083bae000000003727b0f8790000000837a58010f8586000000488d058c2920fe48394278757983ba80000000"
    "ff7470488b82880000004885c0753c8b928000000089d0c1e80e83e03f83f81d7351498b84c0400400004885c0744481"
    "e2ff3f00003b10733a488b40084885c07431486bd2384801d07228488b004885c074204839c8741b4983c2384d39da0f"
    "82e9feffff41ffc14183f91d0f8298feffffc3baffffffffe983e419fd"
)
ORIGINAL_CALL = b"\xe8" + struct.pack("<i", NATIVE_CHARGE_RVA - SPRINT_CALL_RVA - 5)


class UnsupportedBuild(ValueError):
    """This is not the inspected original or the exact owned projection."""


def identify(image: bytes) -> bool:
    """Return whether our patch is present; reject every foreign modification."""
    digest = hashlib.sha256(image).hexdigest()
    if len(image) == ORIGINAL_SIZE and digest == ORIGINAL_SHA256:
        return False
    if len(image) == ORIGINAL_SIZE + ADDED_SIZE and digest == PATCHED_SHA256:
        return True
    raise UnsupportedBuild("This executable is not the supported original or this sprint patch.")


def _project(original: bytes) -> bytes:
    """Transform a verified PE image; kept separate for synthetic preservation tests."""
    if original[:2] != b"MZ" or len(original) < 0x40:
        raise UnsupportedBuild("The executable has no valid DOS header.")
    pe = struct.unpack_from("<I", original, 0x3C)[0]
    if pe + 264 > len(original) or original[pe:pe+4] != b"PE\0\0":
        raise UnsupportedBuild("The executable has no valid PE header.")
    machine, count = struct.unpack_from("<HH", original, pe + 4)
    optional_size = struct.unpack_from("<H", original, pe + 20)[0]
    opt = pe + 24
    if machine != 0x8664 or not 1 <= count <= 96 or optional_size != 240:
        raise UnsupportedBuild("The executable is not the reviewed x64 PE layout.")
    if struct.unpack_from("<H", original, opt)[0] != 0x20B:
        raise UnsupportedBuild("The executable is not PE32+.")
    section_alignment, file_alignment = struct.unpack_from("<II", original, opt + 32)
    if (section_alignment, file_alignment) != (0x1000, 0x200):
        raise UnsupportedBuild("The executable uses an unsupported alignment.")
    table = opt + optional_size
    if table + 40 * count > len(original):
        raise UnsupportedBuild("The section table is truncated.")
    sections = []
    for index in range(count):
        header = table + 40 * index
        virtual_size, rva, raw_size, raw = struct.unpack_from("<IIII", original, header + 8)
        flags = struct.unpack_from("<I", original, header + 36)[0]
        if raw + raw_size > len(original):
            raise UnsupportedBuild("A section leaves the executable.")
        sections.append((header, virtual_size, rva, raw_size, raw, flags))
    last = max(sections, key=lambda section: section[2])
    header, virtual_size, rva, raw_size, raw, flags = last
    end = raw + raw_size
    if (flags != 0x60000020 or virtual_size != raw_size or
            rva + virtual_size != HOOK_RVA or end != max(s[4] + s[3] for s in sections)):
        raise UnsupportedBuild("The final executable section does not match the reviewed layout.")
    security = opt + 112 + 4 * 8
    certificate, certificate_size = struct.unpack_from("<II", original, security)
    if certificate != end or certificate + certificate_size != len(original):
        raise UnsupportedBuild("The signed-file trailer does not match the reviewed layout.")
    owners = [s for s in sections if s[2] <= SPRINT_CALL_RVA and SPRINT_CALL_RVA + 5 <= s[2] + s[3]]
    if len(owners) != 1:
        raise UnsupportedBuild("The sprint call has no unique section.")
    owner = owners[0]
    call = owner[4] + SPRINT_CALL_RVA - owner[2]
    if original[call:call+5] != ORIGINAL_CALL:
        raise UnsupportedBuild("The sprint stamina call changed.")
    if len(NATIVE_CODE) > ADDED_SIZE:
        raise UnsupportedBuild("The native routine exceeds its reserved size.")
    result = bytearray(original[:end] + NATIVE_CODE.ljust(ADDED_SIZE, b"\0") + original[end:])
    struct.pack_into("<I", result, header + 8, virtual_size + ADDED_SIZE)
    struct.pack_into("<I", result, header + 16, raw_size + ADDED_SIZE)
    code_size = struct.unpack_from("<I", original, opt + 4)[0]
    struct.pack_into("<I", result, opt + 4, code_size + ADDED_SIZE)
    struct.pack_into("<I", result, opt + 56, (HOOK_RVA + ADDED_SIZE + 0xFFF) & ~0xFFF)
    # Application PE images do not require a nonzero checksum. The modified
    # image is no longer authenticode-valid; the original certificate is retained.
    struct.pack_into("<I", result, opt + 64, 0)
    struct.pack_into("<I", result, security, certificate + ADDED_SIZE)
    result[call:call+5] = b"\xe8" + struct.pack("<i", HOOK_RVA - SPRINT_CALL_RVA - 5)
    return bytes(result)


def build(original: bytes, enabled: bool) -> bytes:
    """Pure transformation. Saving or importing this module never installs anything."""
    if type(enabled) is not bool:
        raise ValueError("Sprint enabled must be a boolean.")
    if identify(original):
        raise UnsupportedBuild("Build from the verified original backup, not a patched executable.")
    if not enabled:
        return original
    result = _project(original)
    if not identify(result):
        raise UnsupportedBuild("The generated sprint patch did not verify.")
    return result
