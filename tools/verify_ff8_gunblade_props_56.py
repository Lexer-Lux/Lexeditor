"""Prove why the two Gunblade c0m records appear in encounter data."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.ff8 import formats  # noqa: E402


def main() -> int:
    enemies = {row["id"]: row for row in formats.enemy_rows()["rows"]}
    assert enemies[82]["role"] == "battle-prop"
    assert enemies[142]["role"] == "battle-prop"
    assert "battle prop" in enemies[82]["name"].casefold()
    assert "battle prop" in enemies[142]["name"].casefold()
    assert enemies[82]["scanDescription"] == "NOT A TARGET."

    encounters = formats.encounter_rows()["rows"]
    uses = []
    for encounter in encounters:
        for slot in encounter["slots"]:
            if slot["enemyId"] in (82, 142):
                uses.append((encounter["id"], slot))
    assert uses
    assert all(not slot["targetable"] for _encounter, slot in uses)
    assert all(not slot["loaded"] for _encounter, slot in uses)
    combined = next(row for row in encounters if row["id"] == 832)
    fake = next(slot for slot in combined["slots"] if slot["enemyId"] == 75)
    prop = next(slot for slot in combined["slots"] if slot["enemyId"] == 142)
    assert fake["loaded"] and fake["targetable"] and fake["visible"]
    assert not prop["loaded"] and not prop["targetable"] and not prop["visible"]

    print("FF8 Gunblade records are non-loaded, non-targetable battle props")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
