from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import unittest

from games.chrono_trigger.inventory import inventory_archive


class IndexOnlyArchive:
    def __init__(self, paths: list[str] | list[tuple[str, int]] | list[tuple[str, int, int]]):
        self.path = Path("resources.bin")
        self.entries = []
        self._declared_sizes: dict[str, int] = {}
        self.peeked: list[str] = []
        for value in paths:
            if isinstance(value, tuple):
                if len(value) == 3:
                    path, stored_size, declared_size = value
                    self._declared_sizes[path] = declared_size
                else:
                    path, stored_size = value
                self.entries.append(SimpleNamespace(path=path, stored_size=stored_size))
            else:
                self.entries.append(SimpleNamespace(path=value))

    def declared_payload_size(self, entry) -> int:
        self.peeked.append(entry.path)
        return self._declared_sizes[entry.path]

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
        self.assertFalse(payload["peekDeclaredSizes"])
        self.assertEqual(archive.peeked, [])
        enemy = payload["candidates"]["enemy"]
        self.assertEqual(enemy["samples"][0]["path"], "Game/battle/enemy/Enemy_0001.dat")
        self.assertGreaterEqual(enemy["samples"][0]["score"], 4)
        self.assertEqual(enemy["directoryClusters"][0], {"path": "Game/battle/enemy", "count": 1})
        self.assertEqual(enemy["extensionClusters"][0], {"extension": ".dat", "count": 1})
        self.assertEqual(enemy["storedSizeClusters"], [])
        self.assertEqual(enemy["declaredSizeClusters"], [])
        self.assertGreaterEqual(payload["candidates"]["item"]["matchCount"], 2)
        self.assertIn("ARC1-index-only", payload["method"])
        self.assertIn("stored sizes", payload["method"])

    def test_sample_limit_is_bounded_without_changing_match_count(self):
        archive = IndexOnlyArchive([f"Game/enemy/Enemy_{index:04d}.dat" for index in range(10)])
        payload = inventory_archive(archive, sample_limit=2)
        family = payload["candidates"]["enemy"]
        self.assertEqual(family["matchCount"], 10)
        self.assertEqual(len(family["samples"]), 2)
        self.assertEqual(family["directoryClusters"], [{"path": "Game/enemy", "count": 10}])

    def test_stored_size_clusters_use_index_metadata_without_reading_payloads(self):
        archive = IndexOnlyArchive([
            ("Game/enemy/Enemy_0001.dat", 64),
            ("Game/enemy/Enemy_0002.dat", 64),
            ("Game/enemy/Enemy_0003.dat", 80),
            ("Game/boss/Boss_0001.dat", 80),
            ("Game/common/not_related.dat", 64),
        ])
        payload = inventory_archive(archive, sample_limit=10)
        enemy = payload["candidates"]["enemy"]
        self.assertEqual(enemy["matchCount"], 4)
        self.assertEqual(enemy["storedSizeClusters"], [
            {"storedSize": 64, "count": 2},
            {"storedSize": 80, "count": 2},
        ])
        self.assertEqual(enemy["samples"][0]["storedSize"], 80)
        self.assertEqual(enemy["directoryClusters"][0], {"path": "Game/enemy", "count": 3})
        self.assertEqual(archive.peeked, [])

    def test_declared_size_peek_clusters_four_byte_header_metadata(self):
        archive = IndexOnlyArchive([
            ("Game/enemy/Enemy_0001.dat", 40, 128),
            ("Game/enemy/Enemy_0002.dat", 42, 128),
            ("Game/enemy/Enemy_0003.dat", 50, 160),
            ("Game/common/not_related.dat", 20, 999),
        ])
        payload = inventory_archive(archive, sample_limit=10, peek_declared_sizes=True)
        enemy = payload["candidates"]["enemy"]
        self.assertTrue(payload["peekDeclaredSizes"])
        self.assertEqual(enemy["declaredSizeClusters"], [
            {"declaredSize": 128, "count": 2},
            {"declaredSize": 160, "count": 1},
        ])
        self.assertEqual(enemy["samples"][0]["declaredSize"], 128)
        self.assertEqual(set(archive.peeked), {
            "Game/enemy/Enemy_0001.dat",
            "Game/enemy/Enemy_0002.dat",
            "Game/enemy/Enemy_0003.dat",
        })
        self.assertIn("four-byte decoded entry-size prefixes", payload["method"])
        self.assertIn("no candidate gzip payloads were decompressed", payload["method"])

    def test_declared_size_peek_records_per_entry_errors_without_aborting(self):
        archive = IndexOnlyArchive([
            ("Game/enemy/Enemy_0001.dat", 40, 128),
            ("Game/enemy/Enemy_0002.dat", 42),
        ])
        payload = inventory_archive(archive, peek_declared_sizes=True)
        enemy = payload["candidates"]["enemy"]
        bad = next(row for row in enemy["samples"] if row["path"].endswith("0002.dat"))
        self.assertIn("declaredSizeError", bad)
        self.assertEqual(enemy["declaredSizeClusters"], [{"declaredSize": 128, "count": 1}])

    def test_cluster_order_is_deterministic_on_ties(self):
        archive = IndexOnlyArchive([
            ("Game/z_enemy/Enemy_0001.dat", 20),
            ("Game/a_enemy/Enemy_0002.bin", 10),
        ])
        family = inventory_archive(archive)["candidates"]["enemy"]
        self.assertEqual([row["path"] for row in family["directoryClusters"]], [
            "Game/a_enemy", "Game/z_enemy",
        ])
        self.assertEqual(family["storedSizeClusters"], [
            {"storedSize": 10, "count": 1},
            {"storedSize": 20, "count": 1},
        ])


if __name__ == "__main__":
    unittest.main()
