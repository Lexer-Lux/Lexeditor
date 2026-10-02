"""No Hext hook may overwrite an instruction a native branch jumps to.

A hook that replaces several instructions with one jump breaks any native
jump or call aimed at the second or later of them: the CPU lands inside the
new jump. Vibration Consolidation did exactly that at 004C8D8F (004C8CC2
jumps to 004C8D93), and pausing early in an enemy attack crashed. Every
tweak mod in the library that can be switched on alone is built here with
every on/off setting on, and every native branch target in .text is checked
against the bytes its patches overwrite.

The tweaks live in the reader's mod library now, so this needs both that
library and the verified FF8_EN.exe; it skips when either is absent (CI).
"""
import re
import struct
from pathlib import Path

import pytest

from core import script_mods
from plugins.ff8 import paths, runtime_layout, tweak_mods

capstone = pytest.importorskip("capstone")
EXE = paths.GAME_ROOT / "FF8_EN.exe"
# These refuse to build until their feature is finished; they cannot be
# switched on alone.
NOT_ALONE = {"full-screen-world-map", "battle-results-item-help"}


def _text_section(data):
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    count = struct.unpack_from("<H", data, pe + 6)[0]
    optional = struct.unpack_from("<H", data, pe + 20)[0]
    for index in range(count):
        at = pe + 24 + optional + index * 40
        if data[at:at + 5] == b".text":
            size, rva, raw_size, raw = struct.unpack_from("<IIII", data, at + 8)
            return 0x400000 + rva, size, data[raw:raw + raw_size]
    raise AssertionError("no .text section")


def _library_tweaks():
    library = Path(paths.MODS_ROOT)
    if not library.is_dir():
        pytest.skip(f"The FF8 tweak-mod library is not installed ({library})")
    rows = [row for row in runtime_layout.catalog(paths.PROJECT_ROOT, library)
            if not row.get("selected") and script_mods.is_script_mod(Path(row["path"]))]
    if not rows:
        pytest.skip(f"No tweak mods in {library}")
    return rows


def _all_on(root):
    """The mod's values with every on/off setting switched on."""
    values = script_mods.values(root)
    for field in script_mods.schema(root)["fields"]:
        if field["type"] == "bool":
            values[field["key"]] = True
    return values


def build_all_hext():
    """Every tweak mod's Hext output, built in memory; nothing is written."""
    if not EXE.is_file():
        pytest.skip("FF8_EN.exe is not installed")
    rows = _library_tweaks()
    roots = {row["id"]: Path(row["path"]) for row in rows}
    context = tweak_mods.BuildContext(paths.GAME_ROOT, paths.BASELINE_ROOT, roots)
    try:
        context.executable()
    except tweak_mods.BuildError as error:
        pytest.skip(str(error))
    patches, refused = [], {}
    for mod_id, root in roots.items():
        context.current = mod_id
        module = script_mods.import_module(root, script_mods.ENTRY_MODULE)
        try:
            outputs = module.build(_all_on(root), context)
        except Exception as first:
            try:  # a setting that is not finished yet refuses; try the defaults
                outputs = module.build(script_mods.values(root), context)
            except Exception:
                refused[mod_id] = str(first)
                continue
        patches += [text if isinstance(text, str) else text.decode("utf-8")
                    for path, text in outputs.items() if str(path).startswith("hext/")]
    unexpected = {mod_id: why for mod_id, why in refused.items() if mod_id not in NOT_ALONE}
    assert not unexpected, f"tweak mods that should build alone refused: {unexpected}"
    return "\n".join(patches)


def test_no_native_branch_lands_inside_a_hook():
    patch = build_all_hext()
    base, size, code = _text_section(EXE.read_bytes())
    spans = []
    for line in patch.splitlines():
        match = re.fullmatch(r"\s*([0-9A-Fa-f]+)\s*=\s*([0-9A-Fa-f ]+)", line)
        if match:
            start = int(match[1], 16)
            length = len(bytes.fromhex(match[2]))
            if base <= start < base + size and length > 1:
                spans.append((start, start + length))
    assert len(spans) > 50, "the patch should touch many code sites"
    inside = {}
    for low, high in spans:
        for address in range(low + 1, high):
            inside[address] = (low, high)
    disassembler = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    disassembler.skipdata = True
    problems = []
    for instruction in disassembler.disasm(code, base):
        if not (instruction.mnemonic.startswith("j") or instruction.mnemonic == "call"):
            continue
        if not instruction.op_str.startswith("0x"):
            continue
        target = int(instruction.op_str, 16)
        span = inside.get(target)
        if span and not span[0] <= instruction.address < span[1]:
            # Rewritten in the patch itself, as the pause fix does.
            if any(low <= instruction.address < high for low, high in spans):
                continue
            problems.append(f"{instruction.address:08X} -> {target:08X} inside {span[0]:08X}-{span[1]:08X}")
    assert not problems, problems
