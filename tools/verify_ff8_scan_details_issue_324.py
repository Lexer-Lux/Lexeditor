"""Regression contract for data-driven FF8 Scan details (issue #324)."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.ff8 import enemy_tables, scan_details, scan_text

SCHEMA = ROOT / "games" / "ff8" / "schema"


def main() -> int:
    devour = json.loads((SCHEMA / "devour.json").read_text(encoding="utf-8"))["devour"]
    assert [(row["id"], row["name"]) for row in devour] == [
        (0, "HP Recovery"), (1, "Full HP Recovery"), (2, "HP & Status Rec."),
        (3, "Damage & Zombie"), (4, "Damage(m) & Poison"),
        (5, "Damage & Dark"), (6, "Damage(s) & Poison"), (7, "Damage"),
        (8, "Dmg&Random Status"), (9, "No Change"), (10, "Strength +1"),
        (11, "Defense +1"), (12, "Magic +1"), (13, "Spirit +1"),
        (14, "Speed +1"), (15, "Max HP +10"), (255, "Immune"),
    ]
    choices = enemy_tables.choices(SCHEMA, [], [])
    assert choices["devour"] == devour

    tables = {
        "elementDefence": [
            {"slot": 0, "percent": 150},  # weak Fire
            {"slot": 1, "percent": 50},   # resist Ice
            {"slot": 2, "percent": 0},    # immune Thunder
            {"slot": 3, "percent": -25},  # absorb Earth
            *({"slot": slot, "percent": 100} for slot in range(4, 8)),
        ],
        "devour": [
            {"slot": 0, "devourId": 0},
            {"slot": 1, "devourId": 10},
            {"slot": 2, "devourId": 255},
        ],
    }
    page = scan_details.build_page(tables, devour)
    assert page == (
        "DETAILS\n"
        "Weak: Fire 150%\n"
        "Resist: Ice 50%\n"
        "Immune: Thunder\n"
        "Absorb: Earth 25%\n"
        "Devour Low: HP Recovery\n"
        "Devour Mid: Strength +1\n"
        "Devour High: Immune"
    )
    # The generated page must use only glyphs accepted by the existing Scan
    # encoder; this is the exact data eventually written to battle_scans.msd.
    encoded = scan_text.encode_text(page)
    assert scan_text.decode_text(encoded) == page

    neutral = scan_details.build_page({
        "elementDefence": [{"slot": slot, "percent": 100} for slot in range(8)],
        "devour": [{"slot": 0, "devourId": 1}, {"slot": 1, "devourId": 9},
                   {"slot": 2, "devourId": 42}],
    }, devour)
    assert "Elements: Neutral" in neutral
    assert "Devour High: Unknown 42" in neutral
    scan_text.encode_text(neutral)

    editor = (ROOT / "games" / "ff8" / "editor.html").read_text(encoding="utf-8")
    for marker in (
        "enemyGeneratedScanDetails", "UPDATE DETAILS", "UPDATE ALL",
        "choices.devour", "Tier level cut-offs vary",
    ):
        assert marker in editor, marker
    assert "Stored Devour ID" not in editor

    print("PASS: FF8 issue #324 uses proven Devour names and encodable data-driven Scan details")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
