"""Toggleable native ammunition patch for the pinned Remastered executable.

The payload is original freestanding code, not a DLL. It calls existing game
routines; no renderer, input-device hook, game archive or asset is bundled.
See ammunition_controls.md. Appearance/gameplay still require in-game testing.
"""
from __future__ import annotations
import base64
import hashlib
import zlib
import json
from pathlib import Path
import struct

TWEAK_ID = "later_game_ammunition"
LABEL = "Later-Game Ammunition"
HELP = ("Shows both equipped ammunition types for the active bow or crossbow. "
        "R1 fires primary ammo and R2 fires secondary ammo. "
        "Works with a right-hand weapon or a two-handed left-hand weapon. "
        "Save stores this setting in the mod project. "
        "Apply changes the closed game's executable, and Restore removes the patch. "
        "Experimental: test offline.")
DEFAULT_ENABLED = False
EXECUTABLE = "DarkSoulsRemastered.exe"
ORIGINAL_SIZE = 50286344
ORIGINAL_SHA256 = "a45aaa36dd2f6cc151670a639ea5547043cf38ea79ff4178b963c6ed71f98d7b"
PATCHED_SHA256 = "197725ce7cf216e5db1b5c64b464e33377d63a59562dcf19eded5663ea5f0362"
IMAGE_BASE = 0x140000000
PAYLOAD_RVA = 0x319E000
PAYLOAD_OFFSET = 0x2FF5800
SCRATCH_RVA = 0x1D0AF80
SCRATCH_SIZE = 128
TABLE_OFFSET = 0x1B64E00
TABLE_SIZE = 0x1528BC
TEXT_RVA = 0x2019000
TEXT_OFFSET = 0x1E70800
# Only complete instructions are redirected. All original functions remain
# intact so fallback calls and other callers retain their native behavior.
HOOKS = (
    (0x397577, 0xE8, 0x399410, "ammo_frame_bridge"),
    (0x676E4F, 0xE8, 0x676E80, "ammo_hud_shortcut"),
    (0x676E71, 0xE9, 0x677990, "ammo_hud_visibility"),
    (0x677ACA, 0xE9, 0x678500, "ammo_hud_arrow"),
    (0x677AD1, 0xE9, 0x678500, "ammo_hud_arrow"),
    (0x714EBC, 0xE8, 0x71ABD0, "ammo_hud_mode"),
    (0x67A32B, 0xE8, 0x71ABD0, "ammo_hud_mode"),
    (0x67A472, 0xE8, 0x71ABD0, "ammo_hud_mode"),
    (0x67A4DD, 0xE8, 0x67BB20, "ammo_reticle"),
)
HEADER_ORIGINAL = {
    0x19C: 0x319B000, 0x1D0: 0x319B000, 0x1D8: 0x2FF5493,
    0x220: 0x1D0B000, 0x224: TABLE_SIZE, 0x228: 0x2FF2800, 0x22C: 0x2708,
    0x2E0: 0x2E5F78, 0x3D0: 0x1182000, 0x3D8: 0x1182000,
}

class UnsupportedBuild(ValueError):
    """Unsupported, conflicting, stale or damaged executable/payload."""

def fingerprint(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def _align(value, alignment):
    return (value + alignment - 1) & -alignment

def _payload():
    path = Path(__file__).with_name("ammunition_payload.json")
    if path.stat().st_size > 256 * 1024:
        raise UnsupportedBuild("The ammunition payload exceeds its size limit")
    spec = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(spec, dict) or spec.get("schema") != 1 or spec.get("rva") != PAYLOAD_RVA
            or spec.get("scratchRva") != SCRATCH_RVA or spec.get("scratchSize") != SCRATCH_SIZE):
        raise UnsupportedBuild("Unsupported ammunition payload")
    try:
        compressed = base64.b64decode(spec["payloadZlibBase64"], validate=True)
        decoder = zlib.decompressobj()
        raw = decoder.decompress(compressed, 65537)
    except (ValueError, zlib.error) as error:
        raise UnsupportedBuild("Invalid ammunition payload stream") from error
    if not decoder.eof or decoder.unconsumed_tail or decoder.unused_data:
        raise UnsupportedBuild("Invalid or oversized ammunition payload stream")
    if not 0 < len(raw) <= 65536 or fingerprint(raw) != spec.get("payloadSha256"):
        raise UnsupportedBuild("The ammunition payload did not verify")
    for name in ("ammunition_native.c", "ammunition_bridge.S"):
        source = Path(__file__).with_name(name).read_text(encoding="utf-8").encode("utf-8")
        if fingerprint(source) != spec.get("sourceHashes", {}).get(name):
            raise UnsupportedBuild("Native source changed; rebuild the ammunition payload")
    previous = PAYLOAD_RVA
    functions = spec["functions"]
    if not isinstance(functions, list) or not 1 <= len(functions) <= 256:
        raise UnsupportedBuild("Invalid native function table")
    for start, end, unwind in functions:
        if not previous <= start < end <= PAYLOAD_RVA + len(raw):
            raise UnsupportedBuild("Unsorted or overlapping native functions")
        if not PAYLOAD_RVA <= unwind <= PAYLOAD_RVA + len(raw) - 4:
            raise UnsupportedBuild("Invalid native unwind reference")
        if raw[unwind-PAYLOAD_RVA] & 7 != 1:
            raise UnsupportedBuild("Unsupported native unwind version")
        previous = end
    for _, _, _, name in HOOKS:
        address = spec["entrypoints"][name]
        if not any(start <= address < end for start, end, _ in functions):
            raise UnsupportedBuild("A native entrypoint has no unwind record")
    return spec, raw

