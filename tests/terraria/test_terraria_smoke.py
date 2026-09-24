from __future__ import annotations

import unittest

from plugins.terraria.plugin import smoke


class TerrariaSmokeTests(unittest.TestCase):
    def test_smoke_is_isolated_and_completes(self):
        messages = smoke()
        self.assertEqual(len(messages), 2)
        self.assertIn("temporary project", messages[0])
        self.assertIn("untouched", messages[1])


if __name__ == "__main__":
    unittest.main()
