"""HTTP edit and copy requests must never truncate a PARAM record identity."""
import json
import threading
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from plugins.ds3 import server
from plugins.ds3.formats import RegulationDocument
from test_ds3_plugin import _bnd4, METADATA


def test_ds3_requests_preserve_data_after_invalid_identity_then_reopen_valid_edits(monkeypatch):
    document = RegulationDocument(_bnd4(), METADATA)
    monkeypatch.setattr(server, "_document", lambda: document)
    monkeypatch.delenv("LEXEDITOR_MOD_READ_ONLY", raising=False)
    table = "Magic"
    row_id = document.params[table].rows[0].row_id
    new_id = max(row.row_id for row in document.params[table].rows) + 1
    field = next(field for field in document.read_row(table, row_id)["fields"]
                 if field["editable"] and field["type"] == "number"
                 and field["minimum"] <= 1 <= field["maximum"])
    before = document.plaintext()
    service = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    thread = threading.Thread(target=service.serve_forever, daemon=True)
    thread.start()

    def post(route, payload):
        request = Request(f"http://127.0.0.1:{service.server_port}/api/{route}",
                          data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=5) as response:
            return json.load(response)

    try:
        for invalid in (row_id + 0.5, True, False, str(row_id) + ".5", None):
            requests = [
                ("edit", {"table": table, "id": invalid, "field": field["key"], "value": 1}),
                ("create", {"table": table, "sourceId": invalid, "id": new_id, "name": "Copy"}),
            ]
            for route, payload in requests:
                with pytest.raises(HTTPError) as refused:
                    post(route, payload)
                assert refused.value.code == 400
                assert "integer" in json.load(refused.value)["error"]
                assert document.plaintext() == before and document.dirty_count == 0
        post("edit", {"table": table, "id": row_id, "field": field["key"], "value": 1})
        post("create", {"table": table, "sourceId": row_id, "id": new_id, "name": "Copy"})
        reopened = RegulationDocument(document.export(), METADATA)
        assert reopened.read_row(table, new_id)["name"] == "Copy"
        for identity in (row_id, new_id):
            fields = {item["key"]: item["value"] for item in reopened.read_row(table, identity)["fields"]}
            assert fields[field["key"]] == 1
    finally:
        service.shutdown()
        service.server_close()
        thread.join(timeout=5)
