from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import hashlib
import tempfile
import unittest

from games.chrono_trigger.changes import list_changes, revert_change


class _Archive:
    def __init__(self, rows: dict[str, bytes]):
        self.rows = rows

    def read(self, path: str) -> bytes:
        if path not in self.rows:
            raise KeyError(path)
        return self.rows[path]


class ChangeInventoryTests(unittest.TestCase):
    def _store(self, root: Path, vanilla: dict[str, bytes]):
        return SimpleNamespace(project_root=root, writable=True, archive=_Archive(vanilla))

    def test_classifies_modified_added_and_redundant_overrides(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-chrono-changes-") as temp_name:
            project = Path(temp_name) / "Project"
            (project / "Game").mkdir(parents=True)
            (project / "Game/modified.dat").write_bytes(b"changed")
            (project / "Game/redundant.dat").write_bytes(b"same")
            (project / "Game/added.dat").write_bytes(b"new")
            (project / "lexeditor-project.json").write_text("{}", encoding="utf-8")
            (project / ".lexeditor-deployment.json").write_text("{}", encoding="utf-8")
            result = list_changes(self._store(project, {
                "Game/modified.dat": b"vanilla",
                "Game/redundant.dat": b"same",
            }))
            by_path = {row["path"]: row for row in result["rows"]}
            self.assertEqual(by_path["Game/modified.dat"]["status"], "modified")
            self.assertEqual(by_path["Game/redundant.dat"]["status"], "redundant")
            self.assertEqual(by_path["Game/added.dat"]["status"], "added")
            self.assertEqual(result["counts"], {"modified": 1, "added": 1, "redundant": 1})
            self.assertNotIn("lexeditor-project.json", by_path)
            self.assertNotIn(".lexeditor-deployment.json", by_path)

    def test_revert_requires_current_hash_and_removes_only_overlay(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-chrono-changes-") as temp_name:
            project = Path(temp_name) / "Project"
            target = project / "Game/field/test.dat"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"changed")
            store = self._store(project, {"Game/field/test.dat": b"vanilla"})
            with self.assertRaises(RuntimeError):
                revert_change(store, "Game/field/test.dat", "0" * 64)
            self.assertTrue(target.is_file())
            expected = hashlib.sha256(b"changed").hexdigest()
            result = revert_change(store, "Game/field/test.dat", expected)
            self.assertFalse(target.exists())
            self.assertEqual(result["changeCount"], 0)
            self.assertEqual(store.archive.read("Game/field/test.dat"), b"vanilla")

    def test_revert_rejects_traversal(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-chrono-changes-") as temp_name:
            project = Path(temp_name) / "Project"
            project.mkdir()
            store = self._store(project, {})
            with self.assertRaises(ValueError):
                revert_change(store, "../outside.dat", "0" * 64)

    def test_inventory_rejects_symlink_when_supported(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-chrono-changes-") as temp_name:
            root = Path(temp_name)
            project = root / "Project"
            project.mkdir()
            outside = root / "outside.dat"
            outside.write_bytes(b"outside")
            link = project / "linked.dat"
            try:
                link.symlink_to(outside)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks are unavailable on this platform")
            with self.assertRaises(RuntimeError):
                list_changes(self._store(project, {}))


if __name__ == "__main__":
    unittest.main()
