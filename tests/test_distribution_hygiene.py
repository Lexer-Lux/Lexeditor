"""Development waste must never enter an end-user resource package."""
from pathlib import Path
import tempfile
import unittest

from tools.build_distribution import resource_files


class DistributionHygieneTests(unittest.TestCase):
    def test_resources_exclude_builds_profiles_and_dependency_trees(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            expected = ['ui/framework.js', 'plugins/blank/editor.html', 'assets/icon.png']
            discarded = ['_scratch/huge-build/source.cpp', '.venv/module.py',
                         'plugins/blank/_scratch/profile.json', 'plugins/blank/vcpkg/source.py',
                         'plugins/blank/.build/generated.json', 'plugins/blank/build/generated.py',
                         'plugins/blank/__pycache__/module.py', 'ui/node_modules/library.js',
                         'plugins/ff8/ffnx_driver/source.py', 'plugins/blank/game-data/private.json']
            for relative in expected + discarded:
                path = root / relative; path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('fixture', encoding='utf-8')
            self.assertEqual({str(path.relative_to(root).as_posix()) for path in resource_files(root)}, set(expected))

    def test_bundled_helpers_ship_and_are_the_pinned_files(self):
        """A vendored helper that is not in the installer is not vendored."""
        import hashlib
        import reshade_projects
        from plugins.ff7r2 import shader_injector
        from tools.build_distribution import VENDORED_HELPERS

        root = Path(__file__).resolve().parents[1]
        for relative in VENDORED_HELPERS:
            self.assertTrue((root / relative).is_file(), relative)
        pinned = {f"tools/reshade/{reshade_projects.PINNED_LOADER}/{name}": reshade_projects.PINNED_SETUP_SHA256[variant]
                  for variant, name in reshade_projects.VENDORED_SETUPS.items()}
        pinned[shader_injector.ARCHIVE.relative_to(root).as_posix()] = shader_injector.ARCHIVE_SHA256
        for relative, digest in pinned.items():
            self.assertIn(relative, VENDORED_HELPERS)
            self.assertEqual(hashlib.sha256((root / relative).read_bytes()).hexdigest(), digest, relative)
        # The resource walk alone would leave them out, which is why they are listed.
        walked = {path.relative_to(root).as_posix() for path in resource_files(root)}
        for relative in VENDORED_HELPERS:
            if relative.endswith((".exe", ".zip")):
                self.assertNotIn(relative, walked)


if __name__ == '__main__':
    unittest.main()
