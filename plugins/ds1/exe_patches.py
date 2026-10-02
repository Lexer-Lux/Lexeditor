"""Combine DS1 tweak mods' native patches into one Remastered executable.

Dark Souls Remastered has no runtime patch loader like FF8's FFNx: a native
tweak has to live in DarkSoulsRemastered.exe itself. Each enabled tweak mod
builds a patch description (see `validate`) instead of a finished
executable, and this module combines all of them onto the verified vanilla
build, so tweaks never fight over the same address, header field or
exception table:

- code islands go after every original file byte (the retained certificate
  included) in the final, already executable section. An island may ask for a
  fixed address (position-dependent compiled code); the rest are placed after
  it, 16-byte aligned, with their rel32 displacements relocated;
- every island's function entries join the original exception table, which
  is rebuilt once, sorted, after the last island;
- hooks replace whole instructions whose original bytes must match;
- PE headers are written once for the combined layout.

Microsoft's PE/COFF and x64 exception-handling documentation supplied the
format facts.
"""
from __future__ import annotations

import hashlib
import struct

EXECUTABLE = "DarkSoulsRemastered.exe"
VANILLA_SIZE = 50286344
VANILLA_SHA256 = "a45aaa36dd2f6cc151670a639ea5547043cf38ea79ff4178b963c6ed71f98d7b"
SPEC_VERSION = 1
MAX_ISLAND = 256 * 1024
MAX_FUNCTIONS = 1024


class PatchError(ValueError):
    """A patch description or the executable cannot be combined safely."""


def _align(value: int, alignment: int) -> int:
    return (value + alignment - 1) & -alignment


class _Pe:
    """The few PE32+ fields a native tweak touches, read from the vanilla build."""

    def __init__(self, data: bytes):
        if data[:2] != b"MZ":
            raise PatchError("Not a Windows executable")
        self.nt = struct.unpack_from("<I", data, 0x3C)[0]
        if data[self.nt:self.nt + 4] != b"PE\0\0":
            raise PatchError("Missing PE signature")
        count = struct.unpack_from("<H", data, self.nt + 6)[0]
        optional_size = struct.unpack_from("<H", data, self.nt + 20)[0]
        self.optional = self.nt + 24
        if struct.unpack_from("<H", data, self.optional)[0] != 0x20B:
            raise PatchError("Not a 64-bit executable")
        self.size_of_code = self.optional + 4
        self.size_of_image = self.optional + 56
        self.checksum = self.optional + 64
        directories = self.optional + 112
        self.exception = directories + 3 * 8
        self.security = directories + 4 * 8
        table = self.optional + optional_size
        self.sections = []
        for index in range(count):
            at = table + index * 40
            name = data[at:at + 8].rstrip(b"\0").decode("ascii", "replace")
            vsize, rva, raw_size, raw = struct.unpack_from("<IIII", data, at + 8)
            flags = struct.unpack_from("<I", data, at + 36)[0]
            self.sections.append({"name": name, "header": at, "vsize": vsize, "rva": rva,
                                  "rawSize": raw_size, "raw": raw, "flags": flags})
        self.last = self.sections[-1]
        if not self.last["flags"] & 0x20000000:
            raise PatchError("The final section is not executable")

    def offset(self, rva: int, length: int) -> int:
        for section in self.sections:
            if section["rva"] <= rva and rva + length <= section["rva"] + min(section["vsize"], section["rawSize"]):
                return section["raw"] + rva - section["rva"]
        raise PatchError(f"{rva:X} is not inside file-backed section data")


def _hex(value, label: str) -> bytes:
    if not isinstance(value, str):
        raise PatchError(f"{label} must be hex text")
    try:
        return bytes.fromhex(value)
    except ValueError as error:
        raise PatchError(f"{label} is not valid hex") from error


def _int(value, label: str, low: int = 0, high: int = 0xFFFFFFFF) -> int:
    if type(value) is not int or not low <= value <= high:
        raise PatchError(f"{label} must be a whole number from {low} to {high}")
    return value


