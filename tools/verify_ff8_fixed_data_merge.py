"""Verify priority merge units for FF8 fixed-record editor files."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.ff8 import fixed_data_merge, paths


def main() -> None:
    price_path = "direct/menu/price.bin"
    vanilla = (paths.BASELINE_ROOT / "menu" / "price.bin").read_bytes()
    low = bytearray(vanilla)
    high = bytearray(vanilla)
    low[0:2] = (123).to_bytes(2, "little")
    low[4:6] = (234).to_bytes(2, "little")
    high[0:2] = (345).to_bytes(2, "little")
    high[2] = (vanilla[2] + 1) & 0xFF
    merged, conflicts = fixed_data_merge.merge(
        vanilla, [("low", bytes(low)), ("high", bytes(high))],
        fixed_data_merge.SPECS[price_path], price_path)
    assert int.from_bytes(merged[0:2], "little") == 345
    assert merged[2] == high[2]
    assert int.from_bytes(merged[4:6], "little") == 234
    assert conflicts == [{
        "unit": f"{price_path}:record:0:buy_price",
        "winner": "high", "claimants": ["low", "high"],
    }]

    item_path = "direct/menu/mitem.bin"
    item = (paths.BASELINE_ROOT / "menu" / "mitem.bin").read_bytes()
    flag_low = bytearray(item)
    flag_high = bytearray(item)
    flag_low[1] ^= 0x01
    flag_high[1] ^= 0x02
    merged_flags, flag_conflicts = fixed_data_merge.merge(
        item, [("low", bytes(flag_low)), ("high", bytes(flag_high))],
        fixed_data_merge.SPECS[item_path], item_path)
    assert merged_flags[1] == (item[1] ^ 0x03)
    assert flag_conflicts == []
    print("PASS: FF8 fixed data merges by fields and independent flag bits; higher priority wins field collisions")


if __name__ == "__main__":
    main()
