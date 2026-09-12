from __future__ import annotations

import sys
import unittest

import runtime_bootstrap


class ChronoTriggerRuntimeBootstrapTests(unittest.TestCase):
    def test_chrono_trigger_service_is_explicitly_allowed(self):
        module = "games.chrono_trigger.server"
        self.assertIn(module, runtime_bootstrap.SERVICE_MODULES)
        self.assertEqual(runtime_bootstrap.service_command(module), [sys.executable, "-m", module])

    def test_unregistered_service_still_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "Unsupported plugin service"):
            runtime_bootstrap.service_command("games.chrono_trigger.not_a_service")


if __name__ == "__main__":
    unittest.main()