def validate(spec: dict, owner: str) -> dict:
    """Check one tweak's patch description and return it normalised.

    {"version": 1,
     "islands": [{"name": str, "rva": int (optional, fixed address),
                  "code": hex, "relocations": [{"at": int, "rel32": int target RVA}],
                  "functions": [[start, end, unwind] offsets into the island]}],
     "hooks": [{"rva": int, "original": hex,
                "bytes": hex | "branch": {"opcode": "E8"|"E9", "island": str, "offset": int},
                "pad": hex (optional)}],
     "sectionVirtualSize": {section name: minimum virtual size} (optional)}
    """
    if not isinstance(spec, dict) or spec.get("version") != SPEC_VERSION:
        raise PatchError(f"{owner}: unsupported native patch description")
    islands, names = [], set()
    for raw in spec.get("islands", []):
        name = raw.get("name") if isinstance(raw, dict) else None
        if not isinstance(name, str) or not name or name in names:
            raise PatchError(f"{owner}: every island needs a unique name")
        names.add(name)
        code = _hex(raw.get("code"), f"{owner} island {name}")
        if not 0 < len(code) <= MAX_ISLAND:
            raise PatchError(f"{owner} island {name} is empty or too large")
        relocations = [(_int(item.get("at"), "relocation offset", 0, len(code) - 4),
                        _int(item.get("rel32"), "relocation target"))
                       for item in raw.get("relocations", [])]
        functions = []
        previous = 0
        for row in raw.get("functions", []):
            if not isinstance(row, list) or len(row) != 3:
                raise PatchError(f"{owner} island {name}: function entries are [start, end, unwind]")
            start, end, unwind = (_int(value, "function offset", 0, len(code)) for value in row)
            if not previous <= start < end or unwind > len(code) - 4 or code[unwind] & 7 != 1:
                raise PatchError(f"{owner} island {name}: invalid or unsorted function entry")
            previous = end
            functions.append((start, end, unwind))
        if len(functions) > MAX_FUNCTIONS:
            raise PatchError(f"{owner} island {name}: too many function entries")
        fixed = raw.get("rva")
        islands.append({"owner": owner, "name": name, "code": code, "relocations": relocations,
                        "functions": functions, "rva": None if fixed is None else _int(fixed, "island address")})
    hooks = []
    for raw in spec.get("hooks", []):
        rva = _int(raw.get("rva"), f"{owner} hook address")
        original = _hex(raw.get("original"), f"{owner} hook {rva:X} original")
        pad = _hex(raw.get("pad", ""), f"{owner} hook {rva:X} padding")
        if "bytes" in raw:
            replacement = ("bytes", _hex(raw["bytes"], f"{owner} hook {rva:X}"))
        else:
            branch = raw.get("branch")
            if not isinstance(branch, dict) or branch.get("opcode") not in ("E8", "E9") or branch.get("island") not in names:
                raise PatchError(f"{owner} hook {rva:X} needs bytes or a branch into one of its islands")
            replacement = ("branch", int(branch["opcode"], 16), branch["island"],
                           _int(branch.get("offset", 0), "branch offset"))
        length = len(replacement[1]) if replacement[0] == "bytes" else 5
        if length + len(pad) != len(original) or not original:
            raise PatchError(f"{owner} hook {rva:X} must replace exactly its original instruction bytes")
        hooks.append({"owner": owner, "rva": rva, "original": original, "replacement": replacement, "pad": pad})
    sizes = spec.get("sectionVirtualSize", {})
    if not isinstance(sizes, dict):
        raise PatchError(f"{owner}: sectionVirtualSize must map section names to sizes")
    return {"owner": owner, "islands": islands, "hooks": hooks,
            "sectionVirtualSize": {str(key): _int(value, "section size") for key, value in sizes.items()}}


def _rel32(source_next: int, target: int) -> bytes:
    value = target - source_next
    if not -(1 << 31) <= value < (1 << 31):
        raise PatchError("A branch is outside rel32 range")
    return struct.pack("<i", value)


