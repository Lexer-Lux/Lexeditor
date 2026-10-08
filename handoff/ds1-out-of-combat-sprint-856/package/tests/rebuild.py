"""Reproduce authored code and its relocation records with GNU binutils."""
from __future__ import annotations
from pathlib import Path
import re
import subprocess
import tempfile

TARGETS = {
    "world_chr_man": 0x1C77E50, "native_charge": 0x339680,
    "battle_getter": 0x392B80, "no_battle_getter": 0x391820,
    "handle_accessor_vtable": 0x139DB00, "resolve_target": 0x61A820,
}


def rebuild(root: Path) -> tuple[bytes, list[tuple[int, int]]]:
    with tempfile.TemporaryDirectory(prefix="lexeditor-sprint-asm-") as temporary:
        folder = Path(temporary)
        obj, binary = folder / "sprint.o", folder / "sprint.bin"
        subprocess.run(["as", "--64", "-o", str(obj), str(root / "script/sprint_x64.S")], check=True)
        subprocess.run(["objcopy", "-O", "binary", "--only-section=.text", str(obj), str(binary)], check=True)
        report = subprocess.run(["readelf", "-rW", str(obj)], check=True,
                                capture_output=True, text=True).stdout
        relocations = []
        for line in report.splitlines():
            if "R_X86_64_" not in line:
                continue
            match = re.fullmatch(
                r"([0-9a-f]+)\s+[0-9a-f]+\s+R_X86_64_(?:PC32|PLT32)\s+[0-9a-f]+\s+(\w+)\s+- 4",
                line.strip())
            if match is None or match[2] not in TARGETS:
                raise ValueError("Unreviewed assembly relocation: " + line)
            relocations.append((int(match[1], 16), TARGETS[match[2]]))
        data = binary.read_bytes()
        if len(relocations) != 6 or any(data[at:at+4] != b"\0"*4 for at, _ in relocations):
            raise ValueError("The assembly externals changed")
        return data, sorted(relocations)
