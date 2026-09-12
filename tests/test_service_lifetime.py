"""Real child services: normal stop, restart and abrupt host death."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from service_session import LocalPluginSession

ROOT = Path(__file__).resolve().parents[1]


def session():
    return LocalPluginSession(module='games.blank.server', plugin_id='blank',
                              app_root=ROOT, check=lambda: [])


class ServiceLifetimeTests(unittest.TestCase):
    @unittest.skipUnless(os.name == 'nt', 'Windows GUI interpreter')
    def test_pythonw_service_stops_without_console_stream_objects(self):
        import service_session
        original = service_session.service_command
        def command(module, **kwargs):
            result = original(module, **kwargs)
            result[0] = str(Path(result[0]).with_name('pythonw.exe'))
            return result
        child = session()
        try:
            with patch.object(service_session, 'service_command', side_effect=command):
                child.start()
            child.stop()
            self.assertTrue(child.wait_closed())
        finally:
            child.stop()

    def test_normal_stop_closes_port_and_allows_restart(self):
        child = session()
        try:
            for _ in range(2):
                self.assertEqual(child.start()['pluginId'], 'blank')
                with self.assertRaisesRegex(RuntimeError, 'already running'):
                    child.start()
                child.stop()
                self.assertTrue(child.wait_closed(), 'Service survived stop')
        finally:
            child.stop()

    def test_service_exits_when_host_is_killed(self):
        code = '''
import json,os,time
from pathlib import Path
from service_session import LocalPluginSession
s=LocalPluginSession(module='games.blank.server',plugin_id='blank',app_root=Path.cwd(),check=lambda:[])
s.start()
print(json.dumps({'pid':os.getpid(),'port':s.port}),flush=True)
time.sleep(120)
'''
        host = subprocess.Popen([sys.executable, '-c', code], cwd=ROOT,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        try:
            import socket
            line = host.stdout.readline()
            self.assertTrue(line, host.stderr.read() if host.poll() is not None else 'No host handshake')
            state = json.loads(line)
            # The Windows venv launcher can have a separate interpreter child.
            os.kill(state['pid'], signal.SIGTERM)
            host.wait(timeout=10)
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                with socket.socket() as probe:
                    probe.settimeout(.2)
                    if probe.connect_ex(('127.0.0.1', state['port'])) != 0:
                        break
                time.sleep(.05)
            else:
                self.fail('Service survived the host process')
        finally:
            if host.poll() is None:
                host.kill(); host.wait(timeout=10)
            host.stdout.close(); host.stderr.close()


if __name__ == '__main__':
    unittest.main()
