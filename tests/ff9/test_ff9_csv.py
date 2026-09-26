"""Synthetic schemas only: no proprietary or upstream game records committed."""
from pathlib import Path
import hashlib
import pytest
from plugins.ff9 import memoria_baseline as baseline, memoria_csv as csv, paths


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
    assert len(csv.DATASETS) == 42
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


def test_optional_trailing_composite_schema_uses_active_record_width(tmp_path):
    path = tmp_path / "BattleParameters.csv"
    path.write_text(
        "#! IncludeWeaponSound\n"
        "# Id;Name;WeaponSounds;WeaponOffset;TranceParameters;\n"
        "# Int32;String;Int32[];Float[X,Y];{Anim[2];WeaponBone(Int32)}\n"
        "0;Test;1, 2;# actor\n", encoding="utf-8")
    doc = csv.MemoriaCsvDocument(path)
    assert doc.columns == ["Id", "Name", "WeaponSounds"]
    assert [field["key"] for field in doc.fields] == doc.columns


def test_schema_column_names_are_trimmed(tmp_path):
    path = tmp_path / "Commands.csv"
    path.write_text("# Id\t;Value\t\n# Int32;UInt8\n0;7\n", encoding="utf-8")
    doc = csv.MemoriaCsvDocument(path)
    assert doc.columns == ["Id", "Value"]



def test_shop_integer_array_is_editable_and_uses_real_suffix_name(store):
    fixture(store, "shops", b"# Comment;Id;Items\n# ;Int32;Int32[]\nShop 0000;0;1, 2;# Shop 0000 Dali Weapon Shop\n")
    loaded = store.load("shops")
    field = next(value for value in loaded["fields"] if value["key"] == "Items")
    assert field["kind"] == "list" and field["itemKind"] == "integer" and field["editable"]
    assert loaded["rows"][0]["name"] == "Dali Weapon Shop"
    saved = store.save("shops", loaded["sha256"], [{"line": loaded["rows"][0]["line"], "values": {"Items": "3, 4, 5"}}])
    assert saved["rows"][0]["values"]["Items"] == "3, 4, 5"
    assert b"Shop 0000;0;3, 4, 5;# Shop 0000 Dali Weapon Shop" in Path(saved["sourcePath"]).read_bytes()


def test_integer_array_rejects_non_numeric_entries(store):
    fixture(store, "shops", b"# Comment;Id;Items\n# ;Int32;Int32[]\nShop 0000;0;1, 2;# Shop 0000 Test\n")
    loaded = store.load("shops")
    with pytest.raises(ValueError, match="whole numbers"):
        store.save("shops", loaded["sha256"], [{"line": loaded["rows"][0]["line"], "values": {"Items": "1, nope"}}])


def test_project_overlay_reports_the_values_the_record_shipped_with(store):
    """A property can be put back to the game's own value, not the mod's copy."""
    fixture(store, "items", b"# Id;Value\n# Int32;UInt8\n0;1\n1;2\n")
    loaded = store.load("items")
    assert "vanilla" not in loaded, "a baseline needs no second copy of itself"
    saved = store.save("items", loaded["sha256"], [
        {"line": loaded["rows"][0]["line"], "values": {"Value": 9}}])
    assert saved["source"] == "project"
    assert saved["rows"][0]["values"]["Value"] == 9
    assert saved["vanilla"] == {str(saved["rows"][0]["line"]): {"Id": 0, "Value": 1},
                                str(saved["rows"][1]["line"]): {"Id": 1, "Value": 2}}


def test_failed_default_baseline_is_retried(tmp_path, monkeypatch):
    payload = b"# Id;Value\n# Int32;UInt8\n0;1\n"
    monkeypatch.setattr(paths, "DATA_ROOT", tmp_path / "cache")
    monkeypatch.setattr(baseline, "FILES", {"Items/Test.csv": hashlib.sha256(payload).hexdigest()})
    monkeypatch.setattr(baseline, "_last", None)
    calls = {"count": 0}
    def downloader(_relative):
        calls["count"] += 1
        if calls["count"] == 1:
            raise OSError("temporary network failure")
        return payload
    first = baseline.ensure(downloader=downloader)
    second = baseline.ensure(downloader=downloader)
    assert not first["ready"] and second["ready"] and calls["count"] == 2


