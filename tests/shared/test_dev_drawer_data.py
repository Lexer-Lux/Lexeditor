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

    def test_the_copied_line_verifier_still_detects_a_copy(self):
        """The column reads zero today, and zero must mean "none", not "blind".

        Both copied-code budgets reached zero on 2026-09-25, so a test that
        required the repository to be in debt would now be a test of the debt.
        This gives the verifier a tree of its own - two plugins holding one
        function written twice - and requires it to name the copy.
        """
        import tempfile

        verifier = load_verifier("verify_shared_code_budget")
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            for plugin in ("alpha", "beta"):
                target = root / "plugins" / plugin / "server.py"
                target.parent.mkdir(parents=True)
                target.write_text(
                    "def send(payload, destination):\n"
                    "    data = payload.encode('utf-8')\n"
                    "    destination.write(data)\n"
                    "    destination.flush()\n"
                    "    total = len(data)\n"
                    "    destination.write(b'')\n"
                    "    return total\n",
                    encoding="utf-8")
            original = verifier.ROOT
            verifier.ROOT = root
            try:
                counts = verifier.counts()
            finally:
                verifier.ROOT = original
        self.assertEqual(counts, {"beta": 6}, counts)


if __name__ == "__main__":
    unittest.main()
