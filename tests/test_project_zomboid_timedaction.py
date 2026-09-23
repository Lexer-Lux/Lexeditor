from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from games.project_zomboid import core, timedaction


class ProjectZomboidTimedActionTests(unittest.TestCase):
    def test_action_anim_round_trips_and_preserves_unmodeled_fields(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            scripts = root / "42" / "media" / "scripts"
            scripts.mkdir(parents=True)
            path = scripts / "actions.txt"
            path.write_text(
                '''module Base\n{\n'''
                ''' timedAction BuildThing\n {\n'''
                '''  metabolics = HeavyWork,\n'''
                '''  actionAnim = Loot,\n'''
                '''  animVarKey = LootPosition,\n'''
                '''  animVarVal = Low,\n'''
                '''  completionSound = BuildFence,\n'''
                '''  muscleStrainParts = Neck;Torso_Upper,\n'''
                '''  prop1 = Base.HammerModel,\n'''
                ''' }\n}\n''', encoding="utf-8")
            row = timedaction.read(root)["rows"][0]
            saved = timedaction.save(root, row["path"], row["module"], row["id"], row["sha256"], {
                "actionAnim": "BuildLow",
            })
            self.assertEqual(saved["fields"]["actionAnim"], "BuildLow")
            text = path.read_text(encoding="utf-8")
            for preserved in (
                "metabolics = HeavyWork,",
                "animVarKey = LootPosition,",
                "completionSound = BuildFence,",
                "muscleStrainParts = Neck;Torso_Upper,",
                "prop1 = Base.HammerModel,",
            ):
                self.assertIn(preserved, text)

    def test_missing_duplicate_and_invalid_action_anim_fail_closed(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            scripts = root / "42" / "media" / "scripts"
            scripts.mkdir(parents=True)
            path = scripts / "actions.txt"
            path.write_text(
                '''module Base\n{\n'''
                ''' timedAction Missing { metabolics = Default, }\n'''
                ''' timedAction Duplicate { actionAnim = Loot, actionAnim = Build, }\n'''
                ''' timedAction Valid { actionAnim = Loot, }\n'''
                '''}\n''', encoding="utf-8")
            rows = timedaction.read(root)["rows"]
            missing = next(row for row in rows if row["id"] == "Missing")
            with self.assertRaisesRegex(core.ProjectZomboidError, "missing"):
                timedaction.save(root, missing["path"], missing["module"], missing["id"], missing["sha256"], {
                    "actionAnim": "Build",
                })
            duplicate = next(row for row in timedaction.read(root)["rows"] if row["id"] == "Duplicate")
            with self.assertRaisesRegex(core.ProjectZomboidError, "duplicated"):
                timedaction.save(root, duplicate["path"], duplicate["module"], duplicate["id"], duplicate["sha256"], {
                    "actionAnim": "Build",
                })
            valid = next(row for row in timedaction.read(root)["rows"] if row["id"] == "Valid")
            with self.assertRaisesRegex(core.ProjectZomboidError, "cannot be empty"):
                timedaction.save(root, valid["path"], valid["module"], valid["id"], valid["sha256"], {
                    "actionAnim": "",
                })


if __name__ == "__main__":
    unittest.main()
