from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from games.project_zomboid import core, vehicle


class ProjectZomboidVehicleTests(unittest.TestCase):
    def make_project(self, root: Path) -> Path:
        project = root / "mod"
        scripts = project / "42" / "media" / "scripts"
        scripts.mkdir(parents=True)
        (project / "42" / "mod.info").write_text("name=Test\nid=Test\n", encoding="utf-8")
        (scripts / "vehicle.txt").write_text(
            '''module Base\n{\n'''
            '''  vehicle TestCar\n  {\n'''
            '''    animalTrailerSize = 500,\n'''
            '''    carMechanicsOverlay = CarMechanics,\n'''
            '''    carModelName = TestCar,\n'''
            '''    engineForce = 3000,\n'''
            '''    engineIdleSpeed = 750,\n'''
            '''    engineLoudness = 100,\n'''
            '''    engineQuality = 100,\n'''
            '''    engineRepairLevel = 4,\n'''
            '''    engineRPMType = jeep,\n'''
            '''    gearRatioCount = 5,\n'''
            '''    hasLighter = true,\n'''
            '''    isSmallVehicle = false,\n'''
            '''    FutureField = KeepMe,\n'''
            '''    part Engine { category = engine, }\n'''
            '''  }\n}\n''', encoding="utf-8")
        return project

    def test_surgical_vehicle_edit_preserves_nested_structure(self):
        with tempfile.TemporaryDirectory() as name:
            root = self.make_project(Path(name))
            row = vehicle.read(root)["rows"][0]
            saved = vehicle.save(
                root, row["path"], row["module"], row["id"], row["sha256"],
                {"engineForce": "4200", "gearRatioCount": "6", "hasLighter": "false"},
            )
            text = (root / row["path"]).read_text(encoding="utf-8")
            self.assertEqual(saved["fields"]["engineForce"], "4200")
            self.assertEqual(saved["fields"]["gearRatioCount"], "6")
            self.assertEqual(saved["fields"]["hasLighter"], "false")
            self.assertIn("FutureField = KeepMe,", text)
            self.assertIn("part Engine { category = engine, }", text)

    def test_vehicle_validation_is_typed(self):
        with tempfile.TemporaryDirectory() as name:
            root = self.make_project(Path(name))
            row = vehicle.read(root)["rows"][0]
            bad = (
                ("engineForce", "nan", "finite"),
                ("engineForce", "-1", ">= 0"),
                ("engineQuality", "1.5", "integer"),
                ("gearRatioCount", "10", "between 1 and 9"),
                ("hasLighter", "yes", "true or false"),
            )
            for key, value, message in bad:
                with self.subTest(key=key, value=value):
                    with self.assertRaisesRegex(core.ProjectZomboidError, message):
                        vehicle.save(root, row["path"], row["module"], row["id"], row["sha256"], {key: value})

    def test_missing_and_stale_vehicle_edits_fail_closed(self):
        with tempfile.TemporaryDirectory() as name:
            root = self.make_project(Path(name))
            script = root / "42" / "media" / "scripts" / "vehicle.txt"
            script.write_text(script.read_text(encoding="utf-8").replace("    carModelName = TestCar,\n", ""), encoding="utf-8")
            row = vehicle.read(root)["rows"][0]
            with self.assertRaisesRegex(core.ProjectZomboidError, "missing: carModelName"):
                vehicle.save(root, row["path"], row["module"], row["id"], row["sha256"], {"carModelName": "Other"})
            script.write_text(script.read_text(encoding="utf-8") + "// external\n", encoding="utf-8")
            with self.assertRaisesRegex(core.ProjectZomboidError, "changed outside Lexeditor"):
                vehicle.save(root, row["path"], row["module"], row["id"], row["sha256"], {"engineForce": "4000"})


if __name__ == "__main__":
    unittest.main()