def compose(vanilla: bytes, specs: list[dict]) -> bytes:
    """The vanilla executable with every validated tweak patch applied.

    With no patches it returns the vanilla bytes unchanged.
    """
    if len(vanilla) != VANILLA_SIZE or hashlib.sha256(vanilla).hexdigest() != VANILLA_SHA256:
        raise PatchError("The source is not the supported vanilla Remastered executable")
    patches = [spec for spec in specs if spec["islands"] or spec["hooks"] or spec["sectionVirtualSize"]]
    if not patches:
        return bytes(vanilla)
    pe = _Pe(vanilla)
    last = pe.last
    section_end = last["rva"] + last["vsize"]
    # Islands start after every original byte, the certificate included, at
    # the first page boundary past the section whose file offset clears them.
    base = _align(section_end, 0x1000)
    while last["raw"] + base - last["rva"] < len(vanilla):
        base += 0x1000
    islands = [island for spec in patches for island in spec["islands"]]
    placed, cursor = [], base
    for island in sorted((item for item in islands if item["rva"] is not None), key=lambda item: item["rva"]):
        if island["rva"] < cursor:
            raise PatchError(f"{island['owner']}: island {island['name']} overlaps another tweak's code")
        placed.append((island["rva"], island))
        cursor = island["rva"] + len(island["code"])
    for island in (item for item in islands if item["rva"] is None):
        rva = _align(cursor, 16)
        placed.append((rva, island))
        cursor = rva + len(island["code"])
    placed.sort(key=lambda item: item[0])
    addresses = {(island["owner"], island["name"]): rva for rva, island in placed}

    def file_offset(rva: int) -> int:
        return last["raw"] + rva - last["rva"]

    table_rva = _align(cursor, 16)
    table_offset = file_offset(table_rva)
    original_offset, original_size = struct.unpack_from("<II", vanilla, pe.exception)
    original_table = vanilla[pe.offset(original_offset, original_size):][:original_size]
    entries = list(struct.iter_unpack("<III", original_table))
    if any(a[0] > b[0] for a, b in zip(entries, entries[1:])) or entries[-1][1] > base:
        raise PatchError("The original exception table cannot be extended safely")
    for rva, island in placed:
        entries.extend((rva + start, rva + end, rva + unwind) for start, end, unwind in island["functions"])
    entries.sort(key=lambda row: row[0])
    if any(a[1] > b[0] for a, b in zip(entries, entries[1:])):
        raise PatchError("Two tweaks' native functions overlap")
    table = b"".join(struct.pack("<III", *row) for row in entries)
    size = _align(table_offset + len(table), 0x200)
    raw_size = size - last["raw"]
    image_size = _align(last["rva"] + raw_size, 0x1000)

    result = bytearray(vanilla)
    result.extend(b"\0" * (size - len(result)))
    for rva, island in placed:
        code = bytearray(island["code"])
        for at, target in island["relocations"]:
            code[at:at + 4] = _rel32(rva + at + 4, target)
        start = file_offset(rva)
        result[start:start + len(code)] = code
    result[table_offset:table_offset + len(table)] = table

    claimed: list[tuple[int, int, str]] = []
    for spec in patches:
        for hook in spec["hooks"]:
            rva, original = hook["rva"], hook["original"]
            for low, high, owner in claimed:
                if rva < high and low < rva + len(original):
                    raise PatchError(f"{hook['owner']} and {owner} both patch the instruction at {rva:X}")
            claimed.append((rva, rva + len(original), hook["owner"]))
            at = pe.offset(rva, len(original))
            if vanilla[at:at + len(original)] != original:
                raise PatchError(f"{hook['owner']}: the instruction at {rva:X} does not match this build")
            kind = hook["replacement"]
            if kind[0] == "bytes":
                replacement = kind[1]
            else:
                _kind, opcode, name, offset = kind
                target = addresses[(hook["owner"], name)] + offset
                replacement = bytes((opcode,)) + _rel32(rva + 5, target)
            result[at:at + len(original)] = replacement + hook["pad"]

    for spec in patches:
        for name, minimum in spec["sectionVirtualSize"].items():
            section = next((item for item in pe.sections if item["name"] == name), None)
            following = next((item for item in pe.sections if item["rva"] > (section or {}).get("rva", -1)), None)
            if section is None or following is None or not section["vsize"] <= minimum <= following["rva"] - section["rva"]:
                raise PatchError(f"{spec['owner']}: cannot grow {name} to {minimum:X}")
            current = struct.unpack_from("<I", result, section["header"] + 8)[0]
            struct.pack_into("<I", result, section["header"] + 8, max(current, minimum))

    # One layout, one set of headers. SizeOfCode follows the image size, as
    # the reviewed tweaks wrote it; the loader does not read it.
    struct.pack_into("<I", result, pe.size_of_code, image_size)
    struct.pack_into("<I", result, pe.size_of_image, image_size)
    struct.pack_into("<I", result, pe.checksum, 0)
    struct.pack_into("<II", result, pe.exception, table_rva, len(table))
    # The retained certificate no longer matches; the directory stops naming it.
    struct.pack_into("<II", result, pe.security, 0, 0)
    struct.pack_into("<II", result, last["header"] + 8, raw_size, last["rva"])
    struct.pack_into("<I", result, last["header"] + 16, raw_size)
    return bytes(result)
