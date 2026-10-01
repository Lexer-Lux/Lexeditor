"""Loopback item editor; installed data is never a write destination."""
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import threading
from urllib.parse import parse_qs, urlparse

from core.plugin_http import PluginRequestHandler
from .formats import FormatError
from .store import ItemStore

ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = Path(__file__).resolve().parent
LOCK = threading.RLock()
STORE = ItemStore(os.environ.get('LEXEDITOR_DS1_ROOT', r'C:\Program Files (x86)\Steam\steamapps\common\DARK SOULS REMASTERED'),
                  None if os.environ.get('LEXEDITOR_NO_MOD') == '1' else os.environ.get('LEXEDITOR_DS1_PROJECT'),
                  os.environ.get('LEXEDITOR_MOD_READ_ONLY') == '1' or os.environ.get('LEXEDITOR_NO_MOD') == '1'
                  or not os.environ.get('LEXEDITOR_DS1_PROJECT'))


class Handler(PluginRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        if path in ('/api/state', '/api/table', '/api/row'):
            try:
                with LOCK:
                    if path == '/api/state':
                        result = STORE.state()
                    elif path == '/api/table':
                        result = {'rows': STORE.get().list_rows(query.get('tab', [''])[0]), 'dirtyCount': STORE.get().dirty_count}
                    else:
                        result = {'row': STORE.get().read_row(query.get('table', [''])[0], int(query.get('id', [''])[0])), 'dirtyCount': STORE.get().dirty_count}
                    self.send_json(result)
            except (FormatError, ValueError, OSError, KeyError, UnicodeError) as error:
                self.send_json({'error': str(error)}, 400)
            return
        if path == "/":
            self.send_file(PLUGIN_ROOT / "editor.html")
        elif path == "/api/plugin":
            self.send_json({"apiVersion": 1, "pluginId": "ds1",
                            "name": "Dark Souls Remastered", "hosted": True,
                            "capabilities": ["items", "project-export", "byte-preserving-roundtrip"]})
        elif self.send_page_module(PLUGIN_ROOT, path):
            return
        elif path.startswith("/shared/"):
            shared = (ROOT / "ui").resolve()
            target = (shared / path.removeprefix("/shared/")).resolve()
            if shared in target.parents and target.is_file():
                self.send_file(target)
            elif path == '/shared/distribution-notices.json':
                self.send_json([])
            else:
                self.send_json({"error": "Not found"}, 404)
        else:
            self.send_json({"error": "Not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            if path not in ('/api/edit', '/api/save', '/api/discard'):
                self.send_json({'error': 'Not found'}, 404)
                return
            origin = self.headers.get('Origin')
            if origin and origin != f"http://{self.headers.get('Host')}":
                raise PermissionError('Cross-origin writes are not permitted')
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 65536:
                raise ValueError('Invalid request size')
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict): raise ValueError('Expected an object')
            with LOCK:
                if path == '/api/edit':
                    row = STORE.edit(payload.get('table'), payload.get('id'), payload.get('field'), payload.get('value'))
                    result = {'row': row, 'dirtyCount': STORE.get().dirty_count}
                elif path == '/api/save':
                    result = STORE.save()
                else:
                    result = STORE.discard()
                self.send_json(result)
        except PermissionError as error:
            self.send_json({'error': str(error)}, 403)
        except (FormatError, ValueError, OSError, KeyError, TypeError) as error:
            self.send_json({'error': str(error)}, 400)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", int(os.environ.get("LEXEDITOR_PORT", "0"))), Handler).serve_forever()
