from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from games.project_zomboid import core


SCRIPT = """module LexTest
{
    item TestItem
    {
        DisplayCategory = Tool,
        ItemType = base:normal,
        Weight = 0.3,
        Icon = Radio,
        UnknownFutureField = KeepMe,
        component Example
        {
            Weight = 99,
        }
    }
}
"""


class ProjectZomboidCoreTests(unittest.TestCase):
    def make_project(self, parent: Path) -> Path:
        root = parent / "Lex Test Mod"
        (root / "42" / "media" / "scripts").mkdir(parents=True)
        (root / "common" / "media").mkdir(parents=True)
        (root / "42" / "mod.info").write_text(
            "name=Lex Test Mod\n"
            "id=LexTest\n"
            "versionMin=42.20\n"
            "poster=poster.png\n"
            "FutureKey=KeepThis\n",
            encoding="utf-8",
        )
        (root / "42" / "media" / "scripts" / "items.txt").write_text(
            SCRIPT, encoding="utf-8"
        )
        return root

    def test_mod_info_surgical_save_preserves_unknown_fields_and_rejects_stale_write(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_project(Path(temp))
            before = core.read_mod_info(root)
            saved = core.save_mod_info(
                root, before["sha256"], {"author": "Lexer", "versionMax": "42.20.4"}
            )
            text = (root / "42" / "mod.info").read_text(encoding="utf-8")
            self.assertEqual(saved["fields"]["author"], "Lexer")
            self.assertIn("poster=poster.png", text)
            self.assertIn("FutureKey=KeepThis", text)
            with self.assertRaisesRegex(core.ProjectZomboidError, "changed outside Lexeditor"):
                core.save_mod_info(root, before["sha256"], {"author": "Stale"})

    def test_item_edit_changes_only_selected_existing_properties(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_project(Path(temp))
            row = core.read_items(root)["rows"][0]
            saved = core.save_item(
                root,
                row["path"],
                row["module"],
                row["id"],
                row["sha256"],
                {"ItemType": "base:food", "Weight": "0.5"},
            )
            text = (root / "42" / "media" / "scripts" / "items.txt").read_text(encoding="utf-8")
            self.assertEqual(saved["fields"]["ItemType"], "base:food")
            self.assertEqual(saved["fields"]["Weight"], "0.5")
            self.assertIn("UnknownFutureField = KeepMe,", text)
            self.assertIn("Weight = 99,", text)
            self.assertEqual(text.count("Weight = 0.5,"), 1)

    def test_item_same_line_duplicate_fails_closed_without_counting_nested_property(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_project(Path(temp))
            script = root / "42" / "media" / "scripts" / "items.txt"
            original = script.read_text(encoding="utf-8").replace(
                "        Weight = 0.3,\n",
                "        Weight = 0.3, Weight = 0.7,\n",
            )
            script.write_text(original, encoding="utf-8")
            row = core.read_items(root)["rows"][0]
            self.assertIn("Weight", row["duplicateKeys"])
            with self.assertRaisesRegex(core.ProjectZomboidError, "duplicated item properties: Weight"):
                core.save_item(
                    root, row["path"], row["module"], row["id"], row["sha256"],
                    {"Weight": "0.5"},
                )
            self.assertEqual(script.read_text(encoding="utf-8"), original)

            script.write_text(SCRIPT, encoding="utf-8")
            clean = core.read_items(root)["rows"][0]
            self.assertNotIn("Weight", clean["duplicateKeys"])
            self.assertEqual(clean["fields"]["Weight"], "0.3")

    def test_item_writer_rejects_missing_property_and_invalid_item_type(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_project(Path(temp))
            row = core.read_items(root)["rows"][0]
            with self.assertRaisesRegex(core.ProjectZomboidError, "ItemType"):
                core.save_item(
                    root, row["path"], row["module"], row["id"], row["sha256"],
                    {"ItemType": "Normal"},
                )
            current = core.read_items(root)["rows"][0]
            script = root / current["path"]
            script.write_text(script.read_text(encoding="utf-8").replace("Icon = Radio,\n", ""), encoding="utf-8")
            current = core.read_items(root)["rows"][0]
            with self.assertRaisesRegex(core.ProjectZomboidError, "missing: Icon"):
                core.save_item(
                    root, current["path"], current["module"], current["id"], current["sha256"],
                    {"Icon": "NewIcon"},
                )

    def test_deploy_and_undeploy_are_owned_and_external_change_safe(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = self.make_project(base)
            user_root = base / "Zomboid"
            with patch.dict(os.environ, {"LEXEDITOR_PROJECT_ZOMBOID_USER_ROOT": str(user_root)}):
                state = core.deploy(root)
                target = Path(state["target"])
                self.assertTrue(state["owned"])
                self.assertTrue((target / "42" / "mod.info").is_file())
                (target / "42" / "mod.info").write_text("external change", encoding="utf-8")
                with self.assertRaisesRegex(core.ProjectZomboidError, "changed externally"):
                    core.deploy(root)
                with self.assertRaisesRegex(core.ProjectZomboidError, "changed externally"):
                    core.undeploy(root)

    def test_data_map_distinguishes_structured_partial_and_recognized_content(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_project(Path(temp))
            (root / "42" / "media" / "lua").mkdir(parents=True)
            rows = core.data_map(root)["rows"]
            statuses = {row["filename"]: row["status"] for row in rows}
            self.assertEqual(statuses["42/mod.info"], "structured")
            self.assertEqual(statuses["42/media/scripts/items.txt"], "partial")
            self.assertEqual(statuses["42/media/lua/**"], "recognized")


if __name__ == "__main__":
    unittest.main()
