"""Source guards for the issue-201 child-vulnerability boundary (no game).

Issue 201 stays safe-disabled on purpose: the only resolved mechanism
intercepts process-wide predicates that also own shop, station, and paperboy
interactions, so installing it would regress normal play. A safe
entity-local mechanism still needs research. These tests lock the boundary
into the source: the module states safe-disabled, installs no hook, performs
no entity write, keeps only diagnostic logging, and stays wired into the
script entry points so the boundary is reviewed rather than silently dropped.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "plugins" / "rdr2" / "native_runtime" / "GameplayTweaks"
MODULE = RUNTIME / "modules" / "child_vulnerability.cpp"


class ChildSafetyBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = MODULE.read_text(encoding="utf-8")
        cls.script = (RUNTIME / "script.cpp").read_text(encoding="utf-8")

    def test_module_states_safe_disabled(self):
        self.assertIn("safe-disabled", self.source)
        self.assertIn("install no hook", self.source)
        self.assertIn("no-resolved-entity-local-mechanism", self.source)

    def test_module_installs_no_hook(self):
        calls = re.findall(
            r"\b\w*(?:[Hh]ook|[Rr]egister\w*|[Ss]ubscribe\w*)\s*\(", self.source)
        self.assertEqual(calls, [])

    def test_module_performs_no_entity_write(self):
        writes = re.findall(r"\b(?:PED|ENTITY|PLAYER|WEAPON)::\w+", self.source)
        self.assertEqual(writes, [])

    def test_module_only_logs(self):
        self.assertIn('gtLog("child-vuln"', self.source)

    def test_entry_points_stay_defined_and_init_wired(self):
        self.assertIn("initializeChildVulnerability", self.script)
        self.assertIn("updateChildVulnerability", self.source)
        self.assertIn("initializeChildVulnerability", self.source)


if __name__ == "__main__":
    unittest.main()
