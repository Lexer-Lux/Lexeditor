from pathlib import Path
import tempfile
import unittest

from games.bannerlord.runtime_data import deployment_status


def write_module(game: Path, module_id: str, extra: str = "") -> Path:
    folder = game / "Modules" / module_id
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "SubModule.xml").write_text(
        f'''<Module>
  <Name value="{module_id}" />
  <Id value="{module_id}" />
  <Version value="v1.0.0" />
  <SingleplayerModule value="true" />
  {extra}
</Module>
''',
        encoding="utf-8",
    )
    return folder


class BannerlordDependencyDiagnosticTests(unittest.TestCase):
    def test_deployment_preserves_legacy_extended_dependency_origins(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            game = root / "game"
            executable = game / "bin" / "Win64_Shipping_Client" / "Bannerlord.exe"
            executable.parent.mkdir(parents=True)
            executable.write_bytes(b"")

            write_module(game, "After.Library")
            write_module(game, "Optional.Library")
            deployed = write_module(
                game,
                "Selected",
                '''<LoadAfterModules>
    <LoadAfterModule Id="After.Library" />
  </LoadAfterModules>
  <OptionalDependModules>
    <DependModule Id="Optional.Library" />
  </OptionalDependModules>''',
            )
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "SubModule.xml").write_text(
                (deployed / "SubModule.xml").read_text(encoding="utf-8"),
                encoding="utf-8",
            )

            status = deployment_status(workspace, game)
            by_id = {row["id"]: row for row in status["dependencies"]}

            after = by_id["After.Library"]
            self.assertEqual(after["source"], "extended")
            self.assertEqual(after["origin"], "LoadAfterModules")
            self.assertEqual(after["order"], "LoadAfterThis")
            self.assertFalse(after["optional"])

            optional = by_id["Optional.Library"]
            self.assertEqual(optional["source"], "extended")
            self.assertEqual(optional["origin"], "OptionalDependModules/DependModule")
            self.assertEqual(optional["order"], "")
            self.assertTrue(optional["optional"])

            self.assertEqual(status["loadOrder"], ["Selected", "After.Library"])
            self.assertTrue(status["runnable"])


if __name__ == "__main__":
    unittest.main()
