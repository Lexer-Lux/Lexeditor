"""Fixed-width DataObject batches are validated before bytes or cached values change."""
import copy
import json
import struct
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

import pytest

from plugins.ff7r.dataobject import DataObjectPackage
from plugins.ff7r.plugin import FF7RSession, _test_package


GOOD = {"entry": 0, "property": "Power", "value": 99}


def package():
    return DataObjectPackage.from_bytes(*_test_package())


@pytest.mark.parametrize("value", [True, False, 0.5, "0.5", None, [], {}, float("inf"), float("nan")])
@pytest.mark.parametrize("array", [False, True])
def test_invalid_identity_after_good_edit_is_atomic(value, array):
    item = package()
    before = copy.deepcopy(item.api_payload())
    bad = ({"entry": 0, "property": "Values_Array", "index": value, "value": 5}
           if array else {"entry": value, "property": "Enabled", "value": False})
    with pytest.raises(ValueError, match="must be an integer"):
        item.apply_edits([GOOD, bad])
    assert item.api_payload() == before
    assert bytes(item.uexp_bytes) == _test_package()[1]


@pytest.mark.parametrize("bad", [
    None, [], {}, {**GOOD, "property": None}, {**GOOD, "property": []},
    {**GOOD, "entry": -1}, {**GOOD, "entry": 1}, {**GOOD, "offset": 0},
    {**GOOD, "property": "missing"}, {**GOOD, "index": 0},
    {**GOOD, "property": "Description", "value": "Changed"},
    {**GOOD, "property": "Mode", "value": "NotInNameTable"},
    {**GOOD, "property": "Values_Array"},
    {**GOOD, "property": "Values_Array", "index": -1},
    {**GOOD, "property": "Values_Array", "index": 3},
    {**GOOD, "property": "Values_Array", "index": 0, "value": 32768},
    {**GOOD, "property": "Enabled", "value": 1},
    {**GOOD, "property": "Enabled", "value": "false"},
    {**GOOD, "property": "Enabled", "value": None},
    {**GOOD, "value": 2147483648}, {**GOOD, "value": -2147483649},
    {**GOOD, "value": True}, {**GOOD, "value": 1.5}, GOOD,
])
def test_later_rejection_preserves_entire_batch(bad):
    item = package()
    before = copy.deepcopy(item.api_payload())
    with pytest.raises((ValueError, TypeError, IndexError)):
        item.apply_edits([GOOD, bad])
    assert item.api_payload() == before
    assert bytes(item.uasset_bytes) == _test_package()[0]
    assert bytes(item.uexp_bytes) == _test_package()[1]


@pytest.mark.parametrize("edits", [None, False, True, 0, {}, "", (), iter(())])
def test_actual_array_required(edits):
    item = package()
    with pytest.raises(ValueError, match="array"):
        item.apply_edits(edits)
    assert bytes(item.uexp_bytes) == _test_package()[1]


def float_package():
    uasset, source = _test_package()
    original = package()
    uexp = bytearray(source)
    assert uexp[26] == 7  # First property's type byte in the authored fixture.
    uexp[26] = 9
    struct.pack_into("<f", uexp, original.entries[0].offsets["Power"].offset, 1.25)
    return DataObjectPackage.from_bytes(uasset, bytes(uexp))


@pytest.mark.parametrize("value", [True, False, None, [], {}, float("nan"), float("inf"), 1e300])
def test_invalid_float_after_array_edit_is_atomic(value):
    item = float_package()
    before = copy.deepcopy(item.api_payload())
    source = bytes(item.uexp_bytes)
    with pytest.raises(ValueError):
        item.apply_edits([
            {"entry": 0, "property": "Values_Array", "index": 1, "value": 25},
            {**GOOD, "value": value},
        ])
    assert item.api_payload() == before
    assert bytes(item.uexp_bytes) == source


