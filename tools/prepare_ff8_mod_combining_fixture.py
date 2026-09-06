"""Prepare the reproducible two-mod fixture for FF8 issue #100.

The fixture is generated from the user's extracted baseline price.bin, so no
copyrighted game data is stored in the repository. It creates two ordinary
Lexeditor folder mods whose overlapping and independent price edits are easy
to observe in Balamb's general store.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.ff8 import paths

LOW_ID = "issue100-low-priority"
HIGH_ID = "issue100-high-priority"
# price.bin records are four bytes: uint16 buy-price/10, multiplier, unknown.
# Item IDs come from games/ff8/schema/item.json.
PRICE_EDITS = {
    LOW_ID: {1: 1230, 3: 5670},       # Potion, Hi-Potion
    HIGH_ID: {1: 4560, 7: 8910},     # Potion collision, Phoenix Down independent
}
EXPECTED_LOW_HIGH = {1: 4560, 3: 5670, 7: 8910}
EXPECTED_HIGH_LOW = {1: 1230, 3: 5670, 7: 8910}


def set_buy_price(raw: bytearray, item_id: int, gil: int) -> None:
    if gil < 0 or gil > 655350 or gil % 10:
        raise ValueError(f"Invalid FF8 buy price: {gil}")
    offset = item_id * 4
    if offset + 4 > len(raw):
        raise ValueError(f"price.bin does not contain item {item_id}")
    raw[offset:offset + 2] = (gil // 10).to_bytes(2, "little")


def build_variant(vanilla: bytes, edits: dict[int, int]) -> bytes:
    if len(vanilla) % 4:
        raise ValueError("price.bin has a partial item record")
    raw = bytearray(vanilla)
    for item_id, gil in edits.items():
        set_buy_price(raw, item_id, gil)
    return bytes(raw)


def write_mod(root: Path, mod_id: str, name: str, order: int, payload: bytes) -> None:
    direct = root / "direct" / "menu"
    direct.mkdir(parents=True, exist_ok=True)
    (direct / "price.bin").write_bytes(payload)
    (root / "mod.json").write_text(json.dumps({
        "id": mod_id,
        "name": name,
        "order": order,
        "enabled": False,
        "version": "issue-100-fixture-v1",
    }, indent=2) + "\n", encoding="utf-8", newline="\n")


def prepare(output: Path, baseline: Path) -> tuple[Path, Path]:
    baseline = Path(baseline).resolve(strict=True)
    vanilla = baseline.read_bytes()
    if len(vanilla) < 8 * 4 or len(vanilla) % 4:
        raise ValueError("The selected price.bin is not a usable FF8 item-price table")
    output = Path(output).resolve()
    low = output / LOW_ID
    high = output / HIGH_ID
    for target in (low, high):
        if target.exists():
            shutil.rmtree(target)
    write_mod(low, LOW_ID, "Issue #100 — Low Priority", 0,
              build_variant(vanilla, PRICE_EDITS[LOW_ID]))
    write_mod(high, HIGH_ID, "Issue #100 — High Priority", 1,
              build_variant(vanilla, PRICE_EDITS[HIGH_ID]))
    (output / "TEST-INSTRUCTIONS.txt").write_text(
        "FF8 issue #100 — record-based mod combining\n"
        "\n"
        "These two mods are generated from your own extracted price.bin.\n"
        "Copy both folders into Lexeditor's managed FF8 mods folder, or run this\n"
        "script with --install to create them there automatically.\n"
        "\n"
        "Test A — Low then High (High is higher priority):\n"
        "  Potion:      4560 gil\n"
        "  Hi-Potion:   5670 gil\n"
        "  Phoenix Down:8910 gil\n"
        "\n"
        "Test B — reverse the two mods so Low is higher priority:\n"
        "  Potion:      1230 gil\n"
        "  Hi-Potion:   5670 gil\n"
        "  Phoenix Down:8910 gil\n"
        "\n"
        "The Potion collision must follow the later/higher-priority mod; the\n"
        "independent Hi-Potion and Phoenix Down edits must survive either order.\n",
        encoding="utf-8", newline="\n")
    return low, high


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path,
                        default=paths.BASELINE_ROOT / "menu" / "price.bin",
                        help="Extracted vanilla menu/price.bin")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "build" / "ff8-issue-100-fixture")
    parser.add_argument("--install", action="store_true",
                        help="Write the two fixture mods directly to Lexeditor's FF8 managed-mod folder")
    args = parser.parse_args()
    output = paths.MODS_ROOT if args.install else args.output
    low, high = prepare(output, args.baseline)
    print(f"Prepared {low}")
    print(f"Prepared {high}")
    if args.install:
        print("Open FF8 Load Order in Lexeditor, enable both issue #100 fixture mods, and Save Order.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
