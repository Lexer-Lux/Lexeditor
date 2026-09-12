from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


paths_file = Path("games/bannerlord/paths.py")
replace_once(
    paths_file,
    '''def clear_write_helper(path: Path) -> None:\n''',
    '''def is_contained_file(root: Path, path: Path) -> bool:\n    """Return whether an existing file resolves inside ``root``."""\n    root = Path(root).resolve()\n    try:\n        target = Path(path).resolve()\n    except OSError:\n        return False\n    return target.is_file() and (target == root or root in target.parents)\n\n\ndef clear_write_helper(path: Path) -> None:\n''',
    "contained discovery helper",
)

module_data = Path("games/bannerlord/module_data.py")
replace_once(
    module_data,
    '''    for path in sorted(project.glob(pattern)):\n        if not path.is_file():\n            continue\n''',
    '''    for path in sorted(project.glob(pattern)):\n        if not paths.is_contained_file(project, path):\n            continue\n''',
    "source row containment",
)
replace_once(
    module_data,
    '''    submodule = project / "SubModule.xml"\n    rows.append(\n''',
    '''    submodule = project / "SubModule.xml"\n    submodule_available = paths.is_contained_file(project, submodule)\n    rows.append(\n''',
    "submodule discovery containment",
)
text = module_data.read_text(encoding="utf-8")
count = text.count("submodule.is_file()")
if count != 7:
    raise SystemExit(f"submodule availability replacement: expected seven matches, found {count}")
module_data.write_text(text.replace("submodule.is_file()", "submodule_available"), encoding="utf-8")
replace_once(
    module_data,
    '''    for index, path in enumerate(sorted(path for path in project.glob("*.csproj") if path.is_file())):\n''',
    '''    for index, path in enumerate(sorted(path for path in project.glob("*.csproj") if paths.is_contained_file(project, path))):\n''',
    "project discovery containment",
)
replace_once(
    module_data,
    '''        if not source.is_file():\n            continue\n''',
    '''        if not paths.is_contained_file(project, source):\n            continue\n''',
    "structured C# discovery containment",
)
replace_once(
    module_data,
    '''    if (project / "Design.txt").is_file():\n''',
    '''    if paths.is_contained_file(project, project / "Design.txt"):\n''',
    "design source discovery containment",
)

module_xml = Path("games/bannerlord/module_xml_data.py")
replace_once(
    module_xml,
    '''        if path.is_file()\n    ]\n''',
    '''        if paths.is_contained_file(project, path)\n    ]\n''',
    "ModuleData listing containment",
)

gauntlet = Path("games/bannerlord/gauntlet_data.py")
replace_once(
    gauntlet,
    '''from .paths import clear_write_helper, contained_project_path\n''',
    '''from .paths import clear_write_helper, contained_project_path, is_contained_file\n''',
    "Gauntlet containment import",
)
replace_once(
    gauntlet,
    '''        if path.is_file()\n    ]\n''',
    '''        if is_contained_file(project, path)\n    ]\n''',
    "Gauntlet listing containment",
)

server = Path("games/bannerlord/server.py")
replace_once(
    server,
    '''from .deploy_data import sync_project_assets\n''',
    '''from . import paths\nfrom .deploy_data import sync_project_assets\n''',
    "server paths import",
)
replace_once(
    server,
    '''        if path == "/api/module":\n            source = PROJECT / "SubModule.xml"\n            if not source.is_file():\n                self.send_json({"error": f"SubModule.xml not found: {source}"}, 404)\n                return\n            try:\n                self.send_json(read_submodule(source))\n            except Exception as error:\n                self.send_json({"error": str(error)}, 500)\n            return\n''',
    '''        if path == "/api/module":\n            try:\n                source = paths.contained_project_path(PROJECT, "SubModule.xml")\n                if not source.is_file():\n                    self.send_json({"error": f"SubModule.xml not found: {source}"}, 404)\n                    return\n                self.send_json(read_submodule(source))\n            except ValueError as error:\n                self.send_json({"error": str(error)}, 400)\n            except Exception as error:\n                self.send_json({"error": str(error)}, 500)\n            return\n''',
    "module GET containment",
)
replace_once(
    server,
    '''        if path == "/api/module/save":\n            source = PROJECT / "SubModule.xml"\n            if not source.is_file():\n                self.send_json({"error": f"SubModule.xml not found: {source}"}, 404)\n                return\n            try:\n                self.send_json(save_module(source, self.read_json()))\n            except (ValueError, TypeError, json.JSONDecodeError) as error:\n                self.send_json({"error": str(error)}, 400)\n            except Exception as error:\n                self.send_json({"error": str(error)}, 500)\n            return\n''',
    '''        if path == "/api/module/save":\n            try:\n                source = paths.contained_project_path(PROJECT, "SubModule.xml")\n                if not source.is_file():\n                    self.send_json({"error": f"SubModule.xml not found: {source}"}, 404)\n                    return\n                self.send_json(save_module(source, self.read_json()))\n            except (ValueError, TypeError, json.JSONDecodeError) as error:\n                self.send_json({"error": str(error)}, 400)\n            except Exception as error:\n                self.send_json({"error": str(error)}, 500)\n            return\n''',
    "module POST containment",
)

Path("tests/test_bannerlord_discovery_containment.py").write_text(r'''from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from games.bannerlord.gauntlet_data import list_prefabs
from games.bannerlord.module_data import data_map
from games.bannerlord.module_xml_data import list_documents


class BannerlordDiscoveryContainmentTests(unittest.TestCase):
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
''', encoding="utf-8")
