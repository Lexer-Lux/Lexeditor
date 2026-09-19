from __future__ import annotations

from pathlib import Path
import unittest

from tools.build_distribution import resource_files


ROOT = Path(__file__).resolve().parents[1]


class ProjectZomboidDistributionTests(unittest.TestCase):
    def test_build42_mod_info_template_is_packaged(self):
        resources = {path.relative_to(ROOT).as_posix() for path in resource_files(ROOT)}
        self.assertIn("games/project_zomboid/template/42/mod.info", resources)


if __name__ == "__main__":
    unittest.main()
