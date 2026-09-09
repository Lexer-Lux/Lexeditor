from pathlib import Path
import tempfile
import unittest

from games.bannerlord.module_relations import read_module_relations


class BannerlordModuleRelationTests(unittest.TestCase):
    def test_current_inverse_and_incompatible_shapes_are_read(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "SubModule.xml"
            path.write_text(
                '''<Module>
  <ModulesToLoadAfterThis>
    <Module Id="Native" />
    <Module Id="Sandbox" />
  </ModulesToLoadAfterThis>
  <IncompatibleModules>
    <Module Id="Bad.Mod" />
  </IncompatibleModules>
</Module>''',
                encoding="utf-8",
            )
            self.assertEqual(
                read_module_relations(path),
                {
                    "loadAfterThis": ["Native", "Sandbox"],
                    "incompatible": ["Bad.Mod"],
                },
            )

    def test_legacy_incompatible_shape_remains_readable(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "SubModule.xml"
            path.write_text(
                '<Module><IncompatibleModules><IncompatibleModule Id="Old.Mod" />'
                '</IncompatibleModules></Module>',
                encoding="utf-8",
            )
            self.assertEqual(read_module_relations(path)["incompatible"], ["Old.Mod"])


if __name__ == "__main__":
    unittest.main()
