from pathlib import Path
import tempfile
import unittest

from games.bannerlord.module_data import read_submodule, save_module


class BannerlordModuleMetadataTests(unittest.TestCase):
    def test_url_and_update_info_round_trip_and_insert_before_structural_sections(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "SubModule.xml"
            path.write_text(
                """<Module>
  <Name value="Example" />
  <Id value="Example" />
  <Version value="v1.0.0" />
  <DependedModules><DependedModule Id="Native" /></DependedModules>
  <SubModules />
</Module>
""",
                encoding="utf-8",
            )
            result = save_module(path, {"metadata": {
                "moduleCategory": "Singleplayer",
                "moduleType": "Community",
                "url": "https://example.invalid/mod",
                "updateInfo": "NexusMods:1234;GitHub:user/repo",
            }})
            module = result["module"]
            self.assertEqual(module["url"], "https://example.invalid/mod")
            self.assertEqual(module["updateInfo"], "NexusMods:1234;GitHub:user/repo")
            rewritten = path.read_text(encoding="utf-8")
            structural = rewritten.index("<DependedModules>")
            for tag in ("<ModuleCategory", "<ModuleType", "<Url", "<UpdateInfo"):
                self.assertLess(rewritten.index(tag), structural)

    def test_existing_metadata_position_and_unknown_attributes_are_preserved(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "SubModule.xml"
            path.write_text(
                """<Module>
  <Name value="Example" />
  <Url value="old" Future="keep" />
  <Id value="Example" />
  <Version value="v1.0.0" />
  <DependedModules />
</Module>
""",
                encoding="utf-8",
            )
            before = path.read_text(encoding="utf-8").index("<Url")
            save_module(path, {"metadata": {"url": "new"}})
            rewritten = path.read_text(encoding="utf-8")
            self.assertIn('Future="keep"', rewritten)
            self.assertLess(rewritten.index("<Url"), rewritten.index("<Id"))
            self.assertGreaterEqual(before, 0)

    def test_blank_optional_community_metadata_removes_elements(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "SubModule.xml"
            path.write_text(
                '<Module><Name value="Example" /><Id value="Example" /><Version value="v1.0.0" /><Url value="x" /><UpdateInfo value="NexusMods:1" /></Module>',
                encoding="utf-8",
            )
            result = save_module(path, {"metadata": {"url": "", "updateInfo": ""}})
            self.assertEqual(result["module"]["url"], "")
            self.assertEqual(result["module"]["updateInfo"], "")
            rewritten = path.read_text(encoding="utf-8")
            self.assertNotIn("<Url", rewritten)
            self.assertNotIn("<UpdateInfo", rewritten)

    def test_update_info_grammar_matches_documented_community_forms(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "SubModule.xml"
            path.write_text('<Module><Name value="Example" /><Id value="Example" /><Version value="v1.0.0" /></Module>', encoding="utf-8")
            accepted = [
                "NexusMods:123",
                "GitHub:user/repo",
                "NexusMods:123;GitHub:user/repo",
                "GitHub:user/repo;NexusMods:123",
            ]
            for value in accepted:
                save_module(path, {"metadata": {"updateInfo": value}})
                self.assertEqual(read_submodule(path)["updateInfo"], value)
            with self.assertRaisesRegex(ValueError, "updateInfo must be"):
                save_module(path, {"metadata": {"updateInfo": "https://example.invalid"}})


if __name__ == "__main__":
    unittest.main()