def test_symbolic_integer_enums_are_named_editable_choices(store):
    fixture(store, "actions",
            b"# Comment;id;menuWindow;targets\n"
            b"# ;Int32;UInt8;UInt8\n"
            b"Fire;1;Hp(1);SingleEnemy(2);# Fire\n"
            b"Cure;2;Hp(1);ManyAny(3);# Cure\n")
    loaded = store.load("actions")
    menu = next(field for field in loaded["fields"] if field["key"] == "menuWindow")
    targets = next(field for field in loaded["fields"] if field["key"] == "targets")
    assert menu["kind"] == "enum" and menu["editable"] and menu["choices"] == ["Hp(1)"]
    assert targets["kind"] == "enum" and targets["editable"]
    saved = store.save("actions", loaded["sha256"], [{
        "line": loaded["rows"][0]["line"], "values": {"targets": "ManyAny(3)"}
    }])
    assert saved["rows"][0]["values"]["targets"] == "ManyAny(3)"
    with pytest.raises(ValueError, match="named values"):
        store.save("actions", saved["sha256"], [{
            "line": saved["rows"][0]["line"], "values": {"targets": "Invented(99)"}
        }])


def test_status_visual_vectors_and_color_are_bounded_fixed_lists(store):
    fixture(store, "status-data",
            b"# Comment;Id;SPSExtraPos;SHPExtraPos;ColorBase\n"
            b"# ;Int32;Vector3;Vector3;Int32[3]\n"
            b"Petrify;0;1, 2, 3;4, 5, 6;-48, -72, -88;# Petrify\n")
    loaded = store.load("status-data")
    fields = {field["key"]: field for field in loaded["fields"]}
    assert fields["SPSExtraPos"]["kind"] == "fixed-list"
    assert fields["SPSExtraPos"]["length"] == 3 and fields["SPSExtraPos"]["itemKind"] == "number"
    assert fields["ColorBase"]["kind"] == "fixed-list"
    assert fields["ColorBase"]["length"] == 3 and fields["ColorBase"]["itemKind"] == "integer"
    row = loaded["rows"][0]
    assert row["values"]["SPSExtraPos"] == [1.0, 2.0, 3.0]
    assert row["values"]["ColorBase"] == [-48, -72, -88]
    saved = store.save("status-data", loaded["sha256"], [{
        "line": row["line"],
        "values": {"SPSExtraPos": [1.5, 2.0, 3.0], "ColorBase": [-40, -70, -80]},
    }])
    assert saved["rows"][0]["values"]["SPSExtraPos"] == [1.5, 2.0, 3.0]
    assert b"1.5, 2, 3" in Path(saved["sourcePath"]).read_bytes()
    with pytest.raises(ValueError, match="exactly 3"):
        store.save("status-data", saved["sha256"], [{
            "line": saved["rows"][0]["line"], "values": {"ColorBase": [1, 2]}
        }])


def test_comments_are_source_annotations_not_editable_gameplay_fields(store):
    fixture(store, "shops",
            b"# Comment;Id;Items\n# ;Int32;Int32[]\nShop 0000;0;1, 2;# Shop 0000 Dali\n")
    loaded = store.load("shops")
    comment = next(field for field in loaded["fields"] if field["key"] == "Comment")
    assert comment["editable"] is False
    with pytest.raises(ValueError, match="not an editable field"):
        store.save("shops", loaded["sha256"], [{
            "line": loaded["rows"][0]["line"], "values": {"Comment": "Fake game name"}
        }])


@pytest.mark.parametrize(("key", "data", "expected"), [
    ("leveling",
     b"# Experience;BonusHP;BonusMP\n# UInt32;UInt16;UInt16\n0;250;200;# Level 1\n",
     1),
    ("initial-items",
     b"# ItemID;Count\n# Int32;UInt8\n236;7;# Potion\n",
     None),
    ("world-transport",
     b"# type;speed_move\n# Byte;Int16\n0;112;# Walking\n",
     None),
    ("world-weather",
     b"# light0.vx;fogAMP\n# Int16;UInt16\n100;4096;# Daylight 0\n",
     None),
])
def test_no_id_tables_never_invent_a_displayed_record_id(store, key, data, expected):
    fixture(store, key, data)
    assert store.load(key)["rows"][0]["id"] == expected


def test_field_labels_are_humanized_without_changing_keys(store):
    fixture(store, "status-data",
            b"# Comment;Id;SPSExtraPos;SHPExtraPos;ColorBase\n"
            b"# ;Int32;Vector3;Vector3;Int32[3]\n"
            b"Petrify;0;1, 2, 3;4, 5, 6;-48, -72, -88;# Petrify\n")
    loaded = store.load("status-data")
    labels = {field["key"]: field["label"] for field in loaded["fields"]}
    assert labels["SPSExtraPos"] == "SPS Extra Position"
    assert labels["SHPExtraPos"] == "SHP Extra Position"
    assert labels["ColorBase"] == "Glow Base Color"
    assert csv._field_label("DefaultCommandSet") == "Default Command Set"
