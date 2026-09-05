"""Static and mutation contracts for FF8 issues 92 and 94."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import re
import sys
import tempfile

from capstone import CS_ARCH_X86, CS_MODE_32, Cs


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.ff8 import flat_stat_abilities, formats, kernel_text, max_spell  # noqa: E402


EXE = Path(r"D:\SteamLibrary\steamapps\common\FINAL FANTASY VIII\FF8_EN.exe")
EXPECTED_EXE = "064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570"


def emitted(patch: str, address: int) -> bytes:
    match = re.search(rf"(?m)^{address:X} = ([0-9A-F ]+)$", patch)
    assert match, f"missing patch at {address:08X}"
    return bytes.fromhex(match.group(1))


def assert_cap_source(payload: bytes) -> None:
    assert max_spell.LIMIT_VALUE.to_bytes(4, "little") in payload
    instructions = list(Cs(CS_ARCH_X86, CS_MODE_32).disasm(payload, max_spell.SCALE_CAVE))
    assert any(row.mnemonic == "div" and row.op_str == "ecx" for row in instructions)
    assert not any(row.mnemonic == "mov" and row.op_str == "ecx, 0x64" for row in instructions)


assert EXE.is_file()
assert sha256(EXE.read_bytes()).hexdigest() == EXPECTED_EXE
with EXE.open("rb") as stream:
    flat_stat_abilities.verify_executable(stream)
    max_spell.verify_executable(stream)

for bad in (0, 256, True, 1.5, "many"):
    try:
        max_spell.bounded_limit(bad)
    except ValueError:
        pass
    else:
        raise AssertionError(f"invalid Max Spell value accepted: {bad!r}")

patch = max_spell.build_hext(True, 255)
assert emitted(patch, max_spell.LIMIT_VALUE) == b"\xff"
for address, _original in max_spell.STOCK_LIMIT_SITES:
    assert emitted(patch, address) == b"\xff"
for address, _original, replacement in max_spell.UNSIGNED_STOCK_BRANCHES:
    assert emitted(patch, address) == bytes((replacement,))
assert_cap_source(emitted(patch, max_spell.SCALE_CAVE))
literal_mutant = emitted(patch, max_spell.SCALE_CAVE).replace(
    bytes.fromhex("0F B6 0D") + max_spell.LIMIT_VALUE.to_bytes(4, "little"),
    bytes.fromhex("B9 64 00 00 00 90 90"),
)
try:
    assert_cap_source(literal_mutant)
except AssertionError:
    pass
else:
    raise AssertionError("a hard-coded junction denominator passed the Max Spell contract")
for cap in (1, 50, 100, 255):
    for effect in (1, 20, 100, 255):
        assert effect * cap // cap == effect
        assert effect * cap * 100 // cap == effect * 100

flat_patch = flat_stat_abilities.build_hext(True)
assert emitted(flat_patch, flat_stat_abilities.STAT_BONUS_BASE) == flat_stat_abilities.STAT_BONUS_BASE_FLAT
for address in flat_stat_abilities.STANDARD_APPLY_SITES:
    payload = emitted(flat_patch, address)
    assert payload.startswith(bytes.fromhex("01 C1 89 CA"))
    assert bytes.fromhex("1F 85 EB 51") not in payload
mutant = flat_patch.replace(
    flat_stat_abilities.STAT_BONUS_BASE_FLAT.hex(" ").upper(),
    flat_stat_abilities.STAT_BONUS_BASE_ORIGINAL.hex(" ").upper(),
    1,
)
assert emitted(mutant, flat_stat_abilities.STAT_BONUS_BASE) != flat_stat_abilities.STAT_BONUS_BASE_FLAT

with tempfile.TemporaryDirectory(prefix="lexeditor-flat-stat-") as name:
    project = Path(name)
    target, enabled_raw, changed = flat_stat_abilities.transformed_kernel(
        project, formats.paths.BASELINE_ROOT, True,
    )
    assert changed == 38
    rows = kernel_text.rows(enabled_raw, formats.SECTIONS)["rows"]
    names = [row["value"] for row in rows if row["sectionId"] == 44 and row["slot"] == 0]
    descriptions = [row["value"] for row in rows if row["sectionId"] == 44 and row["slot"] == 1]
    assert len(names) == 19 and all("%" not in value for value in names)
    assert len(descriptions) == 19 and all(value.endswith(" points") for value in descriptions)
    target.parent.mkdir(parents=True)
    target.write_bytes(enabled_raw)
    _target, disabled_raw, changed = flat_stat_abilities.transformed_kernel(
        project, formats.paths.BASELINE_ROOT, False,
    )
    assert changed == 38
    disabled_rows = kernel_text.rows(disabled_raw, formats.SECTIONS)["rows"]
    vanilla_rows = kernel_text.rows(
        (formats.paths.BASELINE_ROOT / "main" / "kernel.bin").read_bytes(),
        formats.SECTIONS,
    )["rows"]
    assert [row["value"] for row in disabled_rows] == [row["value"] for row in vanilla_rows]

print("FF8 Max Spell and Flat +Stat static and mutation checks passed")
