from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from games.project_zomboid import core, fixing


class ProjectZomboidFixingTests(unittest.TestCase):
    def test_condition_modifier_round_trips_and_preserves_repair_grammar(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            scripts = root / "42" / "media" / "scripts"
            scripts.mkdir(parents=True)
            path = scripts / "fixing.txt"
            path.write_text(
                '''module Base\n{\n'''
                ''' fixing RepairHammer\n {\n'''
                '''  Require = Base.Hammer;Base.Glue,\n'''
                '''  Fixer = Base.DuctTape=2;Woodwork=1,\n'''
                '''  Fixer = Base.Woodglue=1;Woodwork=2,\n'''
                '''  GlobalItem = Base.Nails=3;Base.Woodglue=1,\n'''
                '''  ConditionModifier = 1.0,\n'''
                ''' }\n}\n''',
                encoding="utf-8",
            )
            row = fixing.read(root)["rows"][0]
            saved = fixing.save(root, row["path"], row["module"], row["id"], row["sha256"], {
                "ConditionModifier": "0.65",
            })
            self.assertEqual(saved["fields"]["ConditionModifier"], "0.65")
            text = path.read_text(encoding="utf-8")
            self.assertIn("Require = Base.Hammer;Base.Glue,", text)
            self.assertEqual(text.count("Fixer ="), 2)
            self.assertIn("GlobalItem = Base.Nails=3;Base.Woodglue=1,", text)

    def test_invalid_or_missing_condition_modifier_fails_closed(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            scripts = root / "42" / "media" / "scripts"
            scripts.mkdir(parents=True)
            path = scripts / "fixing.txt"
            path.write_text(
                '''module Base\n{\n'''
                ''' fixing NoModifier { Require = Base.Hammer, }\n'''
                ''' fixing HasModifier { ConditionModifier = 1.0, }\n'''
                '''}\n''', encoding="utf-8")
            rows = fixing.read(root)["rows"]
            missing = next(row for row in rows if row["id"] == "NoModifier")
            with self.assertRaisesRegex(core.ProjectZomboidError, "missing"):
                fixing.save(root, missing["path"], missing["module"], missing["id"], missing["sha256"], {
                    "ConditionModifier": "0.5",
                })
            current = next(row for row in fixing.read(root)["rows"] if row["id"] == "HasModifier")
            with self.assertRaisesRegex(core.ProjectZomboidError, "finite"):
                fixing.save(root, current["path"], current["module"], current["id"], current["sha256"], {
                    "ConditionModifier": "nan",
                })


if __name__ == "__main__":
    unittest.main()
