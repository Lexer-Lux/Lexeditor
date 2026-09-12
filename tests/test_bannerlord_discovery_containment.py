from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from games.bannerlord import paths
from games.bannerlord.gauntlet_data import list_prefabs
from games.bannerlord.module_data import data_map
from games.bannerlord.module_xml_data import list_documents


class BannerlordDiscoveryContainmentTests(unittest.TestCase):
    def test_contained_file_helper_keeps_real_project_files(self):
        with tempfile.TemporaryDirectory() as name:
            project = Path(name)
            source = project / "inside.xml"
            source.write_text("<Inside />", encoding="utf-8")
            self.assertTrue(paths.is_contained_file(project, source))
            self.assertFalse(paths.is_contained_file(project, project / "missing.xml"))

    def test_discovery_suppresses_files_resolving_outside_project(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            project = root / "project"
            project.mkdir()
            (project / "src").mkdir()
            (project / "ModuleData").mkdir()
            (project / "GUI" / "Prefabs").mkdir(parents=True)
            (project / "SubModule.xml").write_text('<Module><Id value="Inside"/></Module>', encoding="utf-8")
            (project / "Escape.csproj").write_text('<Project />', encoding="utf-8")
            (project / "src" / "Escape.cs").write_text('class Escape {}', encoding="utf-8")
            (project / "ModuleData" / "escape.xml").write_text('<Items />', encoding="utf-8")
            (project / "GUI" / "Prefabs" / "escape.xml").write_text('<Prefab />', encoding="utf-8")

            outside = root / "outside"
            outside.mkdir()
            outside_targets = {}
            project_root = project.resolve()
            for relative in (
                "SubModule.xml",
                "Escape.csproj",
                "src/Escape.cs",
                "ModuleData/escape.xml",
                "GUI/Prefabs/escape.xml",
            ):
                target = outside / relative.replace("/", "-")
                target.write_text("outside", encoding="utf-8")
                outside_targets[project_root / relative] = target.resolve()

            real_resolve = Path.resolve

            def fake_resolve(path, *args, **kwargs):
                redirected = outside_targets.get(Path(path))
                if redirected is not None:
                    return redirected
                return real_resolve(path, *args, **kwargs)

            with patch.object(Path, "resolve", new=fake_resolve):
                rows = {row["filename"]: row for row in data_map(project)["rows"]}
                self.assertEqual(rows["SubModule.xml"]["coverage"], "unavailable")
                self.assertFalse(rows["SubModule.xml"]["openable"])
                self.assertNotIn("Escape.csproj", rows)
                self.assertNotIn("src/Escape.cs", rows)
                self.assertNotIn("ModuleData/escape.xml", rows)
                self.assertNotIn("GUI/Prefabs/escape.xml", rows)
                self.assertEqual(list_documents(project), [])
                self.assertEqual(list_prefabs(project), [])


if __name__ == "__main__":
    unittest.main()
