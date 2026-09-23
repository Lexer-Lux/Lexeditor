from pathlib import Path
import tempfile
import unittest

from games.bannerlord.module_data import read_submodule, save_module


DESCRIPTOR = '''<Module>
  <Name value="Community Editor" />
  <Id value="Community.Editor" />
  <Version value="v1.0.0" />
  <SingleplayerModule value="true" />
  <DependedModuleMetadatas>
    <!-- keep this comment -->
    <DependedModuleMetadata id="Library" order="LoadBeforeThis" version="v2.0.*" Mystery="keep" />
    <FutureMetadata value="preserve" />
  </DependedModuleMetadatas>
  <LoadAfterModules><LoadAfterModule Id="Legacy.After" /></LoadAfterModules>
  <OptionalDependModules><DependModule Id="Legacy.Optional" /></OptionalDependModules>
</Module>
'''


class BannerlordCommunityEditorTests(unittest.TestCase):
    def test_read_and_save_blse_rows_preserve_unknown_and_legacy_data(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "SubModule.xml"
            path.write_text(DESCRIPTOR, encoding="utf-8")
            module = read_submodule(path)
            self.assertEqual(len(module["communityDependencies"]), 1)
            row = module["communityDependencies"][0]
            self.assertEqual(row["id"], "Library")
            self.assertEqual(row["order"], "LoadBeforeThis")
            self.assertEqual(row["version"], "v2.0.*")
            self.assertEqual(row["attributes"]["Mystery"], "keep")

            result = save_module(path, {"communityDependencies": [{
                **row,
                "order": "LoadAfterThis",
                "version": "v2.1.0-v2.9.*",
                "optional": True,
                "incompatible": False,
            }]})
            self.assertEqual(result["saved"], 1)
            self.assertTrue(Path(result["backup"]).is_file())
            rewritten = path.read_text(encoding="utf-8")
            self.assertIn('Mystery="keep"', rewritten)
            self.assertIn('FutureMetadata value="preserve"', rewritten)
            self.assertIn('LoadAfterModule Id="Legacy.After"', rewritten)
            self.assertIn('DependModule Id="Legacy.Optional"', rewritten)
            saved = result["module"]["communityDependencies"][0]
            self.assertEqual(saved["order"], "LoadAfterThis")
            self.assertEqual(saved["version"], "v2.1.0-v2.9.*")
            self.assertTrue(saved["optional"])

    def test_new_blse_incompatible_row_uses_current_lowercase_attribute_shape(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "SubModule.xml"
            path.write_text('<Module><Id value="Example" /></Module>', encoding="utf-8")
            result = save_module(path, {"communityDependencies": [{
                "index": None,
                "id": "New.Library",
                "order": "",
                "version": "v1.2.*",
                "optional": False,
                "incompatible": True,
                "attributes": {},
            }]})
            row = result["module"]["communityDependencies"][0]
            self.assertEqual(row["id"], "New.Library")
            rewritten = path.read_text(encoding="utf-8")
            self.assertIn('<DependedModuleMetadata id="New.Library" version="v1.2.*" incompatible="true"', rewritten)
            self.assertNotIn('order=', rewritten)
            self.assertNotIn('optional="false"', rewritten)

    def test_invalid_blse_order_and_empty_id_are_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "SubModule.xml"
            path.write_text('<Module><Id value="Example" /></Module>', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "order must be"):
                save_module(path, {"communityDependencies": [{"id": "Library", "order": "Sideways"}]})
            with self.assertRaisesRegex(ValueError, "needs an ID"):
                save_module(path, {"communityDependencies": [{"id": "", "order": ""}]})


if __name__ == "__main__":
    unittest.main()
