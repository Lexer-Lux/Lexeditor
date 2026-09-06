"""Synthetic schemas only: no proprietary or upstream game records committed."""
from pathlib import Path
import hashlib
import pytest
from games.ff9 import memoria_baseline as baseline, memoria_csv as csv, paths


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "GAME_ROOT", tmp_path / "game")
    monkeypatch.setattr(paths, "PROJECT_ROOT", tmp_path / "project")
    monkeypatch.setattr(paths, "DATA_ROOT", tmp_path / "cache")
    monkeypatch.setattr(csv, "ensure_baseline", lambda: {"ready": True})
    return csv.MemoriaDataStore()


def fixture(store, key, data):
    relative = csv.DATASET_BY_KEY[key].relative_path
    path = store.baseline_roots[0] / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


@pytest.mark.parametrize("key,data,field,value,kind", [
    ("character-parameters", b"\xef\xbb\xbf# Id;DefaultRow;DefaultCategory\n# Int32;Boolean;UInt8\n0;1;9;# Test actor\n", "DefaultRow", False, "boolean"),
    ("default-equipment", b"# Comment;Id;Weapon;Accessory\n# ;Int32;Int32;Int32\nTest\x92s set;0;1;-1;# test\n", "Weapon", -1, "integer"),
    ("leveling", b"# Experience;BonusHP;BonusMP\n# UInt32;UInt16;UInt16\n0;250;200;# Level 1\n16;314;206;# Level 2\n", "BonusHP", 400, "integer"),
])
def test_added_datasets_round_trip_to_project(store, key, data, field, value, kind):
    source = fixture(store, key, data)
    loaded = store.load(key)
    descriptor = next(f for f in loaded["fields"] if f["key"] == field)
    assert descriptor["kind"] == kind and descriptor["editable"]
    updated = store.save(key, loaded["sha256"], [{"line": loaded["rows"][0]["line"], "values": {field: value}}])
    assert updated["source"] == "project" and updated["rows"][0]["values"][field] == value
    assert source.read_bytes() == data
    assert csv.DATASET_BY_KEY[key].tab == "characters"
    if key == "leveling":
        assert [row["id"] for row in loaded["rows"]] == [1, 2]
    if key == "default-equipment":
        assert b"\x92" in Path(updated["sourcePath"]).read_bytes()
    if key == "character-parameters":
        assert Path(updated["sourcePath"]).read_bytes().startswith(b"\xef\xbb\xbf")


@pytest.mark.parametrize("ending", [b"", b"\n", b"\r\n", b"\r"])
def test_preserve_line_endings_and_no_final_newline(store, ending):
    data = b"# Id;Value\r\n# Int32;UInt8\n0;1;# untouched\r\n1;2;# change" + ending
    fixture(store, "items", data)
    loaded = store.load("items")
    result = store.save("items", loaded["sha256"], [{"line": loaded["rows"][1]["line"], "values": {"Value": 3}}])
    assert Path(result["sourcePath"]).read_bytes() == data.replace(b"1;2;# change", b"1;3;# change")


def test_empty_save_does_not_create_overlay(store):
    path = fixture(store, "items", b"# Id;Value\n# Int32;UInt8\n0;1\n")
    data = store.load("items")
    assert store.save("items", data["sha256"], [])["source"] == "baseline"
    assert not store.project_data.exists()
    assert path.is_file()


@pytest.mark.parametrize("value", [-1, 256, 1.5, True, "4"])
def test_bounded_byte_rejects_invalid_values_without_writing(store, value):
    fixture(store, "items", b"# Id;Value\n# Int32;UInt8\n0;1\n")
    data = store.load("items")
    with pytest.raises(ValueError):
        store.save("items", data["sha256"], [{"line": data["rows"][0]["line"], "values": {"Value": value}}])
    assert not store.project_data.exists()


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_float_edits_must_be_finite(store, value):
    fixture(store, "items", b"# Id;Value\n# Int32;Single\n0;1.0\n")
    data = store.load("items")
    with pytest.raises(ValueError, match="finite"):
        store.save("items", data["sha256"], [{"line": data["rows"][0]["line"], "values": {"Value": value}}])
    assert not store.project_data.exists()


def test_nonfinite_source_is_not_exposed_as_invalid_json(store):
    fixture(store, "items", b"# Id;Value\n# Int32;Single\n0;NaN\n")
    with pytest.raises(ValueError, match="finite"):
        store.load("items")


def test_stale_source_refused(store):
    source = fixture(store, "items", b"# Id;Value\n# Int32;UInt8\n0;1\n")
    data = store.load("items")
    source.write_bytes(source.read_bytes().replace(b"0;1", b"0;2"))
    with pytest.raises(RuntimeError, match="changed"):
        store.save("items", data["sha256"], [{"line": data["rows"][0]["line"], "values": {"Value": 3}}])
    assert not store.project_data.exists()


def test_change_during_document_edit_refused(store, monkeypatch):
    source = fixture(store, "items", b"# Id;Value\n# Int32;UInt8\n0;1\n")
    data = store.load("items")
    apply = csv.MemoriaCsvDocument.apply
    def race(self, changes):
        apply(self, changes)
        source.write_bytes(source.read_bytes().replace(b"0;1", b"0;2"))
    monkeypatch.setattr(csv.MemoriaCsvDocument, "apply", race)
    with pytest.raises(RuntimeError, match="changed"):
        store.save("items", data["sha256"], [{"line": data["rows"][0]["line"], "values": {"Value": 3}}])
    assert not (store.project_data / "Items/Items.csv").exists()
    assert not list(store.project_data.rglob("*.tmp"))


def test_project_cannot_be_installed_baseline(store):
    source = fixture(store, "items", b"# Id;Value\n# Int32;UInt8\n0;1\n")
    store.project_data = store.baseline_roots[0]
    data = store.load("items")
    with pytest.raises(RuntimeError, match="separate"):
        store.save("items", data["sha256"], [{"line": data["rows"][0]["line"], "values": {"Value": 3}}])
    assert source.read_bytes().endswith(b"0;1\n")


def test_all_datasets_have_pinned_baseline_paths():
    assert len(csv.DATASETS) == 12
    assert {d.relative_path for d in csv.DATASETS} == set(baseline.FILES)


def test_bad_baseline_download_does_not_replace_file(tmp_path, monkeypatch):
    data = b"verified synthetic CSV\n"
    monkeypatch.setattr(baseline, "FILES", {"Characters/Leveling.csv": hashlib.sha256(data).hexdigest()})
    target = tmp_path / "StreamingAssets/Data/Characters/Leveling.csv"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"old")
    result = baseline.ensure(tmp_path, downloader=lambda _: b"bad")
    assert not result["ready"] and result["problems"]
    assert target.read_bytes() == b"old"
    result = baseline.ensure(tmp_path, downloader=lambda _: data)
    assert result["ready"] and target.read_bytes() == data
