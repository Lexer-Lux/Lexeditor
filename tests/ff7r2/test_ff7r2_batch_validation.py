"""Rejected scalar batches preserve bytes and cached fields, including later failures."""
import json
from pathlib import Path
import struct
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from plugins.ff7r2.dataobject import DataObjectError, DataObjectPackage
from plugins.ff7r2.plugin import Ff7r2Session
from ff7r2_fixture import battle_player_parameter_fixture, fixture


GOOD = {"nameIndex": 1, "property": "HPMax", "value": 1234}


@pytest.mark.parametrize("key", ["nameIndex", "nameNumber"])
@pytest.mark.parametrize("value", [True, False, 0.5, "1.5", None, [], {}, float("inf"), float("nan")])
def test_bad_identity_after_valid_edit_is_atomic(key, value):
    package = DataObjectPackage.from_bytes(fixture())
    before = package.payload()
    bad = {"nameIndex": 1, "property": "Strength", "value": 44, key: value}
    with pytest.raises(DataObjectError, match="must be an integer"):
        package.apply_edits([GOOD, bad])
    assert package.payload() == before
    assert package.to_bytes() == fixture()


@pytest.mark.parametrize("bad", [
    None, [], {}, {**GOOD, "property": None}, {**GOOD, "property": []},
    {**GOOD, "value": 40000, "property": "Strength"},
    {**GOOD, "value": 1.5}, {**GOOD, "value": True},
    {**GOOD, "property": "Mode", "value": "ModeB"},
    {**GOOD, "property": "missing"}, {**GOOD, "nameIndex": 9999},
    {**GOOD, "offset": 0}, GOOD,
])
def test_later_invalid_field_does_not_apply_earlier_field(bad):
    package = DataObjectPackage.from_bytes(fixture())
    before = package.payload()
    with pytest.raises(DataObjectError):
        package.apply_edits([GOOD, bad])
    assert package.payload() == before
    assert package.to_bytes() == fixture()


@pytest.mark.parametrize("edits", [None, False, True, 0, {}, "", (), iter(())])
def test_collection_must_be_an_actual_array(edits):
    package = DataObjectPackage.from_bytes(fixture())
    with pytest.raises(DataObjectError, match="array"):
        package.apply_edits(edits)
    assert package.to_bytes() == fixture()


@pytest.mark.parametrize("value", [-(1 << 63), (1 << 63) - 1, (1 << 53) + 1])
def test_int64_remains_read_only_and_byte_exact(value):
    source = fixture(hp_type=8)
    package = DataObjectPackage.from_bytes(source)
    before = package.payload()
    assert package.records[0].fields[0].editable is False
    with pytest.raises(DataObjectError, match="read-only"):
        package.apply_edits([{**GOOD, "value": str(value)}])
    assert package.to_bytes() == source
    assert package.payload() == before


def test_finite_float_too_large_for_storage_rejects_whole_batch():
    source = battle_player_parameter_fixture()
    package = DataObjectPackage.from_bytes(source)
    row = package.records[0]
    before = package.payload()
    with pytest.raises(DataObjectError, match="storage range"):
        package.apply_edits([
            {"nameIndex": row.key.index, "property": "KeyDownTime", "value": 0.5},
            {"nameIndex": row.key.index, "property": "KeyDownEffectCreateTime", "value": 1e300},
        ])
    assert package.to_bytes() == source
    assert package.payload() == before


def test_valid_identity_forms_empty_batch_and_noop():
    package = DataObjectPackage.from_bytes(fixture())
    assert package.apply_edits([]) == 0
    assert package.apply_edits([{**GOOD, "nameIndex": "1", "nameNumber": 0.0}]) == 1
    assert package.apply_edits([{**GOOD, "nameIndex": 1.0}]) == 0
    assert package.records[0].fields[0].value == 1234


def request_json(url, body=None):
    request = Request(url)
    if body is not None:
        request.data = json.dumps(body).encode("utf-8")
        request.add_header("Content-Type", "application/json")
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read())


@pytest.mark.parametrize("existing", [False, True])
def test_http_rejected_batches_preserve_new_or_existing_output(tmp_path, existing):
    asset = Path("End/Content/DataObject/Resident/PlayerParameter.uasset")
    source = tmp_path / "source" / asset
    source.parent.mkdir(parents=True)
    original = fixture()
    source.write_bytes(original)
    (tmp_path / "lexeditor-project.json").write_text('{"format":1,"game":"ff7r2"}', encoding="utf-8")
    target = tmp_path / "content" / asset
    if existing:
        target.parent.mkdir(parents=True)
        candidate = DataObjectPackage.from_bytes(original)
        candidate.apply_edits([{**GOOD, "value": 1111}])
        target.write_bytes(candidate.to_bytes())

    def files():
        return {str(path.relative_to(tmp_path)): path.read_bytes()
                for path in tmp_path.rglob("*") if path.is_file()}

    with Ff7r2Session({"LEXEDITOR_FF7R2_PROJECT": str(tmp_path)}) as session:
        data = request_json(session.url + "api/player-parameter")
        before = files()
        bad_edits = [
            {**GOOD, "nameIndex": 1.5, "property": "Strength"},
            {**GOOD, "nameIndex": True, "property": "Strength"},
            {**GOOD, "nameNumber": 0.5, "property": "Strength"},
            {**GOOD, "nameNumber": False, "property": "Strength"},
            {**GOOD, "property": None}, {**GOOD, "offset": 0},
            {**GOOD, "value": True, "property": "Strength"},
            {**GOOD, "value": 1.5, "property": "Strength"},
            {**GOOD, "value": 40000, "property": "Strength"},
            {**GOOD, "property": "Mode", "value": "ModeB"},
            GOOD,
        ]
        collections = [None, False, {}, "", *[[GOOD, bad] for bad in bad_edits]]
        for changes in collections:
            with pytest.raises(HTTPError) as caught:
                request_json(session.url + "api/player-parameter/save", {
                    "sha256": data["activeSha256"], "changes": changes,
                })
            assert caught.value.code == 400
            assert json.loads(caught.value.read())["error"]
            assert files() == before
            assert request_json(session.url + "api/player-parameter") == data

        active = target.read_bytes() if existing else original
        package = DataObjectPackage.from_bytes(active)
        expected = bytearray(active)
        struct.pack_into("<i", expected, package.records[0].fields[0].offset, 1234)
        saved = request_json(session.url + "api/player-parameter/save", {
            "sha256": data["activeSha256"], "changes": [GOOD],
        })
        assert saved["changedFields"] == 1
        assert target.read_bytes() == bytes(expected)
        assert source.read_bytes() == original
        reloaded = request_json(session.url + "api/player-parameter")
        assert reloaded["activeSha256"] == saved["activeSha256"]
        assert reloaded["records"][0]["fields"][0]["value"] == 1234
