"""Development waste must never enter an end-user resource package."""
from pathlib import Path
import tempfile
import unittest

from tools.build_distribution import resource_files


class DistributionHygieneTests(unittest.TestCase):
    def test_resources_exclude_builds_profiles_and_dependency_trees(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            expected = ['ui/framework.js', 'games/blank/editor.html', 'assets/icon.png']
            discarded = ['_scratch/huge-build/source.cpp', '.venv/module.py',
                         'games/blank/_scratch/profile.json', 'games/blank/vcpkg/source.py',
                         'games/blank/.build/generated.json', 'games/blank/build/generated.py',
                         'games/blank/__pycache__/module.py', 'ui/node_modules/library.js',
                         'games/ff8/ffnx_driver/source.py', 'games/blank/game-data/private.json']
            for relative in expected + discarded:
                path = root / relative; path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('fixture', encoding='utf-8')
            self.assertEqual({str(path.relative_to(root).as_posix()) for path in resource_files(root)}, set(expected))


if __name__ == '__main__':
    unittest.main()
