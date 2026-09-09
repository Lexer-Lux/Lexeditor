from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from games.bannerlord.gauntlet_data import (
    augment_data_map,
    list_prefabs,
    read_prefab,
    save_prefab,
)


PREFAB = '''<Prefab>
  <!-- preserve this comment and formatting -->
  <Window>
    <Widget WidthSizePolicy="StretchToParent" HeightSizePolicy="Fixed" SuggestedHeight="24" IsEnabled="false" IsVisible="@IsEnabled">
      <Children>
        <TextWidget Text="@LeaderIconText" Brush.TextHorizontalAlignment="Center" Color="#ffffff" />
      </Children>
    </Widget>
  </Window>
</Prefab>
'''


class BannerlordGauntletTests(unittest.TestCase):
    def fixture(self):
        temporary = tempfile.TemporaryDirectory()
        project = Path(temporary.name)
        source = project / "GUI" / "Prefabs" / "Mission" / "LexerMoraleBars.xml"
        source.parent.mkdir(parents=True)
        source.write_text(PREFAB, encoding="utf-8")
        return temporary, project, source

    def test_prefab_scan_exposes_tree_and_typed_existing_attributes(self):
        temporary, project, _source = self.fixture()
        try:
            self.assertEqual(
                list_prefabs(project),
                ["GUI/Prefabs/Mission/LexerMoraleBars.xml"],
            )
            value = read_prefab(project, "GUI/Prefabs/Mission/LexerMoraleBars.xml")
            widget = next(row for row in value["elements"] if row["tag"] == "Widget")
            self.assertEqual(widget["path"], "Prefab[0]/Window[0]/Widget[0]")
            self.assertEqual(widget["depth"], 2)
            attributes = {row["name"]: row for row in widget["attributes"]}
            self.assertEqual(attributes["WidthSizePolicy"]["kind"], "enum")
            self.assertEqual(attributes["SuggestedHeight"]["kind"], "number")
            self.assertEqual(attributes["IsEnabled"]["kind"], "bool")
            self.assertEqual(attributes["IsVisible"]["kind"], "binding")
        finally:
            temporary.cleanup()

    def test_save_is_surgical_validated_and_backed_up(self):
        temporary, project, source = self.fixture()
        try:
            value = read_prefab(project, "GUI/Prefabs/Mission/LexerMoraleBars.xml")
            widget = next(row for row in value["elements"] if row["tag"] == "Widget")
            result = save_prefab(
                project,
                value["relativePath"],
                [
                    {
                        "elementPath": widget["path"],
                        "tag": widget["tag"],
                        "attribute": "SuggestedHeight",
                        "originalValue": "24",
                        "value": 30,
                    },
                    {
                        "elementPath": widget["path"],
                        "tag": widget["tag"],
                        "attribute": "IsEnabled",
                        "originalValue": "false",
                        "value": True,
                    },
                ],
            )
            self.assertEqual(result["saved"], 2)
            self.assertTrue(Path(result["backup"]).is_file())
            rewritten = source.read_text(encoding="utf-8")
            self.assertIn("<!-- preserve this comment and formatting -->", rewritten)
            self.assertIn('SuggestedHeight="30"', rewritten)
            self.assertIn('IsEnabled="true"', rewritten)
            self.assertIn('IsVisible="@IsEnabled"', rewritten)
            self.assertEqual(rewritten.count("\n"), PREFAB.count("\n"))
        finally:
            temporary.cleanup()

    def test_stale_attribute_and_path_escape_are_rejected(self):
        temporary, project, source = self.fixture()
        try:
            value = read_prefab(project, "GUI/Prefabs/Mission/LexerMoraleBars.xml")
            widget = next(row for row in value["elements"] if row["tag"] == "Widget")
            source.write_text(PREFAB.replace('SuggestedHeight="24"', 'SuggestedHeight="25"'), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "changed on disk"):
                save_prefab(
                    project,
                    value["relativePath"],
                    [{
                        "elementPath": widget["path"],
                        "tag": widget["tag"],
                        "attribute": "SuggestedHeight",
                        "originalValue": "24",
                        "value": 30,
                    }],
                )
            with self.assertRaisesRegex(ValueError, "only opens XML files under GUI/Prefabs"):
                read_prefab(project, "../outside.xml")
        finally:
            temporary.cleanup()

    def test_prefab_root_redirection_outside_project_is_rejected(self):
        temporary, project, _source = self.fixture()
        try:
            outside = project.parent / (project.name + "-outside-gauntlet")
            outside.mkdir()
            project_resolved = project.resolve()
            prefab_root = project_resolved / "GUI" / "Prefabs"
            outside_resolved = outside.resolve()
            real_resolve = Path.resolve

            def fake_resolve(path, *args, **kwargs):
                if path == prefab_root:
                    return outside_resolved
                return real_resolve(path, *args, **kwargs)

            with patch.object(Path, "resolve", new=fake_resolve):
                with self.assertRaisesRegex(ValueError, "project path escaped"):
                    read_prefab(project, "GUI/Prefabs/Mission/LexerMoraleBars.xml")
        finally:
            if 'outside' in locals() and outside.exists():
                outside.rmdir()
            temporary.cleanup()

    def test_data_map_upgrades_only_gauntlet_prefabs(self):
        value = augment_data_map({"rows": [
            {"filename": "GUI/Prefabs/Mission/Test.xml", "coverage": "source", "target": ""},
            {"filename": "ModuleData/items.xml", "coverage": "source", "target": ""},
        ]})
        prefab, module_data = value["rows"]
        self.assertEqual(prefab["coverage"], "structured")
        self.assertEqual(prefab["target"], "gauntlet")
        self.assertEqual(prefab["editorPath"], "GUI/Prefabs/Mission/Test.xml")
        self.assertEqual(module_data["coverage"], "source")


if __name__ == "__main__":
    unittest.main()
