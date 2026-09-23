import unittest

from games.bannerlord.plugin import PLUGIN, smoke


class BannerlordSmokeTests(unittest.TestCase):
    def test_plugin_exposes_and_passes_isolated_service_smoke(self):
        self.assertIs(PLUGIN.smoke, smoke)
        checks = smoke()
        self.assertGreaterEqual(len(checks), 6)
        self.assertTrue(any("selected project/game roots" in line for line in checks))
        self.assertTrue(any("child service stopped cleanly" in line for line in checks))


if __name__ == "__main__":
    unittest.main()
