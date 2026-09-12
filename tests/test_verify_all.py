"""Exercise verifier failure, timeout, log retention and selection behavior."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools import verify_all


class RunnerTests(unittest.TestCase):
    def test_noisy_check_cannot_fill_the_drive(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); script = root / 'verify_noisy.py'
            script.write_text("print('x' * 50000, flush=True)", encoding='utf-8')
            code, tail, context = verify_all._once(script, 10, root, max_log_bytes=1024)
            self.assertEqual(code, 125)
            self.assertIn('OUTPUT LIMIT', tail)
            self.assertIn('OUTPUT LIMIT', context)
            self.assertLess((root / 'verify_noisy.attempt-1.log').stat().st_size, 1200)

    def test_legacy_console_encoding_cannot_drop_the_report(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); (root / 'tools').mkdir()
            (root / 'tools/verify_unicode.py').write_text("print('\\u2139 complete')", encoding='utf-8')
            code = "from tools import verify_all as v; from pathlib import Path; import sys; v.ROOT=Path(sys.argv.pop(1)); sys.exit(v.main())"
            result = subprocess.run([sys.executable, '-c', code, str(root), '--jobs', '1', '--retries', '0'],
                                    cwd=verify_all.ROOT, env=dict(os.environ, PYTHONIOENCODING='ascii'),
                                    capture_output=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('\u2139 complete', result.stdout.decode('utf-8'))
            self.assertTrue((root / '_scratch/verify-results/report.json').is_file())

    def test_failure_retains_full_utf8_output(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            script = root / "verify_failure.py"
            script.write_text("print('first line \\u2713'); print('last line'); raise SystemExit(7)", encoding="utf-8")
            code, tail, context = verify_all._once(script, 10, root)
            self.assertEqual(code, 7)
            self.assertEqual(tail, "last line")
            # The tail is one line; the context carries the lines above it,
            # which is the whole reason it exists.
            self.assertIn("first line \u2713", context)
            self.assertIn("first line \u2713", (root / "verify_failure.attempt-1.log").read_text(encoding="utf-8"))

    def test_timeout_is_bounded_and_reported(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            script = root / "verify_hang.py"
            script.write_text("import time; print('started', flush=True); time.sleep(60)", encoding="utf-8")
            code, tail, context = verify_all._once(script, .5, root)
            self.assertEqual(code, 124)
            self.assertIn("TIMEOUT", tail)
            self.assertIn("started", context)
            self.assertIn("started", (root / "verify_hang.attempt-1.log").read_text(encoding="utf-8"))

    def test_retry_is_visible_and_timeout_is_not_retried(self):
        with patch.object(verify_all, "_once",
                          side_effect=[(1, "failed", "failed"), (0, "ok", "ok")]), \
             patch.object(verify_all.time, "sleep"):
            self.assertIn("FLAKY", verify_all.run(Path("fixture.py"))[3])
        with patch.object(verify_all, "_once",
                          return_value=(124, "TIMEOUT", "TIMEOUT")) as once:
            self.assertEqual(verify_all.run(Path("fixture.py"))[1], 124)
            once.assert_called_once()

    def test_a_check_that_cannot_run_here_is_skipped_not_failed(self):
        # The reason a verifier could not run is often not on the last line: a
        # shell puts the missing name on one line and "operable program or
        # batch file" on the next. Reading only the tail called that a failure.
        tail = "operable program or batch file."
        context = ("'wibble' is not recognized as an internal or external "
                   "command,\noperable program or batch file.")
        with patch.object(verify_all, "_once", return_value=(1, tail, context)) as once:
            _tool, code, _seconds, report = verify_all.run(Path("fixture.py"))
        self.assertEqual(code, 0)
        self.assertIn("SKIPPED", report)
        self.assertIn("not installed", report)
        once.assert_called_once()

    def test_list_excludes_self_and_active_plugin_patterns(self):
        result = subprocess.run([sys.executable, str(Path(verify_all.__file__)), "--list", "--exclude", "ff7"],
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("verify_all.py", result.stdout)
        self.assertNotIn("ff7", result.stdout)
        self.assertIn("verify_frontend_syntax.py", result.stdout)


if __name__ == "__main__":
    unittest.main()
