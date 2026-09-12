from pathlib import Path
import tempfile
import unittest

from games.bannerlord.module_data import read_submodule, save_module


CURRENT = '''<Module>
  <Name value="Relations" />
  <Id value="Relations" />
  <Version value="v1" />
  <SingleplayerModule value="true" />
  <DependedModules />
  <ModulesToLoadAfterThis>
    <Module Id="Native" Mystery="keep" />
  </ModulesToLoadAfterThis>
  <IncompatibleModules>
    <Module Id="Bad.Mod" Mystery="keep" />
  </IncompatibleModules>
  <SubModules />
  <Xmls />
</Module>
'''


class BannerlordSubmoduleRelationEditorTests(unittest.TestCase):
    def test_current_relation_shapes_are_structured_and_preserve_unknown_attributes(self):
        with tempfile.TemporaryDirectory() as name:
            source = Path(name) / "SubModule.xml"
            source.write_text(CURRENT, encoding="utf-8")
            module = read_submodule(source)
            self.assertEqual([row["id"] for row in module["modulesToLoadAfterThis"]], ["Native"])
            self.assertEqual([row["id"] for row in module["incompatibleModules"]], ["Bad.Mod"])
            self.assertEqual(module["incompatibleModules"][0]["elementTag"], "Module")

            saved = save_module(
                source,
                {
                    "modulesToLoadAfterThis": [
                        {**module["modulesToLoadAfterThis"][0], "id": "SandBoxCore"},
                        {"index": None, "id": "Sandbox", "attributes": {}},
                    ],
                    "incompatibleModules": [
                        {**module["incompatibleModules"][0], "id": "Other.Mod"},
                        {"index": None, "id": "New.Bad.Mod", "attributes": {}},
                    ],
                },
            )
            self.assertGreaterEqual(saved["saved"], 4)
            self.assertEqual(
                [row["id"] for row in saved["module"]["modulesToLoadAfterThis"]],
                ["SandBoxCore", "Sandbox"],
            )
            self.assertEqual(
                [row["id"] for row in saved["module"]["incompatibleModules"]],
                ["Other.Mod", "New.Bad.Mod"],
            )
            rewritten = source.read_text(encoding="utf-8")
            self.assertIn('<Module Id="SandBoxCore" Mystery="keep"', rewritten)
            self.assertIn('<Module Id="Other.Mod" Mystery="keep"', rewritten)
            self.assertIn('<Module Id="New.Bad.Mod"', rewritten)
            self.assertTrue(Path(saved["backup"]).is_file())

    def test_legacy_incompatible_element_is_preserved_when_edited(self):
        with tempfile.TemporaryDirectory() as name:
            source = Path(name) / "SubModule.xml"
            source.write_text(
                CURRENT.replace('<Module Id="Bad.Mod" Mystery="keep" />',
                                '<IncompatibleModule Id="Bad.Mod" Mystery="keep" />'),
                encoding="utf-8",
            )
            module = read_submodule(source)
            self.assertEqual(module["incompatibleModules"][0]["elementTag"], "IncompatibleModule")
            saved = save_module(
                source,
                {"incompatibleModules": [{**module["incompatibleModules"][0], "id": "Still.Legacy"}]},
            )
            self.assertIn(
                '<IncompatibleModule Id="Still.Legacy" Mystery="keep"',
                source.read_text(encoding="utf-8"),
            )
            self.assertEqual(saved["module"]["incompatibleModules"][0]["elementTag"], "IncompatibleModule")


if __name__ == "__main__":
    unittest.main()
