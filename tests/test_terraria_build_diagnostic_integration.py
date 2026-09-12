from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from games.terraria import server


class TerrariaBuildDiagnosticIntegrationTests(unittest.TestCase):
    def test_native_build_returns_structured_project_diagnostics(self):
        previous_project = os.environ.get("LEXEDITOR_TERRARIA_PROJECT")
        previous_install = os.environ.get("LEXEDITOR_TERRARIA_ROOT")
        previous_save_root = server.TMODLOADER_SAVE_ROOT
        try:
            with tempfile.TemporaryDirectory() as directory:
                base = Path(directory)
                install = base / "tModLoader"
                launch = install / "LaunchUtils"
                launch.mkdir(parents=True)
                (install / "tModLoader.dll").write_bytes(b"")
                (launch / "busybox64.exe").write_bytes(b"")
                (launch / "ScriptCaller.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")

                project = base / "Save" / "ModSources" / "ExampleMod"
                source = project / "Content" / "Items" / "BrokenItem.cs"
                source.parent.mkdir(parents=True)
                source.write_text("public class BrokenItem {}\n", encoding="utf-8")
                (project / "build.txt").write_text("displayName = Example\n", encoding="utf-8")
                (project / "ExampleMod.csproj").write_text("<Project />\n", encoding="utf-8")

                save_root = base / "Save"
                os.environ["LEXEDITOR_TERRARIA_PROJECT"] = str(project)
                os.environ["LEXEDITOR_TERRARIA_ROOT"] = str(install)
                server.TMODLOADER_SAVE_ROOT = save_root

                def fake_run(command, **_kwargs):
                    output = f"{source}(7,9): error CS0103: The name 'Nope' does not exist in the current context\n"
                    return subprocess.CompletedProcess(command, 1, stdout=output, stderr="")

                result = server.build_project(run_command=fake_run, platform_name="nt")
                self.assertFalse(result["ok"])
                self.assertEqual(result["exitCode"], 1)
                self.assertEqual(len(result["diagnostics"]), 1)
                diagnostic = result["diagnostics"][0]
                self.assertEqual(diagnostic["path"], "Content/Items/BrokenItem.cs")
                self.assertTrue(diagnostic["projectFile"])
                self.assertEqual((diagnostic["line"], diagnostic["column"]), (7, 9))
                self.assertEqual(diagnostic["code"], "CS0103")
        finally:
            server.TMODLOADER_SAVE_ROOT = previous_save_root
            if previous_project is None:
                os.environ.pop("LEXEDITOR_TERRARIA_PROJECT", None)
            else:
                os.environ["LEXEDITOR_TERRARIA_PROJECT"] = previous_project
            if previous_install is None:
                os.environ.pop("LEXEDITOR_TERRARIA_ROOT", None)
            else:
                os.environ["LEXEDITOR_TERRARIA_ROOT"] = previous_install


if __name__ == "__main__":
    unittest.main()
