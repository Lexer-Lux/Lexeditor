"""Real virtual-save dispatch rejects malformed identities without changing configs."""
import json
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

import pytest

from plugins.ff7r import atb_tweaks, encounter_tweaks, graphics_tweaks, lockon_tweaks, no_more_cheats_tweaks, runtime_dataobject, storage
from plugins.ff7r.plugin import FF7RSession
import test_ff7r_atb_tweaks as fixtures


CASES = [
    (runtime_dataobject.RUNTIME_TWEAKS_ASSET, "CutsceneBaseMultiplier", 1.75),
    (graphics_tweaks.GRAPHICS_TWEAKS_ASSET, "DisableEyeAdaptation", False),
    (encounter_tweaks.ENCOUNTER_TWEAKS_ASSET, "Chapter5SubwayReducedTurret", False),
    (lockon_tweaks.BETTER_LOCKON_ASSET, "RemovePrompt", False),
    (no_more_cheats_tweaks.NO_MORE_CHEATS_ASSET, "Enabled", False),
    (atb_tweaks.ATB_SETTINGS_ASSET, "MovementMultiplier", 2.0),
    (atb_tweaks.ATB_RESIDENT_ASSET, "OverrideValue", 2.0),
    (atb_tweaks.ATB_GUARD_ASSET, "OverrideValue", 2.0),
    (atb_tweaks.ATB_ABILITY_ASSET, "OverrideATB", 2000),
]


def files(root):
    return {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def invalid_batches(good):
    changes = [{"entry": value} for value in [True, False, 0.5, "0.5", None, [], {}, float("inf")]]
    changes.extend([{"offset": 0}, {"property": []}, {"property": None}, {"index": 0}])
    return [None, False, {}, "", [good, None], [good, good], *[[good, {**good, **change}] for change in changes]]


@pytest.mark.parametrize("asset,prop,value", CASES)
@pytest.mark.parametrize("existing", [False, True])
def test_direct_virtual_dispatch_preserves_new_or_existing_configs(tmp_path, asset, prop, value, existing):
    index = fixtures._index(tmp_path / "fixtures")
    args = (tmp_path / "game", tmp_path / "cache", tmp_path / "project", index, asset)
    good = {"entry": 0, "property": prop, "value": value}
    package, source_sha, _ = storage.load_package(*args, vanilla=False)
    data = package.api_payload(source_sha256=source_sha)
    if existing:
        storage.save_edits(*args, source_sha256=data["sourceSha256"], active_sha256=data["activeSha256"], edits=[good])
        package, source_sha, _ = storage.load_package(*args, vanilla=False)
        data = package.api_payload(source_sha256=source_sha)
    before = files(tmp_path)
    for edits in invalid_batches(good):
        with pytest.raises((TypeError, ValueError)):
            storage.save_edits(*args, source_sha256=data["sourceSha256"], active_sha256=data["activeSha256"], edits=edits)
        assert files(tmp_path) == before
        reloaded, source_sha, _ = storage.load_package(*args, vanilla=False)
        assert reloaded.api_payload(source_sha256=source_sha) == data

    saved = storage.save_edits(*args, source_sha256=data["sourceSha256"], active_sha256=data["activeSha256"],
                               edits=[{**good, "entry": "0"}])
    assert saved["saved"] == 1
    reloaded, source_sha, _ = storage.load_package(*args, vanilla=False)
    assert reloaded.entries[0].values[prop] == value
    assert reloaded.api_payload(source_sha256=source_sha)["activeSha256"] == saved["activeSha256"]


def request_json(url, body=None):
    request = Request(url)
    if body is not None:
        request.data = json.dumps(body).encode("utf-8")
        request.add_header("Content-Type", "application/json")
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read())


@pytest.mark.parametrize("existing", [False, True])
def test_http_virtual_dispatch_preserves_configs_and_reloads(tmp_path, existing):
    fixture_root = tmp_path / "fixtures"
    index = fixtures._index(fixture_root)
    game = tmp_path / "game"
    (game / "End/Content/Paks").mkdir(parents=True)
    project = tmp_path / "project"
    with FF7RSession({
        "LEXEDITOR_FF7R_ROOT": str(game), "LEXEDITOR_FF7R_DATA_ROOT": str(tmp_path / "data"),
        "LEXEDITOR_FF7R_PROJECT": str(project), "LEXEDITOR_FF7R_TEST_DATAOBJECTS": str(fixture_root),
    }) as session:
        for asset, prop, value in CASES:
            data_url = session.url + "api/data?asset=" + quote(asset, safe="")
            data = request_json(data_url)
            good = {"entry": 0, "property": prop, "value": value}
            body = {"asset": asset, "sourceSha256": data["sourceSha256"], "activeSha256": data["activeSha256"]}
            if existing:
                request_json(session.url + "api/save", {**body, "edits": [good]})
                data = request_json(data_url)
                body["activeSha256"] = data["activeSha256"]
            before = files(project)
            source_before = files(fixture_root)
            for edits in invalid_batches(good):
                with pytest.raises(HTTPError) as caught:
                    request_json(session.url + "api/save", {**body, "edits": edits})
                assert caught.value.code == 400
                assert json.loads(caught.value.read())["error"]
                assert files(project) == before
                assert files(fixture_root) == source_before
                assert request_json(data_url) == data
            saved = request_json(session.url + "api/save", {**body, "edits": [{**good, "entry": 0.0}]})
            assert saved["saved"] == 1
            reloaded = request_json(data_url)
            assert reloaded["records"][0]["values"][prop] == value
            assert reloaded["activeSha256"] == saved["activeSha256"]
            assert files(fixture_root) == source_before
