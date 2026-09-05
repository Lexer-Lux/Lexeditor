"""Static and binary round-trip contract for GitHub #69."""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.ff7.kernel import CATEGORIES, Kernel, resolve_kernel  # noqa: E402


ROOTS = (
    Path(r"D:\SteamLibrary\steamapps\common\FINAL FANTASY VII"),
    Path(r"D:\SteamLibrary\steamapps\common\FINAL FANTASY VII Steam Edition"),
)
EXPECTED = {"items": 128, "weapons": 128, "armor": 32, "accessories": 32, "materia": 96}


def main() -> int:
    kernels = []
    for root in ROOTS:
        source, relative = resolve_kernel(root)
        kernel = Kernel(source)
        kernels.append(kernel)
        assert {key: len(kernel.records(key)) for key in CATEGORIES} == EXPECTED
        assert kernel.records("items")[0]["name"] == "Potion"
        assert kernel.records("weapons")[0]["name"] == "Buster Sword"
        assert relative.as_posix().lower().endswith("data/lang-en/kernel/kernel.bin")
    assert kernels[0].sha256 == kernels[1].sha256

    kernel = kernels[0]
    before_sections = tuple(bytes(value) for value in kernel.sections)
    records = kernel.records("weapons")
    original = records[0]["values"]["attackStrength"]
    records[0]["values"]["attackStrength"] = original + 1
    kernel.apply("weapons", records)
    changed = [(section, offset) for section, (before, after) in enumerate(zip(before_sections, kernel.sections), 1)
               for offset, (left, right) in enumerate(zip(before, after)) if left != right]
    assert changed == [(6, 4)], changed
    with tempfile.TemporaryDirectory(prefix="lexeditor-ff7-contract-", ignore_cleanup_errors=True) as name:
        target = Path(name) / "KERNEL.BIN"
        kernel.save(target)
        reopened = Kernel(target)
        assert reopened.records("weapons")[0]["values"]["attackStrength"] == original + 1
        assert [len(section) for section in reopened.sections] == [len(section) for section in kernel.sections]

    invalid = kernels[1].records("materia")
    invalid[0]["values"]["level2Ap"] = 1
    try:
        kernels[1].apply("materia", invalid)
    except ValueError as error:
        assert "multiple of 100" in str(error)
    else:
        raise AssertionError("Materia AP accepted a value that cannot be represented in KERNEL.BIN")
    print("PASS: both FF7 products share the proved English kernel layout")
    print("PASS: 416 names and records decode with exact expected counts")
    print("PASS: a weapon edit changes one documented byte and survives save/readback")
    print("PASS: scaled materia AP rejects unrepresentable values")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
