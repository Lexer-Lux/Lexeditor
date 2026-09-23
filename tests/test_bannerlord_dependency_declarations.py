from pathlib import Path
import tempfile
import unittest

from games.bannerlord.dependency_relations import dependency_declaration_conflicts
from games.bannerlord.game_launch import module_load_order


def module_model(*, dependencies=(), load_after=(), incompatible=()):
    return {
        "dependencies": [{"id": value, "optional": optional} for value, optional in dependencies],
        "modulesToLoadAfterThis": [{"id": value} for value in load_after],
        "incompatibleModules": [{"id": value} for value in incompatible],
    }


def write_module(game: Path, module_id: str, *, dependencies=(), incompatible=()) -> Path:
    folder = game / "Modules" / module_id
    folder.mkdir(parents=True, exist_ok=True)
    dependency_lines = []
    for dep_id, optional in dependencies:
        optional_attribute = ' Optional="true"' if optional else ""
        dependency_lines.append(
            f'    <DependedModule Id="{dep_id}"{optional_attribute} />'
        )
    deps = "\n".join(dependency_lines)
    inc = "\n".join(f'    <Module Id="{value}" />' for value in incompatible)
    (folder / "SubModule.xml").write_text(
        f"""<Module>
  <Name value="{module_id}" />
  <Id value="{module_id}" />
  <Version value="v1.0.0" />
  <SingleplayerModule value="true" />
  <DependedModules>
{deps}
  </DependedModules>
  <IncompatibleModules>
{inc}
  </IncompatibleModules>
</Module>
""",
        encoding="utf-8",
    )
    return folder


class BannerlordDependencyDeclarationTests(unittest.TestCase):
    def test_loadable_and_incompatible_is_a_declaration_conflict_even_when_optional(self):
        issues = dependency_declaration_conflicts(
            module_model(dependencies=(("Library", True),), incompatible=("Library",)),
            [],
        )
        self.assertTrue(any("both loadable and incompatible" in issue for issue in issues))

    def test_before_and_after_is_a_declaration_conflict_before_sorting(self):
        issues = dependency_declaration_conflicts(
            module_model(dependencies=(("Library", False),), load_after=("Library",)),
            [],
        )
        self.assertTrue(any("both LoadBeforeThis and LoadAfterThis" in issue for issue in issues))

    def test_raw_blse_incompatible_order_is_a_declaration_conflict(self):
        issues = dependency_declaration_conflicts(
            module_model(),
            [{
                "id": "Library",
                "order": "LoadBeforeThis",
                "optional": False,
                "incompatible": True,
                "origin": "DependedModuleMetadatas",
            }],
        )
        self.assertTrue(any("marked incompatible but also declares LoadBeforeThis" in issue for issue in issues))

    def test_optional_circular_declarations_are_rejected_without_enabling_optional_target(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            game = root / "game"
            write_module(game, "Library", dependencies=(("Selected", True),))
            write_module(game, "Selected", dependencies=(("Library", True),))
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "SubModule.xml").write_text('<Module><Id value="Selected" /></Module>', encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "circular LoadBeforeThis dependency declarations"):
                module_load_order(game, workspace)

    def test_optional_loadable_and_incompatible_target_is_rejected_even_if_not_installed(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            game = root / "game"
            write_module(
                game,
                "Selected",
                dependencies=(("Missing.Optional", True),),
                incompatible=("Missing.Optional",),
            )
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "SubModule.xml").write_text('<Module><Id value="Selected" /></Module>', encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "both loadable and incompatible"):
                module_load_order(game, workspace)


if __name__ == "__main__":
    unittest.main()
