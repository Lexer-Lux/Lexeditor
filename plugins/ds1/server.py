"""Loopback parameter editor; only explicit deployment writes installed data."""
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import threading
from urllib.parse import parse_qs, urlparse

from core.plugin_http import PluginRequestHandler
from . import deployment, data_map
from .formats import FormatError
from .store import ItemStore
from .stamina_rebalance import StaminaRebalance

ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = Path(__file__).resolve().parent
LOCK = threading.RLock()
STORE = ItemStore(os.environ.get('LEXEDITOR_DS1_ROOT', r'C:\Program Files (x86)\Steam\steamapps\common\DARK SOULS REMASTERED'),
                  None if os.environ.get('LEXEDITOR_NO_MOD') == '1' else os.environ.get('LEXEDITOR_DS1_PROJECT'),
                  os.environ.get('LEXEDITOR_MOD_READ_ONLY') == '1' or os.environ.get('LEXEDITOR_NO_MOD') == '1'
                  or not os.environ.get('LEXEDITOR_DS1_PROJECT'))
RULES = StaminaRebalance(STORE.game_root, STORE.project, STORE.read_only)
NATIVE_TABS = {"encumbrance", "misc", "tweaks"}


class Handler(PluginRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        if path in ('/api/state', '/api/table', '/api/row', '/api/attacks', '/api/data-map'):
            try:
                with LOCK:
                    if path == '/api/state':
                        result = STORE.state()
                        result['nativeRules'] = RULES.snapshot()
                    elif path == '/api/data-map':
                        result = data_map.build(STORE.get(), STORE.source, RULES.snapshot(refresh=True))
                    elif path == '/api/attacks':
                        result = STORE.get().attack_references().list(int(query.get('monster', [''])[0]), query.get('all', ['0'])[0] == '1')
                        result['dirtyCount'] = STORE.get().dirty_count
                    elif path == '/api/table':
                        tab = query.get('tab', [''])[0]
                        result = {'rows': RULES.list_rows(tab) if tab in NATIVE_TABS else STORE.get().list_rows(tab)}
                    else:
                        table, row_id = query.get('table', [''])[0], int(query.get('id', [''])[0])
                        row = RULES.read_row(row_id) if table == 'NativeRules' else STORE.get().read_row(table, row_id)
                        result = {'row': RULES.describe_row(row, STORE.get())}
                    result['dirtyCount'] = STORE.get().dirty_count + RULES.dirty_count
                    self.send_json(result)
            except (FormatError, RuntimeError, ValueError, OSError, KeyError, UnicodeError) as error:
                self.send_json({'error': str(error)}, 400)
            return
        if path == '/api/deployment':
            try:
                with LOCK:
                    self.send_json(RULES.deployment_status())
            except (RuntimeError, ValueError, OSError, KeyError) as error:
                self.send_json({'error': str(error)}, 400)
            return
        if path == "/":
            self.send_file(PLUGIN_ROOT / "editor.html")
        elif path == "/api/plugin":
            self.send_json({"apiVersion": 1, "pluginId": "ds1",
                            "name": "Dark Souls Remastered", "hosted": True,
                            "capabilities": ["items", "monster-resistances", "enemy-attacks", "effects", "encumbrance", "native-stamina", "project-export", "byte-preserving-roundtrip", "mod-deployment"]})
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
                self.send_json({'error': 'Not found'}, 404)
        else:
            self.send_json({'error': 'Not found'}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            if path not in ('/api/edit', '/api/save', '/api/discard', '/api/deployment/apply', '/api/deployment/disable'):
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
                    if payload.get('table') == 'NativeRules':
                        row = RULES.edit_row(payload.get('id'), payload.get('field'), payload.get('value'))
                    else:
                        row = STORE.edit(payload.get('table'), payload.get('id'), payload.get('field'), payload.get('value'))
                        row = RULES.describe_row(row, STORE.get())
                    result = {'row': row, 'dirtyCount': STORE.get().dirty_count}
                elif path == '/api/save':
                    RULES.validate_save()
                    STORE.validate_save()
                    result = STORE.save()
                    RULES.save()
                elif path == '/api/discard':
                    result = STORE.discard()
                    RULES.discard()
                elif path == '/api/deployment/apply':
                    result = RULES.apply(STORE)
                else:
                    result = RULES.restore()
                result['dirtyCount'] = STORE.get().dirty_count + RULES.dirty_count
                result['nativeRules'] = RULES.snapshot()
                self.send_json(result)
        except PermissionError as error:
            self.send_json({'error': str(error)}, 403)
        except (FormatError, RuntimeError, ValueError, OSError, KeyError, TypeError) as error:
            self.send_json({'error': str(error)}, 400)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", int(os.environ.get("LEXEDITOR_PORT", "0"))), Handler).serve_forever()
