from pathlib import Path
import tempfile
import unittest

from games.bannerlord.module_data import save_module


BASE = '''<Module>
  <Name value="Example" />
  <Id value="Example" />
  <Version value="v1.0.0" />
  <SingleplayerModule value="true" />
  <DependedModules>
    <DependedModule Id="Library" />
  </DependedModules>
  <ModulesToLoadAfterThis />
  <IncompatibleModules />
  <DependedModuleMetadatas />
</Module>
'''


class BannerlordRelationSavePreflightTests(unittest.TestCase):
    def test_cross_section_before_after_conflict_is_rejected_without_writing(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "SubModule.xml"
            path.write_text(BASE, encoding="utf-8")
            before = path.read_bytes()
            with self.assertRaisesRegex(ValueError, "both LoadBeforeThis and LoadAfterThis"):
                save_module(path, {"communityDependencies": [{
                    "id": "Library",
                    "order": "LoadAfterThis",
                    "optional": False,
                    "incompatible": False,
                    "version": "",
                }]})
            self.assertEqual(path.read_bytes(), before)
            self.assertFalse(path.with_name(path.name + ".lexeditor.bak").exists())
            self.assertFalse(path.with_name(path.name + ".lexeditor.tmp").exists())

    def test_incompatible_ordered_blse_row_is_rejected_without_writing(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "SubModule.xml"
            path.write_text(BASE, encoding="utf-8")
            before = path.read_bytes()
            with self.assertRaisesRegex(ValueError, "marked incompatible but also declares LoadBeforeThis"):
                save_module(path, {"communityDependencies": [{
                    "id": "Other",
                    "order": "LoadBeforeThis",
                    "optional": False,
                    "incompatible": True,
                    "version": "",
                }]})
            self.assertEqual(path.read_bytes(), before)

    def test_single_payload_can_resolve_existing_cross_section_conflict(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "SubModule.xml"
            path.write_text(
                BASE.replace(
                    '<ModulesToLoadAfterThis />',
                    '<ModulesToLoadAfterThis><Module Id="Library" /></ModulesToLoadAfterThis>',
                ),
                encoding="utf-8",
            )
            result = save_module(path, {
                "dependencies": [{
                    "index": 0,
                    "id": "Library",
                    "dependentVersion": "",
                    "optional": False,
                    "attributes": {},
                }],
                "modulesToLoadAfterThis": [],
            })
            self.assertGreater(result["saved"], 0)
            self.assertNotIn('<Module Id="Library"', path.read_text(encoding="utf-8"))

    def test_same_direction_duplicate_metadata_remains_saveable(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "SubModule.xml"
            path.write_text(BASE.replace('<DependedModules>\n    <DependedModule Id="Library" />\n  </DependedModules>', '<DependedModules />'), encoding="utf-8")
            result = save_module(path, {"communityDependencies": [
                {"id": "Library", "order": "LoadBeforeThis", "optional": True, "incompatible": False, "version": ""},
                {"id": "Library", "order": "LoadBeforeThis", "optional": False, "incompatible": False, "version": ""},
            ]})
            self.assertGreater(result["saved"], 0)


if __name__ == "__main__":
    unittest.main()
