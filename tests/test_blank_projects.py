"""Blank samples survive service ports and reject failed writes without losing data."""
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
from games.blank import server


class BlankProjectsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='lexeditor-blank-projects-')
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'samples.json'
        self.patch = patch.object(server, 'PROJECTS_PATH', self.path)
        self.patch.start(); self.addCleanup(self.patch.stop)
        self.http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        threading.Thread(target=self.http.serve_forever, daemon=True).start()
        self.addCleanup(self.http.server_close); self.addCleanup(self.http.shutdown)
        self.url = f'http://127.0.0.1:{self.http.server_port}/api/projects'
        self.value = {'current': 'Sample', 'projects': {'Sample': {'rows': [], 'demo': {'value': 103}}}}

    def write(self, value, **headers):
        with urlopen(Request(self.url, json.dumps(value).encode(), {'Content-Type': 'application/json', **headers})) as response:
            return json.load(response)

    def test_round_trip_and_invalid_write_preserves_file(self):
        self.assertEqual(self.write(self.value), {'saved': True})
        original = self.path.read_bytes()
        with self.assertRaises(HTTPError): self.write({'current': 'missing', 'projects': {}})
        self.assertEqual(self.path.read_bytes(), original)
        with urlopen(self.url) as response: self.assertEqual(json.load(response), self.value)

    def test_atomic_write_failure_preserves_data_and_removes_temporary(self):
        self.write(self.value); original = self.path.read_bytes()
        with patch.object(server.os, 'replace', side_effect=OSError('disk full')):
            with self.assertRaises(HTTPError): self.write(self.value)
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_cross_origin_and_size_limit(self):
        with self.assertRaises(HTTPError) as caught: self.write(self.value, Origin='https://other.example')
        self.assertEqual(caught.exception.code, 403)
        # Exercise the real size check with a small body. A multi-megabyte send
        # can race the server's early rejection and produce a socket error.
        with patch.object(server, 'MAX_PROJECT_BYTES', 64):
            with self.assertRaises(HTTPError) as caught:
                self.write({'projects': {}, 'padding': 'x' * 65})
            self.assertEqual(caught.exception.code, 400)
            self.assertIn('storage limit', json.load(caught.exception)['error'])
        self.assertFalse(self.path.exists())

    def test_corrupt_data_is_reported_without_overwrite(self):
        self.path.write_text('invalid')
        with self.assertRaises(HTTPError): urlopen(self.url)
        self.assertEqual(self.path.read_text(), 'invalid')


if __name__ == '__main__': unittest.main()
