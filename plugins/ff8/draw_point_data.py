"""What each draw point gives: the executable's DrawPointData table, edited by Hext.

FF8_EN.exe (2013 Steam build) keeps one byte per draw point at 0x00B92328:
bits 0-5 are the magic ID, bit 6 makes the point refill, bit 7 is high yield.
Draw ID N is at 0x00B92328 + (N - 1); IDs 1-128 are field draw points and
129-256 are the world map's (codex/ff8/world-draw-points.md). The game reads
the table each time a point is drawn, so a patch applies to existing saves.

Lexeditor never writes the executable. An edit becomes one Hext line per
changed byte in the project's own patch file, and that file is also where the
current values are read back from, so it is the only record of the edit.
"""
from __future__ import annotations

import re
import struct
import tempfile
from pathlib import Path

from . import paths, runtime_layout

TABLE_ADDRESS = 0x00B92328
COUNT = 256
PATCH_NAME = "Lexeditor.DRAW_POINTS.txt"
HEXT_SUFFIX = Path("ff8") / "en_nv"
# Draw IDs 1-18 as shipped, from the FF8 modding wiki's draw point list. A
# different executable build does not hold these bytes here, and is refused.
SIGNATURE = bytes.fromhex("55 44 99 9B 0D CC C7 D5 C1 E9 E6 72 55 06 E3 D8 DE DD")
MAGIC_MASK, REFILL, HIGH_YIELD = 0x3F, 0x40, 0x80
_LINE = re.compile(r"^\s*([0-9A-Fa-f]+)\s*=\s*([0-9A-Fa-f]{2})\s*(?:#.*)?$")


def _file_offset(exe: bytes, address: int) -> int:
    pe = struct.unpack_from("<I", exe, 0x3C)[0]
    if exe[pe:pe + 4] != b"PE\0\0":
        raise ValueError("FF8_EN.exe is not a Windows executable")
    sections = struct.unpack_from("<H", exe, pe + 6)[0]
    optional = struct.unpack_from("<H", exe, pe + 20)[0]
    image_base = struct.unpack_from("<I", exe, pe + 24 + 28)[0]
    table = pe + 24 + optional
    rva = address - image_base
    for index in range(sections):
        _name, _vsize, vaddr, raw_size, raw_pointer = struct.unpack_from("<8sIIII", exe, table + index * 40)
        if vaddr <= rva < vaddr + raw_size:
            return raw_pointer + rva - vaddr
    raise ValueError(f"Address {address:08X} is not stored in FF8_EN.exe")


def vanilla_table(exe_path: Path | None = None) -> bytes:
    exe = (exe_path or paths.GAME_ROOT / "FF8_EN.exe").read_bytes()
    offset = _file_offset(exe, TABLE_ADDRESS)
    table = exe[offset:offset + COUNT]
    if table[:len(SIGNATURE)] != SIGNATURE:
        raise ValueError("This FF8_EN.exe is not the 2013 Steam build whose draw point table Lexeditor knows")
    return table


def patch_path(dataset: str = "current") -> Path | None:
    relative = Path("hext") / HEXT_SUFFIX / PATCH_NAME
    if dataset == "vanilla":
        return None
    if dataset == "current":
        return paths.PROJECT_ROOT / relative
    if dataset.startswith("reference:"):
        return paths.PROJECT_ROOT / "references" / dataset.partition(":")[2] / relative
    if dataset.startswith("mod:"):
        return runtime_layout.root_for_mod(paths.PROJECT_ROOT, paths.MODS_ROOT, dataset.partition(":")[2]) / relative
    raise ValueError(f"Unknown dataset: {dataset}")


def parse_patch(text: str) -> dict[int, int]:
    """Draw ID to byte, for every line of the patch that writes the table."""
    values = {}
    for line in text.splitlines():
        match = _LINE.match(line)
        if not match:
            continue
        address, value = int(match.group(1), 16), int(match.group(2), 16)
        if TABLE_ADDRESS <= address < TABLE_ADDRESS + COUNT:
            values[address - TABLE_ADDRESS + 1] = value
    return values


def table(dataset: str = "current", exe_path: Path | None = None) -> bytes:
    data = bytearray(vanilla_table(exe_path))
    path = patch_path(dataset)
    if path is not None and path.is_file():
        for draw_id, value in parse_patch(path.read_text(encoding="utf-8")).items():
            data[draw_id - 1] = value
    return bytes(data)


def rows(dataset: str = "current") -> dict:
    try:
        data = table(dataset)
    except (OSError, ValueError) as error:
        return {"rows": [], "error": str(error), "address": f"{TABLE_ADDRESS:08X}"}
    return {"address": f"{TABLE_ADDRESS:08X}", "rows": [
        {"id": index + 1, "magicId": value & MAGIC_MASK, "refill": bool(value & REFILL),
         "highYield": bool(value & HIGH_YIELD)} for index, value in enumerate(data)]}


def encode(edit: dict) -> int:
    magic = edit.get("magicId")
    if not isinstance(magic, int) or isinstance(magic, bool) or not 0 <= magic <= MAGIC_MASK:
        raise ValueError("Draw point magic must be a magic ID from 0 to 63")
    for key in ("refill", "highYield"):
        if not isinstance(edit.get(key), bool):
            raise ValueError(f"Draw point {key} must be true or false")
    return magic | (REFILL if edit["refill"] else 0) | (HIGH_YIELD if edit["highYield"] else 0)


def build_patch(values: dict[int, int], vanilla: bytes) -> str:
    lines = ["# Lexeditor: what each draw point gives. One byte per draw ID in FF8_EN.exe's",
             "# DrawPointData table: magic ID in bits 0-5, refill 0x40, high yield 0x80."]
    for draw_id in sorted(values):
        if values[draw_id] != vanilla[draw_id - 1]:
            lines.append(f"{TABLE_ADDRESS + draw_id - 1:X} = {values[draw_id]:02X}  # draw ID {draw_id}")
    return "\n".join(lines) + "\n"


def save(edits: list[dict], exe_path: Path | None = None, project_root: Path | None = None) -> dict:
    if not edits:
        return {"saved": 0, "file": ""}
    vanilla = vanilla_table(exe_path)
    root = project_root or paths.PROJECT_ROOT
    destination = root / "hext" / HEXT_SUFFIX / PATCH_NAME
    values = parse_patch(destination.read_text(encoding="utf-8")) if destination.is_file() else {}
    seen = set()
    for edit in edits:
        draw_id = edit.get("id")
        if not isinstance(draw_id, int) or isinstance(draw_id, bool) or not 1 <= draw_id <= COUNT:
            raise ValueError("Draw ID must be 1 to 256")
        if draw_id in seen:
            raise ValueError(f"Draw ID {draw_id} is edited twice")
        seen.add(draw_id)
        values[draw_id] = encode(edit)
    changed = {draw_id: value for draw_id, value in values.items() if value != vanilla[draw_id - 1]}
    if not changed:
        destination.unlink(missing_ok=True)
        return {"saved": len(edits), "file": str(destination)}
    destination.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=".draw-points-", suffix=".txt", dir=destination.parent)
    try:
        with open(handle, "w", encoding="utf-8", newline="\n", closefd=True) as stream:
            stream.write(build_patch(changed, vanilla))
        Path(temporary).replace(destination)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return {"saved": len(edits), "file": str(destination)}
