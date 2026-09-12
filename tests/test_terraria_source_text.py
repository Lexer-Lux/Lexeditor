from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import tempfile
import unittest

from games.terraria.source_text import UTF8_BOM, save_source, source_file_state, source_index


class TerrariaSourceTextTests(unittest.TestCase):
    def test_indexes_project_sources_and_ignores_build_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Content").mkdir()
            (root / "obj").mkdir()
            (root / "Main.cs").write_text("namespace Example;\n", encoding="utf-8")
            (root / "Content" / "Item.cs").write_text("class Item {}\n", encoding="utf-8")
            (root / "obj" / "Generated.cs").write_text("class Generated {}\n", encoding="utf-8")

            index = source_index(root)
            self.assertEqual(
                [row["path"] for row in index["files"]],
                ["Content/Item.cs", "Main.cs"],
            )
            self.assertTrue(all(row["editable"] for row in index["files"]))

    def test_save_preserves_bom_and_original_crlf_style(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "Example.cs"
            original = UTF8_BOM + b"namespace Example;\r\n\r\npublic class One {}\r\n"
            target.write_bytes(original)
            state = source_file_state(root, "Example.cs")
            self.assertEqual(state["sha256"], sha256(original).hexdigest())

            saved = save_source(
                root,
                "Example.cs",
                "namespace Example;\n\npublic class Two {}\n",
                state["sha256"],
            )
            raw = target.read_bytes()
            self.assertTrue(raw.startswith(UTF8_BOM))
            self.assertIn(b"public class Two {}\r\n", raw)
            self.assertNotIn(b"\n", raw.replace(b"\r\n", b""))
            self.assertEqual(saved["sha256"], sha256(raw).hexdigest())

    def test_semantic_noop_after_browser_newline_normalization_is_byte_exact(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "Example.cs"
            original = b"line one\r\nline two\r\n"
            target.write_bytes(original)
            state = source_file_state(root, "Example.cs")
            saved = save_source(root, "Example.cs", "line one\nline two\n", state["sha256"])
            self.assertEqual(target.read_bytes(), original)
            self.assertEqual(saved["sha256"], state["sha256"])

    def test_stale_write_and_path_escape_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "Example.cs"
            target.write_text("class Example {}\n", encoding="utf-8")
            state = source_file_state(root, "Example.cs")
            target.write_text("class ChangedElsewhere {}\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "changed outside Lexeditor"):
                save_source(root, "Example.cs", "class Lexeditor {}\n", state["sha256"])
            with self.assertRaisesRegex(ValueError, "Invalid C# source path"):
                source_file_state(root, "../Outside.cs")
            with self.assertRaisesRegex(ValueError, "Invalid C# source path"):
                source_file_state(root, "build.txt")

    def test_non_utf8_and_nul_source_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "Bad.cs"
            target.write_bytes(b"\xff\xfe\xfd")
            with self.assertRaisesRegex(ValueError, "not UTF-8"):
                source_file_state(root, "Bad.cs")

            target.write_bytes(b"class Bad {\x00}\n")
            with self.assertRaisesRegex(ValueError, "NUL"):
                source_file_state(root, "Bad.cs")


if __name__ == "__main__":
    unittest.main()
