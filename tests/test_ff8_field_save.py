"""A failed field save must not leave a partly updated mod."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from games.ff8 import field_data


class FieldSaveTests(unittest.TestCase):
    def test_repeated_saves_keep_one_backup_and_preserve_history(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "a.inf"
            path.write_bytes(b"0000")
            historical = root / "a.inf.20260901-120000.bak"
            historical.write_bytes(b"history")
            for number in range(1, 101):
                field_data._write_atomic(path, f"{number:04d}".encode())
            latest = root / "a.inf.lexeditor-auto.bak"
            self.assertEqual(latest.read_bytes(), b"0099")
            self.assertEqual(path.read_bytes(), b"0100")
            self.assertEqual(historical.read_bytes(), b"history")
            self.assertEqual(len(list(root.iterdir())), 3)
            self.assertEqual(sum(entry.stat().st_size for entry in root.iterdir()), 15)
            before = {entry.name: (entry.read_bytes(), entry.stat().st_mtime_ns)
                      for entry in root.iterdir()}
            for _ in range(100):
                field_data._write_atomic(path, b"0100")
            self.assertEqual(before, {entry.name: (entry.read_bytes(), entry.stat().st_mtime_ns)
                                     for entry in root.iterdir()})

    def test_rollback_failure_keeps_original_save_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            first, second = Path(temporary) / "a.inf", Path(temporary) / "b.inf"
            first.write_bytes(b"old")
            original = OSError("save failed")
            with patch.object(field_data, "_write_atomic", side_effect=[
                    None, original, OSError("restore failed")]):
                with self.assertRaisesRegex(OSError, "could not restore") as raised:
                    field_data._write_batch([(first, b"new"), (second, b"new")])
            self.assertIs(raised.exception.__cause__, original)
            self.assertIn(str(first), str(raised.exception))

    def test_all_maps_are_validated_before_any_file_is_written(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "first.inf"
            destination.write_bytes(b"original")
            with patch.object(field_data, "_prepare_inf_edits", side_effect=[
                    (destination, b"edited"), ValueError("bad second map")]):
                with self.assertRaisesRegex(ValueError, "bad second map"):
                    field_data.save([{"type": "entrance", "map": "one"},
                                     {"type": "entrance", "map": "two"}])
            self.assertEqual(destination.read_bytes(), b"original")
            self.assertEqual(list(Path(temporary).glob("*.bak")), [])

    def test_failed_later_write_restores_existing_and_removes_new_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            existing, new, failed = [root / name for name in ("old.inf", "new.jsm", "fail.msd")]
            existing.write_bytes(b"original")
            real_write = field_data._write_atomic

            def write(path, data, **kwargs):
                if path == failed:
                    raise OSError("simulated disk failure")
                real_write(path, data, **kwargs)

            with patch.object(field_data, "_write_atomic", side_effect=write):
                with self.assertRaisesRegex(OSError, "simulated disk failure"):
                    field_data._write_batch([(existing, b"edited"), (new, b"added"), (failed, b"fail")])
            self.assertEqual(existing.read_bytes(), b"original")
            self.assertFalse(new.exists())
            self.assertFalse(failed.exists())
            self.assertEqual(len(list(root.glob("*.bak"))), 1)
            self.assertEqual(next(root.glob("*.bak")).read_bytes(), b"original")
            self.assertEqual(list(root.glob("*.tmp")), [])

    def test_successful_multi_map_save_reports_count_and_writes_all(self):
        with tempfile.TemporaryDirectory() as temporary:
            first, second = Path(temporary) / "a.inf", Path(temporary) / "b.inf"
            with patch.object(field_data, "_prepare_inf_edits", side_effect=[
                    (first, b"first"), (second, b"second")]):
                result = field_data.save([{"type": "entrance", "map": "one"},
                                          {"type": "entrance", "map": "two"}])
            self.assertEqual(result, {"saved": 2, "maps": 2})
            self.assertEqual(first.read_bytes(), b"first")
            self.assertEqual(second.read_bytes(), b"second")

    def test_duplicate_destination_is_rejected_without_writing(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "a.inf"
            with self.assertRaisesRegex(ValueError, "duplicate"):
                field_data._write_batch([(path, b"one"), (path, b"two")])
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
