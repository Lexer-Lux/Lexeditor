"""Verify independent and conflicting FF8 kernel changes compose by unit."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.ff8 import formats, kernel_merge, kernel_text, paths


def main() -> None:
    vanilla = (paths.BASELINE_ROOT / "main" / "kernel.bin").read_bytes()
    section2 = int.from_bytes(vanilla[8:12], "little")
    size = int(formats.SECTIONS[2]["sub_section_size"])
    mod1 = bytearray(vanilla)
    mod2 = bytearray(vanilla)
    original_conflict = vanilla[section2 + 4]
    original_independent = vanilla[section2 + size + 4]
    original_second = vanilla[section2 + 5]
    mod1[section2 + 4] = (original_conflict + 1) & 0xFF
    mod1[section2 + size + 4] = (original_independent + 1) & 0xFF
    mod2[section2 + 4] = (original_conflict + 2) & 0xFF
    mod2[section2 + 5] = (original_second + 1) & 0xFF
    mod1_bytes, _ = kernel_text.apply_edits(bytes(mod1), formats.SECTIONS, [{
        "sectionId": 33, "recordId": 1, "slot": 0, "value": "LOW PRIORITY",
    }])
    mod2_bytes, _ = kernel_text.apply_edits(bytes(mod2), formats.SECTIONS, [{
        "sectionId": 33, "recordId": 2, "slot": 0, "value": "HIGH PRIORITY",
    }])
    merged, conflicts = kernel_merge.merge(
        vanilla, [("low", mod1_bytes), ("high", mod2_bytes)], formats.SECTIONS)
    merged_section2 = int.from_bytes(merged[8:12], "little")
    assert merged[merged_section2 + 4] == (original_conflict + 2) & 0xFF
    assert merged[merged_section2 + size + 4] == (original_independent + 1) & 0xFF
    assert merged[merged_section2 + 5] == (original_second + 1) & 0xFF
    text = {(row["recordId"], row["slot"]): row["value"]
            for row in kernel_text.rows(merged, formats.SECTIONS)["rows"]
            if row["sectionId"] == 33}
    assert text[(1, 0)] == "LOW PRIORITY"
    assert text[(2, 0)] == "HIGH PRIORITY"
    conflict = next(row for row in conflicts if row["unit"] == "kernel:section:2:record:0:byte:4")
    assert conflict["winner"] == "high" and conflict["claimants"] == ["low", "high"]
    print("PASS: FF8 kernel record bytes and text merge independently; higher priority wins collisions")


if __name__ == "__main__":
    main()
