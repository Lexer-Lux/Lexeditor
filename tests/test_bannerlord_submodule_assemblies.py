from pathlib import Path
import tempfile
import unittest

from games.bannerlord.module_data import read_submodule, save_module


DESCRIPTOR = '''<Module>
  <Name value="Assembly Fixture" />
  <Id value="AssemblyFixture" />
  <Version value="v1" />
  <ModuleCategory value="Singleplayer" />
  <DependedModules />
  <SubModules>
    <SubModule>
      <Name value="Assembly Fixture" />
      <DLLName value="AssemblyFixture.dll" />
      <SubModuleClassType value="AssemblyFixture.SubModule" />
      <Assemblies>
        <Assembly value="0Harmony.dll" Mystery="keep" />
        <Assembly value="Mono.Cecil.dll" />
      </Assemblies>
      <Tags />
    </SubModule>
  </SubModules>
</Module>
'''


class BannerlordSubmoduleAssemblyTests(unittest.TestCase):
    def test_additional_assemblies_round_trip_and_preserve_unknown_attributes(self):
        with tempfile.TemporaryDirectory() as name:
            source = Path(name) / "SubModule.xml"
            source.write_text(DESCRIPTOR, encoding="utf-8")
            module = read_submodule(source)
            submodule = module["submodules"][0]
            self.assertEqual(
                [row["value"] for row in submodule["assemblies"]],
                ["0Harmony.dll", "Mono.Cecil.dll"],
            )

            edited = {
                **submodule,
                "assemblies": [
                    {**submodule["assemblies"][0], "value": "Harmony.Next.dll"},
                    {"index": None, "value": "New.Dependency.dll", "attributes": {}},
                ],
            }
            saved = save_module(source, {"submodules": [edited]})
            self.assertEqual(
                [row["value"] for row in saved["module"]["submodules"][0]["assemblies"]],
                ["Harmony.Next.dll", "New.Dependency.dll"],
            )
            rewritten = source.read_text(encoding="utf-8")
            self.assertIn('<Assembly value="Harmony.Next.dll" Mystery="keep"', rewritten)
            self.assertIn('<Assembly value="New.Dependency.dll"', rewritten)
            self.assertNotIn("Mono.Cecil.dll", rewritten)
            self.assertTrue(Path(saved["backup"]).is_file())

    def test_empty_assembly_name_is_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            source = Path(name) / "SubModule.xml"
            source.write_text(DESCRIPTOR, encoding="utf-8")
            submodule = read_submodule(source)["submodules"][0]
            with self.assertRaisesRegex(ValueError, "assembly 1 needs a value"):
                save_module(
                    source,
                    {"submodules": [{**submodule, "assemblies": [{"index": None, "value": ""}]}]},
                )


if __name__ == "__main__":
    unittest.main()
