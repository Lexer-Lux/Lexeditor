from __future__ import annotations

import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.request import urlopen

from games.chrono_trigger.data import OverlayStore
from games.chrono_trigger.plugin import _build_smoke_archive, _field_event
import games.chrono_trigger.server as server


class EventAuditServerTests(unittest.TestCase):
    def test_loopback_api_exposes_read_only_event_audit(self):
        with tempfile.TemporaryDirectory(prefix="chrono-event-audit-server-") as temp_name:
            root = Path(temp_name)
            game = root / "game"
            project = root / "project"
            game.mkdir()
            _build_smoke_archive(game / "resources.bin", [
                ("Game/field/atel/Atel_0001.dat", _field_event(bytes((0x82, 0x04, 0x00)))),
                ("Game/field/atel/Atel_0002.dat", _field_event(bytes((0x8E, 0x80, 0x00)))),
            ])
            store = OverlayStore(game / "resources.bin", project)

            original_store = server._store
            server._store = lambda: store
            httpd = server.create_server(0)
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{httpd.server_address[1]}"
                with urlopen(base + "/api/plugin", timeout=5) as response:
                    plugin = json.load(response)
                self.assertIn("field-event-audit", plugin["capabilities"])

                with urlopen(base + "/api/event-audit?source=mine&event=2", timeout=5) as response:
                    audit = json.load(response)
                self.assertEqual(audit["kind"], "chrono-trigger-event-audit")
                self.assertEqual(audit["eventId"], 2)
                self.assertEqual(audit["scanSource"], "mine")
                self.assertEqual(audit["selectedEventIds"], [2])
                self.assertEqual(audit["auditedEventIds"], [2])
                self.assertEqual(audit["scanErrorCount"], 0)
                self.assertEqual(audit["argumentCommands"], 1)
                self.assertEqual(audit["readOnlyCommands"], 1)
                self.assertEqual(audit["writableCommands"], 0)
            finally:
                httpd.shutdown()
                httpd.server_close()
                thread.join(timeout=5)
                server._store = original_store


if __name__ == "__main__":
    unittest.main()
