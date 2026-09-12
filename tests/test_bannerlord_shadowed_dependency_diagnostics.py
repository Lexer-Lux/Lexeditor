from pathlib import Path
import tempfile
import unittest

from games.bannerlord.runtime_data import deployment_status


def write_selected(game: Path) -> Path:
    folder = game / "Modules" / "Selected"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "SubModule.xml").write_text(
        '''<Module>
  <Name value="Selected" />
  <Id value="Selected" />
  <Version value="v1.0.0" />
  <SingleplayerModule value="true" />
  <DependedModules>
    <DependedModule Id="Missing.Library" />
  </DependedModules>
  <DependedModuleMetadatas>
    <DependedModuleMetadata id="Missing.Library" order="LoadBeforeThis" optional="true" />
  </DependedModuleMetadatas>
</Module>
''',
        encoding="utf-8",
    )
    return folder


class BannerlordShadowedDependencyDiagnosticTests(unittest.TestCase):
    def test_shadowed_native_required_row_does_not_block_optional_extended_relation(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            game = root / "game"
            executable = game / "bin" / "Win64_Shipping_Client" / "Bannerlord.exe"
            executable.parent.mkdir(parents=True)
            executable.write_bytes(b"")
            deployed = write_selected(game)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "SubModule.xml").write_text(
                (deployed / "SubModule.xml").read_text(encoding="utf-8"),
                encoding="utf-8",
            )

            status = deployment_status(workspace, game)
            rows = [row for row in status["dependencies"] if row["id"] == "Missing.Library"]
            self.assertEqual(len(rows), 2)
            effective = next(row for row in rows if row["effective"])
            shadowed = next(row for row in rows if not row["effective"])
            self.assertEqual(effective["origin"], "DependedModuleMetadatas")
            self.assertTrue(effective["optional"])
            self.assertEqual(shadowed["origin"], "DependedModules")
            self.assertEqual(shadowed["shadowedByOrigin"], "DependedModuleMetadatas")
            self.assertTrue(shadowed["overriddenByCommunityMetadata"])
            self.assertFalse(any("Missing required dependencies" in issue for issue in status["issues"]))
            self.assertEqual(status["loadOrder"], ["Selected"])
            self.assertTrue(status["runnable"])


if __name__ == "__main__":
    unittest.main()
