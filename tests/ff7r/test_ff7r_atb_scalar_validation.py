"""ATB overrides must fit source storage before config saves, including later edits."""
import json
import struct
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

import pytest

from plugins.ff7r import atb_tweaks as atb
from plugins.ff7r.plugin import FF7RSession
import test_ff7r_atb_tweaks as fixtures


CASES = [
    (atb.ATB_RESIDENT_ASSET, "|ParamFloat", "OverrideValue", "FLOAT"),
    (atb.ATB_RESIDENT_ASSET, "|ParamInt", "OverrideValue", "INT32"),
    (atb.ATB_GUARD_ASSET, None, "OverrideValue", "FLOAT"),
    (atb.ATB_ABILITY_ASSET, None, "OverrideATB", "INT32"),
]


def target_index(spec, suffix):
    return next(i for i, row in enumerate(spec["entries"]) if suffix is None or row["tag"].endswith(suffix))


def bad_values(storage_type):
    shared = [True, False, None, [], {}, "2", float("inf"), float("nan"), 10 ** 400]
    return shared + ([1.5, -2147483649, 2147483648] if storage_type == "INT32" else [-1e300, 1e300])


def files(root):
    return {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()}


@pytest.mark.parametrize("asset,suffix,prop,storage_type", CASES)
@pytest.mark.parametrize("existing", [False, True])
def test_later_invalid_scalar_keeps_new_or_existing_config(tmp_path, asset, suffix, prop, storage_type, existing):
    index = fixtures._index(tmp_path / "fixtures")
    game, cache, project = tmp_path / "game", tmp_path / "cache", tmp_path / "project"
    spec = atb.resource_spec(asset, game, cache, project, index)
    target = target_index(spec, suffix)
    good = {"entry": 1 if target == 0 else 0, "property": prop, "value": 2}
    if existing:
        atb.save_virtual_edits(game, cache, project, index, asset,
                              source_sha256=spec["sourceSha256"], active_sha256=spec["activeSha256"], edits=[good])
        spec = atb.resource_spec(asset, game, cache, project, index)
    before = files(tmp_path)
    for value in bad_values(storage_type):
        with pytest.raises(ValueError):
            atb.save_virtual_edits(game, cache, project, index, asset,
                                  source_sha256=spec["sourceSha256"], active_sha256=spec["activeSha256"],
                                  edits=[good, {"entry": target, "property": prop, "value": value}])
        assert files(tmp_path) == before
        assert atb.resource_spec(asset, game, cache, project, index) == spec


@pytest.mark.parametrize("asset,suffix,prop,storage_type", CASES)
def test_valid_storage_boundaries_and_vanilla_reset_reload(tmp_path, asset, suffix, prop, storage_type):
    index = fixtures._index(tmp_path / "fixtures")
    game, cache, project = tmp_path / "game", tmp_path / "cache", tmp_path / "project"
    spec = atb.resource_spec(asset, game, cache, project, index)
    target = target_index(spec, suffix)
    source_values = dict(spec["entries"][target]["values"])
    values = [-2147483648, 2147483647] if storage_type == "INT32" else [-3.4028234663852886e38, 3.4028234663852886e38, 0.1]
    for value in values:
        saved = atb.save_virtual_edits(game, cache, project, index, asset,
                                      source_sha256=spec["sourceSha256"], active_sha256=spec["activeSha256"],
                                      edits=[{"entry": target, "property": prop, "value": value}])
        spec = atb.resource_spec(asset, game, cache, project, index)
        expected = value if storage_type == "INT32" else struct.unpack("<f", struct.pack("<f", value))[0]
        assert spec["entries"][target]["values"][prop] == expected
        assert spec["activeSha256"] == saved["activeSha256"]
    vanilla = source_values["VanillaATB" if storage_type == "INT32" and asset == atb.ATB_ABILITY_ASSET else "VanillaValue"]
    atb.save_virtual_edits(game, cache, project, index, asset,
                          source_sha256=spec["sourceSha256"], active_sha256=spec["activeSha256"],
                          edits=[{"entry": target, "property": prop, "value": vanilla}])
    reset = atb.resource_spec(asset, game, cache, project, index)
    assert reset["entries"][target]["values"][prop] == vanilla
    config = atb.load_atb_config(project)
    bucket = ("residentOverrides" if asset == atb.ATB_RESIDENT_ASSET else
              "guardOverrides" if asset == atb.ATB_GUARD_ASSET else "abilityCostOverrides")
    assert spec["entries"][target]["tag"] not in config[bucket]


def request_json(url, body=None):
    request = Request(url)
    if body is not None:
        request.data = json.dumps(body).encode("utf-8")
        request.add_header("Content-Type", "application/json")
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read())


@pytest.mark.parametrize("existing", [False, True])
def test_http_scalar_rejection_preserves_config_and_valid_reload(tmp_path, existing):
    fixture_root = tmp_path / "fixtures"
    fixtures._index(fixture_root)
    game, project = tmp_path / "game", tmp_path / "project"
    (game / "End/Content/Paks").mkdir(parents=True)
    with FF7RSession({
        "LEXEDITOR_FF7R_ROOT": str(game), "LEXEDITOR_FF7R_DATA_ROOT": str(tmp_path / "data"),
        "LEXEDITOR_FF7R_PROJECT": str(project), "LEXEDITOR_FF7R_TEST_DATAOBJECTS": str(fixture_root),
    }) as session:
        for asset, suffix, prop, storage_type in CASES:
            data_url = session.url + "api/data?asset=" + quote(asset, safe="")
            data = request_json(data_url)
            target = next(i for i, row in enumerate(data["records"]) if suffix is None or row["tag"].endswith(suffix))
            good = {"entry": 1 if target == 0 else 0, "property": prop, "value": 2}
            body = {"asset": asset, "sourceSha256": data["sourceSha256"], "activeSha256": data["activeSha256"]}
            if existing:
                request_json(session.url + "api/save", {**body, "edits": [good]})
                data = request_json(data_url)
                body["activeSha256"] = data["activeSha256"]
            before = files(project)
            source_before = files(fixture_root)
            for value in bad_values(storage_type):
                with pytest.raises(HTTPError) as caught:
                    request_json(session.url + "api/save", {**body, "edits": [good, {"entry": target, "property": prop, "value": value}]})
                assert caught.value.code == 400
                assert json.loads(caught.value.read())["error"]
                assert files(project) == before and files(fixture_root) == source_before
                assert request_json(data_url) == data
            value = 2147483647 if storage_type == "INT32" else 0.1
            saved = request_json(session.url + "api/save", {**body, "edits": [{"entry": target, "property": prop, "value": value}]})
            reloaded = request_json(data_url)
            expected = value if storage_type == "INT32" else struct.unpack("<f", struct.pack("<f", value))[0]
            assert reloaded["records"][target]["values"][prop] == expected
            assert reloaded["activeSha256"] == saved["activeSha256"]
            assert files(fixture_root) == source_before