def test_valid_batch_matches_manual_patch_and_reload():
    uasset, source = _test_package()
    item = package()
    row = item.entries[0]
    expected = bytearray(source)
    struct.pack_into("<i", expected, row.offsets["Power"].offset, -2147483648)
    expected[row.offsets["Enabled"].offset] = 0
    struct.pack_into("<iI", expected, row.offsets["Mode"].offset, item.uasset.names.index("ModeB"), 0)
    struct.pack_into("<h", expected, row.offsets["Values_Array"].offset + 6, 32767)
    item.apply_edits([
        {**GOOD, "entry": "0", "value": "-2147483648", "index": None},
        {"entry": 0.0, "property": "Enabled", "value": False},
        {"entry": 0, "property": "Mode", "value": "ModeB"},
        {"entry": 0, "property": "Values_Array", "index": 1.0, "value": 32767},
    ])
    assert bytes(item.uexp_bytes) == bytes(expected)
    reread = DataObjectPackage.from_bytes(uasset, bytes(expected))
    assert reread.entries[0].values == item.entries[0].values
    assert reread.entries[0].values["Description"] == "$Item_Test"
    item.apply_edits([])
    assert bytes(item.uexp_bytes) == bytes(expected)


def request_json(url, body=None):
    request = Request(url)
    if body is not None:
        request.data = json.dumps(body).encode("utf-8")
        request.add_header("Content-Type", "application/json")
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read())


@pytest.mark.parametrize("existing", [False, True])
def test_http_invalid_batches_preserve_both_project_files(tmp_path, existing):
    asset = "End/Content/GameContents/DataObject/Resident/Equipment"
    fixture_root = tmp_path / "fixtures"
    source_uasset = fixture_root / (asset + ".uasset")
    source_uexp = fixture_root / (asset + ".uexp")
    source_uasset.parent.mkdir(parents=True)
    uasset, uexp = _test_package()
    source_uasset.write_bytes(uasset)
    source_uexp.write_bytes(uexp)
    game = tmp_path / "game"
    (game / "End/Content/Paks").mkdir(parents=True)
    project = tmp_path / "project"
    target_uasset = project / "content" / (asset + ".uasset")
    target_uexp = project / "content" / (asset + ".uexp")
    if existing:
        item = package()
        item.apply_edits([{**GOOD, "value": 77}])
        target_uasset.parent.mkdir(parents=True)
        target_uasset.write_bytes(uasset)
        target_uexp.write_bytes(item.uexp_bytes)

    def files():
        return {str(path.relative_to(project)): path.read_bytes()
                for path in project.rglob("*") if path.is_file()}

    with FF7RSession({
        "LEXEDITOR_FF7R_ROOT": str(game), "LEXEDITOR_FF7R_DATA_ROOT": str(tmp_path / "data"),
        "LEXEDITOR_FF7R_PROJECT": str(project), "LEXEDITOR_FF7R_TEST_DATAOBJECTS": str(fixture_root),
    }) as session:
        data_url = session.url + "api/data?asset=" + quote(asset, safe="")
        data = request_json(data_url)
        before = files()
        bad = [
            {**GOOD, "entry": 0.5}, {**GOOD, "entry": True},
            {**GOOD, "property": "Values_Array", "index": 1.5},
            {**GOOD, "property": "Values_Array", "index": False},
            {**GOOD, "property": "Enabled", "value": 1},
            {**GOOD, "property": "Description", "value": "Changed"},
            {**GOOD, "property": "Mode", "value": "Absent"},
            {**GOOD, "offset": 0}, {**GOOD, "property": None},
            {**GOOD, "value": 2147483648}, GOOD,
        ]
        for edits in [None, False, {}, "", *[[GOOD, edit] for edit in bad]]:
            with pytest.raises(HTTPError) as caught:
                request_json(session.url + "api/save", {
                    "asset": asset, "sourceSha256": data["sourceSha256"],
                    "activeSha256": data["activeSha256"], "edits": edits,
                })
            assert caught.value.code == 400
            assert json.loads(caught.value.read())["error"]
            assert files() == before
            assert request_json(data_url) == data
            assert source_uasset.read_bytes() == uasset
            assert source_uexp.read_bytes() == uexp

        expected = bytearray(target_uexp.read_bytes() if existing else uexp)
        struct.pack_into("<i", expected, package().entries[0].offsets["Power"].offset, 99)
        result = request_json(session.url + "api/save", {
            "asset": asset, "sourceSha256": data["sourceSha256"],
            "activeSha256": data["activeSha256"], "edits": [GOOD],
        })
        assert result["saved"] == 1
        assert target_uasset.read_bytes() == uasset
        assert target_uexp.read_bytes() == bytes(expected)
        reloaded = request_json(data_url)
        assert reloaded["records"][0]["values"]["Power"] == 99
        assert reloaded["usingProject"] is True
