from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import unittest

from games.chrono_trigger.inventory import inventory_archive


class IndexOnlyArchive:
    def __init__(self, paths: list[str]):
        self.path = Path("resources.bin")
        self.entries = [SimpleNamespace(path=path) for path in paths]

    def read(self, _path: str):
        raise AssertionError("inventory must not decompress resource payloads")


class InventoryTests(unittest.TestCase):
    def test_discovers_candidate_families_from_actual_paths_only(self):
        archive = IndexOnlyArchive([
            "Game/battle/enemy/Enemy_0001.dat",
            "Game/battle/formation/Formation_0001.dat",
            "Game/common/item_table.bin",
            "Game/field/MapTable/MapTable_0001.dat",
            "Localize/en/msg/item.txt",
            "Game/chara/png/crono.png",
        ])
        payload = inventory_archive(archive, sample_limit=10)
        self.assertEqual(payload["resourceCount"], 6)
        self.assertEqual(payload["topLevel"]["Game"], 5)
        self.assertEqual(payload["extensions"][".dat"], 3)
        enemy = payload["candidates"]["enemy"]
        self.assertEqual(enemy["samples"][0]["path"], "Game/battle/enemy/Enemy_0001.dat")
        self.assertGreaterEqual(enemy["samples"][0]["score"], 4)
        self.assertGreaterEqual(payload["candidates"]["item"]["matchCount"], 2)
        self.assertIn("ARC1-index-only", payload["method"])

    def test_sample_limit_is_bounded_without_changing_match_count(self):
        archive = IndexOnlyArchive([f"Game/enemy/Enemy_{index:04d}.dat" for index in range(10)])
        payload = inventory_archive(archive, sample_limit=2)
        family = payload["candidates"]["enemy"]
        self.assertEqual(family["matchCount"], 10)
        self.assertEqual(len(family["samples"]), 2)


if __name__ == "__main__":
    unittest.main()
