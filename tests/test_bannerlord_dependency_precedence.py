from pathlib import Path
import tempfile
import unittest

from games.bannerlord.game_launch import module_load_order


def write_module(game: Path, module_id: str, *, native=(), native_after=(), community=()) -> Path:
    folder = game / "Modules" / module_id
    folder.mkdir(parents=True, exist_ok=True)
    native_xml = "\n".join(f'    <DependedModule Id="{value}" />' for value in native)
    after_xml = "\n".join(f'    <Module Id="{value}" />' for value in native_after)
    community_xml = "\n".join(
        "    <DependedModuleMetadata " + " ".join(part for part in (
            f'id="{row["id"]}"',
            f'order="{row.get("order", "")}"' if row.get("order") else "",
            'optional="true"' if row.get("optional") else "",
        ) if part) + " />"
        for row in community
    )
    (folder / "SubModule.xml").write_text(f'''<Module>
  <Id value="{module_id}" />
  <Name value="{module_id}" />
  <Version value="v1.0.0" />
  <SingleplayerModule value="true" />
  <DependedModules>
{native_xml}
  </DependedModules>
  <ModulesToLoadAfterThis>
{after_xml}
  </ModulesToLoadAfterThis>
  <DependedModuleMetadatas>
{community_xml}
  </DependedModuleMetadatas>
</Module>
''', encoding="utf-8")
    return folder


def workspace(root: Path) -> Path:
    value = root / "workspace"
    value.mkdir()
    (value / "SubModule.xml").write_text('<Module><Id value="Selected" /></Module>', encoding="utf-8")
    return value


class BannerlordDependencyPrecedenceTests(unittest.TestCase):
    def test_community_load_after_overrides_duplicate_native_dependency_edge(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); game = root / "game"
            write_module(game, "Library")
            write_module(game, "Selected", native=("Library",), community=[{"id":"Library","order":"LoadAfterThis"}])
            with self.assertRaisesRegex(RuntimeError, "both LoadBeforeThis and LoadAfterThis"):
                module_load_order(game, workspace(root))

    def test_first_community_duplicate_optional_row_wins_requiredness(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); game = root / "game"
            write_module(game, "Library")
            write_module(game, "Selected", community=[
                {"id":"Library","order":"LoadBeforeThis","optional":True},
                {"id":"Library","order":"LoadBeforeThis"},
            ])
            self.assertEqual(module_load_order(game, workspace(root)), ["Selected"])

    def test_first_community_duplicate_order_wins_without_creating_cycle(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); game = root / "game"
            write_module(game, "Library")
            write_module(game, "Selected", community=[
                {"id":"Library","order":"LoadBeforeThis"},
                {"id":"Library","order":"LoadBeforeThis","optional":True},
            ])
            self.assertEqual(module_load_order(game, workspace(root)), ["Library", "Selected"])

    def test_native_dependency_precedes_duplicate_native_load_after_relation(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); game = root / "game"
            write_module(game, "Library")
            write_module(game, "Selected", native=("Library",), native_after=("Library",))
            with self.assertRaisesRegex(RuntimeError, "both LoadBeforeThis and LoadAfterThis"):
                module_load_order(game, workspace(root))


if __name__ == "__main__":
    unittest.main()
