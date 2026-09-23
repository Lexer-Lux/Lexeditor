from __future__ import annotations

from pathlib import Path
import unittest

from tools.build_distribution import resource_files


ROOT = Path(__file__).resolve().parents[1]


class ProjectZomboidDistributionTests(unittest.TestCase):
    def test_project_zomboid_editor_and_template_are_packaged(self):
        resources = {path.relative_to(ROOT).as_posix() for path in resource_files(ROOT)}
        for relative in (
            "plugins/project_zomboid/editor.html",
            "plugins/project_zomboid/editor.js",
            "plugins/project_zomboid/editor.css",
            "plugins/project_zomboid/template/42/mod.info",
        ):
            with self.subTest(relative=relative):
                self.assertIn(relative, resources)


if __name__ == "__main__":
    unittest.main()
