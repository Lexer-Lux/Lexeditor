"""Verify the world-map position tables: entity spawns and train exits."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from plugins.ff8 import world_map  # noqa: E402

WORLD_LIMIT = 131072   # the projection in codex/ff8/world-terrain.md spans this


def main() -> int:
    entities = world_map.entity_spawn_positions("vanilla")
    assert entities["section"] == world_map.ENTITY_SPAWN_SECTION == 10
    assert entities["recordSize"] == 16 and entities["count"] == 64, entities["count"]
    assert entities["footer"] == "00 00 00 00", entities["footer"]
    for row in entities["rows"]:
        assert set(row) == {"index", "offset", "x", "y", "z", "yaw", "pitch"}, row
        assert abs(row["x"]) <= WORLD_LIMIT and abs(row["y"]) <= WORLD_LIMIT, row
        assert -32768 <= row["yaw"] <= 32767, row
    # The section is 1028 bytes: 64 records of 16 plus the four-byte footer.
    assert entities["rows"][1]["offset"] - entities["rows"][0]["offset"] == 16

    trains = world_map.train_exit_positions("vanilla")
    assert trains["section"] == world_map.TRAIN_EXIT_SECTION == 12
    assert trains["recordSize"] == 12 and trains["count"] == 3, trains["count"]
    assert trains["footer"] == "00 00 00 00", trains["footer"]
    for row in trains["rows"]:
        assert set(row) == {"index", "offset", "x", "y", "z", "unknownA", "unknownB"}, row
        assert abs(row["x"]) <= WORLD_LIMIT and abs(row["y"]) <= WORLD_LIMIT, row
        assert 0 <= row["unknownA"] <= 255 and 0 <= row["unknownB"] <= 255, row

    # A section whose size is not records plus a footer is refused rather than
    # read as if the arithmetic worked.
    raw = world_map.ensure_baseline().read_bytes()
    for section, record in ((11, 16), (13, 12), (6, 16)):
        try:
            world_map._position_rows(raw, section, record, (("x", 0, "i"),))
        except ValueError as error:
            assert "records" in str(error) or "footer" in str(error), error
        else:
            raise AssertionError(f"section {section} parsed as {record}-byte records")
    print(json.dumps({"entitySpawns": entities["count"], "trainExits": trains["count"],
                      "entityByteSize": 1028, "trainByteSize": 40,
                      "firstTrainExit": trains["rows"][0]["x"]}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
