from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import unittest

from games.chrono_trigger.probe import probe_family


class FakeArchive:
    def __init__(self, resources: list[tuple[str, bytes, int | None]]):
        self.path = Path("resources.bin")
        self.entries = []
        self.payloads: dict[str, bytes] = {}
        self.declared: dict[str, int] = {}
        self.read_paths: list[str] = []
        self.peek_paths: list[str] = []
        for path, payload, stored_size in resources:
            stored = len(payload) + 12 if stored_size is None else stored_size
            self.entries.append(SimpleNamespace(path=path, stored_size=stored))
            self.payloads[path] = payload
            self.declared[path] = len(payload)

    def declared_payload_size(self, entry) -> int:
        self.peek_paths.append(entry.path)
        return self.declared[entry.path]

    def read(self, entry) -> bytes:
        self.read_paths.append(entry.path)
        return self.payloads[entry.path]


class ProbeTests(unittest.TestCase):
    def test_probes_only_selected_family_and_reports_same_size_differences(self):
        archive = FakeArchive([
            ("Game/enemy/Enemy_0001.dat", bytes((0x10, 0x20, 0x30, 0x40)), None),
            ("Game/enemy/Enemy_0002.dat", bytes((0x10, 0x21, 0x30, 0x41)), None),
            ("Game/item/Item_0001.dat", bytes((0x99, 0x88, 0x77, 0x66)), None),
        ])
        payload = probe_family(archive, "enemy", limit=4, byte_window=4)

        self.assertEqual(payload["family"], "enemy")
        self.assertEqual(payload["candidateCount"], 2)
        self.assertEqual(payload["filteredCandidateCount"], 2)
        self.assertEqual(payload["attemptedCount"], 2)
        self.assertEqual(payload["loadedCount"], 2)
        self.assertEqual(set(archive.read_paths), {
            "Game/enemy/Enemy_0001.dat", "Game/enemy/Enemy_0002.dat",
        })
        comparison = payload["sameSizeComparisons"][0]
        self.assertEqual(comparison["payloadSize"], 4)
        self.assertEqual(comparison["constantByteCount"], 2)
        self.assertEqual(comparison["variableByteCount"], 2)
        self.assertEqual([row["offset"] for row in comparison["variablePositions"]], [1, 3])
        self.assertEqual(comparison["constantRanges"], [
            {"start": 0, "endExclusive": 1, "length": 1, "hex": "10"},
            {"start": 2, "endExclusive": 3, "length": 1, "hex": "30"},
        ])
        self.assertIn("structural diagnostics only", payload["method"])

    def test_path_prefix_scopes_family_before_any_payload_reads(self):
        archive = FakeArchive([
            ("Game/battle/enemy/Enemy_0001.dat", b"AA", None),
            ("Game/battle/enemy/Enemy_0002.dat", b"BB", None),
            ("Game/boss/Boss_0001.dat", b"CC", None),
        ])
        payload = probe_family(
            archive, "enemy", path_prefix="Game\\battle\\enemy", limit=8, byte_window=2,
        )
        self.assertEqual(payload["pathPrefix"], "Game/battle/enemy")
        self.assertEqual(payload["candidateCount"], 3)
        self.assertEqual(payload["filteredCandidateCount"], 2)
        self.assertEqual(payload["attemptedCount"], 2)
        self.assertEqual(archive.read_paths, [
            "Game/battle/enemy/Enemy_0001.dat",
            "Game/battle/enemy/Enemy_0002.dat",
        ])
        self.assertNotIn("Game/boss/Boss_0001.dat", archive.peek_paths)

    def test_declared_size_cap_skips_before_decompression(self):
        archive = FakeArchive([
            ("Game/enemy/Enemy_0001.dat", b"A" * 32, None),
            ("Game/enemy/Enemy_0002.dat", b"B" * 4096, None),
        ])
        payload = probe_family(archive, "enemy", max_payload_bytes=64, max_stored_bytes=8192)

        self.assertEqual(payload["loadedCount"], 1)
        skipped = next(row for row in payload["resources"] if row["path"].endswith("0002.dat"))
        self.assertIn("declared payload size", skipped["skipped"])
        self.assertNotIn("Game/enemy/Enemy_0002.dat", archive.read_paths)
        self.assertIn("Game/enemy/Enemy_0002.dat", archive.peek_paths)

    def test_stored_size_cap_skips_before_size_peek(self):
        archive = FakeArchive([
            ("Game/enemy/Enemy_0001.dat", b"A" * 8, 5000),
        ])
        payload = probe_family(archive, "enemy", max_stored_bytes=64)
        self.assertEqual(payload["loadedCount"], 0)
        self.assertEqual(archive.peek_paths, [])
        self.assertEqual(archive.read_paths, [])
        self.assertIn("stored size", payload["resources"][0]["skipped"])

    def test_limit_is_attempt_cap_and_sorting_is_deterministic(self):
        archive = FakeArchive([
            ("Game/enemy/z/Enemy_0002.dat", b"22", None),
            ("Game/enemy/a/Enemy_0001.dat", b"11", None),
            ("Game/enemy/m/Enemy_0003.dat", b"33", None),
        ])
        payload = probe_family(archive, "enemy", limit=2, byte_window=2)
        self.assertEqual(payload["candidateCount"], 3)
        self.assertEqual(payload["attemptedCount"], 2)
        self.assertEqual([row["path"] for row in payload["resources"]], [
            "Game/enemy/a/Enemy_0001.dat",
            "Game/enemy/m/Enemy_0003.dat",
        ])

    def test_rejects_unknown_family_and_unbounded_values(self):
        archive = FakeArchive([])
        with self.assertRaisesRegex(ValueError, "unknown candidate family"):
            probe_family(archive, "banana")
        with self.assertRaisesRegex(ValueError, "Probe limit"):
            probe_family(archive, "enemy", limit=0)
        with self.assertRaisesRegex(ValueError, "Byte window"):
            probe_family(archive, "enemy", byte_window=9999)


if __name__ == "__main__":
    unittest.main()
