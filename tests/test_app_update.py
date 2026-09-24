import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from core import app_update as update
from core.desktop_host import HostApi


class ReleaseUpdateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="lexeditor-update-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        update.git(self.root, "init")
        update.git(self.root, "config", "user.name", "Fixture")
        update.git(self.root, "config", "user.email", "fixture@example.invalid")
        (self.root / "requirements.txt").write_text("")
        (self.root / "app.py").write_text("print('ready')")
        (self.root / ".gitignore").write_text("projects/\n")
        self.old = self.commit("old")
        (self.root / "new.txt").write_text("release")
        self.new = self.commit("new")
        update.git(self.root, "tag", "v9.0")
        update.git(self.root, "checkout", "-b", "installed", self.old)

    def commit(self, message):
        update.git(self.root, "add", ".")
        update.git(self.root, "commit", "-m", message)
        return update.git(self.root, "rev-parse", "HEAD")

    def check(self):
        return update.check(self.root, release={"tag": "v9.0"}, repository=str(self.root))

    def test_latest_release_install_and_ignored_project_preservation(self):
        self.assertTrue(self.check()["available"])
        project = self.root / "projects" / "mine.txt"
        project.parent.mkdir()
        project.write_bytes(b"my mod")
        backup = update.apply_update(self.root, self.old, self.new, sys.executable)
        self.assertEqual(update.git(self.root, "rev-parse", "HEAD"), self.new)
        self.assertEqual(update.git(self.root, "rev-parse", backup), self.old)
        self.assertEqual(project.read_bytes(), b"my mod")
        self.assertEqual(self.check()["status"], "current")

    def test_dirty_install_is_refused(self):
        (self.root / "app.py").write_text("my edits")
        self.assertEqual(self.check()["status"], "modified")
        with self.assertRaisesRegex(RuntimeError, "changed"):
            update.apply_update(self.root, self.old, self.new, sys.executable)
        self.assertEqual((self.root / "app.py").read_text(), "my edits")

    def test_newer_install_is_not_downgraded(self):
        update.git(self.root, "merge", "--ff-only", self.new)
        (self.root / "local.txt").write_text("newer")
        self.commit("ahead")
        self.assertEqual(self.check()["status"], "ahead")

    def test_failed_startup_restores_previous_source(self):
        update.git(self.root, "checkout", "-b", "bad", self.new)
        (self.root / "app.py").write_text("raise RuntimeError('bad release')")
        bad = self.commit("bad")
        update.git(self.root, "checkout", "installed")
        with self.assertRaisesRegex(RuntimeError, "bad release"):
            update.apply_update(self.root, self.old, bad, sys.executable)
        self.assertEqual(update.git(self.root, "rev-parse", "HEAD"), self.old)
        self.assertFalse((self.root / "new.txt").exists())

    def test_unsaved_editor_blocks_preparation(self):
        import threading
        host = HostApi.__new__(HostApi)
        host._lock = threading.RLock()
        host._dirty_count = 1
        with patch.object(update, "prepare") as prepare:
            with self.assertRaisesRegex(RuntimeError, "Save or discard"):
                host.install_app_update()
            prepare.assert_not_called()

    def test_worker_waits_updates_and_relaunches(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-worker-test-") as tmp:
            job = Path(tmp) / "job"
            job.mkdir()
            plan = job / "plan.json"
            plan.write_text(json.dumps({"root": str(self.root), "current": self.old,
                "target": self.new, "python": sys.executable, "parent": 123, "tag": "v9.0"}))
            def stopped(pid):
                self.assertEqual(pid, 123)
                self.assertEqual(update.git(self.root, "rev-parse", "HEAD"), self.old)
            with patch.object(update, "wait_for_parent", side_effect=stopped) as wait, \
                 patch.object(update.subprocess, "Popen", wraps=update.subprocess.Popen) as process:
                # Patch only the final GUI launch. Git and the startup probe
                # still run as real child processes against the temporary repo.
                original = process._mock_wraps
                def launch(args, **kwargs):
                    if args == [sys.executable, str(self.root / "app.py")] and "capture_output" not in kwargs and "stdout" not in kwargs:
                        return Mock()
                    return original(args, **kwargs)
                process.side_effect = launch
                update.worker(plan)
            wait.assert_called_once()
            self.assertEqual(update.git(self.root, "rev-parse", "HEAD"), self.new)
            self.assertTrue(json.loads((Path(tmp) / "last-result.json").read_text())["success"])

    def test_worker_does_not_replace_files_if_host_stays_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = Path(tmp) / "job"
            job.mkdir()
            plan = job / "plan.json"
            plan.write_text(json.dumps({"root": str(self.root), "parent": 123}))
            with patch.object(update, "wait_for_parent", side_effect=RuntimeError("still open")), \
                 patch.object(update, "apply_update") as apply, patch.object(update.subprocess, "Popen") as launch:
                update.worker(plan)
            apply.assert_not_called()
            launch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
