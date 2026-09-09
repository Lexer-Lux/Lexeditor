from __future__ import annotations

import pytest

from games.ff7r.plugin import _test_text_package
from games.ff7r.textresource import TextFormatError, TextResourcePackage
from games.ff7r.textresource_structural import append_text_entry


def fixture_package():
    uasset, uexp = _test_text_package()
    return uasset, uexp, TextResourcePackage.from_bytes(uasset, uexp, asset="Resident_TxtRes")


def test_append_top_level_text_entry_round_trips_ascii_and_updates_export_size():
    _uasset, uexp, package = fixture_package()

    index = append_text_entry(package, "$Item_DogWhistle_Name", "Dog Whistle")

    assert index == 2
    assert len(package.entries) == 3
    assert package.entries[index].id == "$Item_DogWhistle_Name"
    assert package.entries[index].text == "Dog Whistle"
    assert package.entries[index].subentries == []
    assert len(package.uexp_bytes) > len(uexp)

    reread = TextResourcePackage.from_bytes(bytes(package.uasset_bytes), bytes(package.uexp_bytes))
    assert reread.text_map()["$Item_DogWhistle_Name"] == "Dog Whistle"


def test_append_top_level_text_entry_round_trips_unicode_without_name_map_change():
    uasset, _uexp, package = fixture_package()
    original_names = package.names

    append_text_entry(package, "$Item_DogWhistle_Description", "Makes canine enemies target the user.")
    append_text_entry(package, "$Item_DogWhistle_Name_JPTest", "犬笛")

    reread = TextResourcePackage.from_bytes(bytes(package.uasset_bytes), bytes(package.uexp_bytes))
    assert reread.names == original_names
    assert reread.text_map()["$Item_DogWhistle_Name_JPTest"] == "犬笛"
    assert bytes(package.uasset_bytes) != uasset  # export size changed, not the name map


def test_append_text_entry_rejects_duplicate_empty_and_nul_ids_before_mutation():
    uasset, uexp, package = fixture_package()

    with pytest.raises(ValueError, match="already exists"):
        append_text_entry(package, "$Item_Test", "Duplicate")
    with pytest.raises(ValueError, match="non-empty"):
        append_text_entry(package, "", "Empty ID")
    with pytest.raises(ValueError, match="NUL"):
        append_text_entry(package, "$Bad\0ID", "Bad")

    assert bytes(package.uasset_bytes) == uasset
    assert bytes(package.uexp_bytes) == uexp


def test_append_text_entry_rolls_back_on_reparse_failure(monkeypatch):
    uasset, uexp, package = fixture_package()

    def fail_parse(_data):
        raise TextFormatError("synthetic text reparse failure")

    monkeypatch.setattr(package, "_parse_uexp", fail_parse)
    with pytest.raises(TextFormatError, match="synthetic text reparse failure"):
        append_text_entry(package, "$Item_DogWhistle_Name", "Dog Whistle")

    assert bytes(package.uasset_bytes) == uasset
    assert bytes(package.uexp_bytes) == uexp
    assert [entry.id for entry in package.entries] == ["$Item_Test", "$Line_Test"]
