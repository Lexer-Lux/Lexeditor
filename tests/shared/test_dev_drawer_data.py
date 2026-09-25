"""The developer drawer shows the conversion debt it exists to show.

Its shared-UI and copied-line columns come from the two budget verifiers the
checks run. Those moved from tools/ to tests/shared/ with the rest of the
checks, and the drawer kept importing them from the old folder; the ImportError
was swallowed, so every game reported zero shared selectors and no copied
lines, and the shared-UI disclosure had nothing behind it to open.
"""
from pathlib import Path
import importlib.util
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core.desktop_host import _budget_counts  # noqa: E402


def load_verifier(name: str):
    path = ROOT / "tests" / "shared" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"drawer_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DeveloperDrawerDataTests(unittest.TestCase):
    def test_the_drawer_reads_each_budget_from_where_the_check_lives(self):
        for name in ("verify_shared_ui_budget", "verify_shared_code_budget"):
            with self.subTest(name):
                self.assertTrue((ROOT / "tests" / "shared" / f"{name}.py").is_file(),
                                f"{name} is not where the checks keep it")
                self.assertEqual(_budget_counts(name), load_verifier(name).counts())

    def test_a_verifier_that_is_not_there_reports_nothing_rather_than_guessing(self):
        self.assertEqual(_budget_counts("verify_no_such_budget"), {})

    def test_the_drawer_sees_debt_rather_than_zeroes(self):
        # An empty result means the drawer lost the verifier, not that the work
        # is finished - the duplicated-plugin check reports copies today. If the
        # repository really does reach zero, delete this test with the debt.
        self.assertTrue(_budget_counts("verify_shared_code_budget"),
                        "the drawer would report no copied lines for any game")
        # The shared-UI budget reached zero on 2026-09-25: every plugin
        # stylesheet is tokens only and no plugin builds a table, row or list by
        # hand, so that column reads zero because the debt is paid, not because
        # the drawer lost the verifier. The check that the verifier is still
        # where the drawer reads it is above this one.


if __name__ == "__main__":
    unittest.main()
