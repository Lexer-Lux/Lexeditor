"""Deterministic coverage of job-membership versus actual process-exit races."""
import ctypes
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from games.warband.game_launch import WindowsGameJob, _OwnedProcess


class ProcessAPI:
    def __init__(self):
        self.states = {11: 258, 22: 258}
        self.closed = []

    def QueryInformationJobObject(self, handle, information, buffer, size, returned):
        ctypes.memset(ctypes.addressof(buffer), 0, size)
        return True

    def WaitForSingleObject(self, handle, milliseconds):
        return self.states[handle]

    def GetExitCodeProcess(self, handle):
        return 1

    def CloseHandle(self, handle):
        self.closed.append(handle)


class ExitTrackingTests(unittest.TestCase):
    def make_job(self):
        api = ProcessAPI()
        job = WindowsGameJob.__new__(WindowsGameJob)
        job.handle = 99
        job.kernel = api
        job.process = _OwnedProcess(11, 101, api)
        job._tracked_processes = {101: job.process, 202: _OwnedProcess(22, 202, api)}
        job._job_pids = lambda: []  # Kernel job membership disappears first.
        self.addCleanup(job.close)
        return job, api

    def test_empty_job_does_not_mean_primary_or_child_has_finished(self):
        job, api = self.make_job()
        self.assertEqual(job.pids(), [101, 202])
        api.states[11] = 0
        self.assertEqual(job.pids(), [202])
        self.assertEqual(api.closed, [])
        api.states[22] = 0
        self.assertEqual(job.pids(), [])
        self.assertEqual(api.closed, [22])
        job.close()
        self.assertEqual(api.closed, [22, 99, 11])

    def test_wait_failure_is_not_reported_as_an_exit(self):
        job, api = self.make_job()
        api.states[11] = 0xFFFFFFFF
        with self.assertRaises(OSError):
            job.pids()
        self.assertIn(101, job._tracked_processes)
        with self.assertRaises(OSError):
            job.process.wait(timeout=1)

    def test_wait_timeout_preserves_handle_and_exit_state(self):
        job, api = self.make_job()
        with self.assertRaises(subprocess.TimeoutExpired):
            job.process.wait(timeout=0)
        self.assertIsNone(job.process.returncode)
        api.states[11] = 0
        self.assertEqual(job.process.wait(timeout=1), 1)
        self.assertEqual(api.closed, [])


@unittest.skipUnless(os.name == "nt", "requires real Windows process handles")
class WindowsExitTests(unittest.TestCase):
    def test_stop_releases_working_directory_repeatedly(self):
        for attempt in range(12):
            with self.subTest(attempt=attempt), tempfile.TemporaryDirectory() as name:
                cwd = Path(name) / "working"
                cwd.mkdir()
                marker = Path(name) / "ready"
                script = "import pathlib,sys,time;pathlib.Path(sys.argv[1]).touch();time.sleep(30)"
                job = WindowsGameJob([sys.executable, "-c", script, str(marker)], cwd)
                try:
                    deadline = time.monotonic() + 5
                    while not marker.exists() and time.monotonic() < deadline:
                        time.sleep(.01)
                    self.assertTrue(marker.exists(), "fixture process did not initialize")
                    self.assertTrue(job.pids())
                    job.terminate()
                    deadline = time.monotonic() + 5
                    while job.pids() and time.monotonic() < deadline:
                        time.sleep(.01)
                    self.assertEqual(job.pids(), [])
                    # No retry/ignore_errors: a false exit report leaves this locked.
                    cwd.rmdir()
                finally:
                    job.terminate()
                    if job.process and job.process._handle:
                        job.process.wait(timeout=5)
                    job.close()


if __name__ == '__main__':
    unittest.main()