def _layout():
    spec, raw = _payload()
    table_rva = _align(PAYLOAD_RVA + len(raw), 16)
    table_offset = PAYLOAD_OFFSET + table_rva - PAYLOAD_RVA
    table_size = TABLE_SIZE + len(spec["functions"]) * 12
    size = _align(table_offset + table_size, 0x200)
    image_size = _align(TEXT_RVA + size - TEXT_OFFSET, 0x1000)
    return spec, raw, table_rva, table_offset, table_size, size, image_size

def patched_size():
    return _layout()[5]

def identify(data: bytes) -> str:
    if len(data) == ORIGINAL_SIZE and fingerprint(data) == ORIGINAL_SHA256:
        return "vanilla"
    if len(data) == patched_size() and fingerprint(data) == PATCHED_SHA256:
        return "enabled"
    raise UnsupportedBuild("Unsupported or externally modified executable; no bytes were changed")

def branch(rva, opcode, target):
    value = target-rva-5
    if not -(1 << 31) <= value < (1 << 31):
        raise UnsupportedBuild("The native patch exceeds rel32 range")
    return bytes((opcode,)) + struct.pack("<i", value)

def code_writes():
    spec, raw = _payload()
    writes = [(PAYLOAD_OFFSET, PAYLOAD_RVA, raw)]
    # Every selected site is inside the first .text section.
    for rva, opcode, _, name in HOOKS:
        writes.append((rva-0xc00, rva, branch(rva,opcode,spec["entrypoints"][name])))
    return tuple(writes)

def _enable(original):
    spec, raw, table_rva, table_offset, table_size, size, image_size = _layout()
    for offset, expected in HEADER_ORIGINAL.items():
        if struct.unpack_from("<I", original, offset)[0] != expected:
            raise UnsupportedBuild("The native patch profile does not match the PE headers")
    for rva, opcode, target, _ in HOOKS:
        if original[rva-0xc00:rva-0xc00+5] != branch(rva,opcode,target):
            raise UnsupportedBuild(f"The native call site at {rva:X} does not match")
    result = bytearray(original)
    result.extend(b"\0"*(size-len(result)))
    headers = {0x19C: image_size, 0x1D0: image_size, 0x1D8: 0,
               0x220: table_rva, 0x224: table_size, 0x228: 0, 0x22C: 0,
               0x2E0: 0x2E6000, 0x3D0: size-TEXT_OFFSET, 0x3D8: size-TEXT_OFFSET}
    # The old .data virtual size ends at 1D0AF78. Advertise only new BSS up to
    # the next section at 1D0B000. The aligned 128-byte scratch has no file data.
    # Executable code is appended AFTER every original file byte/certificate.
    for offset, value in headers.items(): struct.pack_into("<I", result, offset, value)
    for offset, _, data in code_writes(): result[offset:offset+len(data)] = data
    table = original[TABLE_OFFSET:TABLE_OFFSET+TABLE_SIZE]
    if len(table) != TABLE_SIZE: raise UnsupportedBuild("Truncated original function table")
    entries = list(struct.iter_unpack("<III", table))
    if any(a[0] > b[0] for a,b in zip(entries,entries[1:])) or entries[-1][1] > PAYLOAD_RVA:
        raise UnsupportedBuild("The original exception table cannot be extended safely")
    result[table_offset:table_offset+TABLE_SIZE] = table
    for i, row in enumerate(spec["functions"]):
        struct.pack_into("<III", result, table_offset+TABLE_SIZE+i*12,*row)
    return bytes(result)

def _disable(candidate):
    original = bytearray(candidate[:ORIGINAL_SIZE])
    for offset, value in HEADER_ORIGINAL.items(): struct.pack_into("<I",original,offset,value)
    for rva, opcode, target, _ in HOOKS:
        original[rva-0xc00:rva-0xc00+5] = branch(rva,opcode,target)
    return bytes(original)

def transform(data: bytes, enabled: bool) -> bytes:
    if type(enabled) is not bool: raise ValueError("Ammunition must be true or false")
    current = identify(data)
    if (current=="enabled") == enabled: return data
    result = _enable(data) if enabled else _disable(data)
    expected = PATCHED_SHA256 if enabled else ORIGINAL_SHA256
    if fingerprint(result) != expected:
        raise UnsupportedBuild("The complete ammunition output did not verify")
    return result

def build_hext(enabled: bool) -> str:
    if type(enabled) is not bool: raise ValueError("Ammunition must be true or false")
    if not enabled: return ""
    lines = ["# Later-Game Ammunition: prepared-image native patch.",
             "# Requires this module's PE/BSS/unwind preparation, not a standalone live patch.",
             "# Source SHA-256: " + ORIGINAL_SHA256]
    for _, rva, data in code_writes():
        for offset in range(0,len(data),32):
            lines.append(f"{IMAGE_BASE+rva+offset:X} = " + data[offset:offset+32].hex(" ").upper())
    return "\n".join(lines)+"\n"
