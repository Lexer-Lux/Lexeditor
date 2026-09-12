from pathlib import Path
import tempfile
import unittest

from games.bannerlord.project_data import read_source, save_source


class BannerlordSourceSafetyTests(unittest.TestCase):
    def test_source_save_requires_loaded_baseline(self):
        with tempfile.TemporaryDirectory() as name:
            project=Path(name); source=project/"notes.cs"; source.write_text("before\n",encoding="utf-8")
            before=source.read_bytes()
            with self.assertRaisesRegex(ValueError,"originally loaded text"):
                save_source(project,"notes.cs","after\n")
            self.assertEqual(source.read_bytes(),before)
            self.assertFalse(source.with_name(source.name+".lexeditor.bak").exists())
            self.assertFalse(source.with_name(source.name+".lexeditor.tmp").exists())

    def test_external_source_change_is_rejected_before_backup_or_write(self):
        with tempfile.TemporaryDirectory() as name:
            project=Path(name); source=project/"notes.cs"; source.write_text("loaded\n",encoding="utf-8")
            baseline=read_source(project,"notes.cs")["text"]
            source.write_text("external\n",encoding="utf-8")
            before=source.read_bytes()
            with self.assertRaisesRegex(ValueError,"changed on disk"):
                save_source(project,"notes.cs","my edit\n",baseline)
            self.assertEqual(source.read_bytes(),before)
            self.assertFalse(source.with_name(source.name+".lexeditor.bak").exists())
            self.assertFalse(source.with_name(source.name+".lexeditor.tmp").exists())

    def test_external_bom_only_change_is_rejected_by_exact_byte_revision(self):
        with tempfile.TemporaryDirectory() as name:
            project=Path(name);source=project/"notes.cs";source.write_bytes(b"\xef\xbb\xbfloaded\r\n")
            loaded=read_source(project,"notes.cs")
            source.write_bytes(b"loaded\r\n")
            before=source.read_bytes()
            with self.assertRaisesRegex(ValueError,"changed on disk"):
                save_source(project,"notes.cs","edited\r\n",loaded["text"],loaded["sourceHash"])
            self.assertEqual(source.read_bytes(),before)
            self.assertFalse(source.with_name(source.name+".lexeditor.bak").exists())

    def test_matching_source_baseline_writes_and_backs_up(self):
        with tempfile.TemporaryDirectory() as name:
            project=Path(name); source=project/"notes.cs"; source.write_text("loaded\n",encoding="utf-8")
            baseline=read_source(project,"notes.cs")["text"]
            result=save_source(project,"notes.cs","edited\n",baseline)
            self.assertEqual(source.read_text(encoding="utf-8"),"edited\n")
            self.assertEqual(Path(result["backup"]).read_text(encoding="utf-8"),"loaded\n")
            self.assertEqual(result["text"],"edited\n")

    def test_existing_utf8_bom_is_preserved_without_duplication(self):
        with tempfile.TemporaryDirectory() as name:
            project=Path(name); source=project/"notes.cs"
            source.write_bytes(b"\xef\xbb\xbfloaded\n")
            baseline=read_source(project,"notes.cs")["text"]
            self.assertEqual(baseline,"loaded\n")
            result=save_source(project,"notes.cs","edited\n",baseline)
            raw=source.read_bytes()
            self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
            self.assertFalse(raw.startswith(b"\xef\xbb\xbf\xef\xbb\xbf"))
            self.assertEqual(result["text"],"edited\n")


if __name__ == "__main__":
    unittest.main()
