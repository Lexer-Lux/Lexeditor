"""Regression contract and player-fixture check for FF8 issue #100."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.ff8 import runtime_layout
from tools.prepare_ff8_mod_combining_fixture import (
    EXPECTED_HIGH_LOW, EXPECTED_LOW_HIGH, HIGH_ID, LOW_ID, PRICE_EDITS,
    prepare,
)


def price(data: bytes, item_id: int) -> int:
    offset = item_id * 4
    return int.from_bytes(data[offset:offset + 2], "little") * 10


def compose_case(root: Path, order: list[str], expected: dict[int, int]) -> None:
    baseline = root / "baseline"
    mods = root / "mods"
    active = root / ("active-" + "-".join(order))
    project = root / "editable"
    project.mkdir(exist_ok=True)
    (project / runtime_layout.MOD_FILE).write_text(json.dumps({
        "id": "editable", "name": "Editable", "enabled": False, "order": 99,
    }), encoding="utf-8")
    rows = runtime_layout.catalog(project, mods)
    enabled = {row["id"]: row["id"] in {LOW_ID, HIGH_ID} for row in rows}
    full_order = [*order, "editable"]
    rows = runtime_layout.configure(project, mods, full_order, enabled)
    result = runtime_layout.compose(project, active, rows, baseline_root=baseline)
    output = (active / "direct" / "menu" / "price.bin").read_bytes()
    vanilla = (baseline / "menu" / "price.bin").read_bytes()
    for item_id, gil in expected.items():
        assert price(output, item_id) == gil, (item_id, price(output, item_id), gil)
    allowed = {item * 4 + byte for item in expected for byte in (0, 1)}
    assert all(a == b or index in allowed
               for index, (a, b) in enumerate(zip(output, vanilla)))
    potion_conflict = next(row for row in result["conflicts"]
                           if row["path"] == "direct/menu/price.bin")
    unit = next(row for row in potion_conflict["units"]
                if row["unit"].endswith("record:1:buy_price"))
    assert unit["winner"] == order[-1]
    assert unit["claimants"] == order


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="lexeditor-ff8-issue100-") as name:
        root = Path(name)
        baseline = root / "baseline" / "menu"
        baseline.mkdir(parents=True)
        vanilla = bytearray((index * 17 + 3) & 0xFF for index in range(8 * 4))
        for item_id, gil in {1: 100, 3: 500, 7: 500}.items():
            offset = item_id * 4
            vanilla[offset:offset + 2] = (gil // 10).to_bytes(2, "little")
        baseline_file = baseline / "price.bin"
        baseline_file.write_bytes(vanilla)
        prepare(root / "mods", baseline_file)

        compose_case(root, [LOW_ID, HIGH_ID], EXPECTED_LOW_HIGH)
        compose_case(root, [HIGH_ID, LOW_ID], EXPECTED_HIGH_LOW)

        low = (root / "mods" / LOW_ID / "direct" / "menu" / "price.bin").read_bytes()
        high = (root / "mods" / HIGH_ID / "direct" / "menu" / "price.bin").read_bytes()
        assert price(low, 1) == PRICE_EDITS[LOW_ID][1]
        assert price(high, 1) == PRICE_EDITS[HIGH_ID][1]
        assert (root / "mods" / "TEST-INSTRUCTIONS.txt").is_file()

    print("PASS: FF8 issue #100 fixture preserves independent record edits and resolves collisions by load order")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
