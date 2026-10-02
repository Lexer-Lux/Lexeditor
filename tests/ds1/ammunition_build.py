"""Build the authored #902 payload; no game file is a build input.

Requires clang with the x86_64-pc-windows-msvc target. The narrow COFF linker
accepts only relative code references and image-relative unwind references.
No imports, runtime DLL, absolute pointers, or proprietary code are bundled.
"""
from __future__ import annotations
import argparse
import base64
import zlib
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "plugins/ds1"
RVA = 0x319E000
SCRATCH_RVA = 0x1D0AF80
SOURCES = ("ammunition_native.c", "ammunition_bridge.S")
FLAGS = ["--target=x86_64-pc-windows-msvc", "-c", "-O2", "-ffreestanding",
         "-fno-stack-protector", "-fno-builtin", "-funwind-tables",
         "-fno-ident", "-Wall", "-Wextra", "-Werror"]
LIMIT = 1024 * 1024

def digest(data):
    return hashlib.sha256(data).hexdigest()

def take(data, offset, size):
    if offset < 0 or size < 0 or offset + size > len(data):
        raise ValueError("Truncated COFF object")
    return data[offset:offset + size]

def coff(data):
    if len(data) > LIMIT or len(data) < 20:
        raise ValueError("Invalid COFF size")
    machine, count, _, symoff, symcount, optional, _ = struct.unpack_from("<HHIIIHH", data)
    if machine != 0x8664 or optional or not 0 < count <= 96 or symcount > 65536:
        raise ValueError("Expected a small x64 COFF object")
    strings = take(data, symoff + symcount * 18, 4)
    strings = take(data, symoff + symcount * 18, struct.unpack("<I", strings)[0])
    def name(raw):
        if raw[:4] == b"\0" * 4:
            offset = struct.unpack_from("<I", raw, 4)[0]
            if not 4 <= offset < len(strings): raise ValueError("Invalid COFF symbol name")
            return strings[offset:].split(b"\0", 1)[0].decode("ascii")
        return raw.split(b"\0", 1)[0].decode("ascii")
    sections = []
    for index in range(count):
        row = take(data, 20 + index * 40, 40)
        size, ptr, rel, _, nr, _, flags = struct.unpack_from("<IIIIHHI", row, 16)
        label = row[:8].rstrip(b"\0").decode("ascii")
        if label.startswith("/"):
            label = strings[int(label[1:]):].split(b"\0", 1)[0].decode("ascii")
        sections.append({"name": label, "data": bytearray(take(data, ptr, size)) if size else bytearray(),
                         "relocs": [struct.unpack("<IIH", take(data, rel + j * 10, 10)) for j in range(nr)],
                         "align": 1 << max(0, ((flags >> 20) & 15) - 1)})
    symbols = {}
    index = 0
    while index < symcount:
        row = take(data, symoff + index * 18, 18)
        value, section, typ, storage, auxiliary = struct.unpack_from("<IhHBB", row, 8)
        symbols[index] = (name(row[:8]), value, section, storage)
        index += 1 + auxiliary
    return sections, symbols

def link(objects):
    loaded = [coff(data) for data in objects]
    cursor = RVA
    selected = []
    for kind in (".text", ".rdata", ".xdata", ".pdata"):
        for obj, (sections, _) in enumerate(loaded):
            for index, section in enumerate(sections, 1):
                if section["name"] == kind and section["data"]:
                    alignment = max(16 if kind == ".text" else 4, section["align"])
                    cursor = (cursor + alignment - 1) & -alignment
                    section["rva"] = cursor
                    selected.append((obj, index, section))
                    cursor += len(section["data"])
    if cursor - RVA > 65536:
        raise ValueError("Native payload exceeds its bound")
    for sections, _ in loaded:
        for section in sections:
            if section["data"] and "rva" not in section and section["name"] != ".llvm_addrsig":
                raise ValueError("Unexpected native section: " + section["name"])
    public = {"game": 0, "scratch": SCRATCH_RVA, "game_gestures": 0x399410}
    for sections, symbols in loaded:
        for name, value, sec, storage in symbols.values():
            if sec > 0 and storage == 2 and "rva" in sections[sec - 1]:
                address = sections[sec - 1]["rva"] + value
                if name in public: raise ValueError("Duplicate public symbol: " + name)
                public[name] = address
    for obj, _, section in selected:
        sections, symbols = loaded[obj]
        for offset, symbol, kind in section["relocs"]:
            if symbol not in symbols: raise ValueError("COFF auxiliary symbol reference")
            name, value, sec, storage = symbols[symbol]
            if sec > 0:
                target = sections[sec - 1]["rva"] + value
            elif sec == 0 and name in public:
                target = public[name]
            else:
                raise ValueError("Unresolved native reference: " + name)
            addend = struct.unpack("<i", take(section["data"], offset, 4))[0]
            if 4 <= kind <= 9:  # REL32 through REL32_5
                value = target + addend - section["rva"] - offset - 4 - (kind - 4)
                if not -(1 << 31) <= value < (1 << 31): raise ValueError("Native rel32 overflow")
                struct.pack_into("<i", section["data"], offset, value)
            elif kind == 3:  # ADDR32NB: .pdata references are image-relative
                value = target + addend
                if not 0 <= value < (1 << 32): raise ValueError("Unwind RVA overflow")
                struct.pack_into("<I", section["data"], offset, value)
            else:
                raise ValueError(f"Unsupported COFF relocation {kind}: {name}")
    image = bytearray(cursor - RVA)
    functions = []
    for _, _, section in selected:
        offset = section["rva"] - RVA
        image[offset:offset + len(section["data"])] = section["data"]
        if section["name"] == ".pdata":
            if len(section["data"]) % 12: raise ValueError("Invalid function table")
            functions.extend(struct.iter_unpack("<III", section["data"]))
    functions.sort()
    for i, (start, end, unwind) in enumerate(functions):
        if not RVA <= start < end <= cursor or not RVA <= unwind < cursor:
            raise ValueError("Native function is outside its payload")
        if i and functions[i - 1][1] > start: raise ValueError("Overlapping functions")
        if image[unwind - RVA] & 7 != 1: raise ValueError("Unsupported unwind version")
    entries = {name: value for name, value in public.items() if name.startswith("ammo_")}
    return bytes(image), functions, entries

def build():
    compiler = shutil.which("clang")
    if not compiler:
        raise RuntimeError("clang is required only to rebuild the native source")
    with tempfile.TemporaryDirectory(prefix="lexeditor-ammunition-build-") as temporary:
        objects = []
        for index, name in enumerate(SOURCES):
            target = Path(temporary) / f"{index}.obj"
            subprocess.run([compiler, *FLAGS, str(PLUGIN / name), "-o", str(target)],
                           check=True, capture_output=True)
            objects.append(target.read_bytes())
        image, functions, entries = link(objects)
    return {"schema": 1, "rva": RVA, "scratchRva": SCRATCH_RVA, "scratchSize": 128,
            "sourceHashes": {name: digest((PLUGIN / name).read_text(encoding="utf-8").encode("utf-8")) for name in SOURCES},
            "payloadSha256": digest(image), "payloadZlibBase64": base64.b64encode(zlib.compress(image, 9)).decode("ascii"),
            "functions": functions, "entrypoints": entries}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    result = build()
    if args.write:
        (PLUGIN / "ammunition_payload.json").write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8")
    else:
        print(json.dumps({k: v for k, v in result.items() if k != "payloadZlibBase64"}, indent=2))
