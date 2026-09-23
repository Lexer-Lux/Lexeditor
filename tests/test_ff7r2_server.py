from __future__ import annotations

import json
from http.client import HTTPConnection
from pathlib import Path
import tempfile

import pytest

from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from games.ff7r2.dataobject import DataObjectPackage
from games.ff7r2.plugin import Ff7r2Session
from ff7r2_fixture import fixture


PLAYER = Path("End/Content/DataObject/Resident/PlayerParameter.uasset")


def _json(url: str, body: dict | None = None) -> dict:
    request = Request(url, method="POST" if body is not None else "GET")
    if body is not None:
        payload = json.dumps(body).encode("utf-8")
        request.data = payload
        request.add_header("Content-Type", "application/json")
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def test_service_stages_save_preserves_source_and_reopens_candidate():
    with tempfile.TemporaryDirectory(prefix="lexeditor-ff7r2-service-") as temp_name:
        root = Path(temp_name)
        project = root / "RebirthMod"
        project.mkdir()
        (project / "lexeditor-project.json").write_text(
            '{"format":1,"game":"ff7r2"}\n', encoding="utf-8")
        source = project / "source" / PLAYER
        source.parent.mkdir(parents=True)
        original = fixture()
        source.write_bytes(original)

        environment = {"LEXEDITOR_FF7R2_PROJECT": str(project)}
        with Ff7r2Session(environment) as session:
            workspace = _json(session.url + "api/workspace")
            assert workspace["playerParameter"]["sourcePresent"] is True
            assert workspace["playerParameter"]["outputPresent"] is False
            assert workspace["delivery"]["staged"] is False
            assert workspace["delivery"]["stagedFileCount"] == 0

            data = _json(session.url + "api/player-parameter")
            cloud = data["records"][0]
            hp = next(field for field in cloud["fields"] if field["name"] == "HPMax")
            assert hp["value"] == 1000
            saved = _json(session.url + "api/player-parameter/save", {
                "sha256": data["activeSha256"],
                "changes": [{
                    "nameIndex": cloud["nameIndex"],
                    "nameNumber": cloud["nameNumber"],
                    "property": "HPMax",
                    "value": 1234,
                }],
            })
            assert saved["changedFields"] == 1
            assert saved["source"] == "project"
            saved_cloud = saved["records"][0]
            assert next(field for field in saved_cloud["fields"]
                        if field["name"] == "HPMax")["value"] == 1234
            assert source.read_bytes() == original
            workspace = _json(session.url + "api/workspace")
            assert workspace["delivery"]["staged"] is True
            assert workspace["delivery"]["stagedFileCount"] == 1
            assert workspace["delivery"]["stagedFiles"] == [
                "content/End/Content/DataObject/Resident/PlayerParameter.uasset"
            ]

            vanilla = _json(session.url + "api/player-parameter?source=vanilla")
            assert next(field for field in vanilla["records"][0]["fields"]
                        if field["name"] == "HPMax")["value"] == 1000

        # Reopen a new managed service to prove the project candidate, not an
        # in-memory object, carries the saved edit.
        with Ff7r2Session(environment) as reopened:
            data = _json(reopened.url + "api/player-parameter")
            assert data["source"] == "project"
            assert next(field for field in data["records"][0]["fields"]
                        if field["name"] == "HPMax")["value"] == 1234
            reset = _json(reopened.url + "api/player-parameter/reset", {})
            assert reset["source"] == "source"
            assert next(field for field in reset["records"][0]["fields"]
                        if field["name"] == "HPMax")["value"] == 1000


def test_missing_source_is_an_explicit_empty_state_not_generic_file_access():
    with tempfile.TemporaryDirectory(prefix="lexeditor-ff7r2-empty-") as temp_name:
        project = Path(temp_name)
        environment = {"LEXEDITOR_FF7R2_PROJECT": str(project)}
        with Ff7r2Session(environment) as session:
            try:
                _json(session.url + "api/player-parameter")
            except HTTPError as error:
                assert error.code == 404
                payload = json.loads(error.read().decode("utf-8"))
                assert "IoStore-state asset" in payload["error"]
                assert payload["workspace"]["playerParameter"]["sourcePresent"] is False
            else:
                raise AssertionError("Missing source unexpectedly opened")


def test_stale_playerparameter_write_is_rejected():
    with tempfile.TemporaryDirectory(prefix="lexeditor-ff7r2-stale-") as temp_name:
        project = Path(temp_name)
        (project / "lexeditor-project.json").write_text(
            '{"format":1,"game":"ff7r2"}\n', encoding="utf-8")
        source = project / "source" / PLAYER
        source.parent.mkdir(parents=True)
        source.write_bytes(fixture())
        environment = {"LEXEDITOR_FF7R2_PROJECT": str(project)}

        with Ff7r2Session(environment) as session:
            before = _json(session.url + "api/player-parameter")
            external = DataObjectPackage.from_bytes(source.read_bytes())
            external.apply_edits([{
                "nameIndex": before["records"][0]["nameIndex"],
                "property": "HPMax",
                "value": 1111,
            }])
            source.write_bytes(external.to_bytes())

            request = Request(
                session.url + "api/player-parameter/save",
                method="POST",
                data=json.dumps({
                    "sha256": before["activeSha256"],
                    "changes": [{
                        "nameIndex": before["records"][0]["nameIndex"],
                        "property": "HPMax",
                        "value": 1234,
                    }],
                }).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with pytest.raises(HTTPError) as caught:
                urlopen(request, timeout=10)
            assert caught.value.code == 400
            payload = json.loads(caught.value.read().decode("utf-8"))
            assert "changed on disk" in payload["error"]
            reopened = _json(session.url + "api/player-parameter")
            hp = next(field for field in reopened["records"][0]["fields"]
                      if field["name"] == "HPMax")
            assert hp["value"] == 1111


def test_negative_content_length_is_rejected_without_unbounded_read():
    with tempfile.TemporaryDirectory(prefix="lexeditor-ff7r2-body-") as temp_name:
        project = Path(temp_name)
        (project / "lexeditor-project.json").write_text(
            '{"format":1,"game":"ff7r2"}\n', encoding="utf-8")
        with Ff7r2Session({"LEXEDITOR_FF7R2_PROJECT": str(project)}) as session:
            parsed = urlparse(session.url)
            connection = HTTPConnection(parsed.hostname, parsed.port, timeout=5)
            try:
                connection.putrequest("POST", "/api/player-parameter/reset")
                connection.putheader("Content-Type", "application/json")
                connection.putheader("Content-Length", "-1")
                connection.endheaders()
                response = connection.getresponse()
                payload = json.loads(response.read().decode("utf-8"))
            finally:
                connection.close()
            assert response.status == 400
            assert "Request size is invalid" in payload["error"]
