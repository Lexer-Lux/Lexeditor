from __future__ import annotations

import subprocess
import unittest
from unittest.mock import patch

from games.palworld.palserver_process import PalServerProcessError, require_stopped, running


class PalServerProcessTests(unittest.TestCase):
    @patch("games.palworld.palserver_process.os.name", "nt")
    @patch("games.palworld.palserver_process.subprocess.run")
    def test_detects_running_palserver(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, '"PalServer.exe","1234","Console"\n', "")
        self.assertTrue(running())
        with self.assertRaises(PalServerProcessError):
            require_stopped()

    @patch("games.palworld.palserver_process.os.name", "nt")
    @patch("games.palworld.palserver_process.subprocess.run")
    def test_no_matching_task_is_stopped(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, "INFO: No tasks are running which match the specified criteria.\n", "")
        self.assertFalse(running())
        require_stopped()

    @patch("games.palworld.palserver_process.os.name", "nt")
    @patch("games.palworld.palserver_process.subprocess.run")
    def test_tasklist_failure_fails_closed(self, run):
        run.return_value = subprocess.CompletedProcess([], 1, "", "failure")
        with self.assertRaises(PalServerProcessError):
            running()


if __name__ == "__main__":
    unittest.main()
