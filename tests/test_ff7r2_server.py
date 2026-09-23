from __future__ import annotations

import json
from http.client import HTTPConnection
from pathlib import Path
import tempfile

import pytest

from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from plugins.ff7r2.dataobject import DataObjectPackage
from plugins.ff7r2.plugin import Ff7r2Session
from ff7r2_fixture import battle_item_possession_fixture, battle_player_parameter_fixture, fixture


PLAYER = Path("End/Content/DataObject/Resident/PlayerParameter.uasset")
BATTLE_PLAYER = Path("End/Content/DataObject/Resident/BattlePlayerParameter.uasset")
BATTLE_ITEM = Path("End/Content/DataObject/Resident/BattleItemPossession.uasset")


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


def test_battle_player_parameter_service_is_schema_validated_and_read_only():
    with tempfile.TemporaryDirectory(prefix="lexeditor-ff7r2-battle-player-") as temp_name:
        project = Path(temp_name)
        (project / "lexeditor-project.json").write_text(
            '{"format":1,"game":"ff7r2"}\n', encoding="utf-8")
        source = project / "source" / BATTLE_PLAYER
        source.parent.mkdir(parents=True)
        original = battle_player_parameter_fixture()
        source.write_bytes(original)

        environment = {"LEXEDITOR_FF7R2_PROJECT": str(project)}
        with Ff7r2Session(environment) as session:
            workspace = _json(session.url + "api/workspace")
            assert workspace["battlePlayerParameter"]["sourcePresent"] is True
            assert workspace["battlePlayerParameter"]["readOnly"] is True

            payload = _json(session.url + "api/battle-player-parameter")
            assert payload["readOnly"] is True
            assert payload["source"] == "source"
            assert payload["recordCount"] == 1
            fields = {field["name"]: field for field in payload["records"][0]["fields"]}
            assert fields["CommandAbilityID_Array"]["value"] == ["AbilityTest"]
            assert fields["UniqueAbilityParameterValue_Array"]["value"] == pytest.approx([1.25, 2.5])
            assert fields["KeyDownTime"]["value"] == pytest.approx(0.4)
            assert all(field["editable"] is False for field in fields.values())
            assert "semantics and safe ranges" in fields["KeyDownTime"]["note"]

            request = Request(
                session.url + "api/battle-player-parameter/save",
                method="POST",
                data=b"{}",
                headers={"Content-Type": "application/json"},
            )
            with pytest.raises(HTTPError) as caught:
                urlopen(request, timeout=10)
            assert caught.value.code == 404
            assert source.read_bytes() == original


def test_battle_player_parameter_rejects_wrong_dataobject_schema():
    with tempfile.TemporaryDirectory(prefix="lexeditor-ff7r2-battle-player-schema-") as temp_name:
        project = Path(temp_name)
        (project / "lexeditor-project.json").write_text(
            '{"format":1,"game":"ff7r2"}\n', encoding="utf-8")
        source = project / "source" / BATTLE_PLAYER
        source.parent.mkdir(parents=True)
        source.write_bytes(fixture())

        with Ff7r2Session({"LEXEDITOR_FF7R2_PROJECT": str(project)}) as session:
            with pytest.raises(HTTPError) as caught:
                _json(session.url + "api/battle-player-parameter")
            assert caught.value.code == 404
            payload = json.loads(caught.value.read().decode("utf-8"))
            assert "BattlePlayerParameter schema is missing proved field" in payload["error"]


def test_battle_item_possession_service_is_read_only():
    with tempfile.TemporaryDirectory(prefix="lexeditor-ff7r2-battle-item-") as temp_name:
        project = Path(temp_name)
        (project / "lexeditor-project.json").write_text(
            '{"format":1,"game":"ff7r2"}\n', encoding="utf-8")
        source = project / "source" / BATTLE_ITEM
        source.parent.mkdir(parents=True)
        original = battle_item_possession_fixture()
        source.write_bytes(original)

        environment = {"LEXEDITOR_FF7R2_PROJECT": str(project)}
        with Ff7r2Session(environment) as session:
            workspace = _json(session.url + "api/workspace")
            assert workspace["battleItemPossession"]["sourcePresent"] is True
            assert workspace["battleItemPossession"]["readOnly"] is True

            payload = _json(session.url + "api/battle-item-possession")
            assert payload["readOnly"] is True
            assert payload["source"] == "source"
            assert payload["recordCount"] == 1
            row = payload["records"][0]
            fields = {field["name"]: field for field in row["fields"]}
            assert fields["StealItemName_Array"]["value"] == ["Potion", "Ether"]
            assert fields["StealItemName_Array"]["arrayCount"] == 2
            assert fields["NormalItemPercent_Array"]["value"] == [25, 75]
            assert all(field["editable"] is False for field in fields.values())
            assert "array-write acceptance" in fields["StealFaildCountArrayIndex"]["note"]

            request = Request(
                session.url + "api/battle-item-possession/save",
                method="POST",
                data=b"{}",
                headers={"Content-Type": "application/json"},
            )
            with pytest.raises(HTTPError) as caught:
                urlopen(request, timeout=10)
            assert caught.value.code == 404
            assert source.read_bytes() == original


def test_battle_item_possession_rejects_wrong_dataobject_schema():
    with tempfile.TemporaryDirectory(prefix="lexeditor-ff7r2-battle-schema-") as temp_name:
        project = Path(temp_name)
        (project / "lexeditor-project.json").write_text(
            '{"format":1,"game":"ff7r2"}\n', encoding="utf-8")
        source = project / "source" / BATTLE_ITEM
        source.parent.mkdir(parents=True)
        # Structurally valid Rebirth DataObject, but deliberately the wrong table.
        source.write_bytes(fixture())

        with Ff7r2Session({"LEXEDITOR_FF7R2_PROJECT": str(project)}) as session:
            with pytest.raises(HTTPError) as caught:
                _json(session.url + "api/battle-item-possession")
            assert caught.value.code == 404
            payload = json.loads(caught.value.read().decode("utf-8"))
            assert "BattleItemPossession schema is missing proved field" in payload["error"]


def test_requested_gameplay_datamap_states_are_explicit():
    with tempfile.TemporaryDirectory(prefix="lexeditor-ff7r2-datamap-") as temp_name:
        project = Path(temp_name)
        (project / "lexeditor-project.json").write_text(
            '{"format":1,"game":"ff7r2"}\n', encoding="utf-8")
        environment = {"LEXEDITOR_FF7R2_PROJECT": str(project)}
        with Ff7r2Session(environment) as session:
            rows = _json(session.url + "api/datamap")["rows"]

    by_issue = {}
    for row in rows:
        for issue in (470, 471, 472, 473, 477):
            if f"#{issue}" in row["filename"]:
                by_issue[issue] = row

    assert set(by_issue) == {470, 471, 472, 473, 477}
    battle_player = next(
        row for row in rows
        if row["filename"].endswith("/BattlePlayerParameter.uasset")
    )
    assert battle_player["status"] == "partial"
    assert battle_player["coverage"] == "view"
    assert battle_player["target"] == "battleparams"
    assert "read-only" in battle_player["controls"].lower()
    assert by_issue[471]["status"] == "partial"
    assert by_issue[471]["coverage"] == "view"
    assert by_issue[471]["target"] == "formulae"
    assert "read-only" in by_issue[471]["controls"].lower()
    for issue in (470, 472, 473, 477):
        assert by_issue[issue]["status"] == "not-integrated"
        assert by_issue[issue]["coverage"] == "unavailable"
        assert "None" in by_issue[issue]["controls"]

