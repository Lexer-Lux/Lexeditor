from pathlib import Path
import tempfile
import unittest

from games.bannerlord.community_metadata import community_version_matches, read_community_dependencies
from games.bannerlord.game_launch import module_load_order
from games.bannerlord.runtime_data import deployment_status


def write_module(
    game: Path,
    module_id: str,
    *,
    version="v1.0.0",
    native_dependencies=(),
    community=(),
) -> Path:
    folder = game / "Modules" / module_id
    folder.mkdir(parents=True, exist_ok=True)
    dependency_lines = []
    for dependency_id, optional in native_dependencies:
        optional_attribute = ' Optional="true"' if optional else ""
        dependency_lines.append(
            f'    <DependedModule Id="{dependency_id}"{optional_attribute} />'
        )
    native_xml = "\n".join(dependency_lines)
    community_xml = "\n".join(
        "    <DependedModuleMetadata "
        + " ".join(
            part
            for part in (
                f'id="{row["id"]}"',
                f'order="{row["order"]}"' if row.get("order") else "",
                'optional="true"' if row.get("optional") else "",
                'incompatible="true"' if row.get("incompatible") else "",
                f'version="{row["version"]}"' if row.get("version") else "",
                row.get("extra", ""),
            )
            if part
        )
        + " />"
        for row in community
    )
    (folder / "SubModule.xml").write_text(
        f'''<Module>
  <Name value="{module_id}" />
  <Id value="{module_id}" />
  <Version value="{version}" />
  <SingleplayerModule value="true" />
  <DependedModules>
{native_xml}
  </DependedModules>
  <DependedModuleMetadatas>
{community_xml}
  </DependedModuleMetadatas>
</Module>
''',
        encoding="utf-8",
    )
    return folder


def write_workspace(root: Path, module_id: str) -> Path:
    workspace = root / "workspace"
    workspace.mkdir()
    (workspace / "SubModule.xml").write_text(
        f'<Module><Id value="{module_id}" /></Module>', encoding="utf-8"
    )
    return workspace


class BannerlordCommunityMetadataTests(unittest.TestCase):
    def test_parser_reads_supported_fields_and_preserves_unknown_attributes(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            module = write_module(
                root,
                "Example",
                community=[{
                    "id": "Library",
                    "order": "LoadBeforeThis",
                    "optional": True,
                    "version": "v2.*",
                    "extra": 'Future="keep"',
                }],
            )
            rows = read_community_dependencies(module / "SubModule.xml")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["id"], "Library")
            self.assertEqual(rows[0]["order"], "LoadBeforeThis")
            self.assertTrue(rows[0]["optional"])
            self.assertFalse(rows[0]["incompatible"])
            self.assertEqual(rows[0]["version"], "v2.*")
            self.assertEqual(rows[0]["attributes"]["Future"], "keep")

    def test_community_version_rules_use_minimums_wildcards_and_ranges(self):
        self.assertTrue(community_version_matches("v2.1.*", "v2.1.9.4"))
        self.assertFalse(community_version_matches("v2.2.*", "v2.1.9.4"))
        self.assertTrue(community_version_matches("v2.0.0-v2.3.*", "v2.3.7"))
        self.assertFalse(community_version_matches("v2.0.0-v2.3.*", "v2.4.0"))
        self.assertFalse(community_version_matches("v1.0.0", "e9.9.9"))
        self.assertIsNone(community_version_matches("not-a-version", "v2.1.0"))

    def test_required_load_before_metadata_enables_and_orders_dependency_first(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            game = root / "game"
            write_module(game, "Library")
            write_module(
                game,
                "Selected",
                community=[{"id": "Library", "order": "LoadBeforeThis"}],
            )
            workspace = write_workspace(root, "Selected")
            self.assertEqual(module_load_order(game, workspace), ["Library", "Selected"])

    def test_required_load_after_metadata_enables_dependency_but_orders_it_after(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            game = root / "game"
            write_module(game, "AfterLibrary")
            write_module(
                game,
                "Selected",
                community=[{"id": "AfterLibrary", "order": "LoadAfterThis"}],
            )
            workspace = write_workspace(root, "Selected")
            self.assertEqual(module_load_order(game, workspace), ["Selected", "AfterLibrary"])

    def test_optional_community_dependency_is_not_auto_enabled(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            game = root / "game"
            write_module(game, "OptionalLibrary")
            write_module(
                game,
                "Selected",
                community=[{
                    "id": "OptionalLibrary",
                    "order": "LoadBeforeThis",
                    "optional": True,
                }],
            )
            workspace = write_workspace(root, "Selected")
            self.assertEqual(module_load_order(game, workspace), ["Selected"])

    def test_community_optional_row_overrides_duplicated_native_requiredness(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            game = root / "game"
            write_module(game, "Library")
            write_module(
                game,
                "Selected",
                native_dependencies=(("Library", False),),
                community=[{
                    "id": "Library",
                    "order": "LoadBeforeThis",
                    "optional": True,
                }],
            )
            workspace = write_workspace(root, "Selected")
            self.assertEqual(module_load_order(game, workspace), ["Selected"])

    def test_community_incompatibility_rejects_an_enabled_module(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            game = root / "game"
            write_module(game, "Native")
            write_module(
                game,
                "Selected",
                community=[{"id": "Native", "incompatible": True}],
            )
            workspace = write_workspace(root, "Selected")
            with self.assertRaisesRegex(RuntimeError, "Incompatible Bannerlord modules"):
                module_load_order(game, workspace)

    def test_missing_required_community_dependency_refuses_play(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            game = root / "game"
            write_module(
                game,
                "Selected",
                community=[{"id": "Missing.Library", "order": "LoadBeforeThis"}],
            )
            workspace = write_workspace(root, "Selected")
            with self.assertRaisesRegex(RuntimeError, "Missing.Library"):
                module_load_order(game, workspace)

    def test_deployment_reports_community_version_warning_without_blocking_play(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            game = root / "game"
            executable = game / "bin" / "Win64_Shipping_Client" / "Bannerlord.exe"
            executable.parent.mkdir(parents=True)
            executable.write_bytes(b"")
            write_module(game, "Library", version="v1.5.0")
            deployed = write_module(
                game,
                "Selected",
                community=[{
                    "id": "Library",
                    "order": "LoadBeforeThis",
                    "version": "v2.*",
                }],
            )
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "SubModule.xml").write_text(
                (deployed / "SubModule.xml").read_text(encoding="utf-8"), encoding="utf-8"
            )

            status = deployment_status(workspace, game)
            community_row = next(row for row in status["dependencies"] if row["source"] == "community")
            self.assertFalse(community_row["versionMatch"])
            self.assertEqual(community_row["order"], "LoadBeforeThis")
            self.assertTrue(any("BLSE community dependency version warning" in issue for issue in status["issues"]))
            self.assertEqual(status["loadOrder"], ["Library", "Selected"])
            self.assertTrue(status["runnable"])


if __name__ == "__main__":
    unittest.main()
