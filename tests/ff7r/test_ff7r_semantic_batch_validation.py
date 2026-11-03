"""Semantic wrappers and generic routing must not discard invalid edit identities."""
import json
import struct
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

import pytest

from plugins.ff7r import semantics, storage
from plugins.ff7r.plugin import FF7RSession
import test_ff7r_semantics as fixtures


def good_edit(kind):
    return ({"entry": 0, "field": "buy", "value": 1234} if kind == "economy" else
            {"entry": 0, "kind": "normal", "field": "chance", "index": 0, "value": 75})


def writer(kind):
    return semantics.save_economy_edits if kind == "economy" else semantics.save_loot_edits


def asset_for(kind):
    return "End/Content/GameContents/DataObject/Resident/" + ("Equipment" if kind == "economy" else "BattleItemPossession")


def files(root):
    return {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()}


@pytest.mark.parametrize("kind,key", [("economy", "entry"), ("loot", "entry"), ("loot", "index")])
@pytest.mark.parametrize("value", [True, False, 0.5, "0.5", None, [], {}, float("inf")])
@pytest.mark.parametrize("existing", [False, True])
def test_direct_bad_identity_preserves_output_pair(tmp_path, kind, key, value, existing):
    index = fixtures._fixture_index(tmp_path / "fixtures")
    project = tmp_path / "project"
    args = (tmp_path / "game", tmp_path / "cache", project, index, asset_for(kind))
    package, sha, _ = storage.load_package(*args, vanilla=False)
    if existing:
        writer(kind)(*args, source_sha256=sha, active_sha256=sha,
                     edits=[{**good_edit(kind), "value": 50}])
        package, sha, _ = storage.load_package(*args, vanilla=False)
    active_sha = storage.sha256_bytes(package.uexp_bytes)
    before = files(tmp_path)
    with pytest.raises(ValueError, match="must be an integer"):
        writer(kind)(*args, source_sha256=sha, active_sha256=active_sha,
                     edits=[good_edit(kind), {**good_edit(kind), key: value}])
    assert files(tmp_path) == before


@pytest.mark.parametrize("kind", ["economy", "loot"])
@pytest.mark.parametrize("extra", [{"offset": 0}, {"field": []}, {"field": None}])
def test_direct_extra_or_nontext_field_after_valid_edit_rejects(tmp_path, kind, extra):
    index = fixtures._fixture_index(tmp_path / "fixtures")
    args = (tmp_path / "game", tmp_path / "cache", tmp_path / "project", index, asset_for(kind))
    package, sha, _ = storage.load_package(*args, vanilla=False)
    before = files(tmp_path)
    with pytest.raises((TypeError, ValueError)):
        writer(kind)(*args, source_sha256=sha, active_sha256=sha,
                     edits=[good_edit(kind), {**good_edit(kind), **extra}])
    assert files(tmp_path) == before


def request_json(url, body=None):
    request = Request(url)
    if body is not None:
        request.data = json.dumps(body).encode("utf-8")
        request.add_header("Content-Type", "application/json")
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read())


@pytest.mark.parametrize("kind", ["economy", "loot"])
@pytest.mark.parametrize("existing", [False, True])
def test_http_generic_and_semantic_routes_preserve_pair_and_reload(tmp_path, kind, existing):
    fixture_root = tmp_path / "fixtures"
    index = fixtures._fixture_index(fixture_root)
    project = tmp_path / "project"
    game = tmp_path / "game"
    (game / "End/Content/Paks").mkdir(parents=True)
    asset = asset_for(kind)
    args = (game, tmp_path / "cache", project, index, asset)
    if existing:
        package, sha, _ = storage.load_package(*args, vanilla=False)
        writer(kind)(*args, source_sha256=sha, active_sha256=sha,
                     edits=[{**good_edit(kind), "value": 50}])
    with FF7RSession({
        "LEXEDITOR_FF7R_ROOT": str(game), "LEXEDITOR_FF7R_DATA_ROOT": str(tmp_path / "data"),
        "LEXEDITOR_FF7R_PROJECT": str(project), "LEXEDITOR_FF7R_TEST_DATAOBJECTS": str(fixture_root),
    }) as session:
        data_url = session.url + "api/data?asset=" + quote(asset, safe="")
        data = request_json(data_url)
        before = files(project)
        source_before = files(fixture_root)
        body = {"asset": asset, "sourceSha256": data["sourceSha256"], "activeSha256": data["activeSha256"]}
        semantic_good = good_edit(kind)
        generic_good = ({"entry": 0, "property": "BuyValue", "value": 1234} if kind == "economy" else
                        {"entry": 0, "property": "NormalItemPercent_Array", "index": 0, "value": 75})
        for route, good in [(f"api/{kind}/save", semantic_good), ("api/save", generic_good)]:
            changes = [{"entry": True}, {"entry": False}, {"entry": 0.5}, {"offset": 0}]
            if kind == "loot":
                changes.extend([{"index": False}, {"index": 0.5}])
            for change in changes:
                with pytest.raises(HTTPError) as caught:
                    request_json(session.url + route, {**body, "edits": [good, {**good, **change}]})
                assert caught.value.code == 400
                assert json.loads(caught.value.read())["error"]
                assert files(project) == before
                assert files(fixture_root) == source_before
                assert request_json(data_url) == data

        source_uasset = fixture_root / (asset + ".uasset")
        source_uexp = fixture_root / (asset + ".uexp")
        target_uasset = project / "content" / (asset + ".uasset")
        target_uexp = project / "content" / (asset + ".uexp")
        raw = target_uexp.read_bytes() if existing else source_uexp.read_bytes()
        package = storage.DataObjectPackage.from_bytes(source_uasset.read_bytes(), raw)
        expected = bytearray(raw)
        field = package.entries[0].offsets[generic_good["property"]]
        if kind == "economy":
            struct.pack_into("<i", expected, field.offset, 1234)
        else:
            expected[field.offset + 4] = 75
        saved = request_json(session.url + f"api/{kind}/save", {**body, "edits": [semantic_good]})
        assert saved["saved"] == 1
        assert target_uasset.read_bytes() == source_uasset.read_bytes()
        assert target_uexp.read_bytes() == bytes(expected)
        reloaded = request_json(data_url)
        assert reloaded["usingProject"] is True
        assert reloaded["activeSha256"] == saved["activeSha256"]
        generic_saved = request_json(session.url + "api/save", {
            **body, "activeSha256": reloaded["activeSha256"], "edits": [generic_good],
        })
        assert generic_saved["surface"] == ("economy" if kind == "economy" else "enemy-loot")
        assert target_uexp.read_bytes() == bytes(expected)
        assert files(fixture_root) == source_before
