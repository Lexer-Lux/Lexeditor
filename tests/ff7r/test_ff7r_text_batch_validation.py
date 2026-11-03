"""Text batch rejection keeps both package bytes and previously returned entries intact."""
import copy
import json
import struct
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

import pytest

from plugins.ff7r import textresource
from plugins.ff7r.plugin import FF7RSession
import test_ff7r_textresource as fixtures


GOOD = {"entry": 0, "text": "An edited sword"}


def package():
    return textresource.TextResourcePackage.from_bytes(*fixtures.fixture_pair())


@pytest.mark.parametrize("bad", [
    None, [], {}, {**GOOD, "entry": True}, {**GOOD, "entry": False},
    {**GOOD, "entry": 0.5}, {**GOOD, "entry": "0.5"},
    {**GOOD, "entry": None}, {**GOOD, "entry": float("inf")},
    {**GOOD, "entry": -1}, {**GOOD, "entry": 2},
    {**GOOD, "text": True}, {**GOOD, "text": None}, {**GOOD, "text": []},
    {**GOOD, "text": "bad\0text"}, {**GOOD, "text": "\ud800"},
    {**GOOD, "subId": False}, {**GOOD, "subId": 0}, {**GOOD, "subId": []},
    {**GOOD, "entry": 1, "subId": "missing"},
    {**GOOD, "offset": 0}, GOOD, {**GOOD, "subId": ""},
])
def test_later_rejection_preserves_bytes_payload_and_cached_entry(bad):
    item = package()
    before = copy.deepcopy(item.api_payload())
    entry = item.entries[0]
    with pytest.raises((ValueError, TypeError, IndexError, KeyError)):
        item.apply_edits([GOOD, bad])
    assert item.api_payload() == before
    assert entry.text == "Buster Sword"
    assert item.entries[0] is entry
    assert (bytes(item.uasset_bytes), bytes(item.uexp_bytes)) == fixtures.fixture_pair()


@pytest.mark.parametrize("edits", [None, False, True, 0, {}, "", (), iter(())])
def test_actual_array_required(edits):
    item = package()
    with pytest.raises(ValueError, match="array"):
        item.apply_edits(edits)
    assert (bytes(item.uasset_bytes), bytes(item.uexp_bytes)) == fixtures.fixture_pair()


@pytest.mark.parametrize("value", ["a" * 64, "é" * 32, "😀" * 16])
def test_encoded_size_includes_terminator_and_rejects_atomically(monkeypatch, value):
    item = package()
    before = copy.deepcopy(item.api_payload())
    monkeypatch.setattr(textresource, "MAX_STRING_BYTES", 64)
    with pytest.raises(ValueError, match="string size"):
        item.apply_edits([GOOD, {"entry": 1, "subId": "ACTOR", "text": value}])
    assert item.api_payload() == before
    assert (bytes(item.uasset_bytes), bytes(item.uexp_bytes)) == fixtures.fixture_pair()


@pytest.mark.parametrize("value", ["a" * 63, "é" * 31, "😀" * 15 + "é"])
def test_encoded_size_boundary_roundtrips(monkeypatch, value):
    item = package()
    monkeypatch.setattr(textresource, "MAX_STRING_BYTES", 64)
    item.apply_edits([{**GOOD, "text": value}])
    reloaded = textresource.TextResourcePackage.from_bytes(bytes(item.uasset_bytes), bytes(item.uexp_bytes))
    assert reloaded.entries[0].text == value
    assert reloaded.entries[1].subentries[0].text == "Cloud"


def test_valid_ascii_unicode_subentry_batch_matches_manual_serialization():
    item = package()
    uasset, _uexp = fixtures.fixture_pair()
    entry = item.entries[0]
    sub = item.entries[1].subentries[0]
    item.apply_edits([
        {**GOOD, "entry": "0"}, {"entry": 1.0, "text": "こんにちは 😀"},
        {"entry": 1, "subId": "ACTOR", "text": "クラウド"},
    ])
    f = fixtures.fstring
    expected = (b"\x00\x03" + f("US") + struct.pack("<iI", 0, 2)
                + f("$Item_Test") + f("An edited sword") + struct.pack("<I", 0)
                + f("$Line_Test") + f("こんにちは 😀") + struct.pack("<I", 1)
                + struct.pack("<Ii", 0, 0) + f("クラウド") + textresource.UNREAL_SIGNATURE)
    expected_uasset = bytearray(uasset)
    struct.pack_into("<i", expected_uasset, len(uasset) - textresource.TEXT_SERIAL_SIZE_FROM_END, len(expected) - 4)
    assert bytes(item.uasset_bytes) == bytes(expected_uasset)
    assert bytes(item.uexp_bytes) == expected
    assert entry.text == "An edited sword" and sub.text == "クラウド"
    reloaded = textresource.TextResourcePackage.from_bytes(bytes(expected_uasset), expected)
    assert reloaded.api_payload()["records"] == item.api_payload()["records"]
    item.apply_edits([])
    assert bytes(item.uexp_bytes) == expected


def request_json(url, body=None):
    request = Request(url)
    if body is not None:
        request.data = json.dumps(body).encode("utf-8")
        request.add_header("Content-Type", "application/json")
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read())


@pytest.mark.parametrize("existing", [False, True])
def test_http_invalid_batches_preserve_new_or_existing_pair(tmp_path, existing):
    asset = "End/Content/GameContents/Text/US/Resident_TxtRes"
    fixture_root = tmp_path / "fixtures"
    source_uasset = fixture_root / (asset + ".uasset")
    source_uexp = fixture_root / (asset + ".uexp")
    source_uasset.parent.mkdir(parents=True)
    uasset, uexp = fixtures.fixture_pair()
    source_uasset.write_bytes(uasset)
    source_uexp.write_bytes(uexp)
    game = tmp_path / "game"
    (game / "End/Content/Paks").mkdir(parents=True)
    project = tmp_path / "project"
    target_uasset = project / "content" / (asset + ".uasset")
    target_uexp = project / "content" / (asset + ".uexp")
    if existing:
        item = package()
        item.apply_edits([{**GOOD, "text": "Existing candidate"}])
        target_uasset.parent.mkdir(parents=True)
        target_uasset.write_bytes(item.uasset_bytes)
        target_uexp.write_bytes(item.uexp_bytes)

    def files():
        return {str(path.relative_to(project)): path.read_bytes()
                for path in project.rglob("*") if path.is_file()}

    with FF7RSession({
        "LEXEDITOR_FF7R_ROOT": str(game), "LEXEDITOR_FF7R_DATA_ROOT": str(tmp_path / "data"),
        "LEXEDITOR_FF7R_PROJECT": str(project), "LEXEDITOR_FF7R_TEST_DATAOBJECTS": str(fixture_root),
    }) as session:
        data_url = session.url + "api/text?asset=" + quote(asset, safe="")
        data = request_json(data_url)
        before = files()
        body = {"asset": asset, **{key: data[key] for key in (
            "sourceUassetSha256", "sourceUexpSha256", "activeUassetSha256", "activeUexpSha256")}}
        bad = [
            {**GOOD, "entry": 0.5}, {**GOOD, "entry": False},
            {**GOOD, "text": "bad\0text"}, {**GOOD, "text": "\ud800"},
            {**GOOD, "subId": []}, {**GOOD, "entry": 1, "subId": "missing"},
            {**GOOD, "offset": 0}, {**GOOD, "text": None}, GOOD,
        ]
        for edits in [None, False, {}, "", *[[GOOD, edit] for edit in bad]]:
            with pytest.raises(HTTPError) as caught:
                request_json(session.url + "api/text/save", {**body, "edits": edits})
            assert caught.value.code == 400
            assert json.loads(caught.value.read())["error"]
            assert files() == before
            assert request_json(data_url) == data
            assert source_uasset.read_bytes() == uasset and source_uexp.read_bytes() == uexp

        result = request_json(session.url + "api/text/save", {
            **body, "edits": [GOOD, {"entry": 1, "subId": "ACTOR", "text": "クラウド 😀"}],
        })
        assert result["saved"] == 2
        reloaded = request_json(data_url)
        assert reloaded["records"][0]["text"] == GOOD["text"]
        assert reloaded["records"][1]["subentries"][0]["text"] == "クラウド 😀"
        assert reloaded["usingProject"] is True
        assert reloaded["activeUassetSha256"] == result["activeUassetSha256"]
        assert reloaded["activeUexpSha256"] == result["activeUexpSha256"]
        assert source_uasset.read_bytes() == uasset and source_uexp.read_bytes() == uexp
